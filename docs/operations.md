# Local operation and recovery

## Import and correction

Use `dfd-dashboard import incident_reports` for the supplied directory or `dfd-dashboard import '/path/to/incident_reports 22.csv'` for one file. Directory discovery accepts `Incident Report*.csv` and `incident_reports*.csv` case-insensitively, including the supplied double-period filename. Other CSV names are ignored during directory imports; explicit single-file imports validate their headers regardless of filename. Input files remain read-only.

Each successful file report reconciles its `source_rows` to `new_candidates + duplicates + enrichments + conflict_versions + invalid_rows`. `new_candidates` means the first accepted version for an identity, even if a later version in the same import makes that identity unresolved. `enrichments` identifies a compatible source providing fields absent from earlier exports. `duplicates` includes a reduced export already covered by an existing detailed record, even when date formatting differs. Importer version 1.1.0 adds `source_format`, `unavailable_columns`, and `enrichments`; earlier reports lack these keys. `updates` remains reserved; manual resolutions are recorded separately. `canonical_added` and `canonical_removed_due_to_conflict` show changes to analytical membership. Import attempts are retained; failed headers or encoding are logged as rejected attempts with no canonical change. Source row numbers count the CSV header as line 1.

Summary exports use `INCIDENT` instead of `INCIDENT NUMBER` and do not supply final incident type, property type, apparatus participation, or station. These absent columns do not create conflicts or clear existing detailed values. Compatible overlaps select the richer source row regardless of import order. Supplied empty values remain explicit observations: differences in shared status, location, date/time, first unit, or shift still create conflicts. Personnel/editor columns are retained only in restricted raw source lineage, not analytical comparisons, dashboard records, or exports. See the [data dictionary](data_dictionary.md) for required columns and missing-data behavior.

The import uses a SQLite write lock and one transaction per file. Do not run multiple import commands concurrently or use the database from a network share. Accepted records, source lineage, and report commit together. A later file omitting an incident does not delete it. Corrected records with changed content are staged as conflicting candidates; they do not overwrite canonical data automatically.

The Data quality view shows recent row issues. For every source-row issue with file and CSV row context, run `mkdir -m 700 -p logs` and then `dfd-dashboard issues > logs/import-issues.jsonl`. This output omits raw addresses and patient details; original exports remain the correction reference.

The Data quality view lists every conflict candidate with `source_row_id`, filename, and CSV row. Have an authorized reviewer compare the original export records, then record the choice and reason:

```sh
dfd-dashboard backup data/before-resolution.sqlite3
dfd-dashboard resolve DFC-26-000740 7804 --reason 'Reviewed against authoritative First Due record on YYYY-MM-DD'
dfd-dashboard audit
```

The ID `7804` is an example from the initial local import and may differ after rebuilding a database. Verify it in the current dashboard before running the command. Every resolution is stored with UTC decision time and reason; a subsequent correction needs a new explicit resolution. Do not use file modification time to choose versions. Confirm the required identity scope with DFD before treating this as an official incident register.

## Coordinates

`latitude_longitude_addresses.json` is a preexisting local cache of uncertain provenance. To maintain it, preserve a copy, review addresses and coordinate differences, edit the cache only after source validation, then run `dfd-dashboard refresh-coordinates`. This reapplies exact normalized-address matches and bumps the data version. The dashboard refreshes results and filter choices every 30 seconds; reload the page for an immediate refresh after imports. No geocoding provider is configured. The viewing browser requests road tiles from OpenStreetMap using map area and zoom level; it does not send incident records or address text in those tile requests. Internet access is required to see roads. If tiles are unavailable, the heat layer and non-map analysis remain, with a visible tile-dependency note. The optional Bootstrap stylesheet request to a CDN carries a routine HTTP request for CSS, not incident rows.

## Backup and restore

The SQLite backup command uses SQLite's online backup API, so the dashboard can remain open:

```sh
dfd-dashboard backup data/backup-YYYY-MM-DD.sqlite3
dfd-dashboard restore-check data/backup-YYYY-MM-DD.sqlite3
```

Store backups with mode 0600 in a restricted directory. A restore should be rehearsed into a **separate** path: copy the chosen backup to `data/restore-check.sqlite3`, run `dfd-dashboard restore-check data/restore-check.sqlite3`, compare `dfd-dashboard --database data/restore-check.sqlite3 audit` to the expected backup snapshot, and only then schedule replacement of the active database while the server is stopped. Preserve the previous active database until validation finishes. Back up before schema changes or resolutions. `data/`, `exports/`, and source reports must be accessible only to authorized local users; do not put them in a public web folder.

## Access, logs, and troubleshooting

The CLI serves on `127.0.0.1:8050` with debug off. This is a local authorized-user design without application accounts. Do not bind to a public interface or share the database without an access-control and hosting review. Dashboard detail and export contain incident number, time, classification, source location, apparatus, station, report status, and source lineage; patient information and personnel details are not displayed. Browser downloads should be moved into approved storage and removed from shared Downloads when no longer needed.

CLI import results go to standard output and errors to standard error. No persistent log is created by default. To retain a restricted operational log, redirect into `logs/`, set directory permissions to 0700, and review/delete logs after 30 days unless department policy requires a different period; no automatic rotation is configured. The app does not log raw patient details. If a file fails, check required header names, UTF-8 encoding, the printed row issue, available disk space, and database permissions. If heat appears without roads, check internet access to OpenStreetMap tile servers in the viewing browser. If an incident is absent from the heatmap, inspect Data quality for `missing`, `cache_conflict`, or `out_of_area` coordinates and review the cache. If filters yield no results, reset them and check the observed date bounds. If dependencies fail, reinstall from `pyproject.toml` and `constraints.txt` in the configured environment.
