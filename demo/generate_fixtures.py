"""Regenerate invented portfolio inputs without reading operational files."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = (
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
KINDS = ("Alarm", "Medical", "Public service", "Fire", "Rescue")
UNITS = ("E22", "E23", "E24", "T1", "SQ21")


def main() -> None:
    coordinates = {}
    for site in range(24):
        coordinates[f"demo-{site + 1:02d}"] = {
            "ADDRESS": f"DEMO LOCATION {site + 1:02d}",
            "LATITUDE": round(41.355 + (site // 6) * 0.026, 6),
            "LONGITUDE": round(-73.515 + (site % 6) * 0.025, 6),
        }
    (HERE / "coordinates.json").write_text(
        json.dumps(coordinates, indent=2) + "\n", encoding="utf-8"
    )

    start = datetime(2026, 1, 3, 8, 0)
    with (HERE / "Incident Report Synthetic.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for index in range(240):
            site = index % 24 + 1
            first = UNITS[index % len(UNITS)]
            writer.writerow(
                {
                    "INCIDENT NUMBER": f"DEMO-{index + 1:04d}",
                    "INCIDENT DATE/TIME": (
                        start
                        + timedelta(hours=index * 3, minutes=(index * 7) % 60)
                    ).strftime("%b %d, %Y %H:%M:%S"),
                    "STATUS": "Authorized",
                    "DISPATCH TYPE": KINDS[(index * 3) % len(KINDS)],
                    "1ST ARRIVING": first,
                    "INCIDENT LOCATION": f"DEMO LOCATION {site:02d}",
                    "SHIFT": "ABCD"[index % 4],
                    "INCIDENT TYPE": KINDS[index % len(KINDS)],
                    "PROPERTY TYPE": (
                        "Invented home",
                        "Invented business",
                        "Invented site",
                    )[index % 3],
                    "APPARATUS": f"{first}, {UNITS[(index + 1) % len(UNITS)]}",
                    "STATION": f"DEMO STATION {index % 3 + 1}",
                }
            )


if __name__ == "__main__":
    main()
