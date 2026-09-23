# Power BI Documentation Generator

## New: process a whole folder of PBIX files

On Windows, install Power BI Desktop and **pbi-tools Desktop**, then run:

```powershell
python generate_docs.py --pbix-folder "C:\Reports" --output-dir "C:\Documentation" --pbi-tools "C:\Tools\pbi-tools\pbi-tools.exe" --recursive
```

Open `C:\Documentation\pbi-home.html`. Each successfully extracted PBIX has an HTML
report; failures appear in the home-page summary and do not stop other files.
Saved usernames and report locations survive reruns. See
[PBIX-QUICKSTART.md](PBIX-QUICKSTART.md) for installation, single-file usage,
logs, limitations and validation status. The Windows extraction dependency is
not bundled; end-to-end testing with actual PBIX files remains pending.


Generate a single, self-contained, interactive HTML documentation file for a Power BI solution — from its **semantic model** (`model.bim`), its **report** (a PBIR `*.Report` folder), or **both together**.

The goal is onboarding: a Power BI developer who has never seen the report before should be able to open one HTML file and understand what the solution contains, where the data comes from, how the report actually consumes the model, what is safe to remove, and where the gotchas are.

No installation beyond Python (3.10 or later). No third-party packages. One command, one file out.

## Explore usage by report page

The shared **Report page** selector stays selected as you move between Columns,
Tables, Usage, Lineage, Pages, Filters, Field manifest, Measures, Sources and the
new exploration views. The report name is always shown; each extract currently
contains one supplied report. Page IDs distinguish duplicate page names.
Search inputs, column sorting and expanded table/measure details are retained
while switching sections within the open document.

| View | What it answers | How to use it |
|---|---|---|
| **Usage matrix** | Which tables and columns feed each page? | Expand a table, search for a column, and select a page cell to inspect its evidence. |
| **Impact inspector** | What would a column or measure change affect? | Choose a field to see downstream calculations and explicit paths to page/visual bindings. Follow **Reads these fields** upstream to inspect source columns. |
| **Page layout** | Which saved visual is using a field? | Select a visual in the schematic or its accessible list to inspect bindings and filters. Hidden pages/visuals are labelled. |
| **Cleanup review** | Which columns warrant removal review, and why? | Start with **Deletion candidate**, inspect dependencies and uncertainty, and export evidence at column/page grain. |
| **Compare extracts** | What changed between two extractions? | Open the newer HTML, select the earlier `--json` file, and inspect added, removed or changed definitions with affected pages. |

For example: select a page, open **Usage matrix**, expand a table and select a
column's cell. Its evidence opens in a side panel. **Trace dependency paths**
shows the column → calculation/measure → visual relationship. Use **Cleanup
review** to assess unreferenced columns across the complete supplied extract.

**Scope is deliberate:** page filters restrict usage and usage exports. Cleanup
assessments, overview counts, relationship structure, security and warnings cover
the whole extract and are labelled accordingly. A column absent from the selected
page may still be needed elsewhere. The cleanup CSV retains one row per column
and resolved page, including a blank page for columns without resolved page use.

Dependency paths are derived from detected explicit DAX references, including
calculated columns and dynamic format expressions. One shortest path is shown
per binding; alternative routes, whole-table semantics, relationships and runtime
filter context are not claimed as precise column paths. The JSON contains these
nodes, reference edges and consumer locations in `columns.dependencyGraph`.
A measure's home table is organisational; its data dependencies and DAX determine
how it responds to filters. The agent Markdown now explains that distinction.

Page layout uses saved page/visual geometry; it does not execute or reproduce
charts. Missing geometry is shown in the visual list. Comparison reads JSON
locally, with no upload, and compares definitions rather than data values. Generate
each snapshot using `--json`, then load the earlier file in the newer HTML.
Comparison includes sources, DAX, columns, hierarchies, relationships, RLS,
bookmarks, filters, pages and visuals. Renamed objects generally appear as removed
and added; page renames retain identity when the page ID is stable. Extracts from
different models/reports or extraction modes display a comparability notice.
Older extracts without page usage cannot provide complete affected-page evidence
for removed model objects. Changes without a resolved page remain visible as
model/unassigned scope; the comparison CSV expands affected pages into rows.

The generated HTML remains one offline file: `explorer.js` and `explorer.css`
are embedded during generation, so you do not need to distribute them beside it.

## Primary sources: external inputs and reporting usage

Use **Primary sources** to see external databases, SharePoint files/lists,
local/network files, folders, web/API endpoints, OData and Azure storage. The
source is the external input: a workbook reader, staging query or calculated
result is not another source. See [CONNECTOR-COVERAGE.md](CONNECTOR-COVERAGE.md)
for documented functions, supported forms and limitations. This implementation
is not the complete Microsoft connector catalogue; unsupported sources remain
visible as unresolved query entries.

The view separates **source identification** from **reporting usage**. It shows
connection queries, consuming model queries, configured partition storage modes,
preparation effects, dependency status and usage evidence/confidence. A model
partition definition does not prove data was loaded, and a referenced source
does not prove its columns survive into a displayed result. Load/refresh execution
is explicitly unknown; Enable load/Include in report refresh are not inferred.

| Reporting usage | Meaning |
| --- | --- |
| Potential reporting dependency | Downstream model table has page usage; this external input's contribution is not proven. |
| Possible model dependency | Page association comes only from possible model dependencies such as relationship paths. |
| Report scope only | Report/bookmark dependency exists without a resolved individual page. |
| No reporting usage found | A model partition exists but no reporting dependency was detected with the available analysis. |
| No model consumer found | A defined shared source has no traced model consumer. |
| Usage unresolved | Missing report/source metadata or incomplete analysis prevents a reliable assessment. |

Merges, row filters and column removal are retained as preparation evidence.
No reporting usage found is **not a deletion verdict**. Sources without identified
pages remain under **No specific page**, including dormant shared queries and
unresolved inputs. Individual report page IDs remain distinct even when their
names match. Both search and reporting-usage filters apply to the export.

**Export primary sources CSV** downloads `<report name>-primary-sources.csv`.
It contains source identities, file/folder/URL, report/page, consumer queries,
dependency and reporting statuses, short controlled usage evidence, configured
storage modes, confidence and runtime/removal limitations. It excludes M, SQL,
referenced-query code and raw extraction notes. Tabs, control characters and
line breaks become spaces, keeping each record on one physical line. Original
code remains in the existing source-object HTML/JSON inventory for verification.

## Sources query CSV

In **Sources**, choose **Export all M queries CSV**. It downloads
`<report name>-source-queries.csv` with exactly:

| report | query name | query m code |
|---|---|---|
| Supplied report name | Table/query or shared-expression name | Complete M expression |

The export covers the whole model, regardless of selected page, and includes
shared M queries, functions and parameters. Single-partition queries use the
table name; multiple partitions use `table / partition`. SQL-only, DAX and
entity partitions are excluded. In model-only mode, the model name replaces
the report name. Multiline expressions and quotes are preserved in CSV fields;
spreadsheet-formula-like cells receive a protective leading apostrophe.

All browser CSV filenames now include the report name (with filename-unsafe
characters replaced). Explicit command-line `--csv PATH` destinations are
unchanged. Regenerate the HTML to obtain the new export button.

See [ADVERSARIAL-REVIEW.md](ADVERSARIAL-REVIEW.md) for the consolidated fix
register, remediation status and reproduction steps.

## Source objects from M and embedded SQL

The **Sources** view now contains a searchable page-level source-object inventory
and **Export source objects CSV (with code)**, downloaded as `<report name>-source-objects.csv`.
It follows the shared report-page selector and its own search/status filters.
The existing three-column M-query CSV is still available and still covers the
whole model. All eight browser CSV exports include the report name.

The new inventory includes report, page and stable page ID, model table, partition,
query name, source type, server/connection, database/service, schema, source object,
page usage, extraction status, notes, evidence, original M, extracted SQL and any
referenced M definitions. The JSON payload exposes the same rows as `sourceObjects`.
The existing `tableSources` inventory remains the partition-level connection
summary; `sourceObjects` is the new object-level inventory. Word/agent exports
retain their existing summaries rather than duplicating all original code.

**View source code** expands the original partition M, resolved native SQL,
referenced staging queries/parameters and extraction evidence. CSV cells contain
complete code without truncation, including newlines and escaped quotes. As with
other exports, spreadsheet-formula-like cells receive a protective apostrophe.
Repeated object references are combined within a model-table partition and page;
objects reached through separate partitions retain their distinct code/provenance.
Multiple statements for one object are preserved with a labelled separator.

Supported patterns include:

- SQL Server `Sql.Database`/`Sql.Databases`, Oracle `Oracle.Database`, Teradata
  `Teradata.Database`, and `Odbc.Query`/`Odbc.DataSource`.
- Native SQL in a connector's `Query` option or `Value.NativeQuery`.
- Static `let` steps, quoted step names, literal shared parameters, text
  concatenation, referenced M queries, navigation records and common table
  transformations/joins/appends. Unused `let` steps do not become output sources.
- SQL joins, comma-separated sources, derived subqueries, scoped CTEs (including
  recursive references), quoted names and qualified cross-database objects.
  CTE names/aliases, strings and comments are not listed as physical objects.

The extractor is a conservative standard-library scanner, **not a complete M or
SQL interpreter**. It does not execute queries, inspect live catalogs, resolve
views to their underlying tables, or verify that named objects exist. Unsupported
functions, dynamic SQL, unresolved parameters, ambiguous connections and cyclic
references retain review notes and coverage gaps. No table/view distinction is
required: both are labelled source objects.

| Status | Meaning |
|---|---|
| Resolved | A source identity was extracted statically from supported expressions. This is not live verification. |
| Partial | An object was identified, but connection context, qualification or query coverage remains uncertain. |
| Unresolved | A source expression or coverage gap did not resolve to an object. |
| Not applicable | The partition declares no direct external M/SQL source, such as a calculated model table. Inspect its upstream model-table dependencies. |

Oracle connection aliases are retained rather than guessed into physical hosts;
a literal `host:port/service` keeps the service separately. Teradata's two-part
SQL names are interpreted as database/object. SQL Server four-part names may
contain linked-server aliases and are marked for review. ODBC DSNs need external
configuration; credentials are not copied into connection-identity fields.
A SQL `USE` statement makes a default database unresolved instead of silently
assigning objects to the original connection database. Unqualified object names
retain a default-namespace caveat. Original M/SQL is retained verbatim for review.

This feature is tested using synthetic expressions and generated HTML/CSV checks.
Real-browser verification is still blocked by the previously recorded Chromium
download failure; no live database or real user PBIP validation is claimed.

## Which columns are used, and which can be deleted?

### Report, table and source summary

The **Tables** view begins with a searchable **Report → page → table → source** summary:

| Report | Report page / ID | Model table / partition | Page usage | Server | Database | Source object / query |
|---|---|---|---|---|---|---|
| Supplied report name | Individual page and stable ID | Model table and partition | Direct / via measures / possible relationship dependency | Connection server | Source database | Schema-qualified object or expandable query text |

There is one row per **report + page + model table + partition**, so usage on
different pages and archive/live sources remain separate. Filter by individual
page in Tables. Tables without a partition or any detected page usage remain
visible with a blank/unresolved page, not duplicated onto unrelated pages. **Export source summary
CSV** exports the filtered rows with full query text; the same rows are available
in JSON as `tableSources`. Existing table details remain below the summary.

The extractor reads SQL text from literal `Sql.Database(..., [Query=...])`,
`Value.NativeQuery(...)`, `Odbc.Query(...)`, and legacy query partitions with
named model connections. Dynamic SQL and ambiguous multi-source M expressions
show the full Power Query expression for inspection. Unknown server/database
values remain unknown; queries are never executed. Navigation metadata supplies
the object type where available; otherwise the label is **Table or view**.
The report name identifies the supplied report, while **Page usage** indicates
how that particular page uses the table. Model-only runs show **Usage unknown**.

### Column usage and deletion assessment

The HTML now opens on **Columns** when a model is supplied. It lists **one row
per report, column and page**, with separate Report, Page and Page ID fields. A column
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
runtime behavior. The same page-level table and column inventories appear in
HTML, CSV, JSON, Word and agent markdown. JSON includes `columns.tablePages`,
`columns.measurePages`, `tableSources`, structured manifest `locations`, and
page-specific `report.filterRows`. Lineage, measure consumers and per-page feeds
use these stable IDs rather than parsing display labels. Report-level filters
are attributed to every real page; bookmark references without a resolved page
remain explicitly unassigned. Per-page usage does not change the model-wide
scope of deletion assessments.

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

Inside, in reading order: an orientation header stating the mode and its honesty limits; counts; broken bindings (combined mode) before anything else; tables at a glance with type, storage, source, and report-usage verdict; modelling caveats; relationships with a mermaid ERD; a **filter-reachability table** describing active relationship paths, with explicit limits on inferring measure filter behaviour; per-table columns; every measure's DAX with resolved dependencies and whether the report uses it; RLS roles; report structure; and the source → table → pages lineage.

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
    template.html           the interactive documentation template
    explorer.js             page scope, matrix, impact, layout, cleanup and comparison
    explorer.css            exploration view styles (embedded into the HTML)
examples/
    Sales.SemanticModel/    synthetic model.bim for trying the tool
    Sales.Report/           synthetic PBIR report folder
```

## Verification

Run `python -m unittest discover -s tests -q`. The suite covers dependency and
source extraction, consistent page identities across CSV/JSON/Word/Markdown,
geometry preservation, and generated JavaScript interactions. Node.js is optional
and required only for the JavaScript checks. Those checks use a DOM adapter;
they do not replace browser rendering checks or validation against your own PBIP.

### Adversarial regressions and browser CI

The review fixes now protect measure detail-row dependencies, preserve quoted
DAX identifiers, detect incomplete page inventories, and propagate calculated-table
and parameter dependencies as **possible** page usage. The selector includes
Possible usage; these paths do not imply that every runtime choice was selected.
The context bar exposes analysis-coverage issues. Comparison now includes shared
expressions, calculation groups and detail rows; it rejects unsupported future
extract schemas.

Run `python tests/run_ci.py` for the strict regression gate (80 tests minimum,
no skipped tests). GitHub Actions runs this plus Chromium checks. For the browser
gate locally, install `playwright@1.62.1` with npm, install its Chromium binary,
run `python tests/build_browser_fixture.py`, then run
`node tests/browser_review.cjs /tmp/pbidocgen-browser.html`.
The fixture is synthetic. Chromium verification in the delivery environment was
blocked by download timeouts; see the review register for the exact status.

### Source-object CSV without code

On **Data sources**, choose **Export source objects CSV (no code)** to download
`<report name>-source-objects-no-code.csv`. It includes the same filtered report/page
and source-object rows, but omits Original M code, Extracted SQL, and Referenced M
code. **Export source objects CSV (with code)** retains the full-code export.
The HTML and JSON still contain original code for verification.

CSV fields are double-quoted; embedded quotes are doubled. Commas and tabs remain
inside their fields, and multiline values retain their line breaks. Use a CSV-aware
importer that respects quoted fields. The no-code export avoids multiline code
cells; it does not remove company identifiers from the remaining source metadata.

## Local documentation home and report details

Every normal generation now refreshes **`pbi-home.html`** beside the report HTML.
Double-click it to browse every `.html` / `.htm` file directly in that folder,
including older generated documents. No server or internet connection is required.
Other home-page catalogues are excluded. Subfolders are not scanned in this first version.
Use `--no-hub` to generate only the individual outputs.

To catalogue files you already generated, without reading a Power BI project again:

```powershell
python generate_docs.py --catalog "C:\Documentation"
```

In each newly generated report, open **Report details**. Set the original report URL
or filesystem path, and optionally a catalogue folder such as `Finance / Monthly`.
The home page shows a folder tree using that override, otherwise the parent path of
the original location. Reports without either appear under **Ungrouped**. The report
card always opens the generated documentation; a separate original-location link
opens the recorded URL/path where browser and office policies allow it. A path
ending in a slash is treated as a folder. This hierarchy is organisational metadata;
it does not move files or scan remote Power BI/SharePoint locations.

Connection references begin with detected source type, server/location and database.
You can add a connection name, authentication method, and username/service account.
These are manually maintained references, not credentials retrieved from the Power BI
Service or gateway. There are no password/token fields. Do not put secrets in these
text fields or URLs. Existing source-code exports retain their original behaviour;
this feature does not redact secrets that might already be embedded in M or SQL.

**To save edits:** click **Download updated HTML**, replace the original document in
your output folder with that download, and choose **Refresh from folder** on the home
page. Edits are embedded in the downloaded HTML, not saved in browser storage.
Selecting a folder updates the current home-page view; **Download refreshed home**
saves that updated list. Put it beside the report files as `pbi-home.html`. Browsers
may append a number to downloaded filenames; replace the original instead of keeping
both copies. Until you save, edits exist only in the open page.

The home page initially shows the snapshot taken at generation time. Browsers cannot
silently watch/read neighbouring files: select the folder again after files change,
or rerun `--catalog`. Folder selection reads HTML metadata without running report
scripts; links opened from that scan use temporary local Blob URLs. The downloaded
home page uses relative filenames so the folder can be moved together.

Regenerating to the **same output filename** preserves its embedded details. Saved
connection references remain available even if the detected sources change; review
those references when changing models. To apply or replace metadata explicitly:

```powershell
python generate_docs.py --project "C:\Reports\Sales.pbip" --output "C:\Documentation\Sales.html" --metadata "C:\Documentation\Sales.metadata.json"
```

Example metadata (only these fields are accepted):

```json
{
  "reportLocation": "C:\\Reports\\Finance\\Sales.pbip",
  "folder": "Finance / Monthly",
  "connections": [
    {
      "sourceType": "SQL",
      "server": "sql01",
      "database": "Reporting",
      "connectionName": "Reporting warehouse",
      "username": "CORP\\report_reader",
      "authentication": "Windows"
    }
  ]
}
```

An empty `{}` metadata file clears previously saved details. Invalid embedded metadata
blocks report replacement, avoiding silent loss. An unrelated file already named
`pbi-home.html` is never overwritten by catalogue generation.

### Verification for the local home

`python tests/run_ci.py` includes catalogue discovery, metadata preservation, validation,
HTML escaping, grouping, account search and safe location-link checks. The optional
DOM integration check exercises edited HTML downloads and reopening, folder scanning,
and saving/reopening the home page:

```text
python tests/build_browser_fixture.py
node tests/check_catalog_dom.cjs
```

The DOM check requires `jsdom` to be installed in your Node environment; it is not a
runtime dependency of the generator. A real-browser counterpart is available as
`node tests/browser_catalog.cjs` with Playwright and Chromium installed. On this
implementation run, 87 regression tests and the DOM integration check passed.
Real-browser/visual verification remains pending because the Chromium download
returned invalid archives in the execution environment.
