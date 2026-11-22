# Danbury Fire Department Emergency Response Dashboard — Build Specification

Status: implementation specification; department decisions are identified in Section 13.  
Project directory: `/Users/sheahanson/EmergencyResponse`  
Initial data review: October 25, 2026

## 1. Purpose and intended users

Build a dashboard for City of Danbury Fire Department (DFD) decision makers to analyze incident demand, apparatus participation, incident types, and incident locations using currently accessible First Due exports. Response-duration analysis is an optional future extension with no delivery timeline.

The application will help DFD:

- Assess incident demand and response activity to inform operational planning and resource allocation.
- Identify incident patterns by date, time of day, weekday, season, shift, company, and location.
- Use incident types and property types to inform training and preincident planning.
- Identify repeat-response locations and candidates for further target-hazard assessment.
- Support policy review, resource allocation, and operational planning with traceable evidence.

Results must make data limitations visible. Incident frequency and apparatus participation alone do not establish hazard severity, training effectiveness, staffing adequacy, or response speed. The current dashboard will not evaluate response durations or response-time target attainment.

## 2. Project constraints and existing application

### 2.1 Location and technology

- Keep application source, documentation, configuration, tests, and project-managed runtime files under the project directory. The Python installation and installed third-party packages may reside outside it.
- Resolve data and asset paths relative to the project root or explicit configuration, independently of the shell's current working directory.
- Use Python code compatible with Python 3.10 or higher. Declare the tested Python version range and dependency versions in `pyproject.toml`; verify the minimum version and selected deployment version before release.
- Retain Dash, Plotly, and Dash Bootstrap Components for the initial implementation.
- Use SQLite for the local MVP database. Reassess the database and hosting architecture before introducing shared deployment or concurrent importing users.
- Start the dashboard through a documented CLI command that launches a local web interface. Bind to localhost by default, with debug mode disabled for normal use.

### 2.2 Existing code and appearance

The starting implementation consists of `main.py`, `app.py`, `Incident_Data.py`, and `dashboard_components.py`. Both `main.py` and `app.py` currently build dashboards; their behavior has diverged.

- Preserve the recognizable dark Bootstrap SUPERHERO appearance, orange headings, cards, and chart-based layout.
- Improve layout, responsive sizing, labels, and navigation where needed. Record reference screenshots before replacing the current interface.
- Consolidate the application into one supported entry point. Retire duplicate implementations after parity checks, retaining useful code through the project's change history.
- Correct inconsistent company/station filtering, abbreviated-versus-full apparatus labels, and components that use different filter scopes.
- Move import, validation, storage, filtering, and statistical calculations out of presentation callbacks.

### 2.3 Project configuration: `pyproject.toml`

Create `pyproject.toml` at the project root as the central project and Python-tool configuration file, following the [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).

- Define the build backend in `[build-system]` and project name, version, description, README, Python requirement, and runtime dependencies in `[project]`.
- Set `requires-python = ">=3.10"` and keep dependency choices compatible with the declared and tested Python versions.
- Define the supported CLI entry point in `[project.scripts]` once the application package is established.
- Separate development/test dependencies, including Ruff and the selected test runner, from runtime dependencies using a documented development dependency group or extra.
- Store Ruff settings in `[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.ruff.format]`. Store test-runner settings here when the selected runner supports it.
- Keep operational paths, source data, credentials, unit mappings, and department policy settings in their appropriate runtime configuration or data files.
- Record resolved dependency versions in a checked-in lock or constraints file supported by the chosen installation workflow. Document how to reproduce both runtime and development environments and update their dependencies.

### 2.4 Ruff linting and formatting

Use Ruff as the required Python linter, import organizer, and formatter. Configure it centrally using the [Ruff configuration documentation](https://docs.astral.sh/ruff/configuration/) and [formatter documentation](https://docs.astral.sh/ruff/formatter/).

- Include Ruff in the reproducible development environment and record its resolved version with the other development tools.
- Set `target-version = "py310"`, `line-length = 100`, and four-space indentation. Use double-quoted strings and space indentation in the formatter configuration.
- Enable lint rule families `E4`, `E7`, `E9`, `F`, `I`, and `UP` for basic errors, unused names/imports, import ordering, and Python modernization compatible with the target version.
- Apply checks to maintained Python application code, tests, and project utilities. Exclude virtual environments, caches, build output, generated files, and historical exploratory notebooks unless those notebooks are explicitly adopted as maintained project code.
- Use narrow, documented exceptions when needed. Do not disable checks broadly to make failing code pass. Review automatic fixes for behavior changes and do not enable unsafe fixes by default.
- Require `ruff check .` and `ruff format --check .` to pass from the project root before accepting implementation work or a release. The checking commands must not modify files.
- Document `ruff check --fix .` and `ruff format .` as developer commands that modify files; inspect resulting changes and run relevant functional tests after fixes.
- Run the same checks in continuous integration when it is introduced. Ruff complements the functional test suite; passing lint and formatting does not establish analytical correctness.

## 3. Data sources and initial findings

### 3.1 Existing inputs

Historical exports from [First Due](https://www.firstdue.com/) reside in `incident_reports/` as `Incident Report*.csv` and `incident_reports*.csv`. Recognize both naming styles case-insensitively, including filenames with an extra period before `.csv`. Preserve source files unchanged.

The original detailed exports contain these columns:

| Source column | Intended use |
| --- | --- |
| `INCIDENT NUMBER` | Source incident identifier; retain as text |
| `INCIDENT DATE/TIME` | Source incident timestamp; meaning requires confirmation |
| `STATUS` | Report workflow status; retain separately from operational disposition |
| `DISPATCH TYPE` | Initial dispatch classification |
| `1ST ARRIVING` | Source-reported first-arriving apparatus |
| `INCIDENT LOCATION` | Original location text |
| `SHIFT` | Source-reported shift, currently A–D |
| `INCIDENT TYPE` | Reported incident classification |
| `PROPERTY TYPE` | Reported property or occupancy classification |
| `APPARATUS` | Apparatus participation; parsing rules require validation |
| `STATION` | Source station value; meaning requires confirmation |

The summary exports added October 26, 2026 use `INCIDENT` (including the observed trailing space) in place of `INCIDENT NUMBER`, and omit `INCIDENT TYPE`, `PROPERTY TYPE`, `APPARATUS`, and `STATION`. They additionally contain officer/editor metadata. Validate each supported layout by its headers; preserve extra fields only in restricted source lineage and do not display personnel/editor fields.

Reconcile overlapping incident identifiers using supplied analytical fields and parsed timestamps. An omitted column does not conflict with a detailed record or erase its information; select the compatible richer source independently of import order. Conflicting supplied values still require review, and a reduced record must not hide conflicting detailed versions. Summary-only incidents remain eligible with unknown final classification/property/station and no inferred apparatus list. Keep dispatch classification and first-arriving unit usable separately, disclose field completeness, and never substitute those values for final incident type or full participation.

An existing `latitude_longitude_addresses.json` file may supply location coordinates. Audit its structure, provenance, matching rules, and coordinate quality before using it. A timestamp alone is not a safe incident or location join key.

### 3.2 Baseline audit

The initial review found 22 CSV files containing 11,000 rows, including 1,500 exact duplicate rows. Removing exact duplicates leaves 9,500 distinct complete rows and 9,499 distinct incident-number values. One incident-number value occurs on two differing records and requires reconciliation.

The observed incident timestamps span April 24, 2025 through April 28, 2026. These bounds do not establish complete coverage between those dates. Recompute the audit when inputs change; these figures are a baseline, not hard-coded application totals.

The current exports do not include dispatch, notification, en route, arrival, or available timestamps needed to calculate response durations. `1ST ARRIVING` identifies an apparatus and must not be treated as an arrival timestamp.

### 3.3 Confirmed access limitation

The project owner reports that First Due changed the reports and data available at their Captain-level user access. Although many operational records remain accessible, the reports containing dispatched, en route, arrival, and clear/in-service time breakdowns are no longer accessible as they were when the project began approximately three years ago.

This is a known source-access constraint, not an application defect or an incomplete import. Access may become available again, but there is no timeline or commitment. Do not make obtaining these reports a prerequisite for implementation, testing, release, or completion of the current dashboard. Develop against the accessible exports without assuming an alternative source for the missing timestamps.

## 4. Delivery scope

### 4.1 Current release: incident-analysis MVP

Deliver an operational local dashboard using the existing exports, including:

- Repeatable, validated imports into SQLite.
- Reconciled incident counts and separate apparatus participation counts.
- Shared filters, incident and property-type breakdowns, temporal trends, location analysis, and shift/company comparisons.
- Searchable incident detail, filtered exports, and a visible data-quality summary.
- Automated tests, installation instructions, operating documentation, and backup/restore procedures.

The MVP is a complete deliverable using currently accessible data. Do not build response-duration cards, charts, target-attainment indicators, or mandatory timestamp import fields for this release. Include a concise data-limitations note explaining that response-duration analysis is unavailable because the necessary First Due reports are outside the project owner's current access. Missing durations must never appear as zero or as failed performance.

### 4.2 Optional future extension: response-performance analysis

If access returns and suitable exports become available, scope response-duration functionality as a separate extension. Section 8 preserves provisional definitions for that work; it is not a scheduled second phase, a current implementation task, or a requirement for MVP acceptance.

Keep the current data model and analytical boundaries maintainable so new fields can be added through migrations later. Do not implement speculative timestamp tables, duration calculations, or target configuration now. The application must not estimate actual durations from incident date/time, apparatus ordering, first-arriving labels, or map distances.

### 4.3 Deferred scope

The initial release does not require live First Due integration, automated dispatch recommendations, predictive staffing models, public hosting, user-account administration, automated hazard designation, or evaluation of individual personnel.

Later releases may add inspection/preplan integration, a maintained target-hazard register, response-district boundaries, station overlays, verified unit commitment/concurrency analysis, and training or incident-outcome data.

## 5. Data definitions and counting rules

### 5.1 Analytical units

- **Incident:** one reconciled event under a verified source identifier. Confirm whether uniqueness also requires department, source system, year, or another field before enforcing the database key.
- **Unit response:** one verified apparatus participation in an incident. Do not create additional responses from repeated apparatus tokens or repeated exports. If future data identifies multiple response legs for the same unit and incident, model those explicitly.
- **Company:** an operational company that may use different apparatus over time. Preserve apparatus identity separately and maintain effective-dated company mappings when needed.
- **First-arriving apparatus:** preserve the source-reported value for the current release. This supports counts and participation comparisons, not elapsed-time calculations. A future timestamp extension must distinguish source-reported first arrival from first qualifying arrival derived from validated timestamps.
- **Station:** retain the source value. Do not assume it identifies a company, first-due area, or geographic district.
- **Shift:** use the source-reported shift. Derive a shift only from a separately approved rotation schedule and boundary rules, recording that it was derived.

An incident with four responding apparatus counts as one incident and four unit responses. Company incident counts may overlap and must not be summed to obtain department incident totals.

Keep these questions separate in filters and labels: which units participated, which unit arrived first, which company participated, and where the incident occurred. A responding company does not establish the incident's first-due geographic district.

### 5.2 Normalization and classification

- Preserve original values alongside normalized values.
- Normalize whitespace and documented placeholders such as `--` to appropriate missing values. Do not treat the literal placeholder as an operational category.
- Use configurable aliases for apparatus/company labels, such as `E24` and `Engine 24`. Match complete parsed identifiers rather than substrings.
- Include unknown and unmapped units in a visible category; do not silently discard volunteer, mutual-aid, reserve, or newly introduced apparatus.
- Preserve dispatch type, incident type, and property type separately.
- Use versioned, documented mappings for broad incident categories and classification changes. Do not assume historical classifications are directly comparable.
- Retain report status and operational disposition separately. Do not infer cancellation or emergency response mode from report authorization status.

### 5.3 Date and time rules

- Confirm what `INCIDENT DATE/TIME` represents before labeling it call-received or dispatch time.
- Display dates and times in `America/New_York`. Preserve original timestamp text and record source timezone assumptions. Store timezone-aware instants in UTC when they can be resolved reliably.
- Flag ambiguous or nonexistent daylight-saving times without silently selecting an interpretation.
- Define date selections as inclusive calendar dates implemented using a start-inclusive, end-exclusive interval ending at local midnight after the selected end date.
- Use start-inclusive, end-exclusive hour ranges; 22:00–06:00 spans midnight. A disabled hour filter means the full day; reject identical enabled start/end values with a clear message.
- Base calendar groupings on the selected incident timestamp in local time. Preserve the reported shift even if its operational day differs from the calendar date.
- Define seasons in configuration, including how December–February is assigned to a year. Label partial periods and compare equivalent periods by default.
- Record known export coverage separately from observed event dates. Absence of incidents does not prove that a period has complete reporting.

## 6. Import and data-quality requirements

### 6.1 Repeatable imports

- Provide a CLI import command for one file or a directory. Record filenames, content hashes, import times, importer/schema versions, and source row numbers.
- Reimporting unchanged files or overlapping exports must leave analytical totals unchanged. Import-attempt history may grow.
- Reconcile exact duplicates using verified incident identity and normalized content while preserving source lineage.
- Preserve conflicting versions in staging and flag them for resolution. Do not silently select the last file read or overwrite a record because it has the same incident number.
- Before reconciliation rules are approved, keep unresolved identities out of canonical analytical totals and report their source-row and candidate-record counts separately. Explain this treatment in the dashboard.
- Apply corrected exports only through a documented precedence or explicit resolution rule. Keep prior values and a resolution audit trail. File modification time alone does not establish authoritative revision order.
- A later export omitting an incident must not delete it from the database without an explicit deletion policy.

### 6.2 Validation and recovery

- Validate headers, encoding, required fields, identifiers, timestamps, apparatus parsing, and recognized mappings.
- Document required columns separately from required row values. A missing location, coordinate, classification, or unit must not discard an otherwise identifiable incident. Retain incidents with unusable timestamps for overall counts where identity is resolved, exclude them from time-filtered results, and disclose that exclusion.
- A file missing required columns must fail with a clear diagnostic and no partial canonical changes. Report additional columns and retain their source values for review.
- Quarantine invalid rows without losing their original values. Commit accepted records and their audit results transactionally; roll back incomplete transactions on failure.
- Produce an import report with reconciled counts for source rows, accepted/new records, updates, duplicates, invalid rows, and unresolved conflicts. Define the categories so users can reconcile the report to its inputs.
- Keep import/reconciliation status distinct from analytical eligibility, such as report-status selection or missing incident classification. The unavailable response timestamps are outside the current import contract; do not count their absence as rejected records, import errors, or defects in the accessible exports.
- Expose malformed dates, unresolved identities, missing coordinates, unmapped units, and other quality issues with enough source context for correction.
- Treat source files as read-only. Prevent overlapping import processes from corrupting data or applying inconsistent resolutions.

## 7. Dashboard requirements

### 7.1 Shared filters and context

Provide filters for date range, hour range, weekday, month/season, reported shift, apparatus/company, dispatch type, incident type, property type, and location. Support multiple selections where practical.

- Apply selections across different dimensions with AND logic and multiple selections within a dimension with OR logic. Document any exception, including apparatus participation versus first-arrival mode.
- In apparatus/company participation mode, an incident qualifies when at least one selected unit/company participated; incident summaries count that incident once, and unit-response summaries count only matching unit responses. In first-arrival mode, qualify incidents by the source-reported first-arriving apparatus. Clearly label first-arrival counts and do not equate them to all participating responses or response speed.
- All cards, charts, tables, drilldowns, and exports must use one shared filter definition and the same reconciled database version.
- A location detail selection adds a location restriction to the active global filters. If that location becomes unavailable after another filter changes, clear the selection and explain why.
- Display active filters, observed date bounds, known coverage limitations, last successful import, and applicable exclusions. Provide a reset action.
- Show useful loading, empty, unavailable, and error states. Prevent stale results from appearing to reflect a newly selected filter or import.

### 7.2 Required views

| View | Required behavior |
| --- | --- |
| Overview | Distinct incident count, unit-response count, leading incident categories, data freshness, and quality indicators |
| Incident types | Counts and shares by original type and approved broad category; allow dispatch-versus-final classification comparison |
| Temporal trends | Hour-of-day, weekday, monthly, seasonal, and year/period views with explicit date bounds |
| Shifts and companies | Separate incident participation, unit responses, and source-reported first arrivals; show unknowns and sample sizes |
| Locations | Incident-density map, repeat-location rankings, property-type breakdowns, and selected-location incident detail |
| Incident detail | Searchable, sortable, paginated records with stable incident references and source lineage |
| Data quality and limitations | Import results, duplicate/conflict treatment, invalid records, missing accessible fields, unmapped units, mapping coverage, and the known response-timestamp access limitation |

Category tables and drilldowns must permit access to all categories. If a chart shows only the leading categories, identify the remainder explicitly. Remove fixed assumptions such as “past year” when the active dates differ.

### 7.3 Geography and repeat locations

- Preserve source addresses and maintain normalized location identifiers with documented matching rules. Do not merge different sites solely because they share a timestamp or similar text.
- Represent unknown coordinates as missing, never `(0, 0)`. Validate coordinate ranges and flag implausible positions, including out-of-area records that may represent legitimate mutual aid.
- Prefer validated source coordinates. Audit existing cached coordinates before reuse. Store coordinate source, matching method, validation status, and available confidence information.
- Keep geocoding outside interactive callbacks. Cache results by normalized location; use configurable provider settings and bounded retries. External geocoding must be explicitly enabled in configuration and documented as sharing location queries with that provider.
- Show located/eligible incident counts and mapping percentage. Exclude unlocated incidents only from spatial plotting, retaining them in applicable non-map totals.
- Count distinct incidents in the density map. Identify any weighting, clustering, aggregation, or smoothing used.
- Keep repeat-location thresholds configurable and show their value and active period. Use confirmed location identity for detail selection.
- Label repeat locations as candidates for investigation. Official target-hazard designation requires approved risk criteria and additional occupancy, preplan, inspection, or hazard data.
- Document external map-service dependencies. If a basemap is unavailable, preserve non-map analysis and show a clear map status.

### 7.4 Comparisons and exports

- Show counts, percentages, sample sizes, and period lengths with clear denominators.
- Flag small samples using a documented configurable threshold. Do not present apparatus or shift comparisons as personnel rankings.
- Show rates per staffed hour, available unit hour, or population only when validated denominator data exists. Do not infer those denominators from incident rows.
- Provide filtered incident and summary CSV exports. Include filter settings, metric definitions/version, generation time, data version, and exclusions in accompanying metadata.
- Ensure exports reconcile to the selected view and distinguish incident-level exports from unit-response exports. Export files must open safely as text data in common spreadsheet software.

## 8. Optional future response-performance reference

This section applies only if timestamp access returns and a response-performance extension is scoped. It does not require current implementation, timestamp acquisition, configuration, or tests. No delivery date is assigned, and the MVP can be completed without it.

### 8.1 Required source data

If suitable exports become accessible again, assess incident and unit identifiers, call-received/creation times, initial dispatch times, per-unit notification times, per-unit en route times, per-unit arrival times, and per-unit clear/in-service or available times where supported. Confirm whether clear and in-service/available represent different events. Assess operational disposition, response mode, and resource eligibility information needed for exclusions.

Every metric must be independently gated by its required fields and confirmed semantics. A supported travel-time metric does not imply that alarm processing or total call-to-arrival can also be calculated.

### 8.2 Metric definitions

The following are proposed definitions pending DFD confirmation of source event meanings:

| Metric | Calculation and analytical grain |
| --- | --- |
| Alarm processing | Initial qualifying unit notification minus call received; one value per eligible incident |
| Unit turnout | Unit en route minus that unit's notification; one value per eligible unit response |
| Unit travel | Unit arrival minus that same unit's en route time; one value per eligible unit response |
| Dispatch-to-first-arrival | First qualifying arrival minus initial incident dispatch; one value per eligible incident |
| Call-to-first-arrival | First qualifying arrival minus call received; one value per eligible incident |
| Unit commitment | Unit available minus a DFD-approved starting event; one value per eligible unit response |

If source dispatch and notification represent different events, preserve both and label each calculation precisely. Define qualifying resources, ties, late-added units, canceled responses, staged units, mutual aid, and emergency/nonemergency response treatment. Do not combine timestamps from different units into a unit travel calculation.

Store durations in seconds and display them with explicit units or an unambiguous minutes:seconds format. Compute differences between resolved instants so midnight, multi-day incidents, and daylight-saving changes are handled correctly.

### 8.3 Statistics, targets, and exclusions

- Show median, 90th percentile, eligible sample size, and percentage meeting each configured target. Mean and additional percentiles may be supplemental.
- Define the percentile algorithm and behavior for empty, single-value, and small samples. Calculate target attainment using unrounded durations and an explicit inclusive target boundary.
- For each metric, show the candidate population, valid observations, and excluded/missing observations, with reasons. Calculate attainment only over eligible valid observations and show timestamp completeness separately.
- Flag negative, out-of-sequence, ambiguous, missing, and suspicious durations. Do not silently trim or replace outliers; retain valid unusually long responses unless an approved exclusion rule applies.
- Configure targets by metric and applicable incident/resource category with effective dates and a documented DFD policy source. Report `Target not configured` when absent.
- Do not label a result as compliance with an external standard unless DFD has identified the applicable standard, edition, population, and calculation rules and those rules have been implemented and verified.


## 9. Architecture and database

### 9.1 Separation of responsibilities

Use a small Python package with these responsibilities. Exact module names may be adjusted while preserving the boundaries:

| Component | Responsibility |
| --- | --- |
| CLI | Import, validate, launch, and expose documented maintenance operations |
| Ingestion | Parse exports, preserve lineage, normalize, reconcile, and report quality |
| Storage | SQLite access, schema constraints, migrations, and transactions |
| Analytics | Shared filters, counting rules, and aggregations; future duration calculations can be added separately |
| Dashboard | Layout, callbacks, charts, tables, and user-facing states |
| Configuration | Paths, mappings, timezone rules, categories, and current analytical/display thresholds |

Keep analytical functions independent of Dash so they can be tested against small verified fixtures. Callbacks must not mutate shared datasets or perform imports or external geocoding. Cache only where needed, using data/configuration versions and filters to prevent stale results.

### 9.2 Logical data model

The database must represent:

- Import batches/files, source rows, validation outcomes, and lineage.
- Canonical incidents with verified identity, source values, normalized values, and status.
- Apparatus identities, company aliases/mappings, and incident-apparatus participation.
- Locations and coordinate provenance/validation.
- Conflicting record versions, resolution decisions, and correction history.
- Schema version and analytical/configuration versions needed to reproduce results.

Per-unit operational timestamps and response-target history are excluded from the current schema requirements. Add them through documented migrations only if the future extension is undertaken. Their absence must not prevent imports or database validation.

Use foreign keys, appropriate uniqueness constraints, and indexes supporting common date, shift, incident-type, unit, and location queries. A flattened apparatus string may be retained as source data but must not be the analytical relationship model.

Keep the default database under `data/` and reports/exports under documented project subdirectories. Do not commit operational records, generated databases, exports, or sensitive logs to a source repository. Include schema migrations and verify backup/restore before applying destructive migrations.

## 10. Operating requirements

- Package dependencies reproducibly and document installation on the intended macOS environment. Use project-relative resources so installation is not tied to the current user's absolute path.
- Keep source exports and databases accessible only to authorized users through appropriate local filesystem permissions. Shared/network deployment requires a separate access-control and hosting design before enabling it.
- Exclude patient information and unnecessary personal details from dashboard views and exports. Document which incident-level fields remain available to authorized users.
- Document external network dependencies and which data is sent to them. Local imports and non-map analysis must work without external services.
- Log import outcomes and actionable application errors without unnecessarily reproducing sensitive incident details. Document log locations and retention settings.
- Support a consistent SQLite backup while the application is in use, or document a required shutdown procedure. Demonstrate restoration to a separate database before release.
- Use responsive charts and readable contrast. Provide visible labels, keyboard-operable controls, and tabular access to important chart values.
- Proposed MVP performance targets: initial dashboard display within 5 seconds and typical filter updates within 2 seconds after warm-up for the reviewed dataset. Before sign-off, record the test machine, dataset size, network conditions, and measurements, and confirm or revise these targets with DFD.

## 11. Tests and acceptance criteria

Use a test suite appropriate to the implemented behavior, with small synthetic or deidentified fixtures whose expected results are independently calculated. Automated tests must not depend on live geocoding, a production database, or unrestricted network access.

### 11.1 Current release acceptance

- A clean environment can install dependencies, import the supplied files, and launch the documented entry point.
- The root `pyproject.toml` provides valid project/build metadata, runtime and development dependency declarations, CLI entry-point configuration, and Ruff settings. The documented reproducible installation workflow installs the application and development tools successfully.
- `ruff check .` and `ruff format --check .` both exit successfully over maintained Python code using the recorded Ruff version and project configuration.
- Import reports reconcile to source rows. The baseline duplicates and identifier conflict are detected and their treatment is visible; totals change only according to documented reconciliation decisions.
- Reimporting unchanged files and overlapping exports leaves canonical incident and unit-response totals unchanged.
- Corrected records follow the resolution policy; invalid files, invalid rows, and failed transactions leave a recoverable and consistent database.
- Verified fixtures produce exact expected incident counts, unit counts, first-arrival counts, category shares, and location totals.
- Combined filters, overnight ranges, date boundaries, multi-year dates, season boundaries, missing values, and unknown apparatus behave as specified.
- Every dashboard output and export reconciles under the same filters and data version. A multi-apparatus incident is not multiplied in incident-level summaries.
- Missing/invalid coordinates remain absent from spatial plots while incidents remain in non-map totals. Mapping coverage is correct.
- Empty datasets, empty selections, missing coordinate caches, stale location selections, and unavailable external maps show useful states without crashing the application.
- The dashboard explains the known timestamp-access limitation without showing duration metrics or target-attainment results. Importing and using the accessible exports requires no duration fields, response targets, or access to restricted reports. First-arriving apparatus counts are labeled as counts, not speed measurements.
- Representative UI checks verify that all views load, filters update connected outputs, incident details are reachable, and exports can be produced.
- Manual visual review confirms the preferred appearance, usable resizing, readable labels, and absence of misleading period descriptions.
- Documented backup/restore works, performance results are recorded, and all required automated checks pass.

### 11.2 Future extension acceptance reference

These criteria apply only to a separately scoped response-performance extension and do not block the current release:

- DFD-approved fixtures verify every implemented interval, eligibility rule, percentile, target boundary, and denominator.
- Tests cover midnight and daylight-saving transitions, multi-day incidents, missing/out-of-order timestamps, cancellations, multiple units, tied arrivals, and valid long durations.
- Incident-level first-arrival metrics use qualifying resources and one value per incident; unit-level metrics use timestamps from the same unit response.
- Eligible, excluded, and missing observations reconcile to the candidate population. No exclusion or outlier treatment is hidden.
- DFD reviews source field mappings and representative results before response-performance features are accepted for operational use.

## 12. Implementation sequence, documentation, and self-checking

### 12.1 Work sequence

1. Audit existing code, CSVs, coordinates, dependencies, and visual behavior. Produce a data-profile report and capture reference screenshots.
2. Establish incident identity, reconcile the known conflict, document source-field semantics, and record unresolved decisions. Continue independent work using the safe defaults in Section 13.
3. Create `README.md`, `pyproject.toml`, reproducible dependency files, Ruff configuration, runtime configuration, and the single-entry-point architecture.
4. Implement SQLite schema/migrations, validated imports, lineage, duplicate handling, and import reports.
5. Implement and verify shared filters, counting rules, and analytics against independently checked fixtures.
6. Implement dashboard views, incident detail, data-quality reporting, and exports while preserving the preferred visual style.
7. Complete Ruff lint/format checks, functional tests, visual review, performance measurement, and backup/restore verification; resolve defects.
8. Complete current-release documentation and release notes. Deliver the incident-analysis MVP without waiting for timestamp access. Keep any future response-performance work in an unscheduled backlog, outside the current implementation tasks and completion criteria.

### 12.2 Required documentation

- `README.md`: purpose, supported environment, reproducible runtime/development installation, import/launch commands, Ruff check/fix/format commands, functional test commands, and quick start.
- `docs/architecture.md`: component boundaries, database model, migrations, configuration, and design decisions.
- `docs/data_dictionary.md`: source/normalized fields, timestamp meanings, identity rules, aliases, category mappings, and coverage assumptions.
- `docs/metrics.md`: current counting rules, filters, category shares, denominators, and exclusions. Document unavailable duration analysis as a known source-access limitation; keep provisional future interval definitions clearly separate from implemented metrics.
- `docs/operations.md`: importing corrected data, resolving conflicts, coordinate maintenance, troubleshooting, backups/restoration, and access/network considerations.
- `docs/validation.md`: fixture expectations, executed checks, visual review, performance environment/results, and release acceptance evidence.
- Release notes and a known-limitations list identifying unavailable analyses and unresolved department decisions.

Documentation must describe implemented behavior and provide commands that have actually been verified.

### 12.3 Self-checking loop and completion

For each task:

1. Identify the applicable acceptance criteria and dependencies.
2. Implement the smallest coherent change satisfying those criteria.
3. Run `ruff check .`, `ruff format --check .`, and relevant functional tests for Python changes; for interface changes, also inspect the affected views. Documentation-only changes require a document review rather than unrelated code checks.
4. Compare outputs with independent expected values or documented requirements.
5. Correct failures and repeat affected checks until they pass.
6. Record the outcome and any remaining dependency or limitation.

Do not treat an unavailable source field or unresolved DFD policy as something repeated code changes can solve. Record the dependency, keep affected results unavailable or clearly qualified, and continue work that does not depend on it. Response-timestamp access is an accepted limitation outside current scope, not an unfinished task. The current release is complete when its applicable acceptance criteria are met or DFD explicitly approves a documented scope change.

## 13. Department decisions and interim defaults

Resolve current-scope questions before relying on the affected analyses. Interim defaults allow independent MVP work to continue without inventing operational policy. Questions about unavailable response timestamps, qualifying timed arrivals, and response-time targets are deferred and do not block current work.

| Decision required | Interim behavior |
| --- | --- |
| Incident identifier uniqueness and the conflicting baseline record | Preserve all source versions; quarantine unresolved identity; disclose exclusions |
| Meaning/timezone of the accessible incident timestamp | Preserve raw values; label the incident timestamp as source-reported; flag unresolved time assumptions |
| Report status eligibility and handling of incomplete reports | Include reconciled records across statuses for exploratory demand analysis, expose status filtering, and clearly label the population |
| Apparatus parsing, company aliases, reserves, and mutual-aid scope | Validate parsing against representative multi-unit rows; retain source identifiers and unknowns; do not infer unverified company assignments |
| Station meaning and geographic district boundaries | Display source station separately; provide no inferred district analysis |
| Shift meaning, rotation, and operational-day boundaries | Use source-reported shift only |
| Incident category mappings, seasons, and small-sample thresholds | Use original categories and monthly trends until configurable rules are documented; always show sample sizes |
| Future timed-arrival eligibility, operational exclusions, and response targets | Defer until suitable timestamps are available and an extension is scoped; retain source-reported first-apparatus counts now |
| Future access to full timestamp reports | No access timeline; record the known limitation and complete the MVP using accessible exports; no acquisition task or release dependency |
| Export coverage and refresh frequency | Require explicit imports; display last import and observed bounds without claiming complete coverage |
| Target-hazard criteria and supporting risk sources | Provide repeat-location/property-type analysis without official hazard designation |
| Deployment audience and export access | Localhost operation using authorized local files; defer shared hosting |
| Final performance environment and targets | Measure against the proposed targets in Section 10 and document results before sign-off |
