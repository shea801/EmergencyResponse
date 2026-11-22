# Architecture

`dfd-dashboard` is the CLI entry point. `ingestion` validates CSV rows, `storage` manages SQLite and numbered migrations, `analytics` applies shared filters and counts, and `dashboard` renders the seven Dash views. `config/dashboard.json` holds timezone, unit aliases, and display thresholds.

The importer retains original source rows and reconciles repeated or compatible exports into one canonical incident per identifier. Conflicting values exclude that identifier until a source version is explicitly selected. Incident and apparatus counts are derived from the same filtered snapshot used by charts and downloads.

The map weights each validated location by its distinct incident count. Plotly blends points with a 10 pixel radius over OpenStreetMap road tiles. Browser tile requests describe the viewport, while Dash sends filtered records to the viewer's browser.

The portfolio path is isolated: [`demo/generate_fixtures.py`](../demo/generate_fixtures.py) invents the CSV and coordinates, and `dfd-dashboard demo` builds `data/portfolio-demo.sqlite3` with a synthetic marker. It refuses an existing unmarked database. The ordinary `serve` command refuses a non-local host; the default operational database and generated demo database are ignored by Git.

SQLite supports the local single-user workflow. Public hosting should point only to the synthetic demo and be reviewed separately for server capacity and access controls.
