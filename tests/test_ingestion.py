"""Small independently counted import and reconciliation fixtures."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from dfd_dashboard.analytics import (
    Filters,
    apply_filters,
    filter_options,
    load_snapshot,
    quality_details,
    summary,
)
from dfd_dashboard.ingestion import (
    IMPORTER_VERSION,
    REQUIRED_COLUMNS,
    import_file,
    import_path,
    parse_timestamp,
)
from dfd_dashboard.storage import backup_database, connect, resolve_identity

SUMMARY_FIELDS = (
    "INCIDENT ",
    "INCIDENT DATE/TIME",
    "INCIDENT LOCATION",
    "DISPATCH TYPE",
    "1ST ARRIVING",
    "SHIFT",
    "OFFICER IN CHARGE",
    "LAST OPENED BY",
    "STATUS",
)


def row(
    identity: str, when: str = "Apr 28, 2026 19:51:03", **overrides: str
) -> dict:
    value = dict.fromkeys(REQUIRED_COLUMNS, "--")
    value.update(
        {
            "INCIDENT NUMBER": identity,
            "INCIDENT DATE/TIME": when,
            "STATUS": "Authorized",
            "DISPATCH TYPE": "FIRE ALARM",
            "1ST ARRIVING": "E22",
            "INCIDENT LOCATION": "12 MAIN ST, DANBURY, CT",
            "SHIFT": "A",
            "INCIDENT TYPE": "Alarm",
            "PROPERTY TYPE": "Residential",
            "APPARATUS": "E22, Engine 22, Truck 1, Mystery 4",
            "STATION": "HQ",
        }
    )
    value.update(overrides)
    return value


def write_csv(
    path: Path, rows: list[dict], fields: tuple[str, ...] = REQUIRED_COLUMNS
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [{field: value.get(field) for field in fields} for value in rows]
        )


def summary_row(identity: str, **overrides: str) -> dict:
    value = {**row(identity, "2026-04-28 19:51:03"), "INCIDENT ": identity}
    value.update(
        {
            "OFFICER IN CHARGE": "Example Officer",
            "LAST OPENED BY": "Example User",
        }
    )
    value.update(overrides)
    return {field: value.get(field) for field in SUMMARY_FIELDS}


def test_directory_discovers_both_filename_styles(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("dfd_dashboard.ingestion.coordinate_index", lambda: {})
    write_csv(tmp_path / "Incident Report 0.csv", [row("D-1")])
    write_csv(
        tmp_path / "incident_reports 22.csv",
        [summary_row("D-1")],
        SUMMARY_FIELDS,
    )
    write_csv(
        tmp_path / "incident_reports 27..csv",
        [summary_row("D-2")],
        SUMMARY_FIELDS,
    )
    write_csv(
        tmp_path / "INCIDENT_REPORTS 33.CSV",
        [summary_row("D-3")],
        SUMMARY_FIELDS,
    )
    (tmp_path / "unrelated.csv").write_text("not an incident export")
    (tmp_path / "incident_reports directory.csv").mkdir()
    with connect(tmp_path / "test.sqlite3") as connection:
        reports = import_path(connection, tmp_path)
        assert len(reports) == 4
        assert sum(report["source_rows"] for report in reports) == 4
        assert sum(report["duplicates"] for report in reports) == 1
        assert len(load_snapshot(connection).incidents) == 3
        version = load_snapshot(connection).version
        assert (
            sum(
                report["duplicates"]
                for report in import_path(connection, tmp_path)
            )
            == 4
        )
        assert load_snapshot(connection).version == version
    empty = tmp_path / "empty"
    empty.mkdir()
    with connect(tmp_path / "test.sqlite3") as connection:
        with pytest.raises(ValueError, match="incident_reports"):
            import_path(connection, empty)


@pytest.mark.parametrize("summary_first", [False, True])
def test_mixed_layout_overlap_preserves_detailed_fields(
    tmp_path: Path, summary_first: bool
) -> None:
    detailed = tmp_path / "Incident Report.csv"
    reduced = tmp_path / "incident_reports 22.csv"
    write_csv(detailed, [row("D-1")])
    write_csv(reduced, [summary_row("D-1")], SUMMARY_FIELDS)
    paths = [reduced, detailed] if summary_first else [detailed, reduced]
    with connect(tmp_path / "test.sqlite3") as connection:
        reports = [import_file(connection, path, coords={}) for path in paths]
        snapshot = load_snapshot(connection)
        assert len(snapshot.incidents) == 1
        assert len(snapshot.responses) == 3
        incident = snapshot.incidents[0]
        assert incident["incident_type"] == "Alarm"
        assert incident["property_type"] == "Residential"
        assert incident["station"] == "HQ"
        assert incident["source_file"] == detailed.name
        assert snapshot.quality["unresolved_identities"] == 0
        assert snapshot.quality["conflict_source_rows"] == 0
        assert quality_details(connection)["conflicts"] == []
        assert (
            reports[1]["enrichments" if summary_first else "duplicates"] == 1
        )
        version = snapshot.version
        for path in paths:
            assert import_file(connection, path, coords={})["duplicates"] == 1
        assert load_snapshot(connection).version == version


def test_summary_only_keeps_unknowns_and_reported_first_unit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incident_reports 22.csv"
    write_csv(
        source,
        [summary_row("D-1", **{"1ST ARRIVING": "Engine 99"})],
        SUMMARY_FIELDS,
    )
    with connect(tmp_path / "test.sqlite3") as connection:
        report = import_file(connection, source, coords={})
        assert report["source_format"] == "summary"
        assert report["unavailable_columns"] == [
            "APPARATUS",
            "INCIDENT TYPE",
            "PROPERTY TYPE",
            "STATION",
        ]
        assert report["invalid_rows"] == 0
        snapshot = load_snapshot(connection)
        incident = snapshot.incidents[0]
        assert incident["local_timestamp"] == "2026-04-28T19:51:03"
        assert incident["incident_type"] is None
        assert incident["property_type"] is None
        assert incident["station"] is None
        assert snapshot.responses == []
        result = summary(snapshot, Filters())
        assert result["incidents"] == 1
        assert result["missing_participation"] == 1
        assert result["missing_incident_types"] == 1
        assert result["missing_property_types"] == 1
        assert "Engine 99" in filter_options(snapshot)["apparatus"]
        assert (
            summary(snapshot, Filters(apparatus=("Engine 99",)))["incidents"]
            == 0
        )
        assert (
            summary(
                snapshot,
                Filters(apparatus=("Engine 99",), mode="first_arrival"),
            )["incidents"]
            == 1
        )
        original = json.loads(
            connection.execute("SELECT raw_json FROM source_rows").fetchone()[
                0
            ]
        )
        assert original["INCIDENT "] == "D-1"
        assert original["OFFICER IN CHARGE"] == "Example Officer"
        issues = connection.execute(
            "SELECT issues_json FROM source_rows"
        ).fetchone()[0]
        assert "absent from participation list" not in issues
        second = tmp_path / "incident_reports 23.csv"
        write_csv(
            second,
            [
                summary_row(
                    "D-1",
                    **{
                        "1ST ARRIVING": "Engine 99",
                        "LAST OPENED BY": "Another User",
                    },
                )
            ],
            SUMMARY_FIELDS,
        )
        assert import_file(connection, second, coords={})["duplicates"] == 1
        assert len(load_snapshot(connection).incidents) == 1


def test_summary_cannot_hide_conflicting_detailed_versions(
    tmp_path: Path,
) -> None:
    detailed = tmp_path / "Incident Report.csv"
    write_csv(
        detailed, [row("D-1"), row("D-1", **{"INCIDENT TYPE": "Medical"})]
    )
    reduced = tmp_path / "incident_reports 22.csv"
    write_csv(reduced, [summary_row("D-1")], SUMMARY_FIELDS)
    with connect(tmp_path / "test.sqlite3") as connection:
        import_file(connection, detailed, coords={})
        assert import_file(connection, reduced, coords={})["duplicates"] == 1
        snapshot = load_snapshot(connection)
        assert snapshot.incidents == []
        assert snapshot.quality["unresolved_identities"] == 1
        assert len(quality_details(connection)["conflicts"]) == 3
        # Resolve to an exact duplicate source row, then repeat a reduced export.
        duplicate = tmp_path / "Incident Report 1.csv"
        write_csv(duplicate, [row("D-1")])
        import_file(connection, duplicate, coords={})
        chosen = connection.execute(
            "SELECT max(id) FROM source_rows"
        ).fetchone()[0]
        resolve_identity(
            connection,
            "D-1",
            chosen,
            "Verified duplicate of chosen detailed record",
        )
        repeated = tmp_path / "incident_reports 23.csv"
        write_csv(repeated, [summary_row("D-1")], SUMMARY_FIELDS)
        import_file(connection, repeated, coords={})
        assert (
            load_snapshot(connection).incidents[0]["incident_type"] == "Alarm"
        )
        changed = tmp_path / "incident_reports 24.csv"
        write_csv(
            changed, [summary_row("D-1", STATUS="Incomplete")], SUMMARY_FIELDS
        )
        assert (
            import_file(connection, changed, coords={})["conflict_versions"]
            == 1
        )
        assert load_snapshot(connection).quality["unresolved_identities"] == 1


def test_summary_header_validation_and_identity_are_strict(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incident_reports 22.csv"
    with connect(tmp_path / "test.sqlite3") as connection:
        # Aliases must not hide two distinct incident-identifier columns.
        write_csv(
            source, [summary_row("D-1")], (*SUMMARY_FIELDS, "INCIDENT NUMBER")
        )
        with pytest.raises(ValueError, match="duplicate CSV header"):
            import_file(connection, source, coords={})
        write_csv(source, [summary_row("D-1")], SUMMARY_FIELDS[1:])
        with pytest.raises(ValueError, match="missing required columns"):
            import_file(connection, source, coords={})
        # Same date/time alone must not reconcile different incident numbers.
        write_csv(
            source, [summary_row("D-1"), summary_row("D-2")], SUMMARY_FIELDS
        )
        import_file(connection, source, coords={})
        assert len(load_snapshot(connection).incidents) == 2


def test_reconciliation_lineage_and_resolution(tmp_path: Path) -> None:
    first = tmp_path / "Incident Report.csv"
    overlap = tmp_path / "Incident Report 1.csv"
    write_csv(first, [row("D-1"), row("D-2", "Apr 28, 2026 23:00:00")])
    write_csv(overlap, [row("D-1"), row("D-2", "Apr 29, 2026 01:00:00")])
    with connect(tmp_path / "test.sqlite3") as connection:
        report_one = import_file(connection, first, coords={})
        report_two = import_file(connection, overlap, coords={})
        snapshot = load_snapshot(connection)
        assert report_one["new_candidates"] == 2
        assert report_two["duplicates"] == 1
        assert report_two["conflict_versions"] == 1
        assert report_two["canonical_removed_due_to_conflict"] == 1
        assert report_two["schema_version"] == 3
        assert (
            connection.execute(
                "SELECT importer_version FROM import_batches ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            == IMPORTER_VERSION
        )
        assert snapshot.quality["source_rows"] == 4
        assert snapshot.quality["duplicate_rows"] == 1
        assert snapshot.quality["unresolved_identities"] == 1
        assert len(snapshot.incidents) == 1
        assert (
            len(snapshot.responses) == 3
        )  # E22 alias and repeated token are one unit.
        assert (
            summary(snapshot, Filters())["incident_types"][0]["share"] == 100
        )

        # An unchanged reimport adds only an attempt; it cannot change canonical totals.
        again = import_file(connection, first, coords={})
        assert again["duplicates"] == 2
        assert len(load_snapshot(connection).incidents) == 1
        chosen = connection.execute(
            "SELECT id FROM source_rows WHERE identity_key='D-2' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        resolve_identity(
            connection, "D-2", chosen, "Reviewed corrected source export"
        )
        assert len(load_snapshot(connection).incidents) == 2
        assert (
            connection.execute("SELECT count(*) FROM resolutions").fetchone()[
                0
            ]
            == 1
        )

        later = tmp_path / "Incident Report 2.csv"
        write_csv(later, [row("D-2", "Apr 30, 2026 03:00:00")])
        import_file(connection, later, coords={})
        assert len(load_snapshot(connection).incidents) == 1
        assert load_snapshot(connection).quality["unresolved_identities"] == 1
        latest = connection.execute(
            "SELECT id FROM source_rows WHERE identity_key='D-2' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        resolve_identity(
            connection, "D-2", latest, "Reviewed later corrected export"
        )
        assert len(load_snapshot(connection).incidents) == 2
        assert (
            connection.execute("SELECT count(*) FROM resolutions").fetchone()[
                0
            ]
            == 2
        )
        repeated_later = tmp_path / "Incident Report 3.csv"
        write_csv(repeated_later, [row("D-2", "Apr 30, 2026 03:00:00")])
        import_file(connection, repeated_later, coords={})
        assert len(load_snapshot(connection).incidents) == 2
        assert load_snapshot(connection).quality["unresolved_identities"] == 0


def test_invalid_file_and_row_are_recoverable(tmp_path: Path) -> None:
    bad_header = tmp_path / "bad.csv"
    write_csv(bad_header, [row("D-1")], REQUIRED_COLUMNS[:-1])
    db = tmp_path / "test.sqlite3"
    with connect(db) as connection:
        with pytest.raises(ValueError, match="missing required columns"):
            import_file(connection, bad_header, coords={})
        assert len(load_snapshot(connection).incidents) == 0
        assert (
            connection.execute(
                "SELECT status FROM import_batches ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
            == "rejected"
        )
        valid = tmp_path / "valid.csv"
        write_csv(valid, [row("D-1"), row("--"), row("D-3", "not a date")])
        report = import_file(connection, valid, coords={})
        assert report["invalid_rows"] == 1
        assert report["canonical_total"] == 2
        snapshot = load_snapshot(connection)
        assert snapshot.quality["invalid_rows"] == 1
        assert (
            len(apply_filters(snapshot, Filters(start_date="2026-04-28"))[0])
            == 1
        )
        assert len(apply_filters(snapshot, Filters())[0]) == 2
        raw = connection.execute(
            "SELECT raw_json FROM source_rows WHERE validation_status='invalid'"
        ).fetchone()[0]
        assert json.loads(raw)["INCIDENT NUMBER"] == "--"
        backup = tmp_path / "backup.sqlite3"
        backup_database(connection, backup)
    with sqlite3.connect(backup) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            restored.execute("SELECT count(*) FROM incidents").fetchone()[0]
            == 2
        )


def test_timestamp_daylight_saving_flags() -> None:
    assert (
        parse_timestamp("Mar 8, 2026 02:30:00")[2] == "nonexistent local time"
    )
    assert parse_timestamp("Nov 1, 2026 01:30:00")[2] == "ambiguous local time"
    assert parse_timestamp("Apr 28, 2026 19:51:03") == (
        "2026-04-28T19:51:03",
        None,
        None,
    )
