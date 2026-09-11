"""Column/page inventory with evidence, not an automatic deletion verdict.

The graph follows measures and calculated columns. Whole-table DAX references
are deliberately review blockers: COUNTROWS(T) does not read every column in T,
but static analysis cannot certify all table-expression semantics.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from .page_references import page_ref

SCOPE = ("Scoped to the supplied model and report. Deletion candidates have no detected "
         "references; check other reports, Excel/composite-model consumers and Power Query "
         "steps before deleting. Static analysis is not proof of safe deletion.")
SOURCE_NOTE = ("Partition source is best effort. Source column is the model input name, "
               "not verified physical lineage through Power Query renames or transformations.")
_COMMENTS_STRINGS = re.compile(r'"(?:[^"]|"")*"|//[^\n]*|--[^\n]*|/\*.*?\*/', re.S)
_REF = re.compile(r"(?:(?:'(?P<quoted>(?:[^']|'')+)'|(?P<table>[^\W\d]\w*))\s*)?"
                  r"\[(?P<field>(?:[^\]]|\]\])+?)\](?!\])", re.UNICODE)


def build_column_usage(model: dict, report: dict | None) -> dict:
    tables = {t["name"]: t for t in model["tables"]}
    table_lookup = {t.casefold(): t for t in tables}
    columns = {("c", t["name"], c["name"]): c for t in tables.values() for c in t["columns"]}
    col_lookup = {(t.casefold(), c.casefold()): key for key in columns for _, t, c in [key]}
    measures = {("m", m["table"], m["name"]): m for m in model["measures"]}
    mea_lookup = {key[2].casefold(): key for key in measures}
    graph = defaultdict(set)
    table_deps = defaultdict(set)
    reasons = defaultdict(set)
    uncertain = defaultdict(set)
    issues = set()

    def label(key):
        return f"{key[1]}[{key[2]}]"

    def refs(expression, home, local_columns=False):
        text = _COMMENTS_STRINGS.sub(lambda m: " " * len(m.group()), expression or "")
        found, spans = set(), []
        for match in _REF.finditer(text):
            field = match["field"].replace("]]", "]")
            table = (match["quoted"] or match["table"] or "").replace("''", "'")
            # DAX keywords before a bare reference (RETURN [Total]) are not
            # qualifiers. A quoted unknown table remains an unresolved ref.
            if match["table"] and table.upper() in {"RETURN", "NOT", "IN", "AND", "OR"} and table.casefold() not in table_lookup:
                table = ""
            key = None
            if table:
                key = col_lookup.get((table.casefold(), field.casefold()))
                candidate = mea_lookup.get(field.casefold())
                if not key and candidate and candidate[1].casefold() == table.casefold():
                    key = candidate
            else:
                if local_columns:
                    key = col_lookup.get((home.casefold(), field.casefold()))
                key = key or mea_lookup.get(field.casefold())
            if key:
                found.add(key)
            else:
                issues.add(f"Unresolved DAX reference {table}[{field}]")
            spans.append(match.span())
        chars = list(text)
        for start, end in spans:
            chars[start:end] = " " * (end - start)
        remainder = "".join(chars)
        whole_tables = set()
        for table in tables:
            quoted = "'" + table.replace("'", "''") + "'"
            if re.search(re.escape(quoted), remainder, re.I) or (
                re.fullmatch(r"[^\W\d]\w*", table) and
                re.search(r"(?<![\w'])" + re.escape(table) + r"(?![\w']|\s*\()", remainder, re.I)
            ):
                whole_tables.add(table)
        return found, whole_tables

    for key, m in measures.items():
        expression = m["expression"] + "\n" + m.get("formatStringExpression", "")
        graph[key], table_deps[key] = refs(expression, key[1])
    for key, c in columns.items():
        if c.get("isCalculated"):
            graph[key], table_deps[key] = refs(c.get("expression"), key[1], True)

    def closure(start):
        seen, touched = set(), set()
        todo = list(graph[start])
        touched.update(table_deps[start])
        while todo:
            key = todo.pop()
            if key in seen:
                continue
            seen.add(key)
            touched.update(table_deps[key])
            todo.extend(graph[key] - seen)
        return seen, touched

    closures = {key: closure(key) for key in list(graph)}
    used_by_measures = defaultdict(set)
    used_by_calculations = defaultdict(set)
    for root, (deps, whole_tables) in closures.items():
        what = ("Measure " if root[0] == "m" else "Calculated column ") + label(root)
        for dep in deps & columns.keys():
            reasons[dep].add(what)
            (used_by_measures if root[0] == "m" else used_by_calculations)[dep].add(label(root))
        for table in whole_tables:
            for key in columns:
                if key[1] == table:
                    uncertain[key].add(f"Whole-table dependency in {what}")

    def retain_expression(expression, home, what):
        deps, whole_tables = refs(expression, home, True)
        expanded = set(deps)
        for dep in deps:
            nested, nested_tables = closures.get(dep, (set(), set()))
            expanded.update(nested)
            whole_tables.update(nested_tables)
        for dep in expanded & columns.keys():
            reasons[dep].add(what)
            used_by_calculations[dep].add(what)
        for key in columns:
            if key[1] in whole_tables:
                uncertain[key].add(f"Whole-table dependency in {what}")

    for root in model.get("dependencyExpressions", []):
        retain_expression(root["expression"], root["table"], root["label"])
    for role in model["roles"]:
        for permission in role["tablePermissions"]:
            retain_expression(permission["filterExpression"], permission["table"],
                              "RLS role " + role["name"])
    for rel in model["relationships"]:
        for side in ("from", "to"):
            key = col_lookup.get((rel[side + "Table"].casefold(), rel[side + "Column"].casefold()))
            if key:
                reasons[key].add("Relationship " + rel["name"] + (" (inactive)" if not rel["isActive"] else ""))
    for table, tbl in tables.items():
        if tbl.get("calculationGroup"):
            for key in columns:
                if key[1] == table:
                    reasons[key].add("Calculation group structure")
        if any(p["type"] == "calculated" for p in tbl["partitions"]):
            for key in columns:
                if key[1] == table:
                    uncertain[key].add("Calculated table output: review its defining DAX before changing columns")
        for hierarchy in tbl["hierarchies"]:
            for column in hierarchy["levels"]:
                key = col_lookup.get((table.casefold(), (column or "").casefold()))
                if key:
                    reasons[key].add("Hierarchy " + hierarchy["name"])
        for c in tbl["columns"]:
            if c.get("sortByColumn"):
                sort = c["sortByColumn"].strip("'")
                key = col_lookup.get((table.casefold(), sort.casefold()))
                if key:
                    reasons[key].add("Sort-by for " + table + "[" + c["name"] + "]")
            if c.get("isKey"):
                reasons[("c", table, c["name"])].add("Model key column")

    # Key by stable page ID, never parse human labels (page names may contain /).
    page_use = defaultdict(lambda: defaultdict(lambda: {"kinds": set(), "evidence": set(), "measures": set()}))
    def usage_entry():
        return {"kinds": set(), "evidence": set(), "fields": set(), "measures": set()}
    table_page_use = defaultdict(lambda: defaultdict(usage_entry))
    measure_page_use = defaultdict(lambda: defaultdict(usage_entry))
    report_use = defaultdict(set)
    report_measures = set()
    bookmark_use = defaultdict(set)
    pages = {p["id"]: p for p in (report or {}).get("pages", [])}

    def resolve(binding):
        table = table_lookup.get((binding.get("table") or "").casefold())
        field = (binding.get("field") or "").casefold()
        kind = binding.get("kind")
        if kind == "hierarchyLevel" and table:
            matches = set()
            for h in tables[table]["hierarchies"]:
                if binding.get("hierarchy") and h["name"] != binding["hierarchy"]:
                    continue
                for level in h.get("levelDetails", []):
                    if (level["name"] or "").casefold() == field:
                        key = col_lookup.get((table.casefold(), (level["column"] or "").casefold()))
                        if key:
                            matches.add(key)
            if len(matches) == 1:
                return matches.pop()
        if kind == "measure":
            key = mea_lookup.get(field)
            if key and (not binding.get("table") or key[1] == table):
                return key
        elif table:
            key = col_lookup.get((table.casefold(), field))
            if key:
                return key
        if field:
            issues.add(f"Unresolved report binding {binding.get('table') or '?'}[{binding.get('field')}]")
        return None

    consumers = []
    node_id = lambda key: json.dumps(key, ensure_ascii=False, separators=(",", ":"))

    def consume(binding, page_ids, evidence, bookmark=False, visual_id=""):
        root = resolve(binding)
        if root is None:
            return
        deps, whole_tables = closures.get(root, (set(), set()))
        page_ids = list(page_ids)
        for pid in page_ids or [""]:
            consumers.append(dict(page_ref(report, pages.get(pid)), node=node_id(root),
                                  visualId=visual_id, evidence=evidence, bookmark=bookmark))
        for key in deps | {root}:
            kind = "Direct" if key == root else "Via measures" if root[0] == "m" else "Via calculations"
            for page_id in page_ids or [""]:
                trow = table_page_use[key[1]][page_id]
                trow["kinds"].add(kind)
                trow["evidence"].add(evidence)
                trow["fields"].add(key[2])
                if root[0] == "m":
                    trow["measures"].add(label(root))
                if key in measures:
                    mrow = measure_page_use[key][page_id]
                    mrow["kinds"].add(kind)
                    mrow["evidence"].add(evidence)
        for table in whole_tables:
            for page_id in page_ids or [""]:
                row = table_page_use[table][page_id]
                row["kinds"].add("Table expression")
                row["evidence"].add(evidence + ": " + label(root))
                if root[0] == "m":
                    row["measures"].add(label(root))
        report_measures.update(label(k) for k in deps | {root} if k in measures)
        affected = deps & columns.keys()
        if root in columns:
            affected = affected | {root}
        for key in affected:
            report_use[key].add(evidence)
            if bookmark:
                bookmark_use[key].add(evidence)
            for page_id in page_ids:
                row = page_use[key][page_id]
                row["kinds"].add("Direct" if key == root else "Via measures" if root[0] == "m" else "Via calculations")
                row["evidence"].add(evidence)
                if root[0] == "m":
                    row["measures"].add(label(root))
        for key in columns:
            if key[1] in whole_tables:
                uncertain[key].add(f"Report uses {label(root)} with a whole-table dependency ({evidence})")

    if report:
        for f in report["reportFilters"] + report.get("otherFields", []):
            consume(f, pages, "Report-level filter or expression")
        for page_id, page in pages.items():
            for f in page["filters"] + page.get("otherFields", []):
                consume(f, [page_id], f.get("level", "page").capitalize() + " filter or expression: " + page["name"])
            for v in page["visuals"]:
                for f in v["fields"]:
                    consume(f, [page_id], f"Visual {v['id']}: {v.get('title') or v['type']}", visual_id=v["id"])
        for bookmark in report["bookmarks"]:
            for f in bookmark["fields"]:
                # A bookmark may affect several pages; do not invent a page.
                consume(f, [], "Bookmark: " + bookmark["name"], bookmark=True)
        if not pages:
            issues.add("No report pages parsed")
        issues.update(w["message"] for w in report["warnings"])
    else:
        issues.add("No report supplied; report usage is unknown")
    issues.update(w["message"] for w in model["warnings"] if w["category"] == "Unreadable definition")

    rows, counts = [], defaultdict(int)
    for key, col in sorted(columns.items()):
        _, table, column = key
        internal = sorted(reasons[key])
        review = sorted(uncertain[key] | issues)
        if report_use[key] or internal:
            decision = "Keep"
        elif review:
            decision = "Review"
        else:
            decision = "Deletion candidate"
        counts[decision] += 1
        if report_use[key]:
            counts["Used in report"] += 1
        explanation = ("Referenced by the supplied report." if report_use[key] else
                       "Required by model dependencies." if internal else
                       "; ".join(review) if review else
                       "No report or model references detected. Validate other consumers and Power Query before removal.")
        sources = []
        for part in tables[table]["partitions"]:
            src = part["source"]
            sources.append(" / ".join(str(x) for x in [part["name"], src["sourceType"], src.get("server"),
                           src.get("database"), src.get("schema"), src.get("object") or src.get("detail")] if x))
        base = dict(table=table, column=column, decision=decision, reason=explanation,
                    report=report["name"] if report else "Not supplied",
                    usedInReport="Yes" if report_use[key] else "Not detected" if report else "Unknown",
                    modelDependencies=internal, reviewNotes=review,
                    usedByMeasures=sorted(used_by_measures[key]),
                    usedByCalculations=sorted(used_by_calculations[key]),
                    bookmarkUsage=sorted(bookmark_use[key]), source=sources,
                    sourceColumn=col.get("sourceColumn") or "", sourceNote=SOURCE_NOTE,
                    expression=col.get("expression") or "", scope=SCOPE)
        for page_id in sorted(page_use[key]) or [None]:
            use = page_use[key].get(page_id)
            rows.append(dict(base, pageId=page_id or "", page=pages[page_id]["name"] if page_id else "",
                             pageScope="Page" if page_id else "Bookmark/report scope only" if report_use[key] else "No page usage detected" if report else "Not assessed",
                             pageUsage=" + ".join(sorted(use["kinds"])) if use else
                             "Bookmark/report scope only" if report_use[key] else
                             "Internal only" if internal else "Not assessed" if not report else "No references detected",
                             pageMeasures=sorted(use["measures"]) if use else [],
                             evidence=sorted(use["evidence"]) if use else sorted(report_use[key])))
    # Track possible relationship dependencies separately on each real page.
    adjacency = defaultdict(set)
    for rel in model["relationships"]:
        if rel["isActive"]:
            adjacency[rel["fromTable"]].add(rel["toTable"])
            adjacency[rel["toTable"]].add(rel["fromTable"])
    for page_id in pages:
        seeds = {t for t, usage in table_page_use.items() if page_id in usage}
        reached, todo = set(seeds), list(seeds)
        while todo:
            for neighbor in adjacency[todo.pop()] - reached:
                reached.add(neighbor)
                todo.append(neighbor)
        for table in (reached - seeds) & tables.keys():
            row = table_page_use[table][page_id]
            row["kinds"].add("Possible relationship dependency")
            row["evidence"].add("Active relationship path to a table used on this page; verify filter propagation.")

    def flatten(table, page_id, use, **extra):
        ref = page_ref(report, pages.get(page_id))
        return dict(ref, table=table, usage=" + ".join(sorted(use["kinds"])) if page_id else "Bookmark/report scope only",
                    scope="Page" if page_id else "Bookmark/report scope only",
                    **{key: sorted(value) for key, value in use.items()}, **extra)
    table_pages = [flatten(table, pid, use) for table, uses in sorted(table_page_use.items()) for pid, use in sorted(uses.items())]
    for table in tables:
        if table not in table_page_use:
            table_pages.append(dict(page_ref(report), table=table,
                                    usage="No page usage detected" if report else "Usage unknown",
                                    scope="No page usage detected" if report else "Not assessed",
                                    kinds=[], evidence=[], fields=[], measures=[]))
    measure_pages = [flatten(key[1], pid, use, measure=key[2]) for key, uses in sorted(measure_page_use.items()) for pid, use in sorted(uses.items())]
    return {"rows": rows, "counts": dict(counts), "columnCount": len(columns), "csvFields": CSV_FIELDS,
            "tablePages": table_pages, "measurePages": measure_pages,
            "reportMeasures": sorted(report_measures),
            "dependencyGraph": {
                "nodes": [dict(id=node_id(k), kind="column" if k[0] == "c" else "measure",
                               table=k[1], name=k[2], label=label(k)) for k in sorted(columns.keys() | measures.keys())],
                "edges": [dict(dependent=node_id(k), dependency=node_id(d))
                          for k, deps in sorted(graph.items()) for d in sorted(deps)],
                "wholeTableDependencies": [dict(node=node_id(k), table=t)
                                           for k, deps in sorted(table_deps.items()) for t in sorted(deps)],
                "consumers": consumers,
            },
            "scope": SCOPE, "sourceNote": SOURCE_NOTE, "issues": sorted(issues)}


CSV_FIELDS = [("decision", "Deletion assessment"), ("usedInReport", "Used in report"),
              ("report", "Report"), ("table", "Table"), ("column", "Column"), ("page", "Report page"), ("pageId", "Page ID"), ("pageScope", "Page scope"),
              ("pageUsage", "Page usage"), ("pageMeasures", "Measures on this page"),
              ("usedByMeasures", "Used by measures (all)"), ("usedByCalculations", "Used by calculations"),
              ("modelDependencies", "Model dependencies"), ("reason", "Assessment reason"),
              ("evidence", "Page evidence"), ("bookmarkUsage", "Bookmark usage"),
              ("source", "Partition sources"), ("sourceColumn", "Source column (model input)"),
              ("expression", "Column expression"), ("reviewNotes", "Review notes"),
              ("sourceNote", "Source limitation"), ("scope", "Assessment scope")]


def csv_cell(value):
    value = "; ".join(value) if isinstance(value, list) else str(value or "")
    # CSV quoting does not prevent Excel from evaluating a formula.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    return value


def write_column_csv(analysis: dict, out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([title for _, title in CSV_FIELDS])
        for row in analysis["rows"]:
            writer.writerow([csv_cell(row[key]) for key, _ in CSV_FIELDS])
    return path
