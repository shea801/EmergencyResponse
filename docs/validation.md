# Validation record — 25 October 2026

## November 22, 2026 — dependency and map alignment

A fresh Python 3.14.3 environment installed the constrained editable package, passed `pip check`, and ran 14 tests successfully. The active-database shell, layout, and callbacks for all seven views returned HTTP 200. The map radius, test, on-screen explanation, and metrics document now agree at 10 pixels; the legend uses the map's blue-to-white `ice` colors. A headless Chrome capture with synthetic incidents showed road tiles and the legend but no visible density layer, so visual map review remains open. Ruff still reports four import-order findings and nine files needing formatting. Python 3.11 execution remains unverified.

## October 26, 2026 — summary export support

Ruff lint and format checks pass, and the expanded suite reports **14 passed** on the configured Python 3.14 interpreter. New independent fixtures cover both filename styles and capitalization, the double-period filename, ignored unrelated files, header aliases/collisions, ISO date parsing, detailed/summary overlap in either import order, retained detailed fields, unchanged reimports, same-date different incident identities, genuine conflicts, partial records that must not mask detailed conflicts, exact duplicate source-row resolutions, later corrections, first-only apparatus filters, unknown field counts, and exports that disclose completeness without including personnel/editor values. Existing functional and dashboard tests continue to pass. The existing Dash DataTable deprecation warnings remain.

All 33 real files were imported into a temporary copy of the existing schema-3 database. File reports reconciled, no rows were invalid, and the result was 14,131 canonical incidents, 17,283 reported unit responses, and 17 unresolved identities. A second import classified every input row as a duplicate and left canonical totals and data version unchanged. SQLite integrity checking returned `ok`. The 17 conflicts comprise the original disputed identity and 16 additional identities with differing supplied observations; omitted summary columns and date text formatting did not create conflicts.

After that trial, the active database was backed up to `data/before-summary-import-20261026-100645.sqlite3` and all files were imported. The active totals match the trial. `data/summary-import-report.jsonl` contains per-file reports and `data/new-format-verification.json` records the trial summary. Historical validation below describes the earlier 22-file dataset, not the enlarged current population. This update does not close the Python 3.11, visual-review, or department-policy release gates.

On the enlarged active database, the application shell, layout, dependencies, and callbacks for all seven views returned HTTP 200 through the local Flask test client. Each view included the notice identifying 4,645 selected incidents without participation lists. Callback measurements were approximately 1.65–1.84 seconds on the configured environment; these are server checks, not browser-render measurements. Active SQLite integrity checking returned `ok`.

## Fixture expectations and automated checks

Synthetic fixtures have three incidents with six distinct unit participations. Two incidents share one address, two have validated coordinates, and one lacks coordinates. The expected map coverage is 2/3 or 66.7%. Two incidents are classified Alarm (66.7%) and one Medical (33.3%). Selecting Engine 22 in participation mode yields two incidents and two matching unit responses; selecting it in source-reported first-arrival mode yields one incident and all three participating responses for that incident. A 22:00–06:00 filter includes the two overnight incidents across 31 December and 1 January. Winter 2026 includes December 2025 and January 2026. Location detail adds an AND restriction, and conflicting global/location-detail choices yield zero incidents.

The ingestion fixture checks a four-row pair of overlapping files: one repeated row, one changed version of the same identifier, one identity excluded pending resolution, then an explicit resolution restoring that identity. It also checks an unchanged reimport, required-header rejection without canonical changes, invalid-row quarantine, malformed timestamp retention in overall totals, daylight-saving ambiguous/nonexistent flags, export package contents, and backup integrity. Dash's layout, dependency endpoint, every view callback, and stale location selection are exercised through Flask's test client without live network or production data. The interface fixture also checks that secondary controls start collapsed, the summary contains a density trace, and the map weights located addresses by distinct incident count over an OpenStreetMap road basemap.

Executed checks on the configured Python 3.14.3 interpreter:

```text
python -m ruff check .             All checks passed
python -m ruff format --check .   All maintained files formatted
python -m pytest -q              7 passed
```

Dash 4.2 emits a deprecation warning for its built-in `dash_table.DataTable`; this does not affect current test results and should be addressed when upgrading Dash. Maintained Python source and tests also parsed with Python 3.10 syntax mode. The current NumPy and pandas pins require Python 3.11 or newer; no Python 3.11 interpreter was available for execution. Python 3.14.3 is the exercised deployment version. The documented standard editable install with constraints succeeded in the configured environment and a fresh temporary virtual environment when PyPI access was available. `pip check` in the fresh environment found no broken requirements; an isolated import path using only its installed packages loaded the dashboard layout (HTTP 200) and audited the project database. The CLI also audited correctly from `/private/tmp`.

## Supplied-data and operational checks

The supplied 22 files imported successfully into schema version 3. `dfd-dashboard audit` reports 11,000 source rows, 1,500 exact repeated rows, one unresolved identity with two source rows, 9,498 canonical incidents, and 17,321 unit responses. Reimporting all unchanged files left these totals and data version 22 unchanged; only attempt history grew. The known disputed identifier remains excluded. All 44 current import attempts recorded importer version 1.0.0, schema version 3, and config version `2026-10-25-1`.

`refresh-coordinates` matched 4,099 canonical location keys to valid numeric entries in the local cache and retained 7,255 mapped incidents. A live SQLite backup was created at `data/final-verification.sqlite3`; `restore-check` reported `integrity: ok` and 9,498 incidents, and an audit of that separate database matched the active database totals and data version 22. An existing schema-1 backup was copied to a separate path and opened with the schema-3 application to verify additive migrations preserved counts.

The supported `dfd-dashboard serve --port 8051` command ran at `127.0.0.1` with debug mode off and served `/` with HTTP 200. The local server was stopped after verification. Dash callback HTTP responses returned 200 for all seven views on the reviewed database. Export ZIP content and metadata reconciled to a synthetic filtered fixture.

## Performance and visual review

Environment: Apple Silicon (`arm64`), macOS 26.6.2, Python 3.14.3, Dash 4.2.0, local SQLite with 9,498 canonical incidents and 17,321 participations. Measurements used Flask's in-process test client, with no network requests or browser rendering. Before the heatmap change, three unfiltered Overview callback responses took 1.314, 1.255, and 1.226 seconds (median 1.255); three Engine 22 filter updates took 0.374, 0.392, and 0.387 seconds (median 0.387). The full incident-detail callback took 1.244 seconds and returned about 4.3 MB. With the summary heatmap, three unfiltered Overview responses took 1.268, 1.309, and 1.282 seconds (median 1.282), each returning about 324 KB. A localhost HTTP GET of `/` returned 200 after final startup. Server callback timings meet the proposed 2-second warm-filter target, but browser rendering and the proposed 5-second initial-display target still need formal measurement and DFD confirmation.

The native computer-use service failed during attempts to capture the legacy dashboard. The updated dashboard was then inspected with local headless Chrome at 1440 and an emulated 390-pixel viewport. Final captures are [desktop](screenshots/overview-desktop.png) and [mobile](screenshots/overview-mobile.png). Both show the road basemap and weighted incident heat, the four main statistics, and the compact filter bar. The emulated mobile document width matched its 390-pixel viewport with no horizontal overflow. Chrome's immediate screenshot sometimes captured the road tiles before the WebGL heat layer was drawn; the final captures were taken after the map settled. A DFD review on the intended viewing machine and the missing legacy reference screenshot remain open before operational sign-off. No response-duration cards or targets are present; the data-quality view explains the current source-access limitation.

## Release decision

The application is a functional incident-analysis MVP candidate. Department review is still required for identity scope and the disputed source version, timestamp semantics, company mappings, coordinate provenance, and export coverage. Python 3.11 execution, browser visual review, and final performance sign-off remain release gates. Missing First Due timing reports are an accepted scope limitation, not a release gate.
