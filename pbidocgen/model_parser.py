"""Parse a TMSL semantic model (model.bim) into a normalized dictionary.

Handles TMSL quirks:
- expressions stored as either a string or a list of lines
- files saved as UTF-8, UTF-8 with BOM, or UTF-16
- optional / missing collections throughout

Everything here is static analysis. DAX and M are parsed with regular
expressions, which covers the overwhelming majority of real-world models but
cannot follow dynamically constructed references.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

_ENCODINGS = ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be")


def load_json_lenient(path: Path) -> dict:
    """Load JSON trying several encodings (model.bim is often UTF-16)."""
    raw = path.read_bytes()
    last_err: Exception | None = None
    for enc in _ENCODINGS:
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_err = exc
    raise ValueError(f"Could not parse {path} as JSON in any known encoding: {last_err}")


def expr_text(value) -> str:
    """TMSL expressions can be a plain string or a list of lines."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


# --------------------------------------------------------------------------
# M / Power Query source extraction
# --------------------------------------------------------------------------

_M_PATTERNS = [
    # (source_type, regex, groups -> dict keys)
    ("SQL Server", re.compile(r'Sql\.Databases?\s*\(\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?', re.I), ("server", "database")),
    ("Azure Synapse / SQL", re.compile(r'AzureSql(?:Database)?\.Databases?\s*\(\s*"([^"]+)"', re.I), ("server",)),
    ("Databricks", re.compile(r'Databricks\.(?:Catalogs|Query|Contents)\s*\(\s*"([^"]+)"', re.I), ("server",)),
    ("Snowflake", re.compile(r'Snowflake\.Databases\s*\(\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?', re.I), ("server", "database")),
    ("Excel workbook", re.compile(r'Excel\.Workbook\s*\(\s*File\.Contents\s*\(\s*"([^"]+)"', re.I), ("path",)),
    ("CSV file", re.compile(r'Csv\.Document\s*\(\s*File\.Contents\s*\(\s*"([^"]+)"', re.I), ("path",)),
    ("SharePoint", re.compile(r'SharePoint\.(?:Files|Contents|Tables)\s*\(\s*"([^"]+)"', re.I), ("url",)),
    ("Web", re.compile(r'Web\.Contents\s*\(\s*"([^"]+)"', re.I), ("url",)),
    ("OData", re.compile(r'OData\.Feed\s*\(\s*"([^"]+)"', re.I), ("url",)),
    ("ODBC", re.compile(r'Odbc\.(?:DataSource|Query)\s*\(\s*"([^"]+)"', re.I), ("dsn",)),
    ("Power Platform dataflow", re.compile(r'PowerPlatform\.Dataflows', re.I), ()),
    ("Power BI dataflow", re.compile(r'PowerBI\.Dataflows', re.I), ()),
]

_ITEM_SCHEMA = re.compile(r'\[\s*(?:Schema\s*=\s*"([^"]+)"\s*,\s*)?Item\s*=\s*"([^"]+)"', re.I)
_NAME_NAV = re.compile(r'\{\s*\[\s*Name\s*=\s*"([^"]+)"', re.I)
_NATIVE_QUERY = re.compile(r'Value\.NativeQuery\s*\(', re.I)
_DATAFLOW_IDS = re.compile(
    r'(workspaceId|dataflowId|entity(?:Name)?)\s*=\s*"([^"]+)"', re.I
)
_CALENDAR = re.compile(r'\bCALENDAR(?:AUTO)?\s*\(', re.I)


def extract_m_source(expression: str, mode: str) -> dict:
    """Best-effort extraction of the upstream source from a partition."""
    src = {
        "sourceType": "Unknown",
        "server": None,
        "database": None,
        "schema": None,
        "object": None,
        "detail": None,
        "nativeQuery": bool(_NATIVE_QUERY.search(expression)),
    }
    if mode == "calculated" or (not expression.strip().lower().startswith("let") and _CALENDAR.search(expression)):
        src["sourceType"] = "Calculated (DAX)"
        if _CALENDAR.search(expression):
            src["detail"] = "Generated date table (CALENDAR/CALENDARAUTO)"
        return src

    for source_type, pattern, keys in _M_PATTERNS:
        m = pattern.search(expression)
        if m:
            src["sourceType"] = source_type
            for key, val in zip(keys, m.groups()):
                if val:
                    src[key if key in src else "detail"] = val
            break

    schema_item = _ITEM_SCHEMA.search(expression)
    if schema_item:
        src["schema"] = schema_item.group(1)
        src["object"] = schema_item.group(2)
    else:
        navs = _NAME_NAV.findall(expression)
        if navs:
            # first navigation is usually the database, last is the object
            if src["database"] is None and len(navs) > 1:
                src["database"] = navs[0]
            src["object"] = navs[-1]

    if src["sourceType"] in ("Power Platform dataflow", "Power BI dataflow"):
        for key, val in _DATAFLOW_IDS.findall(expression):
            k = key.lower()
            if "workspace" in k:
                src["server"] = val
            elif "dataflow" in k:
                src["database"] = val
            else:
                src["object"] = val
    return src


# --------------------------------------------------------------------------
# DAX reference extraction
# --------------------------------------------------------------------------

# 'Table Name'[Column] or Table[Column]
_QUALIFIED_REF = re.compile(r"(?:'([^']+)'|([A-Za-z_][\w ]*?))\s*\[([^\[\]]+)\]")
# bare [Something] not preceded by a table token / quote / closing bracket
_BARE_REF = re.compile(r"(?<![\w'\]])\[([^\[\]]+)\]")
_DAX_COMMENT = re.compile(r"//[^\n]*|--[^\n]*|/\*.*?\*/", re.S)
_DAX_STRING = re.compile(r'"(?:[^"]|"")*"')


def _strip_dax(expression: str) -> str:
    return _DAX_STRING.sub('""', _DAX_COMMENT.sub("", expression))


def extract_dax_refs(expression: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (qualified refs as (table, field), bare [refs])."""
    text = _strip_dax(expression or "")
    qualified = []
    for m in _QUALIFIED_REF.finditer(text):
        table = (m.group(1) or m.group(2) or "").strip()
        field = m.group(3).strip()
        if table:
            qualified.append((table, field))
    # remove qualified spans before scanning for bare refs
    remainder = _QUALIFIED_REF.sub(" ", text)
    bare = [m.group(1).strip() for m in _BARE_REF.finditer(remainder)]
    return qualified, bare


# --------------------------------------------------------------------------
# Main parse
# --------------------------------------------------------------------------

def parse_model(bim_path: str | Path) -> dict:
    bim_path = Path(bim_path)
    doc = load_json_lenient(bim_path)
    model = doc.get("model", doc)

    tables_out: list[dict] = []
    relationships_out: list[dict] = []
    roles_out: list[dict] = []
    warnings: list[dict] = []

    measure_index: dict[str, str] = {}  # measure name -> home table
    column_index: dict[tuple[str, str], dict] = {}

    # ---- tables ---------------------------------------------------------
    for tbl in model.get("tables", []):
        name = tbl.get("name", "")
        columns = []
        for col in tbl.get("columns", []):
            c = {
                "name": col.get("name", ""),
                "dataType": col.get("dataType", ""),
                "isHidden": bool(col.get("isHidden", False)),
                "isCalculated": col.get("type") == "calculated",
                "expression": expr_text(col.get("expression")) or None,
                "sortByColumn": col.get("sortByColumn"),
                "description": expr_text(col.get("description")) or None,
                "dataCategory": col.get("dataCategory"),
                "formatString": col.get("formatString"),
            }
            columns.append(c)
            column_index[(name, c["name"])] = c

        measures = []
        for mea in tbl.get("measures", []):
            measures.append({
                "name": mea.get("name", ""),
                "expression": expr_text(mea.get("expression")),
                "displayFolder": mea.get("displayFolder"),
                "formatString": mea.get("formatString"),
                "description": expr_text(mea.get("description")) or None,
                "isHidden": bool(mea.get("isHidden", False)),
                "table": name,
            })
            measure_index[mea.get("name", "")] = name

        partitions = []
        for part in tbl.get("partitions", []):
            src = part.get("source", {}) or {}
            p_mode = src.get("type", "m")
            expression = expr_text(src.get("expression"))
            partitions.append({
                "name": part.get("name", ""),
                "mode": part.get("mode", "import"),
                "type": p_mode,
                "expression": expression,
                "source": extract_m_source(expression, p_mode),
            })

        hierarchies = [
            {
                "name": h.get("name", ""),
                "levels": [lv.get("column") for lv in h.get("levels", [])],
            }
            for h in tbl.get("hierarchies", [])
        ]

        annotations = {a.get("name"): a.get("value") for a in tbl.get("annotations", [])}

        tables_out.append({
            "name": name,
            "isHidden": bool(tbl.get("isHidden", False)),
            "description": expr_text(tbl.get("description")) or None,
            "dataCategory": tbl.get("dataCategory"),
            "columns": columns,
            "measures": measures,
            "partitions": partitions,
            "hierarchies": hierarchies,
            "annotations": annotations,
        })

    table_names = {t["name"] for t in tables_out}

    # ---- relationships --------------------------------------------------
    for rel in model.get("relationships", []):
        relationships_out.append({
            "name": rel.get("name", ""),
            "fromTable": rel.get("fromTable", ""),
            "fromColumn": rel.get("fromColumn", ""),
            "toTable": rel.get("toTable", ""),
            "toColumn": rel.get("toColumn", ""),
            "isActive": rel.get("isActive", True),
            "crossFilteringBehavior": rel.get("crossFilteringBehavior", "singleDirection"),
            "fromCardinality": rel.get("fromCardinality", "many"),
            "toCardinality": rel.get("toCardinality", "one"),
        })

    # ---- roles ----------------------------------------------------------
    for role in model.get("roles", []):
        roles_out.append({
            "name": role.get("name", ""),
            "modelPermission": role.get("modelPermission", "read"),
            "tablePermissions": [
                {
                    "table": tp.get("name", ""),
                    "filterExpression": expr_text(tp.get("filterExpression")),
                }
                for tp in role.get("tablePermissions", [])
            ],
        })

    # ---- DAX dependency graph ------------------------------------------
    # measure name -> {"measures": set, "columns": set[(table, col)], "tables": set}
    measure_deps: dict[str, dict] = {}
    all_measure_names = set(measure_index)

    for tbl in tables_out:
        for mea in tbl["measures"]:
            qualified, bare = extract_dax_refs(mea["expression"])
            dep_measures, dep_columns, dep_tables = set(), set(), set()
            for table, field in qualified:
                if table in table_names:
                    if (table, field) in column_index:
                        dep_columns.add((table, field))
                        dep_tables.add(table)
                    elif field in all_measure_names:
                        dep_measures.add(field)
                    else:
                        dep_tables.add(table)  # table-level function ref
                elif field in all_measure_names:
                    dep_measures.add(field)
            for field in bare:
                if field in all_measure_names:
                    dep_measures.add(field)
            measure_deps[mea["name"]] = {
                "measures": dep_measures,
                "columns": dep_columns,
                "tables": dep_tables,
            }

    def resolve_tables(measure: str, seen: set[str]) -> set[str]:
        """All tables a measure ultimately touches (cycle-safe)."""
        if measure in seen or measure not in measure_deps:
            return set()
        seen.add(measure)
        deps = measure_deps[measure]
        tables = set(deps["tables"])
        for child in deps["measures"]:
            tables |= resolve_tables(child, seen)
        return tables

    measures_flat = []
    for tbl in tables_out:
        for mea in tbl["measures"]:
            deps = measure_deps.get(mea["name"], {"measures": set(), "columns": set(), "tables": set()})
            mea["dependsOnMeasures"] = sorted(deps["measures"])
            mea["dependsOnColumns"] = sorted(f"{t}[{c}]" for t, c in deps["columns"])
            mea["directTables"] = sorted(deps["tables"])
            mea["allTables"] = sorted(resolve_tables(mea["name"], set()))
            measures_flat.append(mea)

    # calculated column dependencies
    for tbl in tables_out:
        for col in tbl["columns"]:
            if col["isCalculated"] and col["expression"]:
                qualified, bare = extract_dax_refs(col["expression"])
                refs = sorted({f"{t}[{c}]" for t, c in qualified if t in table_names})
                refs += sorted({f"[{b}]" for b in bare if b in all_measure_names})
                col["dependsOn"] = refs
            else:
                col["dependsOn"] = []

    # ---- internal column references (for semantic-only "no internal refs")
    internally_referenced: set[tuple[str, str]] = set()
    for rel in relationships_out:
        internally_referenced.add((rel["fromTable"], rel["fromColumn"]))
        internally_referenced.add((rel["toTable"], rel["toColumn"]))
    for tbl in tables_out:
        for h in tbl["hierarchies"]:
            for lvl in h["levels"]:
                if lvl:
                    internally_referenced.add((tbl["name"], lvl))
        for col in tbl["columns"]:
            if col["sortByColumn"]:
                internally_referenced.add((tbl["name"], col["sortByColumn"]))
    for deps in measure_deps.values():
        internally_referenced |= deps["columns"]
    for tbl in tables_out:
        for col in tbl["columns"]:
            for ref in col["dependsOn"]:
                m = re.match(r"^(.*)\[(.*)\]$", ref)
                if m and m.group(1):
                    internally_referenced.add((m.group(1), m.group(2)))
    for role in roles_out:
        for tp in role["tablePermissions"]:
            qualified, _ = extract_dax_refs(tp["filterExpression"])
            internally_referenced |= {q for q in qualified}

    for tbl in tables_out:
        for col in tbl["columns"]:
            col["internallyReferenced"] = (tbl["name"], col["name"]) in internally_referenced

    # ---- table classification ------------------------------------------
    many_side = {}
    one_side = {}
    for rel in relationships_out:
        many_side[rel["fromTable"]] = many_side.get(rel["fromTable"], 0) + 1
        one_side[rel["toTable"]] = one_side.get(rel["toTable"], 0) + 1

    for tbl in tables_out:
        name = tbl["name"]
        n_cols = len(tbl["columns"])
        n_meas = len(tbl["measures"])
        anns = " ".join(f"{k}={v}" for k, v in tbl["annotations"].items())
        exprs = " ".join(p["expression"] for p in tbl["partitions"])
        col_exprs = " ".join(c["expression"] or "" for c in tbl["columns"])

        is_date = (
            tbl["dataCategory"] == "Time"
            or any(c.get("dataCategory") == "Time" for c in tbl["columns"])
            or bool(_CALENDAR.search(exprs))
        )
        is_field_param = "NAMEOF" in col_exprs.upper() or "ParameterMetadata" in anns
        is_measure_container = n_meas > 0 and n_cols <= 1 and not many_side.get(name) and not one_side.get(name)
        is_helper = n_meas == 0 and not many_side.get(name) and not one_side.get(name) and tbl["isHidden"]

        if is_field_param:
            t_type = "field parameter"
        elif is_date:
            t_type = "date dimension"
        elif is_measure_container:
            t_type = "measure container"
        elif is_helper:
            t_type = "helper"
        elif many_side.get(name, 0) > one_side.get(name, 0):
            t_type = "fact"
        elif one_side.get(name, 0) > 0:
            t_type = "dimension"
        elif many_side.get(name, 0) > 0:
            t_type = "fact"
        else:
            t_type = "disconnected"
        tbl["tableType"] = t_type

    # ---- quality warnings ----------------------------------------------
    for rel in relationships_out:
        if not rel["isActive"]:
            warnings.append({
                "severity": "info",
                "category": "Inactive relationship",
                "message": f"{rel['fromTable']}[{rel['fromColumn']}] → {rel['toTable']}[{rel['toColumn']}] is inactive; it only applies inside USERELATIONSHIP().",
            })
        if rel["crossFilteringBehavior"] == "bothDirections":
            warnings.append({
                "severity": "warning",
                "category": "Bidirectional filter",
                "message": f"{rel['fromTable']} ↔ {rel['toTable']} filters in both directions; check for ambiguity and performance impact.",
            })
        if rel["fromCardinality"] == "many" and rel["toCardinality"] == "many":
            warnings.append({
                "severity": "warning",
                "category": "Many-to-many",
                "message": f"{rel['fromTable']} ↔ {rel['toTable']} is many-to-many.",
            })

    if not any(t["tableType"] == "date dimension" for t in tables_out):
        warnings.append({
            "severity": "warning",
            "category": "No date dimension",
            "message": "No date dimension detected; time intelligence functions may not behave as expected.",
        })

    connected = set()
    for rel in relationships_out:
        connected.add(rel["fromTable"])
        connected.add(rel["toTable"])
    for tbl in tables_out:
        if tbl["name"] not in connected and tbl["tableType"] not in ("measure container", "field parameter", "helper"):
            warnings.append({
                "severity": "info",
                "category": "Disconnected table",
                "message": f"'{tbl['name']}' has no relationships to any other table.",
            })

    return {
        "name": model.get("name") or bim_path.stem,
        "compatibilityLevel": doc.get("compatibilityLevel"),
        "culture": model.get("culture"),
        "tables": tables_out,
        "measures": measures_flat,
        "relationships": relationships_out,
        "roles": roles_out,
        "warnings": warnings,
    }
