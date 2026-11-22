"""The portfolio path uses only invented fixtures and a marked database."""

from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from dfd_dashboard.analytics import load_snapshot
from dfd_dashboard.cli import main
from dfd_dashboard.dashboard import create_app
from dfd_dashboard.demo import (
    DEMO_COORDINATES,
    DEMO_CSV,
    build_demo_database,
    is_demo_database,
)
from dfd_dashboard.storage import connect


def test_demo_is_invented_marked_and_separate(tmp_path: Path) -> None:
    with DEMO_CSV.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    coordinates = json.loads(DEMO_COORDINATES.read_text(encoding="utf-8"))
    assert len(rows) == 240
    assert all(row["INCIDENT NUMBER"].startswith("DEMO-") for row in rows)
    assert all(
        row["INCIDENT LOCATION"].startswith("DEMO LOCATION ") for row in rows
    )
    assert all(
        point["ADDRESS"].startswith("DEMO LOCATION ")
        for point in coordinates.values()
    )

    path = build_demo_database(tmp_path / "demo.sqlite3")
    assert is_demo_database(path)
    with closing(connect(path)) as connection:
        snapshot = load_snapshot(connection)
    assert len(snapshot.incidents) == 240
    assert all(row["latitude"] is not None for row in snapshot.incidents)
    assert (
        "SYNTHETIC DEMO DATA" in create_app(path).layout.children[0].children
    )
    with pytest.raises(FileExistsError):
        build_demo_database(path)


def test_unmarked_database_is_not_demo(tmp_path: Path) -> None:
    path = tmp_path / "unmarked.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE metadata (key TEXT, value TEXT)")
        connection.commit()
    assert not is_demo_database(path)


def test_demo_command_refuses_unmarked_database(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "portfolio-demo.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE metadata (key TEXT, value TEXT)")
        connection.commit()
    monkeypatch.setattr("dfd_dashboard.cli.DEMO_DB", path)
    with pytest.raises(ValueError, match="not marked synthetic"):
        main(["demo"])


def test_operational_server_rejects_public_bind() -> None:
    with pytest.raises(ValueError, match="localhost"):
        main(["serve", "--host", "0.0.0.0"])
