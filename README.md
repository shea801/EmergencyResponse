# Danbury Fire Department incident analysis

Local Dash dashboard for exploratory analysis of the accessible First Due incident exports. It counts reconciled incidents and distinct incident–apparatus participations, and shows incident classifications, source-reported time patterns, shifts, locations, incident detail, and data quality. The dashboard does **not** measure response duration or target attainment because the required First Due timing reports are outside the project owner's current access.

## Quick start on macOS

Use Python 3.11 through 3.14. Python 3.14.3 and the versions in `constraints.txt` were exercised in this project. From the project root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -c constraints.txt -e '.[dev]'
.venv/bin/dfd-dashboard import incident_reports
.venv/bin/dfd-dashboard audit
.venv/bin/dfd-dashboard serve
```

Open <http://127.0.0.1:8050/>. `serve` binds to localhost and disables Dash debug mode. Keep the terminal running while using the dashboard. An explicit database can be selected with `--database /path/to/database.sqlite3` before the subcommand, or with `DFD_DB_PATH`; relative paths resolve from the project root. Source, configuration, and asset paths do not depend on the shell's working directory. Imports are explicit; the dashboard does not watch the export directory.

The same installation without test tools is `.venv/bin/python -m pip install -c constraints.txt -e .`. Update dependency bounds in `pyproject.toml` and verified pins in `constraints.txt` together. The pinned installation passed `pip check` and the test suite in a fresh Python 3.14.3 environment. Python 3.11 execution remains a release check.

## Daily use

```sh
.venv/bin/dfd-dashboard import incident_reports
.venv/bin/dfd-dashboard audit
.venv/bin/dfd-dashboard backup data/backup-2026-10-25.sqlite3
.venv/bin/dfd-dashboard restore-check data/backup-2026-10-25.sqlite3
```

`import` accepts one CSV path or a directory containing `Incident Report*.csv` and `incident_reports*.csv` files (case-insensitive), and prints one JSON report per file. This includes names such as `incident_reports 27..csv`. Repeating an unchanged import changes only attempt history. After the October 26, 2026 upload, all 33 files produce 14,131 canonical incidents and 17,283 reported unit responses; 17 disputed incident identifiers are excluded until a department reviewer selects source versions. See [operations](docs/operations.md) and the dated [data profile](docs/data_profile.md).

The new summary layout uses `INCIDENT` (with optional surrounding whitespace) for the incident number and omits final incident type, property type, full apparatus participation, and station. Matching overlaps preserve those details from compatible older exports; different date text representing the same local time does not create a conflict. New incidents remain included with omitted fields unknown. A first-arriving unit is not substituted for a complete participation list, and dispatch type is not substituted for final incident type. The dashboard and export metadata show field-completeness counts; unit participation filters cover only incidents with reported participation, while first-arrival mode uses the reported first unit.

Use the date, shift, and apparatus controls at the top of every view; open **More filters** for hour, classification, location, and other selections. The incident-concentration heatmap stays beside the main statistics as filters or views change. The download button creates a ZIP with filtered incident, unit-response, and summary CSVs plus metadata for the data version, filters, definitions, and exclusions. CSV cells that could execute as spreadsheet formulas are escaped. The incident detail includes location, incident classification, shift, apparatus, report status, source station, and source file/row; it does not include patient fields. Keep exports within authorized local storage.

## Development checks

After activating `.venv`, run:

```sh
ruff check .
ruff format --check .
pytest -q
```

`ruff check --fix .` and `ruff format .` **modify** code; review their changes and rerun tests. The configured interpreter also supports `.venv/bin/python -m ruff ...` and `.venv/bin/python -m pytest -q`. Ruff covers maintained package code and tests, excluding archived exploratory implementations and notebooks.

## Project guide

- [Architecture](docs/architecture.md): component boundaries, schema, migrations, and configuration.
- [Data dictionary](docs/data_dictionary.md) and [data profile](docs/data_profile.md): source meanings and audited input quality.
- [Metrics](docs/metrics.md): counting, filters, shares, and exclusions.
- [Operations](docs/operations.md): corrected exports, conflict resolution, coordinate maintenance, backup and restoration.
- [Validation](docs/validation.md): fixture expectations, checks, and release evidence.
- [Release notes](docs/release_notes.md) and [known limitations](docs/known_limitations.md).

The existing coordinate cache is used only with exact normalized address matches. Its provenance is unverified. No geocoding request is sent by the application. The Bootstrap SUPERHERO stylesheet comes from a third-party CDN when online; if unavailable, the local CSS still keeps the dashboard functional. Road tiles for the heatmap come from OpenStreetMap and require internet access in the viewing browser. Tile requests include the map area and zoom level, not incident records or address text. Without tile access, the heat layer and non-map analysis remain available, but roads may be blank. Dash and Plotly assets are served locally. See [operations](docs/operations.md) for local access controls.
