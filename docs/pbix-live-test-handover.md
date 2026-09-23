# Live test on real PBIX and PBIP files: handover

**Branch:** `ui-review-fixes`. **Written:** 23 September 2026, 20:00 SAST.
**Updated:** 23 September 2026, after the successful Windows rerun and subsequent usability changes.
**Follows:** [`ui-review-handover.md`](ui-review-handover.md), which covers the UI review; everything in it is done.

## Summary

The generator was run for the first time on real Power BI files: 8 PBIX files from Microsoft's official samples through the full PBIX batch path (pbi-tools, on Windows), and 9 public PBIP projects from GitHub. Four of the eight PBIX files failed, and the ones that worked showed false warnings and no cleanup suggestions. Every failure was in this project's code; pbi-tools extracted all eight files successfully.

The biggest finding affects PBIP projects too: **the report validator rejected `report.json` files saved by any recent Power BI Desktop**, so the report was silently dropped and the whole cleanup review blocked. It hit 4 of the 9 real PBIP projects. Nothing in the existing tests used a recent Desktop file, so it had never shown up.

The original live-test commit (`ed82237`) fixes the 16 problems listed below. Its handover reported 134 unit tests, both Chromium tests and the jsdom check passing. **The Windows PBIX rerun is now complete: 8 generated, 0 failed, all in combined mode.** Later UI changes and their distinct validation limits are recorded below; the earlier browser results do not validate the latest UI.

## Current handover: usability and diagram work

### Confirmed Windows rerun

The user reran the batch successfully. `pbix-samples/documentation/pbix-batch-results.json` records **8 generated, 0 failed**, all in combined mode, at **23 September 2026, 20:21 SAST** (`18:21 UTC`). Regional Sales and Revenue Opportunities no longer fail on model-name validation. The precise original offending field for F4 remains unconfirmed. Generation success is not a full semantic audit of every warning or cleanup candidate.

```powershell
python generate_docs.py --pbix-folder pbix-samples --output-dir pbix-samples\documentation --pbi-tools pbi-tools\pbi-tools.exe
```

### User feedback and implemented changes

The user wants a connected, modern application experience. They objected to reports being below an expanded source table, links opening new tabs, small/faint diagram shapes, and the details panel obscuring Page layout. They like the Page layout schematic and want to retain it.

- **Library:** reports/search are the initial view. Sources and Manage library have separate sidebar destinations. Report links stay in the same tab. File and connection metadata is tucked into expandable card details. The library and reports share a dark sidebar and consistent card styling.
- **Navigation:** reports include a library return link and breadcrumbs. Report sections have hash routes with Back/Forward handling. These remain self-contained offline HTML documents; this is not a server-backed application.
- **Relationships:** larger cards and labels, zoom/reset controls, scrolling, cardinality labels, table focus, and a relationship list filtered to the selected table. Bidirectional lines now receive the intended amber stroke. Same-column and self relationships have curved routes.
- **Lineage:** larger source/table/page cards, zoom/reset, source and page fills with stronger outlines, deduplicated edges, and path selection. Shapes remain fully opaque during selection; only unrelated lines are dimmed. Table details use an explicit link instead of a second click on the same node.
- **Lineage explanation:** Adventure Works DW 2020's only page, Introduction, contains an image and a textbox with no field bindings. Its missing table-to-page connections are expected. No-reference outlines are neutral rather than red; disconnected pages get explanatory text and a reminder that missing references do not establish safe deletion.
- **Page layout:** stronger borders, larger labels, per-page zoom and Fit width, scrollable canvases, and selected-shape indication. Hidden visuals retain full opacity and dashed outlines. At viewport widths of at least 1200px, the 400px details panel has space reserved beside the document; on smaller screens it remains an overlay.
- **Compare extracts:** hidden from normal navigation at the user's request. The section is now **Impact & usage**. Comparison code and the advanced `#compare` route remain. The single-report CLI supports `--json`, but the normal PBIX batch does not produce per-report JSON extracts; `pbix-batch-results.json` is only the batch status, not a comparison baseline. Do not reintroduce the tab without a usable version-history workflow.

**The generator was updated, not just generated files.** Relevant files are `pbidocgen/catalog.html`, `pbidocgen/template.html`, `pbidocgen/explorer.js`, and `pbidocgen/explorer.css`. Navigation documentation is in `README.md`. All eight local sample HTML reports were refreshed with `renderer.render_html` using their existing embedded payloads and saved metadata, followed by `build_catalog`. Their analysis was preserved; these UI refreshes did not repeat PBIX extraction. Future normal generation uses the updated templates.

### Verification and its limits

- Latest full run: `python -X utf8 -m unittest discover -s tests -q`: **134 discovered, 133 passed, 1 skipped**. The skipped case uses a POSIX synthetic pbi-tools executable and is intentionally skipped on Windows.
- After hiding Compare extracts, the targeted `test_explorer.py` suite passed (4 tests, with generated JavaScript checks across extraction modes). `tests/browser_review.cjs` was adjusted to exercise comparison through its advanced route and to expect the renamed section, but was not run in a browser in this session.
- `tests/check_diagrams.cjs` checks the generated diagrams with a DOM adapter. Across the eight real report HTML files, **936 diagram states** passed: shape counts and bounds, finite coordinates, readable nominal node dimensions, opaque selectable nodes, edge-before-node ordering, focus states, and zoom extremes. Page-layout inventory/bounds and zoom controls were checked too. The check is also called from `tests/test_explorer.py` for synthetic extraction modes.
- Actual report state counts: Adventure Works DW 2020 34; AdventureWorks Sales 46; Corporate Spend 73; Performance Analyzer 83; Regional Sales 185; Revenue Opportunities 68; Sales & Returns 379; Supply Chain 68.
- These are structural/JavaScript checks, **not rendered browser or screenshot verification**. They cannot prove text fit, perceived contrast, browser layout, hit targets, or inspector reflow. Latest Chromium/jsdom integration runs remain pending. Do not describe the UI as visually verified.
- Use `-X utf8` on Windows: some existing tests read UTF-8 files without specifying an encoding and otherwise fail under cp1252. `tests/run_ci.py` rejects any skipped test, so its strict gate exits nonzero on this Windows environment despite the passing applicable tests.
- `git diff --check` passed. At handover, HEAD was `8f3a31c` (`ui fixes`), with additional staged and unstaged changes. Preserve the user's staging choices; no commit or staging was performed for this handover update.

Example local diagram check (after generating reports):

```powershell
Get-ChildItem pbix-samples/documentation -Filter '*.html' |
  Where-Object { $_.Name -ne 'pbi-home.html' } |
  ForEach-Object {
    node tests/check_diagrams.cjs $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Diagram audit failed: $($_.Name)" }
  }
```

### Browser-access blocker

Repeated direct attempts to open `file:///D:/GIT/pbi-doc-gen/pbix-samples/documentation/pbi-home.html` through the Codex in-app Browser Use tool were rejected with **“The browser URL policy blocks this action.”** Expanding filesystem access did not resolve it. No successful automated visual walkthrough occurred.

The user supplied settings screenshots: Browser control is enabled; default Agent permissions require approval; the Add site permission dialog requests a website address. Official documentation describes origin rules for HTTP/HTTPS, not a supported `file://` exception. No browser restriction was present in the inspected user `config.toml`. The exact policy source remains unknown. Do not claim that a specific toggle fixes this, enable full CDP access, or route around the explicit tool denial. The user was advised to report the rejection through `/feedback`; submission was not confirmed.

References: [Browser](https://learn.chatgpt.com/docs/browser), [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). User screenshots supported the UI review while browser access was unavailable. Some screenshots still showed the older Lineage text/layout; ask the user to reload the generated file before diagnosing a stale view as a new code failure.

## What was tested

| Set | Files | How |
|---|---|---|
| PBIX | 8 files from [microsoft/powerbi-desktop-samples](https://github.com/microsoft/powerbi-desktop-samples) (MIT): AdventureWorks Sales, Corporate Spend, Regional Sales Sample, Revenue Opportunities (2026 samples), Sales & Returns, Supply Chain, Adventure Works DW 2020, Performance Analyzer export | `generate_docs.py --pbix-folder pbix-samples ...` with pbi-tools 1.2 and Power BI Desktop 2.157, on the developer's machine |
| PBIP | 9 public GitHub projects (listed in `ui-review-handover.md`) | `generate_docs.py --project` and `tests/samples/check_sources.py` |

The PBIX files live in `pbix-samples/` on the developer's machine only (git-ignored); they are not in the repo.

## PBIX results

| File | First run | Cause | Status after Windows rerun |
|---|---|---|---|
| Adventure Works DW 2020 | Generated | (none; image and text-box report only) | No change needed |
| Performance Analyzer export | Generated, 10 false DAX issues, no cleanup | F9 (row-context DAX) | Generated successfully; detailed warning/content verification still pending |
| Sales & Returns | Generated, 801 "bookmarks", 6 false broken bindings | F7, F8, F10 | Generated successfully; detailed warning/content verification still pending |
| Supply Chain | Generated | 1 real stale reference (see "Real findings") | No change needed |
| AdventureWorks Sales (2026) | **Failed**: "Missing or invalid report object: report.json" | F3: report is PBIR inside the PBIX, which pbi-tools 1.2 does not extract | Generated successfully; detailed warning/content verification still pending |
| Corporate Spend (2026) | **Failed**: same | F3 | Generated successfully; detailed warning/content verification still pending |
| Revenue Opportunities (2026) | **Failed**: "Model name must be text" | F4 (and F3 once past it) | Generated successfully; exact original F4 cause remains unconfirmed |
| Regional Sales Sample (2026) | **Failed**: "Model name must be text" | F4 | Generated successfully; exact original F4 cause remains unconfirmed |

Reading the PBIR reports straight out of the three 2026 PBIX files now gives 1, 3 and 3 pages with 17, 20 and 12 visuals, and no warnings.

## Findings and fixes

Severity: **High** = wrong or missing output with no clear warning; **Medium** = false warnings or blocked cleanup; **Low** = presentation.

| # | Severity | Finding | Fix |
|---|---|---|---|
| F1 | High | `validate_report` treated a key called `visual`, `query`, `position` or `objects` anywhere in a file as a visual part. Desktop 2025+ writes `"reportVersionAtImport": {"visual": "2.12.0"}` in every `report.json`, so the file was rejected, report filters were lost and "Report metadata ... missing" blocked all cleanup. Hit 4 of 9 real PBIP projects and all three PBIR-in-PBIX files. | Those keys are checked only at the top of a visual file; field-reference shapes are still checked everywhere (`input_validation.py`). |
| F2 | High | Visual calculations store DAX as `"Expression": "ROUND([MTTR] - [target], 1)"`. The validator rejected the whole visual (15 lost in one project), and each loss became a report-wide issue. | A string `Expression` is accepted under `NativeVisualCalculation`. |
| F3 | High | 2025+ PBIX files keep the report as PBIR under `Report/definition/`. pbi-tools 1.2 extracts no report for them, so the batch failed. | `pbix_batch.extract_pbir` copies `Report/definition/**` out of the PBIX (a zip) when pbi-tools gives no legacy report. Only plain relative paths are written, with a 200 MB cap; the result is read by the normal PBIR parser, so it gets no "legacy layout" caution. |
| F4 | High | "Model name must be text": `validate_model` checked `name` everywhere in the model, including free-form annotation and extended-property payloads, and rejected a missing model name. | Names are checked only on model objects; `value`, `content`, `linguisticMetadata` and `changedProperties` payloads are skipped; a missing root name is allowed. **Unconfirmed:** the exact offending field wasn't seen, because the batch deletes its temporary extraction. |
| F5 | Low | Every PBIX model was named "database" (from pbi-tools' `database.json`). | The PBIX file name is used when the model has none. |
| F6 | High | PBIP projects saved before PBIR keep the whole report in one `report.json` (the legacy layout). The generator produced 0 pages and 0 visuals and still called the mode "combined". Hit 3 of 9 real projects. | `extracted_report.parse_legacy_layout` reads the single file with the same page/visual logic as the pbi-tools adapter, and `parse_report` uses it automatically. Bookmarks come from the report config (groups flattened). |
| F7 | Medium | pbi-tools writes each bookmark as a folder (`bookmark.json` plus one file per visual state); the adapter counted every file, so 18 pages had 801 "bookmarks". | One bookmark per folder, named by its `displayName`. |
| F8 | Medium | Forecast and analytics outputs (`forecastValue`, `confidenceHighBound`, `Calendar.Date` via `TransformTableRef`) were reported as broken bindings. | Transform outputs are skipped; the transform's real inputs are read from its own query. |
| F9 | Medium | Unqualified `[column]` in row context (`FILTER('Events', [component] = "DSE")`, calculated columns iterating another table) was unresolved and became a report-wide issue, blocking all cleanup. | Resolved to the unique column of that name, or the one in a table the expression names; ambiguous cases are scoped to the candidate tables. |
| F10 | Medium | A Q&A visual's saved answer referring to a term that no longer exists (`Sales[Dates]`) was a broken binding. Q&A re-answers at runtime. | Q&A visual fields are flagged `runtime`; unresolved ones produce no issue or warning. |
| F11 | Medium | Columns created inside a measure (`ADDCOLUMNS(T, "__x", ...)` then `[__x]`) were unresolved report-wide issues. | Names defined as string literals in the same expression count as local columns. |
| F12 | Medium | Auto date/time hierarchies (`PropertyVariationSource`) looked like a missing hierarchy, e.g. `Calendar Lookup[Quarter]`. | The binding counts as using the underlying date column. |
| F13 | Medium | An unresolved bare `[column]` in a calculated column, security-role filter or calculated table blocked every table. | Scoped to that expression's home table. |
| F14 | Low | The M tracer flagged row formulas (`Table.AddColumn(..., each Text.Combine(...))`) as coverage gaps, adding an "Unknown" source row. | `each` formulas are not gaps; about 20 more row-level transforms pass their input through. Queries named inside a formula are still followed. |
| F15 | Low | The home page grouped reports by their full path (`D:` > `GIT` > `pbi-doc-gen` > `pbix-samples`); long source tags wrapped and centred; "1 pages". | Grouped by the folder the report is in (an explicit catalogue folder still nests as typed); tags stay on one line with the full name on hover; singular counts. |
| F16 | Low | An Azure Blob file was labelled by its full URL. | Named by file name (`Azure Blob Storage · automl demo.xlsx`). |

### Effect on the nine real PBIP projects

Before → after this commit. "Candidates" counts column and measure deletion candidates; "report-wide issues" are the ones that hold every candidate in Review.

| Project | Pages | Visuals | Candidates | Report-wide issues |
|---|---|---|---|---|
| pbip-documenter sample | 1 → 1 | 2 → 2 | 0 → 0 | 1 → 1 |
| AdventureWorks Sales (toolkit) | 3 → 3 | 8 → 8 | 0 → 13 | 1 → 0 |
| portfolio-mining | 8 → 8 | 163 → 178 | 0 → 100 | 18 → 0 |
| SalesDashboard | 1 → 1 | 9 → 9 | 0 → 2 | 1 → 0 |
| javendia Contoso | 0 → 1 | 0 → 0 | 0 → 0 | 2 → 1 |
| Microsoft SamplePBIP (Sales) | 0 → 5 | 0 → 44 | 0 → 0 | 2 → 1 |
| tmdl-lens fixture (no report) | 0 → 0 | 0 → 0 | 0 → 0 | 4 → 1 |
| Sales Data Analysis | 4 → 4 | 46 → 46 | 0 → 41 | 1 → 0 |
| powerbi-git-demo | 0 → 1 | 0 → 3 | 0 → 0 | 2 → 1 |

Source detection is unchanged: 101 partitions, 0 Unknown, 0 disagreements.

## Real findings (the tool was right)

These are genuine problems in the sample files, correctly reported:

- **Supply Chain:** colour rules on three visuals refer to `Supply Analytics[Category]`, which no longer exists. Power BI ignores them silently.
- **Microsoft SamplePBIP:** a KPI visual uses the measure `_Margin Status`, which is missing from the model.
- **powerbi-git-demo:** a table visual uses `Sales[Sales]`; the model's column is now `Sales Amount`.
- **tmdl-lens fixture:** security roles filter on `[email]` and `[region]`, which the fixture never defines.
- **Duplicate measures:** Supply Chain `% on backorder` = `% on time orders`; Sales & Returns `Returns Indicator` = `Units Returned Indicator`.

## What needs to be done

In priority order.

1. **Complete a rendered UI review once permitted browser access is available.** The PBIX rerun is done. Check Corporate Spend and the other samples in Lineage, Relationships, and Page layout: every source/page/table shape remains visible, labels fit, selection is clear, zoom/scroll works, and the details panel does not obscure content on wide screens. Include keyboard and narrow-screen checks. Retain the Page layout design the user likes. Separately audit report contents/warning counts after the successful rerun; generation alone does not establish their correctness. A future `--keep-extract` option would still help diagnose extraction failures.
2. **Decide the legacy-layout policy.** Every report in the legacy layout (all pre-2025 PBIX files, and PBIP projects saved before PBIR) carries a caution that keeps every column and measure in Review, so their cleanup review never suggests anything. It was a deliberate choice (custom visuals and bookmark page attribution are best-effort there), but with F7–F12 fixed the adapter is much more reliable. Options: keep the policy; scope the caution to the tables that custom visuals and bookmarks touch; or show candidates with a "verify in PBIR" caveat. **Decided and done:** the caution no longer blocks cleanup on its own. Bookmark fields already count as used, so uncertain bookmark page attribution cannot change a deletion decision. Every field stays in Review only when a visual has a data query whose bindings could not be read. On the samples: Adventure Works DW 26 candidates (was 0), Sales & Returns 15, Supply Chain 3; Regional Sales stays blocked by its genuinely missing `Page Details` table.
3. **Explain formatting-only references.** Supply Chain's broken binding comes from a colour rule, not a visual's fields. The warning should say "formatting rule refers to a missing column", which is lower severity, rather than "broken binding". **Done in part (`a7f254b`):** every broken-binding warning now ends with "Used on: page — location" (up to three), so a colour rule, hidden filter or bookmark can be found. Naming the formatting rule itself is still open.
4. **Name custom visuals.** Types appear as internal ids (`PBI_CV_885EF3C3_...`, `simpleImageEBC4...`). Map them to display names from the report's custom visual list or the `CustomVisuals/` folder. **Done in part (`2d914a0`):** GUIDs and timestamps are stripped (`Simple Image (custom)`, `Power Apps (custom)`); bare `PBI_CV_…` ids show as "Custom visual". Reading display names from the report's custom visual list is still open.
5. **Quieten decorative visuals.** Sales & Returns has 67 action buttons plus images and shapes; Page layout and the visual lists could fold decorative visuals (buttons, images, shapes, text boxes without fields) into one "decorative" group. **Done in the Pages view (`40569c6`):** data-free buttons, shapes, images, navigators and text boxes fold into one "N decorative visuals" row. Page layout still draws them, since their position matters.
6. **Scope a missing PBIR `report.json`.** The pbip-documenter sample has pages but no `report.json`, which blocks all cleanup. `report.json` only holds report-level filters, so its absence could be a scoped caution ("report-level filters unknown") instead.
7. **Test real PBIX files in CI.** pbi-tools needs Windows and Power BI Desktop. An optional Windows job running the batch on the samples (downloaded at a pinned commit) would catch regressions in the PBIX path; `tests/test_live_findings.py` covers the individual fixes meanwhile.
8. Still open from the UI review: the CLI `--csv` covers columns only; duplicate detection compares text, not meaning; `model_parser`'s regex source patterns remain only as a fallback.

## Tests added

`tests/test_live_findings.py`, 11 tests: modern `report.json` metadata; visual-calculation DAX; model without a name and free-form payloads; forecast outputs; auto date hierarchy; single-file legacy `report.json` (page order, bookmarks, groups); Q&A answers; pbi-tools bookmark folders; row-context and local DAX columns; PBIR read from a PBIX (including the model name); unsafe zip paths refused. `tests/check_catalog.cjs` covers the new folder grouping.

## More samples: pbi-tools/pbix-samples (commit 179fb48)

Ran the 29 pre-extracted reports in [pbi-tools/pbix-samples](https://github.com/pbi-tools/pbix-samples) (Microsoft monthly demos 2018-2020 plus sample reports) through load, link and render, and opened every tab of every page in Chromium (no script errors).

| Measure | Before | After |
|---|---|---|
| Reports that loaded with tables | 8 of 29 | 29 of 29 |
| Unknown source rows | 904 | 0 |
| Broken bindings | 150 | 55 |

Sources now covered: Excel, SQL Server (incl. native queries), OData, Web/API, CSV, Azure Blob Storage, SharePoint; Snowflake via a separate sample. The remaining broken bindings repeat across the monthly demos (report filters on `ProductCatalog`, `Months`, an old `LocalDateTable`) and look genuine.

Also downloaded to `pbix-samples/` for a Windows batch run: seven Microsoft PBIX files (OData, CSV, SQL, Web API) and `Snowflake_Usage_Sample.pbix` (no licence; local use only). See `pbix-samples/SOURCE-more.txt`.

Still untested: DirectQuery, live connections to a published dataset, Databricks, dataflows. No public PBIX was found; a synthetic PBIP fixture would cover them.
