# Synthetic portfolio dataset

Every incident, identifier, place label, timestamp, category, and coordinate in this directory is invented by `generate_fixtures.py`. The script reads no operational data and makes no network requests. The coordinates form a regular grid near the dashboard's default map center; `DEMO LOCATION` labels are not street addresses or incident sites.

Run `python demo/generate_fixtures.py` only when intentionally regenerating the checked-in CSV and coordinate JSON. From the project root, use `.venv/bin/dfd-dashboard demo` to build `data/portfolio-demo.sqlite3` on first run and serve it at <http://127.0.0.1:8050/>. The generated database is ignored by Git. The demo command refuses an existing database unless it carries the synthetic marker. To rebuild the demo after changing its inputs, delete only `data/portfolio-demo.sqlite3` and run the demo command again.

Use this command for portfolio screenshots and any public presentation. The ordinary `serve` command may load the local operational database and refuses a non-local host. A reverse proxy or tunnel can still expose a localhost service, so point any public deployment only at the marked demo database.
