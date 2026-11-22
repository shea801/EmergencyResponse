"""Supported export layouts and comparisons of fields each source actually supplies."""

from __future__ import annotations

import json
import sqlite3

REQUIRED_COLUMNS = (
    "INCIDENT NUMBER",
    "INCIDENT DATE/TIME",
    "STATUS",
    "DISPATCH TYPE",
    "1ST ARRIVING",
    "INCIDENT LOCATION",
    "SHIFT",
    "INCIDENT TYPE",
    "PROPERTY TYPE",
    "APPARATUS",
    "STATION",
)
SUMMARY_COLUMNS = REQUIRED_COLUMNS[:7]
FILE_PATTERNS = ("incident report*.csv", "incident_reports*.csv")
FIELD_KEYS = {
    "STATUS": "status",
    "DISPATCH TYPE": "dispatch_type",
    "1ST ARRIVING": "first_unit",
    "INCIDENT LOCATION": "location_raw",
    "SHIFT": "shift",
    "INCIDENT TYPE": "incident_type",
    "PROPERTY TYPE": "property_type",
    "STATION": "station",
}


def canonical_header(header: str) -> str:
    header = header.strip().upper()
    return "INCIDENT NUMBER" if header == "INCIDENT" else header


def canonical_row(raw: dict) -> dict:
    return {canonical_header(key): value for key, value in raw.items() if key is not None}


def validate_headers(headers: list[str]) -> tuple[str, list[str], list[str]]:
    canonical = [canonical_header(header) for header in headers]
    if len(canonical) != len(set(canonical)):
        raise ValueError("duplicate CSV header names after alias/whitespace normalization")
    summary = any(header.strip().upper() == "INCIDENT" for header in headers)
    required = SUMMARY_COLUMNS if summary else REQUIRED_COLUMNS
    missing = sorted(set(required) - set(canonical))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    extra = [header for header in headers if canonical_header(header) not in REQUIRED_COLUMNS]
    unavailable = sorted(set(REQUIRED_COLUMNS) - set(canonical))
    return "summary" if summary else "detailed", extra, unavailable


def comparison_values(raw: dict, normalized: dict) -> dict:
    """Absent columns are unknown; supplied empty values remain explicit observations."""
    supplied = canonical_row(raw)
    values = {field: normalized[key] for field, key in FIELD_KEYS.items() if field in supplied}
    if "INCIDENT DATE/TIME" in supplied:
        # Date formatting changes are not changes in the reported event's wall-clock time.
        values["INCIDENT DATE/TIME"] = (
            normalized["local_timestamp"] or normalized["source_timestamp"],
            normalized["utc_timestamp"],
            normalized["timestamp_issue"],
        )
    if "APPARATUS" in supplied:
        values["APPARATUS"] = tuple(sorted(unit["label"] for unit in normalized["units"]))
    return values


def compatible(left: dict, right: dict) -> bool:
    return all(left[key] == right[key] for key in left.keys() & right.keys())


def covers(left: dict, right: dict) -> bool:
    """Whether left already contains all observations supplied by right."""
    return right.keys() <= left.keys() and compatible(left, right)


def versions(connection: sqlite3.Connection, identity: str) -> list[tuple[sqlite3.Row, dict]]:
    rows = connection.execute(
        "SELECT * FROM source_rows WHERE identity_key=? AND validation_status='accepted' "
        "ORDER BY id",
        (identity,),
    ).fetchall()
    # Repeated exports and personnel-only edits must not create analytical versions.
    unique = {}
    for row in rows:
        if row["fingerprint"] not in unique:
            unique[row["fingerprint"]] = (
                row,
                comparison_values(json.loads(row["raw_json"]), json.loads(row["normalized_json"])),
            )
    return list(unique.values())


def has_conflict(candidates: list[tuple[sqlite3.Row, dict]]) -> bool:
    observed = {}
    for _, values in candidates:
        if not compatible(observed, values):
            return True
        observed.update(values)
    return False


def conflicting_identities(connection: sqlite3.Connection) -> set[str]:
    candidates = connection.execute(
        """SELECT identity_key FROM source_rows WHERE validation_status='accepted'
           GROUP BY identity_key HAVING count(DISTINCT fingerprint)>1"""
    ).fetchall()
    return {row[0] for row in candidates if has_conflict(versions(connection, row[0]))}
