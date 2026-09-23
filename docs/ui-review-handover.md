# UI & reporting review: handover

**Branch:** `ui-review-fixes`, created from `pbi-doc-gen-pbix-batch` (`29730a8`).
**Written:** 23 September 2026, at the end of a review session. This file carries the context forward.

## What was done

1. Rendered the generated HTML with a realistic synthetic sample and screenshotted all 20 report views plus the hub in Chromium at 1440×900 and 390×844 (mobile).
2. Compared the rendering against an earlier source-only review (summarised under "Earlier review" below).
3. Added `tests/samples/build_retail_sample.py`, which rebuilds that sample:
   ```
   python tests/samples/build_retail_sample.py sample-output
   python generate_docs.py --catalog sample-output
   ```
   The sample is Retail Sales: 7 tables, 45 columns, 14 measures, 6 relationships, 1 RLS role, and 3 pages (one hidden). Sources are SQL Server `FinanceDW`, the SharePoint workbook `Budget FY26.xlsx` and `\\fileserver\exports\targets.csv`. Unused columns (`LegacyFlag`, `ETLBatchId`, `Email`, `Phone`, `SupplierCode`, `Colour`, `ListPrice`, `FiscalWeek`, `City`) and an unused measure (`Revenue YTD`) are there on purpose. The binding `Date[Calendar]` is also deliberately broken.

No product code had changed at that point. See "Progress" below.

## Progress (23 September 2026, second session)

Plan step 1 is done: task 0 and A1–A5. 113 tests pass (`python tests/run_ci.py`). The new regression tests are in `tests/test_retail_sample.py`.

| Item | What changed | Sample, before → after |
|---|---|---|
| Task 0 | `word_writer.py` no longer puts a backslash inside an f-string expression. README states Python 3.10 or later (the code uses `str \| None` annotations). | `test_page_references` imports again |
| A1 | `column_usage.py` scopes an unresolved `T[F]` to table `T` when `T` exists (`tableIssues`). Bare or unknown-table references, missing pages, report warnings and "no report" stay global (`globalIssues`) and **still hold every candidate in Review**. That is a deliberate choice against the "candidate with caveat" suggestion, because those issues can hide real usage. `issues` is still the union, for the coverage box. `primary_sources.py` gets the same scoping. | Deletion candidates 0 → 13, Review 15 → 2 (`Date[FiscalWeek]`, `Date[Month]`, because the broken binding names Date). The Targets CSV changes from "Usage unresolved" to "No reporting usage found". |
| A5 | Follows from A1: the Impact inspector reads the scoped `reviewNotes`. | `Budget[Amount]` has no review notes |
| A2 | `columns.measures` has one assessment per measure (Keep / Review / Deletion candidate), including dependants, model roots (RLS, calculated columns, calculation items, detail rows) and pages. A measure used only by other unused measures stays a candidate, and the note names those measures. `columns.tables` lists whole tables where every column and measure is a candidate and no relationship touches them. Cleanup review shows both and exports `cleanup-measures.csv`. The CLI `--csv` is still columns only. | `Revenue YTD` is a candidate. The whole `Targets` table is flagged. |
| A3 | The usage matrix hides relationship-only links unless "Include relationship-only" is ticked. | "Possible" cells 10 → 0 by default |
| A4 | New `pbidocgen/source_labels.py` holds one vocabulary and one "type · name" label, used by both `model_parser` and `external_sources`. `Web.Contents` on a SharePoint document becomes "SharePoint file". `File.Contents` becomes "CSV file" / "Excel workbook" by extension. Partitions carry `source.label`, and lineage carries `sourceLabel`. Overview shows labels as pills. Lineage source nodes are wider, shortened in the middle, and have a tooltip. `report_metadata.js` matches saved connection details by type family, so saved usernames survive the rename. | Every screen says `SQL Server · finance-sql.corp.local / FinanceDW`, `SharePoint file · Budget FY26.xlsx`, `CSV file · targets.csv` |

The two parsers are still separate. Only their vocabulary is shared. Merging them fully is still open.

### Step 2 (B1, B2, B5, C)

- **B1:** the report opens on Overview.
- **B2:** the rail has six sections (`SECTIONS` in `template.html`). Every existing view keeps its id and becomes a sub-tab (`id="nav-<view>"`); section buttons are `id="sec-<section>"`. A section remembers the last sub-tab used. `switchTab(id)` still works for every view, so internal links are unchanged. Views not listed in `SECTIONS` fall into "Data & sources".
- **B5:** the scope bar is one sticky row: page selector, a one-line scope note and a coverage badge that opens a popover (no stray arrow). The report name is gone (it is in the rail). The second page selectors on Columns and Tables are removed; page IDs appear in the selector only when two pages share a name. No scope bar on Report details.
- **C:** `--ink2 #4F5B67`, `--ink3 #5E6B78`, `--amber #8A5D00`, `--poss/--warn #A04A07`; all at least 4.5:1 on every panel and badge background. Table headers are 12px sentence case; body `<th>` row headers are no longer styled as tiny column headers. Monospace is kept only for `.ref`, code and dependency paths; badges, nav, eyebrow and coupler labels use the sans font.
- **Browser tests:** `tests/browser_review.cjs` looked for a "Close" button whose accessible name is "Close details", so it had never passed. Fixed, and both `browser_review.cjs` and `browser_catalog.cjs` now pass in Chromium and navigate through sections.

Not done from C: sharing tokens and components with the hub (`catalog.html`). Mobile (B8) is improved by having six buttons instead of 20 but still takes about 180px; a menu button remains for step 4.

### Step 3 (B3, B4, B6)

- **B3:** Sources and Primary sources are one view. It opens with one row per external source (grouped from `primarySources` rows by type, server, database, schema, object and location) with pages as tags, reporting usage and identification status. Selecting a source opens the inspector with connection details, pages, model tables, queries, evidence and the M/SQL code. The page-level Primary sources table, source objects (with code) and the M query export remain as collapsed sections, so every CSV export is unchanged. `switchTab('primary-sources')` still works: it opens Sources with that section expanded.
- **B4:** Page layout is the first tab of Pages & visuals. Boxes are coloured by visual kind (card, slicer, table, chart, text/image), list the measures (Σ) and columns each visual uses, and show a "!" for bindings the analyser could not resolve (same messages as Cleanup review, so `Date[Calendar]` is flagged on "Revenue vs LY"). The inspector explains the unresolved binding.
- **B6:** Measure rows show "used on N pages", the format string and a one-line DAX preview while collapsed, and are grouped by display folder (unfiled last). Search covers names, folders and DAX. The retail sample now has display folders on six measures.
- **Browser test:** the export loop expands a collapsed section before clicking its button.

### Step 4 (B7, B8, D hub index)

- **B7:** Report details has the location and folder side by side, then one table row per connection: source name (file name for file sources), username and authentication inline, and an Edit button that opens a full-width row for name, type, server, database and Remove. A sticky save bar counts unsaved changes against what the file holds and highlights when there are any. Input ids (`doc-location`, `doc-folder`, `doc-<i>-<field>`) and button labels are unchanged, so saved files and the save/reopen flow still work.
- **B8:** below 860px the rail collapses to the report title and a menu button naming the current section; picking a section closes it. The top bar is about 60px instead of about 180px, with no horizontal scroll at 390px.
- **D, hub index:** `renderer.build_summary` adds a `summary` block to every payload (counts, source identities with their model tables, coverage issue count, cleanup candidate and review counts; no code). `catalog.describe_html` and the hub's folder scan both read it through a whitelist (`clean_summary` / `cleanSummary`). The hub has a "Sources across reports" table, source tags on each card that filter the list, mode, coverage and cleanup badges, and search over server, database, file and table names. Older documents are listed with a note to regenerate them.
- **C (hub):** `catalog.html` now uses the report's tokens, buttons, badges and type, including an accessible folder picker button instead of a native file input.
- **Tests:** a summary/whitelist test in `test_catalog.py` (114 total). `browser_catalog.cjs` checks the save bar, the edit row and the hub source index; `browser_review.cjs` checks the mobile menu at 390px. `check_catalog_dom.cjs` (jsdom) passes.

### Still open from the review

- D: documentation coverage on Overview (descriptions, format strings), duplicate-measure detection, and "which visuals show this measure" on Measures (the Page layout and Impact inspector show it).
- The two source parsers (`model_parser` patterns and the M tracer) still exist side by side; only their vocabulary is shared.
- Wide tables (Columns, source objects) still scroll horizontally on laptops.

## Environment notes

- **Line endings:** the Windows clone uses CRLF. From a Linux shell, run git as `git -c core.autocrlf=true …`, otherwise every file shows as modified.
- **Python version:** `pbidocgen/word_writer.py:479` puts a backslash inside an f-string expression (`' › '`). That is a SyntaxError before Python 3.12, and it fails the `test_page_references` import on 3.10. Hoist the separator into a variable. **This is task 0.**
- **Tests:** `python tests/run_ci.py`. It requires at least 80 tests and passes 94 of 95 on Python 3.10 (the one failure is the item above).

## Findings, in priority order

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

## Suggested plan

1. Task 0 (Python 3.12 f-string) plus A1–A5, each with tests. Use the sample to show the before/after counts: Cleanup should list the obviously unused columns, plus `Revenue YTD` once measures are included.
2. B1, B2, B5 (open on Overview, six sections, slim scope bar) and C (contrast and type).
3. B3, B4, B6 (source list, visual page layout, measure rows).
4. B7, B8 and the hub index (D).

## Earlier review (summary)

The earlier review reached the same conclusions without rendering: too many destinations (20), opening on cleanup, overlapping source/lineage views, two page selectors, very wide tables (1000px minimum), mismatched hub and report styling, and cumbersome connection editing. It proposed the six-section structure above, consistent detail panels (source → connection → queries → model tables → pages), a cross-report hub index, and a review workflow that explains what was detected, why it matters, how certain it is and what to check next.
