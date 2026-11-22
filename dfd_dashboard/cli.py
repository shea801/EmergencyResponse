"""Supported local command line interface."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from dfd_dashboard.analytics import load_snapshot
from dfd_dashboard.config import ROOT, database_path
from dfd_dashboard.ingestion import import_path, refresh_coordinates
from dfd_dashboard.storage import backup_database, connect, resolve_identity


def _project_path(path: Path) -> Path:
    return path.expanduser() if path.is_absolute() else ROOT / path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="dfd-dashboard")
    result.add_argument("--database", type=Path, help="Override the project database")
    commands = result.add_subparsers(dest="command", required=True)
    source = commands.add_parser("import", help="Import one CSV or a directory of exports")
    source.add_argument("path", type=Path, nargs="?", default=ROOT / "incident_reports")
    commands.add_parser("audit", help="Print reconciled database counts")
    commands.add_parser("issues", help="Print invalid-row and mapping issues as JSON lines")
    commands.add_parser("refresh-coordinates", help="Reapply the local address cache")
    server = commands.add_parser("serve", help="Run the localhost dashboard")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8050)
    resolution = commands.add_parser("resolve", help="Choose an audited source version")
    resolution.add_argument("identity")
    resolution.add_argument("source_row_id", type=int)
    resolution.add_argument("--reason", required=True)
    backup = commands.add_parser("backup", help="Create a consistent SQLite backup")
    backup.add_argument("target", type=Path)
    restore = commands.add_parser("restore-check", help="Check a separate restored database")
    restore.add_argument("path", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    path = _project_path(args.database) if args.database else database_path()
    if args.command == "restore-check":
        restored_path = _project_path(args.path)
        if not restored_path.exists():
            raise FileNotFoundError(f"Restore candidate not found: {restored_path}")
        with sqlite3.connect(restored_path) as restored:
            result = restored.execute("PRAGMA integrity_check").fetchone()[0]
            count = restored.execute("SELECT count(*) FROM incidents").fetchone()[0]
        print(json.dumps({"integrity": result, "incidents": count}))
        return 0 if result == "ok" else 1
    with closing(connect(path)) as connection:
        if args.command == "import":
            for report in import_path(connection, _project_path(args.path)):
                print(json.dumps(report, sort_keys=True))
        elif args.command == "audit":
            snapshot = load_snapshot(connection)
            print(
                json.dumps(
                    {
                        **snapshot.quality,
                        "canonical_incidents": len(snapshot.incidents),
                        "unit_responses": len(snapshot.responses),
                        "data_version": snapshot.version,
                        "last_successful_import": snapshot.last_import,
                    },
                    indent=2,
                )
            )
        elif args.command == "issues":
            for row in connection.execute(
                """SELECT filename,row_number,identity_key,validation_status,issues_json
                   FROM source_rows WHERE validation_status='invalid' OR issues_json!='[]'
                   ORDER BY id"""
            ):
                print(
                    json.dumps(
                        {
                            "file": row["filename"],
                            "row": row["row_number"],
                            "incident": row["identity_key"],
                            "status": row["validation_status"],
                            "issues": json.loads(row["issues_json"]),
                        }
                    )
                )
        elif args.command == "refresh-coordinates":
            print(json.dumps(refresh_coordinates(connection)))
        elif args.command == "resolve":
            resolve_identity(connection, args.identity, args.source_row_id, args.reason)
            print(f"Resolved {args.identity} to source row {args.source_row_id}")
        elif args.command == "backup":
            backup_database(connection, _project_path(args.target))
            print(f"Backup saved: {_project_path(args.target)}")
        elif args.command == "serve":
            from dfd_dashboard.dashboard import create_app

            app = create_app(path)
            app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
