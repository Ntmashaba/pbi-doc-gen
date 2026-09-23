# UI & reporting review: handover

**Branch:** `ui-review-fixes`, created from `pbi-doc-gen-pbix-batch` (`29730a8`).
**Last updated:** 23 September 2026, 19:35 SAST.

> **Current status:** see [`pbix-live-test-handover.md`](pbix-live-test-handover.md) for the successful 8/8 Windows PBIX rerun, subsequent library/navigation/diagram changes, latest test results, and unresolved Browser Use access blocker. This document records the earlier review; its browser verification results do not cover those later changes.

## Status

All findings from the review are done, including the source-parser merge, which was checked against nine public Power BI projects. 123 unit tests, both Chromium tests and the jsdom hub check pass.

| Finding | Status | Commit |
|---|---|---|
| Task 0: Python 3.10/3.11 SyntaxError in `word_writer.py` | Done | `aefadc9` |
| A1: one broken binding blocks every deletion candidate | Done, with a deliberate change to the suggested fix (see Decisions) | `aefadc9` |
| A2: unused measures missing from Cleanup review | Done, and whole unused tables added | `aefadc9` |
| A3: relationship-only "Possible" fills the usage matrix | Done (hidden unless "Include relationship-only" is ticked) | `aefadc9` |
| A4: same source named differently on each screen | Done: shared names (`aefadc9`), then one source per partition from the M tracer (parser merge) | `aefadc9`, step 7 |
| A5: unrelated issues in the Impact inspector | Done (follows from A1) | `aefadc9` |
| B1: opens on the Columns table | Done (opens on Overview) | `b7997e9` |
| B2: 20 navigation items | Done (six sections with sub-tabs) | `b7997e9` |
| B3: one source row per page; two source views | Done (one row per source, side panel, views merged) | `dc9ab0c` |
| B4: blank page-layout boxes | Done (coloured by kind, fields listed, unresolved bindings flagged) | `dc9ab0c` |
| B5: tall scope bar, stray arrow, second page selector | Done | `b7997e9` |
| B6: measure rows | Done (pages, format, DAX preview, display folders) | `dc9ab0c` |
| B7: Report details editing | Done (compact rows, edit row, save bar) | `206cb9f` |
| B8: navigation fills the phone screen | Done (menu button) | `206cb9f` |
| C: contrast, type, monospace | Done | `b7997e9` |
| C: hub and report look like different products | Done (shared tokens and components) | `206cb9f` |
| D: documentation coverage | Done (Overview and hub cards) | `1701224`, `90a5597` |
| D: duplicate measures | Done (text match after normalising) | `1701224`, `90a5597` |
| D: which visuals show a measure | Done (Measures and Page layout) | `dc9ab0c`, `1701224` |
| D: cross-report hub index | Done | `206cb9f` |
| D: label what static extraction can't know | Done (note on Overview; no combined health score) | `1701224` |
| Extra: wide tables scroll sideways on laptops | Done (Columns 9 → 5 columns, source objects 8 → 4) | `1701224` |
| Extra: `browser_review.cjs` had never passed | Fixed (wrong button name) | `b7997e9` |
| Extra: real projects showed most sources as "Unknown" | Fixed by the parser merge (48 of 101 partitions → 0) | step 7 |

### Retail sample, start → now

| Measure | At `29730a8` | Now |
|---|---|---|
| Column deletion candidates | 0 | 13 |
| Columns held in Review | 15 | 2 (`Date[FiscalWeek]`, `Date[Month]`; the broken binding names Date) |
| Measure deletion candidates | not assessed | 2 (`Revenue YTD`, `Net Sales`) |
| Whole unused tables | not assessed | 1 (`Targets`) |
| "Possible" cells in the usage matrix (default) | 10 | 0 |
| SharePoint workbook's name | "Web" / "Web / API" | `SharePoint file · Budget FY26.xlsx` on every screen |
| Rows in the source list | 20 (one per page and source) | 7 (one per source) |
| Navigation items | 20 | 6 sections |
| Mobile top bar | about 180px (after step 2) | about 60px |

### Real projects, before → after the parser merge

`python tests/samples/check_sources.py FOLDER` runs this check on any folder of PBIP projects.

| Measure (101 partitions in 9 projects) | Before | After |
|---|---|---|
| Partitions whose source shows as "Unknown" | 48 | 0 |
| Partitions where Overview and Sources disagree | 77 | 0 |
| Partitions that had a known source and changed it | n/a | 0 (every change was from "Unknown") |

The projects, all public on GitHub: [microsoft/Analysis-Services](https://github.com/microsoft/Analysis-Services) (`pbidevmode/fabricps-pbip/SamplePBIP`, web CSVs through shared queries), [nox-magistralis/tmdl-lens](https://github.com/nox-magistralis/tmdl-lens) (`sample/`, a fixture of about 20 connector patterns), [javendia/powerbi-semantic-model-testing](https://github.com/javendia/powerbi-semantic-model-testing) (SQL through parameters), [abdeling/portfolio-mining](https://github.com/abdeling/portfolio-mining) (34 tables, folder CSVs), [samueltauil/powerbi-git-demo](https://github.com/samueltauil/powerbi-git-demo) (entered data), [PrathameshKasande/Sales_Data_Analysis](https://github.com/PrathameshKasande/Sales_Data_Analysis) (folder combine, generated calendar), [OskarMiszewski/power-bi-semantic-model-toolkit](https://github.com/OskarMiszewski/power-bi-semantic-model-toolkit) (Excel), [JonathanJihwanKim/pbip-documenter](https://github.com/JonathanJihwanKim/pbip-documenter) (SQL) and [datasciencetrialgit/SalesDashboard](https://github.com/datasciencetrialgit/SalesDashboard) (CSV). They are not vendored into this repo; `tests/test_partition_sources.py` reproduces their patterns.

### Open

- **Honest limits of static tracing** (labelled, not hidden): custom M functions that wrap a connector, URLs built by string concatenation at refresh time, and "combine all files in a folder" (the folder is named, the individual files are not).
- **Possible follow-ups (not in the review):** the CLI `--csv` export covers columns only (measure assessments export from the browser); duplicate detection compares text, not meaning; `model_parser`'s regex patterns remain only as a fallback and could be removed once more real projects have been checked.

### Decisions made along the way

- **A1:** the review suggested showing candidates held back by a global issue as "deletion candidate with a caveat". Instead, issues that can hide real usage (no report supplied, missing or unparsed pages, report warnings, unresolved references to unknown tables) still hold every candidate in Review. Only an unresolved `T[F]` with a known table `T` is scoped to `T`. Reversing this is a small change in `column_usage.py`.
- **B3:** Primary sources was merged into Sources rather than deleted. Its page-level table, the source objects with code and the M query export are collapsed sections, so every CSV export keeps its name and columns, and `switchTab('primary-sources')` still works.
- **B2:** view ids did not change; sections only group them. Internal links and saved state keep working.
- **Hub index:** the hub reads a small, whitelisted `summary` block from each report rather than its full data, so it keeps working as the views change. Reports generated before this change still list, without sources, until regenerated.
- **Parser merge:** the tracer's result replaces the regex result only when it knows more; the regex result stays when the tracer finds nothing or only an unrecognised connector. Partitions of type query, entity (Direct Lake) and calculated are unchanged.
- **Commits** are authored as `Ntmashaba` with a `Co-Authored-By: Claude` line; they were not rewritten to a Claude identity.

## How to check it

```
python tests/run_ci.py                                   # 123 tests, must all pass
python tests/samples/check_sources.py PATH_TO_PBIP_PROJECTS  # 0 Unknown / 0 disagreements expected
python tests/samples/build_retail_sample.py sample-output
python generate_docs.py --catalog sample-output          # open sample-output/pbi-home.html
python tests/build_browser_fixture.py
node tests/browser_review.cjs /tmp/pbidocgen-browser.html   # needs Playwright + Chromium
node tests/browser_catalog.cjs                              # needs Playwright + Chromium
node tests/check_catalog_dom.cjs                            # needs jsdom
```

`tests/test_retail_sample.py` holds the regression tests for the counts above.

## Environment notes

- **Line endings:** the Windows clone uses CRLF. From a Linux shell, run git as `git -c core.autocrlf=true …`, otherwise every file shows as modified. Keep edited files CRLF.
- **Python:** 3.10 or later (the code uses `str | None` annotations). Task 0 removed the only construct that needed 3.12.
- **Browser tests** are not part of `run_ci.py`. They need Playwright with Chromium; `check_catalog_dom.cjs` needs jsdom.

## Progress log

One entry per commit, oldest first. Sample counts in each entry are as of that commit.

### Step 1 (Task 0, A1–A5), `aefadc9`

| Item | What changed | Sample, before → after |
|---|---|---|
| Task 0 | `word_writer.py` no longer puts a backslash inside an f-string expression. README states Python 3.10 or later (the code uses `str \| None` annotations). | `test_page_references` imports again |
| A1 | `column_usage.py` scopes an unresolved `T[F]` to table `T` when `T` exists (`tableIssues`). Bare or unknown-table references, missing pages, report warnings and "no report" stay global (`globalIssues`) and **still hold every candidate in Review**. That is a deliberate choice against the "candidate with caveat" suggestion, because those issues can hide real usage. `issues` is still the union, for the coverage box. `primary_sources.py` gets the same scoping. | Deletion candidates 0 → 13, Review 15 → 2 (`Date[FiscalWeek]`, `Date[Month]`, because the broken binding names Date). The Targets CSV changes from "Usage unresolved" to "No reporting usage found". |
| A5 | Follows from A1: the Impact inspector reads the scoped `reviewNotes`. | `Budget[Amount]` has no review notes |
| A2 | `columns.measures` has one assessment per measure (Keep / Review / Deletion candidate), including dependants, model roots (RLS, calculated columns, calculation items, detail rows) and pages. A measure used only by other unused measures stays a candidate, and the note names those measures. `columns.tables` lists whole tables where every column and measure is a candidate and no relationship touches them. Cleanup review shows both and exports `cleanup-measures.csv`. The CLI `--csv` is still columns only. | `Revenue YTD` is a candidate. The whole `Targets` table is flagged. |
| A3 | The usage matrix hides relationship-only links unless "Include relationship-only" is ticked. | "Possible" cells 10 → 0 by default |
| A4 | New `pbidocgen/source_labels.py` holds one vocabulary and one "type · name" label, used by both `model_parser` and `external_sources`. `Web.Contents` on a SharePoint document becomes "SharePoint file". `File.Contents` becomes "CSV file" / "Excel workbook" by extension. Partitions carry `source.label`, and lineage carries `sourceLabel`. Overview shows labels as pills. Lineage source nodes are wider, shortened in the middle, and have a tooltip. `report_metadata.js` matches saved connection details by type family, so saved usernames survive the rename. | Every screen says `SQL Server · finance-sql.corp.local / FinanceDW`, `SharePoint file · Budget FY26.xlsx`, `CSV file · targets.csv` |

The two parsers are still separate; only their vocabulary is shared (see "Open").

### Step 2 (B1, B2, B5, C), `b7997e9`

- **B1:** the report opens on Overview.
- **B2:** the rail has six sections (`SECTIONS` in `template.html`). Every existing view keeps its id and becomes a sub-tab (`id="nav-<view>"`); section buttons are `id="sec-<section>"`. A section remembers the last sub-tab used. `switchTab(id)` still works for every view, so internal links are unchanged. Views not listed in `SECTIONS` fall into "Data & sources".
- **B5:** the scope bar is one sticky row: page selector, a one-line scope note and a coverage badge that opens a popover (no stray arrow). The report name is gone (it is in the rail). The second page selectors on Columns and Tables are removed; page IDs appear in the selector only when two pages share a name. No scope bar on Report details.
- **C:** `--ink2 #4F5B67`, `--ink3 #5E6B78`, `--amber #8A5D00`, `--poss/--warn #A04A07`; all at least 4.5:1 on every panel and badge background. Table headers are 12px sentence case; body `<th>` row headers are no longer styled as tiny column headers. Monospace is kept only for `.ref`, code and dependency paths; badges, nav, eyebrow and coupler labels use the sans font.
- **Browser tests:** `tests/browser_review.cjs` looked for a "Close" button whose accessible name is "Close details", so it had never passed. Fixed, and both `browser_review.cjs` and `browser_catalog.cjs` now pass in Chromium and navigate through sections.

At this point the hub styling (C) and the mobile menu (B8) were still to do; both were done in step 4.

### Step 3 (B3, B4, B6), `dc9ab0c`

- **B3:** Sources and Primary sources are one view. It opens with one row per external source (grouped from `primarySources` rows by type, server, database, schema, object and location) with pages as tags, reporting usage and identification status. Selecting a source opens the inspector with connection details, pages, model tables, queries, evidence and the M/SQL code. The page-level Primary sources table, source objects (with code) and the M query export remain as collapsed sections, so every CSV export is unchanged. `switchTab('primary-sources')` still works: it opens Sources with that section expanded.
- **B4:** Page layout is the first tab of Pages & visuals. Boxes are coloured by visual kind (card, slicer, table, chart, text/image), list the measures (Σ) and columns each visual uses, and show a "!" for bindings the analyser could not resolve (same messages as Cleanup review, so `Date[Calendar]` is flagged on "Revenue vs LY"). The inspector explains the unresolved binding.
- **B6:** Measure rows show "used on N pages", the format string and a one-line DAX preview while collapsed, and are grouped by display folder (unfiled last). Search covers names, folders and DAX. The retail sample now has display folders on six measures.
- **Browser test:** the export loop expands a collapsed section before clicking its button.

### Step 4 (B7, B8, D hub index, C hub), `206cb9f`

- **B7:** Report details has the location and folder side by side, then one table row per connection: source name (file name for file sources), username and authentication inline, and an Edit button that opens a full-width row for name, type, server, database and Remove. A sticky save bar counts unsaved changes against what the file holds and highlights when there are any. Input ids (`doc-location`, `doc-folder`, `doc-<i>-<field>`) and button labels are unchanged, so saved files and the save/reopen flow still work.
- **B8:** below 860px the rail collapses to the report title and a menu button naming the current section; picking a section closes it. The top bar is about 60px instead of about 180px, with no horizontal scroll at 390px.
- **D, hub index:** `renderer.build_summary` adds a `summary` block to every payload (counts, source identities with their model tables, coverage issue count, cleanup candidate and review counts; no code). `catalog.describe_html` and the hub's folder scan both read it through a whitelist (`clean_summary` / `cleanSummary`). The hub has a "Sources across reports" table, source tags on each card that filter the list, mode, coverage and cleanup badges, and search over server, database, file and table names. Older documents are listed with a note to regenerate them.
- **C (hub):** `catalog.html` now uses the report's tokens, buttons, badges and type, including an accessible folder picker button instead of a native file input.
- **Tests:** a summary/whitelist test in `test_catalog.py` (114 total). `browser_catalog.cjs` checks the save bar, the edit row and the hub source index; `browser_review.cjs` checks the mobile menu at 390px. `check_catalog_dom.cjs` (jsdom) passes.

### Step 5 (remaining D items, wide tables), `1701224`

- **Documentation coverage:** new `pbidocgen/quality.py` adds `payload.quality.documentation` (visible objects only): measures, columns and tables described, measures with a format string (string or expression) and in display folders. Overview shows these as "n of total" tiles, with the measures lacking a format string in an expandable list.
- **Duplicate measures:** `quality.duplicateMeasures` groups measures whose DAX matches after removing whitespace, comments, letter case outside string literals and quotes around simple table names. It does not evaluate DAX, so equivalent measures written differently are not found. Overview links to a Duplicate measures table in Cleanup review (measures, match type, each measure's format string, DAX).
- **Which visuals show a measure:** each expanded measure lists the visuals that show it, directly or "via" the measure the visual binds, using the dependency graph; each links to the visual's bindings.
- **Wide tables:** Columns has 5 columns instead of 9 (report name is in the scope bar; "used in report" and page measures moved into the assessment and usage cells) and source objects 4 instead of 8. Neither scrolls horizontally at 1280px. CSV exports are unchanged.
- **Sample:** adds `Net Sales`, a reformatted copy of Revenue (unused), and descriptions/format strings on two measures. Measure count 15, measure deletion candidates 2.

### Step 6 (hub quality counts), `90a5597`

- The report `summary` also carries `measuresDescribed` and `duplicateMeasureSets`; the hub whitelists both and shows "n of N measures described" and a duplicate-set badge on each card.

### Step 7 (source-parser merge, checked on real projects)

- **Finding:** on nine public PBIP projects, `model_parser` showed 48 of 101 partitions as "Unknown" on Overview, Lineage and Tables, mostly because its regex patterns only read a partition's own M and so missed shared queries and parameters. Overview and Sources disagreed on 77.
- **Merge:** new `pbidocgen/partition_sources.py` runs at the end of `parse_model` and gives every M partition the tracer's best source (resolved, then partial), with `traceStatus`, `tracedFrom` and any `otherSources`. The regex result is kept when the tracer finds nothing, or only an unrecognised connector.
- **Tracer additions (`m_sources.py`):** Power BI and Power Platform dataflows (workspace, dataflow, entity); "Entered data" for `#table`, `Table.FromRows`/`FromRecords`/`FromColumns`; "Generated in Power Query" for date and number lists (a calendar built from another query's dates keeps that query as its source); Snowflake, Databricks and Azure SQL under the regex parser's names; any other `Namespace.Function("…")` outside the standard library as "(unrecognised connector)", still counted as unresolved coverage. `#name(...)` calls are now parsed.
- **Labels (`source_labels.py`):** a file picked from a folder or a SharePoint library is named as that file (`CSV file · DimArea.csv`, `SharePoint file · …`); dataflows are named by entity. Calculated tables are "Calculated (DAX)" on every screen.
- **Tests:** `tests/test_partition_sources.py` (6 tests on these patterns, including "nothing left Unknown" and "Overview and Sources agree"); two existing expectations updated for the new names. `tests/samples/check_sources.py` is the real-project check.

## Original findings

The review as written at the start, kept for reference. Line numbers refer to `29730a8` and have since moved. Every item is resolved except where the status summary above says otherwise.

### A. Screens that give wrong or empty answers (fix first)

| # | Problem | Where | Suggested fix |
|---|---|---|---|
| A1 | One unresolved binding anywhere turns **every** otherwise-unused column into `Review`. The sample's Cleanup review shows 0 deletion candidates, and all 15 unused columns give the reason "Unresolved report binding Date[Calendar]". | `pbidocgen/column_usage.py:305`: `review = sorted(uncertain[key] \| issues)` merges global `issues` into every column. Issues are raised at lines 63, 213, 295–299. | Scope each issue to the table it names (`issues_by_table`), and keep only genuinely global issues (no report, no pages parsed, unreadable definitions) global. Show a candidate held back by a global issue as a deletion candidate with a caveat, not as `Review`. Add a regression test using the sample. |
| A2 | Unused **measures** never reach Cleanup review. `Revenue YTD` is flagged "Not used in report" on the Measures view only. | Cleanup review (`explorer.js`, `cleanup` tab), `column_usage.py` | Add measures, with dependants (other measures, format expressions, calculation items), to the assessment and CSV. |
| A3 | Relationships alone produce "Possible", which fills the usage matrix: most tables show Possible on most pages. | Usage matrix (`explorer.js`, `matrix` tab); verdicts in `linker.py` / `column_usage.py` | Hide relationship-only links by default (or show them faintly), and add a toggle labelled "Include relationship-only". |
| A4 | The SharePoint workbook is called **"Web"** on Overview and Lineage and **"Web / API"** on Sources. Lineage shows "Web" and "CSV file" without names. | `external_sources.py:18` maps `Web.Contents` → `Web / API`; Overview and Lineage labels in `template.html` | When `Web.Contents` points at `*.sharepoint.com` and is wrapped by `Excel.Workbook`/`Csv.Document`, classify it as "SharePoint file". Label every source as type · file/server name, and use the same label on every screen. |
| A5 | The Impact inspector lists global issues (e.g. `Date[Calendar]`) under unrelated fields such as `Budget[Amount]`. | Impact inspector (`explorer.js`, `impact` tab) | Same scoping as A1. |

### B. Navigation and layout

- **B1:** The report opens on the 9-column Columns table (`template.html:704`, `switchTab(has.model ? "columns" : "overview")`). Open on Overview instead.
- **B2:** Cut the 20 navigation items (`TABS` in `template.html:~168` plus the `TABS.splice/push` calls in `explorer.js:300–394`) to six sections: **Overview · Data & sources · Pages & visuals · Impact & changes · Review issues · Report details**. Put existing views inside them as sub-tabs.
- **B3:** Sources and Primary sources show one row per page, so the same workbook appears 3 times and about 4 rows fit on a 1440px screen. Show one row per source, with pages as tags, and open code and evidence in a side panel. Merge the two views.
- **B4:** Page layout (`layout` tab) draws blank cream boxes. Colour them by visual type and usage, list measures and columns inside each box, and open bindings on click. This could become the centre of "Pages & visuals".
- **B5:** The scope bar takes about 110px on every view, repeats the report name, and its "Analysis coverage" box shows a stray ▸ arrow on an empty line. Replace it with a slim sticky bar holding the page selector and a coverage badge. Remove the Columns view's second page selector.
- **B6:** Measures list: show a DAX preview, format and "used on N pages" in the collapsed row, and group by display folder.
- **B7:** Report details: six full-width stacked fields per connection, native unstyled buttons, and a "Download updated HTML" link as the only save. Use compact rows, an edit panel, and a sticky save bar showing unsaved changes.
- **B8:** Mobile (390px): the navigation fills the whole first screen. Collapse it into a menu button or dropdown.

### C. Visual system

- **Contrast:** `--ink3 #8B98A5` on white is about 2.9:1 and links `--amber #B77E00` about 3.5:1, both below WCAG AA (4.5:1). `table.t th` is about 9px uppercase monospace. Darken both tokens and use 12px sentence-case headers.
- **Monospace:** reserve it for identifiers and code, not for labels and navigation groups.
- **Hub vs report:** `catalog.html` (navy/gold, native "Choose Files" inside a dark label) and `template.html` (neutral colours, Power BI yellow) look like different products. Share tokens, buttons and status components between them.

### D. Questions the output doesn't answer yet

- **Documentation coverage:** descriptions, display folders and format strings are parsed (`model_parser.py:228–251, 312`) but descriptions only show inside expanded items, and column descriptions not at all. Add "6 of 14 measures described, 3 without a format string" to Overview.
- **Duplicate measures:** find identical or near-identical DAX saved under different names.
- **Which visuals show a measure:** this exists only in the Impact inspector. Surface it on Page layout and Measures.
- **Hub:** `catalog.py:73–92` already parses each report's full data but only takes title, generated date and pbixSource. Build a cross-report index for source/server/file search ("which reports use FinanceDW / Budget FY26.xlsx"), generation status, coverage, and failed batch runs.
- **Things static extraction can't know** (refresh health, performance, real usage): label them as unavailable, and don't combine everything into one health score.

## Earlier review (summary)

The earlier review reached the same conclusions without rendering: too many destinations (20), opening on cleanup, overlapping source/lineage views, two page selectors, very wide tables (1000px minimum), mismatched hub and report styling, and cumbersome connection editing. It proposed the six-section structure above, consistent detail panels (source → connection → queries → model tables → pages), a cross-report hub index, and a review workflow that explains what was detected, why it matters, how certain it is and what to check next.
