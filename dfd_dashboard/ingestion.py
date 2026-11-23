"""Validated CSV import with immutable source lineage and explicit conflict handling."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from zoneinfo import ZoneInfo

from dfd_dashboard.config import (
    ROOT,
    clean,
    location_key,
    settings,
    unit_label,
)
from dfd_dashboard.source_formats import (
    FILE_PATTERNS,
    canonical_row,
    comparison_values,
    compatible,
    covers,
    validate_headers,
    versions,
)
from dfd_dashboard.source_formats import (
    REQUIRED_COLUMNS as REQUIRED_COLUMNS,
)
from dfd_dashboard.storage import (
    SCHEMA_VERSION,
    bump_version,
    rebuild_identity,
)

IMPORTER_VERSION = "1.1.0"


def parse_timestamp(
    raw: str | None,
) -> tuple[str | None, str | None, str | None]:
    if not raw:
        return None, None, "missing timestamp"
    try:
        local = datetime.strptime(raw, "%b %d, %Y %H:%M:%S")
    except ValueError:
        try:
            local = datetime.fromisoformat(raw)
        except ValueError:
            return None, None, "malformed timestamp"
    if local.tzinfo is not None:
        return (
            local.astimezone(ZoneInfo(settings()["timezone"]))
            .replace(tzinfo=None)
            .isoformat(),
            local.astimezone(timezone.utc).isoformat(),
            None,
        )
    zone = ZoneInfo(settings()["timezone"])
    possible = []
    for fold in (0, 1):
        aware = local.replace(tzinfo=zone, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            possible.append(utc)
    if not possible:
        return local.isoformat(), None, "nonexistent local time"
    if possible[0] != possible[-1]:
        return local.isoformat(), None, "ambiguous local time"
    # The export does not identify its timezone. Do not assert a UTC instant for naive text.
    return local.isoformat(), None, None


def normalize_row(raw: dict) -> tuple[dict | None, list[str]]:
    raw = canonical_row(raw)
    issues: list[str] = []
    identity = clean(raw.get("INCIDENT NUMBER"))
    if not identity:
        return None, ["missing incident identifier"]
    timestamp = clean(raw.get("INCIDENT DATE/TIME"))
    local, utc, time_issue = parse_timestamp(timestamp)
    if time_issue:
        issues.append(time_issue)
    aliases = settings()["unit_aliases"]
    first, first_mapped = unit_label(raw.get("1ST ARRIVING"), aliases)
    apparatus_raw = clean(raw.get("APPARATUS"))
    units = {}
    for token in (apparatus_raw or "").split(","):
        label, mapped = unit_label(token, aliases)
        if label:
            units[label.upper()] = {"label": label, "mapped": mapped}
            if not mapped:
                issues.append(f"unmapped apparatus: {label}")
    if first and not first_mapped:
        issues.append(f"unmapped first-arriving apparatus: {first}")
    if "APPARATUS" in raw and first and first.upper() not in units:
        issues.append(
            "first-arriving apparatus absent from participation list"
        )
    location = clean(raw.get("INCIDENT LOCATION"))
    result = {
        "identity_key": identity,
        "source_timestamp": timestamp,
        "local_timestamp": local,
        "utc_timestamp": utc,
        "timestamp_issue": time_issue,
        "status": clean(raw.get("STATUS")),
        "dispatch_type": clean(raw.get("DISPATCH TYPE")),
        "first_unit": first,
        "first_unit_mapped": first_mapped,
        "location_raw": location,
        "location_key": location_key(location),
        "shift": clean(raw.get("SHIFT")),
        "incident_type": clean(raw.get("INCIDENT TYPE")),
        "property_type": clean(raw.get("PROPERTY TYPE")),
        "apparatus_raw": apparatus_raw,
        "station": clean(raw.get("STATION")),
        "units": sorted(units.values(), key=lambda item: item["label"]),
    }
    return result, sorted(set(issues))


def coordinate_index(path: Path | None = None) -> dict[str, dict]:
    """Use only exact normalized address matches; never match on event timestamp."""
    path = path or ROOT / settings()["coordinate_cache"]
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for item in data.values():
        key = location_key(item.get("ADDRESS"))
        try:
            lat, lon = float(item["LATITUDE"]), float(item["LONGITUDE"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            key
            and math.isfinite(lat)
            and math.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            grouped[key].append((lat, lon))
    result = {}
    for key, values in grouped.items():
        lat, lon = (
            statistics.median(v[0] for v in values),
            statistics.median(v[1] for v in values),
        )
        # Coordinate disagreements larger than roughly 60 m are withheld for review.
        consistent = all(
            abs(a - lat) <= 0.0005 and abs(b - lon) <= 0.0007
            for a, b in values
        )
        in_area = 41.25 <= lat <= 41.55 and -73.65 <= lon <= -73.30
        result[key] = {
            "latitude": lat if consistent else None,
            "longitude": lon if consistent else None,
            "validation_status": (
                "cache_conflict"
                if not consistent
                else "in_area"
                if in_area
                else "out_of_area"
            ),
        }
    return result


def import_file(
    connection: sqlite3.Connection, path: Path, coords: dict | None = None
) -> dict:
    path = path.resolve()
    blob = path.read_bytes()
    file_hash = hashlib.sha256(blob).hexdigest()
    try:
        content = blob.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        _record_rejection(
            connection,
            path.name,
            file_hash,
            "expected UTF-8/UTF-8-SIG encoding",
        )
        raise ValueError(
            f"{path.name}: expected UTF-8/UTF-8-SIG encoding"
        ) from error
    import io

    reader = csv.DictReader(io.StringIO(content, newline=""))
    headers = reader.fieldnames or []
    try:
        source_format, extra, unavailable = validate_headers(headers)
    except ValueError as error:
        _record_rejection(connection, path.name, file_hash, str(error))
        raise ValueError(f"{path.name}: {error}") from error
    rows = list(reader)
    coords = coords if coords is not None else coordinate_index()
    report = {
        "file": path.name,
        "hash": file_hash,
        "source_rows": len(rows),
        "new_candidates": 0,
        "updates": 0,
        "enrichments": 0,
        "duplicates": 0,
        "conflict_versions": 0,
        "invalid_rows": 0,
        "extra_columns": extra,
        "source_format": source_format,
        "unavailable_columns": unavailable,
        "importer_version": IMPORTER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "config_version": settings()["version"],
        "canonical_total": 0,
        "unresolved_identities": 0,
    }
    connection.execute("BEGIN IMMEDIATE")
    try:
        before = {
            row[0]
            for row in connection.execute("SELECT identity_key FROM incidents")
        }
        affected = set()
        existing_versions = {}
        for number, raw in enumerate(rows, start=2):
            prior_file_row = connection.execute(
                "SELECT id FROM source_rows WHERE filename=? AND file_hash=? AND row_number=?",
                (path.name, file_hash, number),
            ).fetchone()
            if prior_file_row:
                report["duplicates"] += 1
                continue
            invalid_shape = None in raw
            normalized, issues = (
                normalize_row(raw)
                if not invalid_shape
                else (None, ["extra CSV fields"])
            )
            identity = (
                normalized["identity_key"]
                if normalized
                else clean(canonical_row(raw).get("INCIDENT NUMBER"))
            )
            fingerprint_value = normalized
            if normalized and unavailable:
                fingerprint_value = {
                    **normalized,
                    "unavailable_columns": unavailable,
                }
            fingerprint = (
                hashlib.sha256(
                    json.dumps(fingerprint_value, sort_keys=True).encode()
                ).hexdigest()
                if normalized
                else None
            )
            if not normalized:
                classification = "invalid_rows"
            else:
                if identity not in existing_versions:
                    existing_versions[identity] = [
                        values for _, values in versions(connection, identity)
                    ]
                existing = existing_versions[identity]
                incoming = comparison_values(raw, normalized)
                classification = (
                    "duplicates"
                    if any(covers(values, incoming) for values in existing)
                    else "conflict_versions"
                    if any(
                        not compatible(values, incoming) for values in existing
                    )
                    else "enrichments"
                    if existing
                    else "new_candidates"
                )
                if classification != "duplicates":
                    existing.append(incoming)
            report[classification] += 1
            connection.execute(
                """INSERT INTO source_rows(
                    file_hash,filename,row_number,identity_key,fingerprint,raw_json,
                    normalized_json,validation_status,issues_json
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    file_hash,
                    path.name,
                    number,
                    identity,
                    fingerprint,
                    json.dumps(raw, ensure_ascii=False),
                    json.dumps(normalized, ensure_ascii=False)
                    if normalized
                    else None,
                    "accepted" if normalized else "invalid",
                    json.dumps(issues),
                ),
            )
            if normalized:
                affected.add(identity)
                key = normalized["location_key"]
                if key:
                    coordinate = coords.get(key)
                    if coordinate:
                        connection.execute(
                            """INSERT INTO locations(
                                location_key,display_name,latitude,longitude,coordinate_source,
                                matching_method,validation_status
                            ) VALUES (?,?,?,?,?,?,?) ON CONFLICT(location_key) DO UPDATE SET
                                latitude=excluded.latitude,longitude=excluded.longitude,
                                coordinate_source=excluded.coordinate_source,
                                matching_method=excluded.matching_method,
                                validation_status=excluded.validation_status""",
                            (
                                key,
                                normalized["location_raw"],
                                coordinate["latitude"],
                                coordinate["longitude"],
                                "existing cache; provenance unverified",
                                "exact normalized address",
                                coordinate["validation_status"],
                            ),
                        )
        for identity in affected:
            rebuild_identity(connection, identity)
        if affected:
            bump_version(connection)
        report["canonical_total"] = connection.execute(
            "SELECT count(*) FROM incidents"
        ).fetchone()[0]
        after = {
            row[0]
            for row in connection.execute("SELECT identity_key FROM incidents")
        }
        report["canonical_added"] = len(after - before)
        report["canonical_removed_due_to_conflict"] = len(before - after)
        report["unresolved_identities"] = unresolved_count(connection)
        connection.execute(
            """INSERT INTO import_batches(
                filename,file_hash,imported_at,status,report_json,
                importer_version,schema_version,config_version
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                path.name,
                file_hash,
                datetime.now(timezone.utc).isoformat(),
                "success",
                json.dumps(report),
                IMPORTER_VERSION,
                SCHEMA_VERSION,
                settings()["version"],
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return report


def _record_rejection(
    connection: sqlite3.Connection, filename: str, file_hash: str, reason: str
) -> None:
    connection.execute(
        """INSERT INTO import_batches(
            filename,file_hash,imported_at,status,report_json,
            importer_version,schema_version,config_version
        ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            filename,
            file_hash,
            datetime.now(timezone.utc).isoformat(),
            "rejected",
            json.dumps(
                {
                    "error": reason,
                    "source_rows": 0,
                    "new_candidates": 0,
                    "updates": 0,
                    "duplicates": 0,
                    "conflict_versions": 0,
                    "invalid_rows": 0,
                }
            ),
            IMPORTER_VERSION,
            SCHEMA_VERSION,
            settings()["version"],
        ),
    )
    connection.commit()


def unresolved_count(connection: sqlite3.Connection) -> int:
    return connection.execute(
        """SELECT count(DISTINCT s.identity_key) FROM source_rows s
           WHERE s.validation_status='accepted' AND NOT EXISTS (
             SELECT 1 FROM incidents i WHERE i.identity_key=s.identity_key
           )"""
    ).fetchone()[0]


def import_path(connection: sqlite3.Connection, path: Path) -> list[dict]:
    files = (
        sorted(
            file
            for file in path.iterdir()
            if file.is_file()
            and any(
                fnmatch(file.name.casefold(), pat) for pat in FILE_PATTERNS
            )
        )
        if path.is_dir()
        else [path]
    )
    if not files:
        raise ValueError(
            f"No Incident Report*.csv or incident_reports*.csv files found in {path}"
        )
    coords = coordinate_index()
    return [import_file(connection, file, coords) for file in files]


def refresh_coordinates(connection: sqlite3.Connection) -> dict:
    """Reapply the audited local address cache without changing incident identity."""
    coords = coordinate_index()
    connection.execute("BEGIN IMMEDIATE")
    try:
        matched = 0
        for row in connection.execute(
            "SELECT location_key FROM locations"
        ).fetchall():
            key = row["location_key"]
            coordinate = coords.get(key)
            if coordinate:
                matched += 1
            connection.execute(
                """UPDATE locations SET latitude=?,longitude=?,coordinate_source=?,
                   matching_method=?,validation_status=? WHERE location_key=?""",
                (
                    coordinate["latitude"] if coordinate else None,
                    coordinate["longitude"] if coordinate else None,
                    "existing cache; provenance unverified"
                    if coordinate
                    else None,
                    "exact normalized address" if coordinate else None,
                    coordinate["validation_status"]
                    if coordinate
                    else "missing",
                    key,
                ),
            )
        bump_version(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"locations": len(coords), "matched_existing_locations": matched}
