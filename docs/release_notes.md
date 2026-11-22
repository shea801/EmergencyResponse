# Release notes

## October 26, 2026 — additional export layout

- Recognize `Incident Report*.csv` and `incident_reports*.csv` case-insensitively, including the supplied double-period filename.
- Accept the summary `INCIDENT` header and omitted final incident type, property type, apparatus list, and station. Preserve original source values and personnel/editor metadata only in restricted raw lineage.
- Reconcile compatible overlaps across layouts and date formats without duplicating incidents or losing detailed fields. Keep genuine shared-field disagreements unresolved and preserve explicit resolution history.
- Include source format, unavailable columns, and compatible enrichments in importer 1.1.0 reports. Show missing-field coverage in dashboard context and export metadata, and include first-only units in filter choices without fabricating participation.
- Verified the 33 supplied files against a database copy, repeated their import without analytical changes, and backed up the active database before importing them. Current totals and conflicts are recorded in the [data profile](data_profile.md).

## 1.0.0 — incident-analysis MVP candidate

- Added a single local CLI, SQLite import and reconciliation, immutable source-row lineage, explicit conflict resolution, quality reporting, backup, and coordinate refresh.
- Added shared date, hour, weekday, month, season, shift, apparatus/company, classification, status, location, and text filters across seven dashboard views and filtered ZIP exports.
- Preserved a dark SUPERHERO-style card and chart layout. Earlier implementations are archived under `legacy/` and are no longer entry points.
- Placed a weighted incident-concentration heatmap beside the main statistics, added OpenStreetMap road tiles, and moved secondary filters into a collapsed **More filters** section.
- Added synthetic fixture tests, Ruff configuration, pinned dependency constraints, and operating documentation.
- Response-duration functionality is intentionally absent because the required timing reports are inaccessible at the project owner's current First Due level.

This is a candidate pending the outstanding department decisions and release checks listed in [known limitations](known_limitations.md) and [validation](validation.md).
