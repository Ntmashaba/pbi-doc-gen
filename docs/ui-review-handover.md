# UI & reporting review: handover

**Branch:** `ui-review-fixes`, created from `pbi-doc-gen-pbix-batch` (`29730a8`).
**Written:** 23 September 2026, at the end of a review session that could not push, so this file carries the context forward.

## What was done

1. Rendered the generated HTML with a realistic synthetic sample and screenshotted all 20 report views plus the hub in Chromium at 1440×900 and 390×844 (mobile).
2. Compared the rendering against an earlier source-only review (summarised under "Earlier review" below).
3. Added `tests/samples/build_retail_sample.py`, which rebuilds that sample:
   ```
   python tests/samples/build_retail_sample.py sample-output
   python generate_docs.py --catalog sample-output
   ```
   The sample is Retail Sales: 7 tables, 45 columns, 14 measures, 6 relationships, 1 RLS role, and 3 pages (one hidden). Sources are SQL Server `FinanceDW`, the SharePoint workbook `Budget FY26.xlsx` and `\\fileserver\exports\targets.csv`. Unused columns (`LegacyFlag`, `ETLBatchId`, `Email`, `Phone`, `SupplierCode`, `Colour`, `ListPrice`, `FiscalWeek`, `City`) and an unused measure (`Revenue YTD`) are there on purpose. The binding `Date[Calendar]` is also deliberately broken.

No product code has changed yet.

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
