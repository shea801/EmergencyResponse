"""Build and identify the intentionally invented portfolio dataset."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from dfd_dashboard.config import ROOT
from dfd_dashboard.ingestion import coordinate_index, import_file
from dfd_dashboard.storage import connect

DEMO_DB = ROOT / "data" / "portfolio-demo.sqlite3"
DEMO_CSV = ROOT / "demo" / "Incident Report Synthetic.csv"
DEMO_COORDINATES = ROOT / "demo" / "coordinates.json"
DEMO_MARKER = "synthetic_portfolio_demo"


def is_demo_database(path: Path) -> bool:
    """Accept only a database explicitly marked by the demo builder."""
    if not path.exists():
        return False
    try:
        with closing(
            sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='dataset_kind'"
            ).fetchone()
    except sqlite3.Error:
        return False
    return bool(row and row[0] == DEMO_MARKER)


def build_demo_database(path: Path = DEMO_DB) -> Path:
    """Create a separate database; never import into an existing file."""
    if path.exists():
        raise FileExistsError(f"Demo database already exists: {path}")
    with closing(connect(path)) as connection:
        report = import_file(
            connection, DEMO_CSV, coords=coordinate_index(DEMO_COORDINATES)
        )
        if report["invalid_rows"] or report["conflict_versions"]:
            raise ValueError("Synthetic fixture did not import cleanly")
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES ('dataset_kind', ?)",
            (DEMO_MARKER,),
        )
        connection.commit()
    return path
