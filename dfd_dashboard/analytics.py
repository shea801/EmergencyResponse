"""Dash-independent snapshots, shared filters, and counting rules."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from dfd_dashboard.config import settings
from dfd_dashboard.ingestion import unresolved_count
from dfd_dashboard.source_formats import conflicting_identities
from dfd_dashboard.storage import data_version


@dataclass(frozen=True)
class Filters:
    start_date: str | None = None
    end_date: str | None = None
    hour_start: int | None = None
    hour_end: int | None = None
    weekdays: tuple[int, ...] = ()
    months: tuple[int, ...] = ()
    seasons: tuple[str, ...] = ()
    shifts: tuple[str, ...] = ()
    apparatus: tuple[str, ...] = ()
    companies: tuple[str, ...] = ()
    mode: str = "participation"
    dispatch_types: tuple[str, ...] = ()
    incident_types: tuple[str, ...] = ()
    property_types: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    location_detail: str | None = None
    search: str = ""

    def __post_init__(self) -> None:
        if (self.hour_start is None) != (self.hour_end is None):
            raise ValueError(
                "Choose both hour boundaries or disable the hour filter"
            )
        if self.hour_start is not None:
            if not (0 <= self.hour_start <= 23 and 0 <= self.hour_end <= 23):
                raise ValueError("Hour boundaries must be between 0 and 23")
            if self.hour_start == self.hour_end:
                raise ValueError(
                    "Identical enabled hour boundaries are not valid"
                )
        if self.mode not in {"participation", "first_arrival"}:
            raise ValueError("Unknown apparatus filter mode")
        if (
            self.start_date
            and self.end_date
            and self.start_date > self.end_date
        ):
            raise ValueError("Start date must be on or before end date")


@dataclass
class Snapshot:
    incidents: list[dict] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)
    version: int = 0
    last_import: str | None = None
    quality: dict = field(default_factory=dict)


def load_snapshot(connection: sqlite3.Connection) -> Snapshot:
    incidents = [
        dict(row)
        for row in connection.execute(
            """SELECT i.*,l.latitude,l.longitude,l.validation_status AS coordinate_status,
               s.filename AS source_file,s.row_number AS source_row
               FROM incidents i LEFT JOIN locations l ON l.location_key=i.location_key
               JOIN source_rows s ON s.id=i.source_row_id ORDER BY i.identity_key"""
        )
    ]
    responses = [
        dict(row)
        for row in connection.execute(
            """SELECT p.identity_key,p.apparatus_label,a.mapped,a.company
               FROM participations p JOIN apparatus a ON a.label=p.apparatus_label"""
        )
    ]
    last = connection.execute(
        "SELECT imported_at FROM import_batches WHERE status='success' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    source = connection.execute(
        "SELECT count(*) AS rows, count(DISTINCT identity_key) AS identities FROM source_rows"
    ).fetchone()
    duplicate = connection.execute(
        """SELECT coalesce(sum(c-1),0) FROM (
            SELECT count(*) c FROM source_rows WHERE validation_status='accepted'
            GROUP BY identity_key,fingerprint
        )"""
    ).fetchone()[0]
    invalid = connection.execute(
        "SELECT count(*) FROM source_rows WHERE validation_status='invalid'"
    ).fetchone()[0]
    conflicts = unresolved_count(connection)
    candidates = connection.execute(
        """SELECT count(*) FROM source_rows s WHERE s.validation_status='accepted'
           AND NOT EXISTS (SELECT 1 FROM incidents i WHERE i.identity_key=s.identity_key)"""
    ).fetchone()[0]
    return Snapshot(
        incidents,
        responses,
        data_version(connection),
        last[0] if last else None,
        {
            "source_rows": source[0],
            "source_identities": source[1],
            "duplicate_rows": duplicate,
            "invalid_rows": invalid,
            "unresolved_identities": conflicts,
            "conflict_source_rows": candidates,
        },
    )


def _time_matches(incident: dict, filters: Filters) -> bool:
    raw = incident["local_timestamp"]
    needs_time = any(
        (
            filters.start_date,
            filters.end_date,
            filters.hour_start is not None,
            filters.weekdays,
            filters.months,
            filters.seasons,
        )
    )
    if not needs_time:
        return True
    if not raw:
        return False
    moment = datetime.fromisoformat(raw)
    day = moment.date().isoformat()
    if filters.start_date and day < filters.start_date:
        return False
    if (
        filters.end_date
        and day
        >= (
            date.fromisoformat(filters.end_date) + timedelta(days=1)
        ).isoformat()
    ):
        return False
    if filters.weekdays and moment.weekday() not in filters.weekdays:
        return False
    if filters.months and moment.month not in filters.months:
        return False
    if filters.seasons:
        season_map = settings()["seasons"]
        if not any(
            moment.month in season_map[name] for name in filters.seasons
        ):
            return False
    if filters.hour_start is not None:
        start, end = filters.hour_start, filters.hour_end
        hour = moment.hour
        if start < end and not start <= hour < end:
            return False
        if start > end and not (hour >= start or hour < end):
            return False
    return True


def apply_filters(
    snapshot: Snapshot, filters: Filters
) -> tuple[list[dict], list[dict]]:
    responses_by_incident: dict[str, list[dict]] = defaultdict(list)
    for response in snapshot.responses:
        responses_by_incident[response["identity_key"]].append(response)
    incidents = []
    responses = []
    for incident in snapshot.incidents:
        if not _time_matches(incident, filters):
            continue
        if any(
            (
                filters.shifts
                and (incident["shift"] or "__unknown__") not in filters.shifts,
                filters.dispatch_types
                and (incident["dispatch_type"] or "__unknown__")
                not in filters.dispatch_types,
                filters.incident_types
                and (incident["incident_type"] or "__unknown__")
                not in filters.incident_types,
                filters.property_types
                and (incident["property_type"] or "__unknown__")
                not in filters.property_types,
                filters.statuses
                and (incident["status"] or "__unknown__")
                not in filters.statuses,
                filters.locations
                and (incident["location_key"] or "__unknown__")
                not in filters.locations,
                filters.location_detail
                and incident["location_key"] != filters.location_detail,
            )
        ):
            continue
        if filters.search:
            haystack = " ".join(
                str(incident[key] or "")
                for key in (
                    "identity_key",
                    "location_raw",
                    "dispatch_type",
                    "incident_type",
                )
            ).casefold()
            if filters.search.casefold().strip() not in haystack:
                continue
        all_responses = responses_by_incident[incident["identity_key"]]
        if filters.mode == "first_arrival":
            if (
                filters.apparatus
                and incident["first_unit"] not in filters.apparatus
            ):
                continue
            if filters.companies:
                first_company = next(
                    (
                        r["company"]
                        for r in all_responses
                        if r["apparatus_label"] == incident["first_unit"]
                    ),
                    None,
                )
                if (first_company or "Unmapped") not in filters.companies:
                    continue
            matched = all_responses
        else:
            matched = [
                r
                for r in all_responses
                if (
                    not filters.apparatus
                    or r["apparatus_label"] in filters.apparatus
                )
                and (
                    not filters.companies
                    or (r["company"] or "Unmapped") in filters.companies
                )
            ]
            if (filters.apparatus or filters.companies) and not matched:
                continue
        incidents.append(incident)
        responses.extend(matched)
    return incidents, responses


def count_by(items: list[dict], key: str) -> list[dict]:
    counts = Counter(item.get(key) or "Unknown" for item in items)
    total = len(items)
    threshold = settings()["small_sample_threshold"]
    return [
        {
            "label": label,
            "count": count,
            "share": round(100 * count / total, 1) if total else 0,
            "sample_note": f"Small sample (<{threshold})"
            if count < threshold
            else "",
        }
        for label, count in sorted(
            counts.items(), key=lambda pair: (-pair[1], pair[0])
        )
    ]


def temporal_counts(incidents: list[dict]) -> dict[str, list[dict]]:
    counters = {
        name: Counter()
        for name in ("hour", "weekday", "month", "season", "year")
    }
    season_map = settings()["seasons"]
    threshold = settings()["small_sample_threshold"]
    dated = 0
    for incident in incidents:
        if not incident["local_timestamp"]:
            continue
        dated += 1
        moment = datetime.fromisoformat(incident["local_timestamp"])
        counters["hour"][f"{moment.hour:02d}:00"] += 1
        counters["weekday"][moment.strftime("%A")] += 1
        counters["month"][moment.strftime("%Y-%m")] += 1
        counters["year"][str(moment.year)] += 1
        season = next(
            name
            for name, months in season_map.items()
            if moment.month in months
        )
        season_year = moment.year + int(
            season == "Winter" and moment.month == 12
        )
        counters["season"][f"{season} {season_year}"] += 1
    return {
        name: [
            {
                "label": label,
                "count": count,
                "share": round(100 * count / dated, 1) if dated else 0,
                "sample_note": f"Small sample (<{threshold})"
                if count < threshold
                else "",
            }
            for label, count in sorted(counter.items())
        ]
        for name, counter in counters.items()
    }


def location_counts(incidents: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    threshold = settings()["small_sample_threshold"]
    for row in incidents:
        key = row["location_key"] or "Unknown"
        item = grouped.setdefault(
            key,
            {
                "key": key,
                "label": row["location_raw"] or "Unknown",
                "count": 0,
                "latitude": row["latitude"],
                "longitude": row["longitude"],
            },
        )
        item["count"] += 1
        item["sample_note"] = (
            f"Small sample (<{threshold})" if item["count"] < threshold else ""
        )
    return sorted(
        grouped.values(), key=lambda item: (-item["count"], item["label"])
    )


def summarize(incidents: list[dict], responses: list[dict]) -> dict:
    located = sum(row["latitude"] is not None for row in incidents)
    first = count_by(
        [{"first_unit": row["first_unit"]} for row in incidents], "first_unit"
    )
    companies = count_by(
        [{"company": row["company"] or "Unmapped"} for row in responses],
        "company",
    )
    company_pairs = {
        (row["identity_key"], row["company"] or "Unmapped")
        for row in responses
    }
    company_incident_rows = count_by(
        [{"company": company} for _, company in company_pairs], "company"
    )
    for row in company_incident_rows:
        row["share"] = (
            round(100 * row["count"] / len(incidents), 1) if incidents else 0
        )
    return {
        "incidents": len(incidents),
        "unit_responses": len(responses),
        "located": located,
        "mapping_percent": round(100 * located / len(incidents), 1)
        if incidents
        else 0,
        "missing_timestamps": sum(
            row["local_timestamp"] is None for row in incidents
        ),
        "missing_participation": sum(
            row["apparatus_raw"] is None for row in incidents
        ),
        "missing_incident_types": sum(
            row["incident_type"] is None for row in incidents
        ),
        "missing_property_types": sum(
            row["property_type"] is None for row in incidents
        ),
        "incident_types": count_by(incidents, "incident_type"),
        "dispatch_types": count_by(incidents, "dispatch_type"),
        "property_types": count_by(incidents, "property_type"),
        "shifts": count_by(incidents, "shift"),
        "units": count_by(
            [{"unit": r["apparatus_label"]} for r in responses], "unit"
        ),
        "companies": companies,
        "company_incidents": company_incident_rows,
        "first_arrivals": first,
        "locations": location_counts(incidents),
        "temporal": temporal_counts(incidents),
    }


def summary(snapshot: Snapshot, filters: Filters) -> dict:
    return summarize(*apply_filters(snapshot, filters))


def filter_options(snapshot: Snapshot) -> dict[str, list]:
    values = {
        "shifts": set(),
        "dispatch_types": set(),
        "incident_types": set(),
        "property_types": set(),
        "statuses": set(),
        "locations": set(),
        "apparatus": set(),
        "companies": set(),
    }
    for incident in snapshot.incidents:
        if incident["first_unit"]:
            values["apparatus"].add(incident["first_unit"])
        for key, column in (
            ("shifts", "shift"),
            ("dispatch_types", "dispatch_type"),
            ("incident_types", "incident_type"),
            ("property_types", "property_type"),
            ("statuses", "status"),
            ("locations", "location_key"),
        ):
            values[key].add(incident[column] or "__unknown__")
    for row in snapshot.responses:
        values["apparatus"].add(row["apparatus_label"])
        values["companies"].add(row["company"] or "Unmapped")
    return {key: sorted(value) for key, value in values.items()}


def quality_details(connection: sqlite3.Connection) -> dict:
    disputed = conflicting_identities(connection)
    problems = [
        dict(row)
        for row in connection.execute(
            """SELECT filename,row_number,identity_key,validation_status,issues_json
               FROM source_rows WHERE validation_status='invalid' OR issues_json!='[]'
               ORDER BY id DESC LIMIT 100"""
        )
    ]
    conflicts = [
        dict(row)
        for row in connection.execute(
            """SELECT s.identity_key,s.id AS source_row_id,s.filename,s.row_number,
               json_extract(s.raw_json,'$."INCIDENT DATE/TIME"') AS source_timestamp
               FROM source_rows s WHERE s.identity_key IN (
                 SELECT identity_key FROM source_rows WHERE validation_status='accepted'
                 GROUP BY identity_key HAVING count(DISTINCT fingerprint)>1
               ) ORDER BY s.identity_key,s.id"""
        )
        if row["identity_key"] in disputed
    ]
    batches = [
        {**dict(row), "report": json.loads(row["report_json"])}
        for row in connection.execute(
            "SELECT * FROM import_batches ORDER BY id DESC LIMIT 25"
        )
    ]
    coordinates = [
        dict(row)
        for row in connection.execute(
            """SELECT l.location_key,l.display_name,l.validation_status,
               l.coordinate_source,count(i.identity_key) AS incidents
               FROM locations l LEFT JOIN incidents i ON i.location_key=l.location_key
               WHERE l.validation_status!='in_area'
               GROUP BY l.location_key ORDER BY incidents DESC,l.location_key LIMIT 100"""
        )
    ]
    return {
        "problems": problems,
        "conflicts": conflicts,
        "coordinates": coordinates,
        "batches": batches,
    }
