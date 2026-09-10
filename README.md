# Power BI Documentation Generator

Generate a single, self-contained, interactive HTML documentation file for a Power BI solution — from its **semantic model** (`model.bim`), its **report** (a PBIR `*.Report` folder), or **both together**.

The goal is onboarding: a Power BI developer who has never seen the report before should be able to open one HTML file and understand what the solution contains, where the data comes from, how the report actually consumes the model, what is safe to remove, and where the gotchas are.

No installation beyond Python. No third-party packages. One command, one file out.

## Which columns are used, and which can be deleted?

The HTML now opens on **Columns** when a model is supplied. It lists **one row
per column and report page**, with deletion assessment and usage first. A column
used on four pages has four rows. A column with no page usage still has one row
with a blank page, so removal candidates remain visible. Page IDs distinguish
pages with identical display names. Counts at the top count distinct columns.

```bash
python generate_docs.py --project path/to/MyReport.pbip --output docs/MyReport.html --csv docs/column-pages.csv
```

- To answer **what columns are used**, choose **Used in report**. The page usage
  shows direct bindings and dependencies through measures or calculated columns.
- To answer **what columns can be deleted**, choose **Deletion candidate**.
  These have no detected references in the supplied model and report. Check
  other reports, Excel/composite-model consumers and Power Query steps before
  removal; the tool does not certify deletion as safe.
- **Keep** means there is a detected report or model dependency. Evidence
  includes all dependent measures (including chains), calculated columns,
  calculated-table/calculation-item expressions, RLS, keys, relationships
  (including inactive ones), hierarchies, sort-by columns and dynamic measure
  format expressions. A measure need not appear in the report to block deleting
  a column it references.
- **Review** means usage cannot be assessed fully. Whole-table DAX references,
  unresolved bindings/DAX references, or unreadable report/model definitions
  block a candidate verdict. With a model alone, report usage is **Unknown**
  and no deletion candidates are issued.

Search across columns, calculations and sources; filter by page or assessment;
click a column heading to sort. **Export filtered CSV** exports the rows currently
shown. `--csv PATH` exports the complete inventory using the same fields, with
UTF-8 BOM for Excel and formula-like cells escaped as text. Report-only mode
does not support column inventory or `--csv`, because the full column list is
unknown without a model.

Expand **Evidence & source** for dependent measures, model dependencies, page
evidence, bookmark usage, partition sources and the source column name retained
in model metadata. This source column is the **model input name**, not verified
physical lineage through Power Query renames or transformations. Multiple
partition sources are listed together without multiplying column/page rows.
Report-level filters apply to every page. Bookmark-only dependencies have a
blank page; the tool does not guess which page a bookmark affects.

This remains static analysis, not a full DAX/M engine. Whole-table dependencies
are review blockers rather than claims that every column is read. Calculation
items, field parameters and calculated tables can require additional review of
runtime behavior. The Columns inventory is included in JSON as `columns`; its
cleanup assessments are available in HTML and CSV, not in the Word/agent layouts.

Run the regression tests with `python -m unittest discover -s tests -v`.

```
python generate_docs.py --model Sales.SemanticModel/model.bim --report Sales.Report --output docs/Sales.html
```

---

## Contents

1. [What you get](#what-you-get)
2. [Requirements](#requirements)
3. [Getting the input files out of Power BI](#getting-the-input-files-out-of-power-bi)
4. [Running the generator](#running-the-generator)
5. [The three modes](#the-three-modes)
6. [Understanding the output — every tab explained](#understanding-the-output--every-tab-explained)
7. [Reading the usage verdicts](#reading-the-usage-verdicts)
8. [Word export](#word-export)
9. [Batch-documenting many reports](#batch-documenting-many-reports)
9. [The embedded JSON (for catalogs and automation)](#the-embedded-json-for-catalogs-and-automation)
10. [Limitations and honesty notes](#limitations-and-honesty-notes)
11. [Agent context (`--agent`)](#agent-context---agent)
12. [Repository layout](#repository-layout)

---

## What you get

One HTML file per run. It opens in any modern browser, works offline, needs no server, and can be emailed, dropped in SharePoint, or committed to a repo. Inside it:

- A **mode banner** showing exactly which inputs were supplied (semantic model, report, or both), so the reader always knows how much the document can honestly claim.
- A **lineage board** (combined mode): sources → model tables → report pages, with clickable path highlighting.
- A **usage verdict for every table** (combined mode): directly used, used via measures, possibly used, or no references — each with the evidence.
- **Per-page "what feeds this"** breakdowns: every visual, its field bindings, and the tables behind them.
- Every **filter** in the report at all three scopes (report / page / visual) with condition hints.
- Full **model reference**: tables with columns and partition M code, measures with highlighted DAX and resolved dependency chains, relationships with an ERD, data sources grouped by server, and RLS roles.
- A **warnings tab**: inactive relationships, bidirectional filters, missing date dimension, broken report bindings, and other things a new developer should know before touching anything.

Everything is cross-linked: click a table name anywhere to jump to its detail; click a measure to see its DAX and everything it depends on.

## Requirements

- Python **3.10 or newer** (standard library only — there is no `pip install` step).
- The input files described below.

Check your Python version with `python --version` (on some systems the command is `python3`).

## Getting the input files out of Power BI

The generator reads the file formats Power BI Desktop produces when you save your work as a **Power BI Project (.pbip)** — a folder-based format designed for source control, rather than the single binary `.pbix`.

### Step 1 — Enable the project save format (one-time setup)

In **Power BI Desktop**:

1. Go to **File → Options and settings → Options → Preview features**.
2. Enable **"Power BI Project (.pbip) save option"** (if listed — in recent Desktop versions this is no longer a preview and is always available).
3. Also enable **"Store reports using enhanced metadata format (PBIR)"** if it appears under preview features. This makes the report save as a folder of readable JSON files, which is what the report parser reads.
4. Restart Power BI Desktop if prompted.

> Menu names shift slightly between Desktop releases. If you can't find an option, search Microsoft's documentation for "Power BI Desktop projects (PBIP)" — the official page tracks the current toggles.

### Step 2 — Save your work as a project

Open your `.pbix` in Power BI Desktop, then **File → Save as** and choose the **`.pbip`** file type. Desktop writes a folder structure next to the `.pbip` file:

```
MyReport.pbip                  ← point --project here and everything else is found
MyReport.Report/               ← report definition
    definition.pbir            ← names the semantic model this report belongs to
    definition/
        report.json
        pages/
            ...
MyReport.SemanticModel/        ← semantic model, in EITHER format:
    model.bim                  ← TMSL, a single JSON file
    ...or...
    definition/                ← TMDL, a folder of .tmdl files (Desktop's default)
        model.tmdl
        relationships.tmdl
        tables/*.tmdl
```

### Step 3 — Nothing to do: both model formats are read

Power BI Desktop stores the semantic model as either **TMSL** (`model.bim`) or **TMDL** (a `definition/` folder of `.tmdl` files). Recent Desktop versions default to TMDL. **The generator reads both**, and produces identical documentation either way — point `--model` at the `*.SemanticModel` folder and it works out which format is inside.

You do not need Tabular Editor, and you do not need to convert anything.

### Step 4 — Confirm the report saved in PBIR format

The report parser expects the **enhanced (PBIR)** folder layout: `MyReport.Report/definition/pages/<page>/page.json` with a `visuals/` subfolder per page. If your `.Report` folder instead contains a single large `report.json` and no `definition/pages/` folder, it was saved in the legacy format — enable the PBIR preview feature (Step 1) and re-save.

### What if I only have one of the two?

That's fine — and it's a designed-for scenario, not a degraded one. See [The three modes](#the-three-modes).

## Running the generator

Clone or download this repository, then from its root folder:

**A whole project (simplest — both artifacts discovered for you):**

```
python generate_docs.py --project path/to/MyReport.pbip --output docs/MyReport.html
```

`--project` also accepts the **project folder**, the **`*.SemanticModel`** folder, or the **`*.Report`** folder. Given a report, the generator follows its `definition.pbir` to find the matching semantic model, so all of these produce the same combined document:

```
python generate_docs.py --project C:/GIT/MyReport            --output docs/MyReport.html
python generate_docs.py --project C:/GIT/MyReport.Report     --output docs/MyReport.html
python generate_docs.py --project C:/GIT/MyReport.SemanticModel --output docs/MyReport.html
```

**Naming both inputs explicitly** (needed when a project holds several artifacts, or when the two live apart):

```
python generate_docs.py --model path/to/MyReport.SemanticModel ^
                        --report path/to/MyReport.Report ^
                        --output docs/MyReport.html ^
                        --title "My Report"
```

(`^` is the Windows line-continuation; on macOS/Linux use `\`.)

`--model` takes the `*.SemanticModel` folder in either format, its inner `definition/` folder, or a `model.bim` file directly. An explicit `--model` or `--report` always overrides what `--project` discovered.

**Semantic model only:**

```
python generate_docs.py --model path/to/model.bim --output docs/model.html
```

**Report only:**

```
python generate_docs.py --report path/to/MyReport.Report --output docs/report.html
```

**All flags:**

| Flag | Meaning |
|---|---|
| `--project` | Path to a `.pbip` file, a project folder, or either artifact folder. Discovers the semantic model and report from it. |
| `--model` | Path to the semantic model: a `*.SemanticModel` folder (TMDL **or** TMSL), its `definition/` folder, or a `model.bim` file. |
| `--report` | Path to the `*.Report` folder (PBIR). Pointing at the inner `definition/` folder also works. |
| `--output`, `-o` | Where to write the HTML. Defaults to `<title>.html` in the current folder. |
| `--title` | Title shown in the document. Defaults to the model or report name. |
| `--json` | Also write the consolidated analysis as a JSON file (see [embedded JSON](#the-embedded-json-for-catalogs-and-automation)). |
| `--csv` | Write the full column/page inventory to this CSV path; requires a semantic model. |
| `--word` | Also write a Word document (`.docx`) — see [Word export](#word-export). Still zero dependencies: the `.docx` is written with the standard library. |
| `--agent` | Also write an agent context document (`.agent.md`) — see [Agent context](#agent-context---agent). |

**Try it right now** with the bundled synthetic example (a small sales model plus a two-page report):

```
python generate_docs.py --project examples/Sales.pbip --output Sales.html
```

Open `Sales.html` in a browser.

## The three modes

The generator detects the mode from what you supply and — importantly — **adjusts what it is willing to claim**.

| Mode | Inputs | What you get | What it will *not* claim |
|---|---|---|---|
| **Combined** | model + report | Everything: lineage, usage verdicts, per-page feeds, full model reference. | — |
| **Semantic-only** | model only | Full model reference: tables, measures, relationships, ERD, sources, RLS, warnings. | It will never call anything "unused". The strongest statement it makes is *"no internal references"* — nothing **inside this model** uses the column. External reports, Excel connections, or composite models might. |
| **Report-only** | report only | Pages, visuals, filters, bookmarks, and a **field manifest**: every field the report demands, treated as an *unresolved requirement*. This is effectively a rebuild specification. | It cannot confirm any referenced field actually exists, cannot reliably distinguish measures from columns, and cannot trace anything to a data source. |

A typical workflow: run semantic-only when you only have the model, then re-run in combined mode once you obtain the report — the document upgrades itself.

## Understanding the output — every tab explained

The left rail groups tabs by what they need. Tabs that don't apply to the current mode are greyed out with a tooltip, never silently empty.

**Overview** — the cover page. The mode banner, headline counts, data sources at a glance, the usage-verdict summary (combined mode), and how many warnings were flagged. If you read nothing else, read this.

**Lineage** *(combined only)* — the three-column flow: source systems on the left, model tables in the middle (colored by usage verdict), report pages on the right. Click any node to highlight every path through it; click a table node a second time to jump to its detail. This answers "if server X goes away, which pages break?" and "what does this page ultimately depend on?" in one glance.

**Usage** *(combined only)* — one row per table with its verdict and, crucially, the **evidence**: which fields are bound where, or which measures pull the table in, or which relationship makes it "possible". Filter chips let you isolate the removal candidates. See [Reading the usage verdicts](#reading-the-usage-verdicts).

**Pages** *(report modes)* — one expandable card per report page. Each contains a rolled-up *"what feeds this page"* table (every model table the page touches and through which fields), then the full visual inventory with per-visual field bindings and visual-level filters, then page-level filters. This is the tab for "I've been asked to change the Sales Overview page — what am I dealing with?"

**Filters** *(report modes)* — every filter in the report in one table, across all three scopes: report-level (applies everywhere), page-level, and visual-level. Includes the filter type (basic, advanced, top N, relative date…) and a best-effort hint of the condition values.

**Field manifest** *(report modes)* — the flat list of every distinct field the report references and everywhere it's used. In combined mode each entry shows how it resolved against the model (column / measure / **broken binding** in red). In report-only mode this is the rebuild spec: hand it to whoever is building the replacement model.

**Tables** *(model modes)* — one expandable card per table: type badge (fact / dimension / date dimension / measure container / field parameter / helper / disconnected), source, every column with its data type and usage status and calculated-column dependencies, hierarchies, and the raw partition M code with highlighting. Tables whose partitions contain a native SQL query are flagged, since their transformations happen upstream of Power Query.

**Measures** *(model modes)* — every measure with syntax-highlighted DAX and its resolved dependency chain: measures it calls (transitively followed, cycle-safe), columns it reads, and **all tables it ultimately touches**. In combined mode each measure is badged used / not used in the report, with the list of visuals using it.

**Relationships** *(model modes)* — an auto-drawn ERD (dimensions left, facts center; dashed lines are inactive relationships; amber lines filter both directions) plus the full relationship table with cardinality and cross-filter direction. Disconnected tables are listed below the diagram rather than omitted silently.

**Sources** *(model modes)* — every upstream system grouped by server/database, with the model tables it feeds and the specific source objects (schema.table, file path, URL…). Extracted statically from partition M expressions.

**Security** *(model modes)* — RLS roles and their filter expressions per table. If no roles exist, the tab says so explicitly, since "no RLS" is itself important information.

**Warnings** — everything the static analysis flagged: inactive relationships (only honored inside `USERELATIONSHIP`), bidirectional filters, many-to-many relationships, missing date dimension, disconnected tables, unreadable report files, and — in combined mode — **broken bindings**, where the report references a field the model doesn't have. Read this tab before changing anything.

## Reading the usage verdicts

In combined mode every table gets exactly one verdict:

| Verdict | Meaning | Typical action |
|---|---|---|
| **direct** | A column or measure homed on this table is bound in a visual, filter, or bookmark. | Load-bearing. Treat with care. |
| **via measures** | Nothing binds this table directly, but the DAX of a measure the report *does* use reads it (followed transitively through measure-calls-measure chains). | Load-bearing but invisible in the report UI — the classic trap for newcomers. |
| **possible** | Not referenced at all, but connected by an **active relationship** to a used table, so it can participate in filter propagation. | Investigate before removing; slicers or RLS may depend on the path. |
| **no references** | Nothing in this report reaches the table, directly or indirectly. | Removal candidate — **but** first verify no *other* report, Excel connection, or composite model uses this same semantic model. This document only sees the report you gave it. |

Column-level verdicts work the same way, with one extra state: *internal only*, meaning the column isn't used by the report but is used inside the model itself (in a relationship, hierarchy, sort-by, RLS filter, measure, or calculated column) — deleting it would break the model even though no visual shows it.

## Word export

Add `--word` to any run to also produce a `.docx`:

```
python generate_docs.py --model model.bim --report MyReport.Report ^
                        --output docs/MyReport.html --word docs/MyReport.docx
```

The Word document is a **second rendering of the same analysis**, not a separate code path — whatever the HTML says, the Word file says. It exists for the situations HTML doesn't fit: formal sign-off, handover packs, attaching to a change request, printing.

It is deliberately *not* the HTML flattened. Word is linear, with no search or click-through lineage, so the document is structured as a narrative: cover with the mode banner (the same "what this document can claim" honesty), overview counts, data sources, table-usage verdicts with evidence, per-page "what feeds this" breakdowns, filters, the field manifest, warnings — then reference appendices (tables with partition M code, measures with DAX and dependency chains, relationships, RLS). Mode rules apply identically: a semantic-only run never claims anything is "unused", and a report-only run presents the manifest as a rebuild specification.

The writer is pure standard library (a `.docx` is a ZIP of XML), so `--word` adds no installation step. For everyday work, prefer the HTML — the Word file is the one you hand to someone.

## Batch-documenting many reports

The generator is one report per invocation by design (one HTML per solution, ready for a catalog). Loop it — add `--word` inside the loop if every report should also get its `.docx`:

**PowerShell:**

```powershell
Get-ChildItem -Directory -Filter "*.Report" | ForEach-Object {
    $name  = $_.Name -replace "\.Report$", ""
    $model = "$name.SemanticModel\model.bim"
    python generate_docs.py --model $model --report $_.FullName --output "docs\$name.html" --title $name
}
```

**bash:**

```bash
for r in *.Report; do
  name="${r%.Report}"
  python generate_docs.py --model "$name.SemanticModel/model.bim" --report "$r" \
                          --output "docs/$name.html" --title "$name"
done
```

## The embedded JSON (for catalogs and automation)

Every generated HTML file carries its full analysis as a JSON object embedded in the page (`const DATA = {...}` in the single `<script>` block). The same payload can be written to a standalone file with `--json out/analysis.json`.

This means each HTML file is simultaneously human documentation **and** a machine-readable record: a future catalog, search index, or impact-analysis tool can harvest the JSONs (or scrape them back out of the HTML files) without re-parsing any Power BI artifacts. Top-level keys: `title`, `mode`, `generated`, `model`, `report`, `linked`.

## Limitations and honesty notes

Know what the tool can and cannot see — the documentation is only as trustworthy as its caveats:

- **Static regex analysis.** DAX and M are parsed with regular expressions, not full language parsers. This covers real-world models well, but dynamically constructed references (e.g., field parameters driving measure selection at runtime, M queries built from parameters) may not fully resolve.
- **One report's view.** "No references" means *this report* doesn't use the table. Other reports sharing the model, Analyze-in-Excel users, and composite models are invisible here.
- **Inactive relationships** are reported but not traversed for the "possible" verdict, since they only apply inside `USERELATIONSHIP()` — which the measure dependency analysis does capture at the table level.
- **Filter condition hints** are best-effort extractions of literal values, not full condition reconstructions. Complex advanced filters show a partial hint or none.
- **Legacy single-file `report.json` reports are not supported.** Re-save with the PBIR format enabled (see [Getting the input files](#getting-the-input-files-out-of-power-bi)). Both semantic model formats — TMSL and TMDL — *are* supported.
- **TMDL reading is a static text parse, not an Analysis Services load.** It covers what Desktop and Tabular Editor write. Translations (`cultures/`) and perspectives are skipped, since nothing downstream uses them. A `.tmdl` file that fails to parse is reported as a warning in the document rather than sinking the run.
- **Custom visuals** are inventoried by their type identifier; their field bindings are extracted the same way as native visuals and usually resolve, but exotic custom-visual query shapes may be missed.

When the tool isn't sure, it says less rather than guessing — that's a feature.

## Agent context (`--agent`)

The HTML documentation is for humans. `--agent` writes a fourth rendering of the **same analysis** for **LLMs and coding agents**: a compact, front-loaded markdown distillation (`<output>.agent.md`) with everything an agent needs to answer *"can I build report X off this model?"* — and nothing it doesn't (no lineage tags, annotations, refresh policies, credentials, or full M scripts; DAX truncated at a budget).

```
python generate_docs.py --model model.bim --agent
python generate_docs.py --model model.bim --report Sales.Report --agent docs/Sales.agent.md
```

Inside, in reading order: an orientation header stating the mode and its honesty limits; counts; broken bindings (combined mode) before anything else; tables at a glance with type, storage, source, and report-usage verdict; modelling caveats; relationships with a mermaid ERD; a **filter-reachability table** — which tables can slice which over active relationships, so feasibility questions need no graph reasoning; per-table columns; every measure's DAX with resolved dependencies and whether the report uses it; RLS roles; report structure; and the source → table → pages lineage.

Because it renders from the same consolidated payload as the HTML, JSON, and Word outputs, the agent doc can never disagree with them — one payload, four renderings. A rough token estimate is printed on generation.

---

## Repository layout

```
generate_docs.py            CLI entry point
pbidocgen/
    model_parser.py         TMSL model.bim → normalized model dict
                            (encoding fallbacks, DAX dependency resolution,
                             M source extraction, table classification, warnings)
    report_parser.py        PBIR .Report folder → pages, visuals, bindings,
                            filters, bookmarks, requirements manifest
    linker.py               combined-mode join: resolves bindings, usage
                            verdicts, lineage, broken-binding detection
    renderer.py             builds the consolidated JSON payload and injects
                            it into the HTML template
    word_writer.py          renders the same payload as a .docx (pure stdlib
                            OOXML — no python-docx, no pip install)
    agent_writer.py         renders the same payload as agent context
                            markdown (--agent) — see "Agent context" above
    tmdl_reader.py          reads a TMDL definition/ folder and emits the
                            same shape a model.bim would, so everything
                            downstream is format-agnostic
    project.py              resolves a .pbip / project folder / artifact
                            folder into the model and report paths
    template.html           the self-contained interactive documentation app
examples/
    Sales.SemanticModel/    synthetic model.bim for trying the tool
    Sales.Report/           synthetic PBIR report folder
```
