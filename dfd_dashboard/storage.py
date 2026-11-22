"""SQLite schema, connection policy, and canonical record reconciliation."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dfd_dashboard.config import database_path, settings
from dfd_dashboard.source_formats import comparison_values, covers, has_conflict, versions

SCHEMA = Path(__file__).parent / "migrations" / "001_initial.sql"
MIGRATION_2 = Path(__file__).parent / "migrations" / "002_import_versions.sql"
MIGRATION_3 = Path(__file__).parent / "migrations" / "003_resolution_watermark.sql"
SCHEMA_VERSION = 3


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA journal_mode=WAL")
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'"
    ).fetchone():
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    version = int(
        connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
    )
    if version < 2:
        connection.executescript(MIGRATION_2.read_text(encoding="utf-8"))
    if version < 3:
        connection.executescript(MIGRATION_3.read_text(encoding="utf-8"))
    if version > SCHEMA_VERSION:
        connection.close()
        raise RuntimeError(f"Database schema {version} is newer than supported {SCHEMA_VERSION}")
    if path.exists():
        os.chmod(path, 0o600)
    return connection


def data_version(connection: sqlite3.Connection) -> int:
    return int(
        connection.execute("SELECT value FROM metadata WHERE key='data_version'").fetchone()[0]
    )


def bump_version(connection: sqlite3.Connection) -> None:
    connection.execute(
        "UPDATE metadata SET value=CAST(value AS INTEGER)+1 WHERE key='data_version'"
    )


def rebuild_identity(connection: sqlite3.Connection, identity_key: str) -> str:
    """Select one verified version or keep a disputed identity outside analytics."""
    candidates = versions(connection, identity_key)
    resolution = connection.execute(
        """SELECT source_row_id,source_row_watermark FROM resolutions
           WHERE identity_key=? ORDER BY id DESC LIMIT 1""",
        (identity_key,),
    ).fetchone()
    chosen = None
    if resolution:
        # Fetch the exact reviewed row even if it is a duplicate of an earlier version.
        selected = connection.execute(
            "SELECT * FROM source_rows WHERE id=? AND identity_key=?",
            (resolution[0], identity_key),
        ).fetchone()
        known = [values for row, values in candidates if row["id"] <= resolution[1]]
        newer = [
            (row, values)
            for row, values in candidates
            if row["id"] > resolution[1] and not any(covers(old, values) for old in known)
        ]
        candidates = (
            [
                (
                    selected,
                    comparison_values(
                        json.loads(selected["raw_json"]), json.loads(selected["normalized_json"])
                    ),
                ),
                *newer,
            ]
            if selected
            else []
        )
    if candidates and not has_conflict(candidates):
        # Both layouts are nested schemas: a compatible detailed export preserves all fields.
        chosen = max(candidates, key=lambda item: len(item[1]))[0]
    connection.execute("DELETE FROM incidents WHERE identity_key=?", (identity_key,))
    if not chosen:
        return "conflict" if candidates else "invalid"
    value = json.loads(chosen["normalized_json"])
    location = value["location_key"]
    if location:
        connection.execute(
            "INSERT OR IGNORE INTO locations(location_key,display_name,validation_status) "
            "VALUES (?,?, 'missing')",
            (location, value["location_raw"]),
        )
    connection.execute(
        """INSERT INTO incidents(
            identity_key,source_row_id,source_timestamp,local_timestamp,utc_timestamp,
            timestamp_issue,status,dispatch_type,first_unit,first_unit_mapped,
            location_raw,location_key,shift,incident_type,property_type,apparatus_raw,station
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            identity_key,
            chosen["id"],
            value["source_timestamp"],
            value["local_timestamp"],
            value["utc_timestamp"],
            value["timestamp_issue"],
            value["status"],
            value["dispatch_type"],
            value["first_unit"],
            int(value["first_unit_mapped"]),
            value["location_raw"],
            location,
            value["shift"],
            value["incident_type"],
            value["property_type"],
            value["apparatus_raw"],
            value["station"],
        ),
    )
    companies = settings()["company_mappings"]
    for unit in value["units"]:
        connection.execute(
            "INSERT INTO apparatus(label,mapped,company) VALUES (?,?,?) "
            "ON CONFLICT(label) DO UPDATE SET mapped=excluded.mapped,company=excluded.company",
            (unit["label"], int(unit["mapped"]), companies.get(unit["label"])),
        )
        connection.execute(
            "INSERT INTO participations(identity_key,apparatus_label) VALUES (?,?)",
            (identity_key, unit["label"]),
        )
    return "accepted"


def resolve_identity(
    connection: sqlite3.Connection, identity_key: str, source_row_id: int, reason: str
) -> None:
    candidate = connection.execute(
        "SELECT id FROM source_rows WHERE id=? AND identity_key=? AND validation_status='accepted'",
        (source_row_id, identity_key),
    ).fetchone()
    if not candidate:
        raise ValueError("Source row is not an accepted version of this incident identity")
    if not reason.strip():
        raise ValueError("Resolution reason is required")
    connection.execute("BEGIN IMMEDIATE")
    try:
        watermark = connection.execute(
            "SELECT max(id) FROM source_rows WHERE identity_key=? AND validation_status='accepted'",
            (identity_key,),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO resolutions(
                identity_key,source_row_id,source_row_watermark,decided_at,reason
            ) VALUES (?,?,?,?,?)""",
            (
                identity_key,
                source_row_id,
                watermark,
                datetime.now(timezone.utc).isoformat(),
                reason.strip(),
            ),
        )
        rebuild_identity(connection, identity_key)
        bump_version(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def backup_database(connection: sqlite3.Connection, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists():
        raise FileExistsError(f"Backup already exists: {target}")
    with sqlite3.connect(target) as output:
        connection.backup(output)
    os.chmod(target, 0o600)
