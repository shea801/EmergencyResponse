"""Independent counting and combined-filter expectations."""

from __future__ import annotations

from pathlib import Path

import pytest

from dfd_dashboard.analytics import (
    Filters,
    apply_filters,
    load_snapshot,
    summary,
)
from dfd_dashboard.dashboard import (
    _filter_from_values,
    _location_map,
    create_app,
    export_package,
)
from dfd_dashboard.ingestion import import_file
from dfd_dashboard.storage import connect

from .test_ingestion import SUMMARY_FIELDS, row, summary_row, write_csv


def _walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


@pytest.fixture
def sample(tmp_path: Path):
    path = tmp_path / "test.sqlite3"
    csv_path = tmp_path / "sample.csv"
    write_csv(
        csv_path,
        [
            row(
                "A-1",
                "Dec 31, 2025 23:30:00",
                **{"INCIDENT LOCATION": "1 SAFE ST"},
            ),
            row(
                "A-2",
                "Jan 1, 2026 02:00:00",
                **{
                    "INCIDENT LOCATION": "2 SAFE ST",
                    "APPARATUS": "Engine 23",
                    "1ST ARRIVING": "Engine 23",
                    "SHIFT": "B",
                    "INCIDENT TYPE": "Medical",
                },
            ),
            row(
                "A-3",
                "Jan 1, 2026 07:00:00",
                **{
                    "INCIDENT LOCATION": "1 SAFE ST",
                    "APPARATUS": "Engine 22, Truck 1",
                    "1ST ARRIVING": "Truck 1",
                    "PROPERTY TYPE": "Commercial",
                },
            ),
        ],
    )
    coords = {
        "1 SAFE ST": {
            "latitude": 41.4,
            "longitude": -73.45,
            "validation_status": "in_area",
        }
    }
    with connect(path) as connection:
        import_file(connection, csv_path, coords=coords)
        snapshot = load_snapshot(connection)
    return path, snapshot


def test_counts_and_filters(sample) -> None:
    _, snapshot = sample
    assert summary(snapshot, Filters())["incidents"] == 3
    assert summary(snapshot, Filters())["unit_responses"] == 6
    assert summary(snapshot, Filters())["located"] == 2
    assert summary(snapshot, Filters())["mapping_percent"] == 66.7
    assert summary(snapshot, Filters())["locations"][0]["count"] == 2
    types = summary(snapshot, Filters())["incident_types"]
    assert [
        (item["label"], item["count"], item["share"]) for item in types
    ] == [
        ("Alarm", 2, 66.7),
        ("Medical", 1, 33.3),
    ]
    assert (
        summary(
            snapshot, Filters(start_date="2026-01-01", end_date="2026-01-01")
        )["incidents"]
        == 2
    )
    overnight = Filters(hour_start=22, hour_end=6)
    assert {
        i["identity_key"] for i in apply_filters(snapshot, overnight)[0]
    } == {"A-1", "A-2"}
    assert summary(snapshot, Filters(seasons=("Winter",)))["incidents"] == 3
    season_year = summary(snapshot, Filters())["temporal"]["season"]
    assert [
        (item["label"], item["count"], item["share"]) for item in season_year
    ] == [("Winter 2026", 3, 100.0)]
    selected = Filters(apparatus=("Engine 22",), shifts=("A",))
    assert summary(snapshot, selected)["incidents"] == 2
    assert summary(snapshot, selected)["unit_responses"] == 2
    first = Filters(apparatus=("Engine 22",), mode="first_arrival")
    assert summary(snapshot, first)["incidents"] == 1
    assert summary(snapshot, first)["unit_responses"] == 3
    assert (
        summary(snapshot, Filters(location_detail="1 SAFE ST"))["incidents"]
        == 2
    )
    assert (
        summary(
            snapshot,
            Filters(locations=("2 SAFE ST",), location_detail="1 SAFE ST"),
        )["incidents"]
        == 0
    )
    assert (
        summary(snapshot, Filters(incident_types=("Medical",), shifts=("B",)))[
            "incidents"
        ]
        == 1
    )
    with pytest.raises(ValueError, match="Identical"):
        Filters(hour_start=8, hour_end=8)

    ui_filters = _filter_from_values(
        (
            (None, None),
            "",
            "",
            ["Thursday"],
            ["January"],
            None,
            None,
            None,
            None,
            "participation",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    )
    assert ui_filters.weekdays == (3,)
    assert ui_filters.months == (1,)
    assert ui_filters.hour_start is None
    assert summary(snapshot, ui_filters)["incidents"] == 2


def test_export_and_dash_shell(sample) -> None:
    path, snapshot = sample
    payload = export_package(snapshot, Filters(apparatus=("Engine 22",)))
    import io
    import json
    import zipfile

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {
            "incidents.csv",
            "unit_responses.csv",
            "summary.csv",
            "metadata.json",
        }
        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["data_version"] == snapshot.version
        assert metadata["filters"]["apparatus"] == ["Engine 22"]
        assert (
            archive.read("incidents.csv").decode("utf-8-sig").count("A-") == 2
        )
        assert (
            archive.read("unit_responses.csv").decode("utf-8-sig").count("A-")
            == 2
        )
    app = create_app(path)
    client = app.server.test_client()
    assert client.get("/").status_code == 200
    layout_response = client.get("/_dash-layout")
    assert layout_response.status_code == 200
    layout = layout_response.json
    advanced = next(
        node for node in _walk(layout) if node.get("type") == "Details"
    )
    assert advanced["props"].get("open") is not True
    advanced_ids = {
        node.get("props", {}).get("id") for node in _walk(advanced)
    }
    assert {
        "hour-start",
        "hour-end",
        "incident-types",
        "location-detail",
    } <= advanced_ids
    assert "apparatus" not in advanced_ids
    assert "apparatus" in {
        node.get("props", {}).get("id") for node in _walk(layout)
    }
    assert client.get("/_dash-dependencies").status_code == 200
    assert client.get("/assets/style.css").status_code == 200
    key = next(
        key for key in app.callback_map if "view-content.children" in key
    )
    callback = app.callback_map[key]
    for view in (
        "overview",
        "types",
        "temporal",
        "units",
        "locations",
        "detail",
        "quality",
    ):
        inputs = [
            {
                **item,
                "value": {
                    "view": view,
                    "refresh": 0,
                    "unit-mode": "participation",
                }.get(item["id"]),
            }
            for item in callback["inputs"]
        ]
        response = client.post(
            "/_dash-update-component",
            json={
                "output": key,
                "outputs": [
                    {"id": "context", "property": "children"},
                    {"id": "cards", "property": "children"},
                    {"id": "view-content", "property": "children"},
                ],
                "inputs": inputs,
                "state": [],
                "changedPropIds": ["view.value"],
            },
        )
        assert response.status_code == 200, (view, response.data[:200])
        if view == "overview":
            cards = response.json["response"]["cards"]["children"]
            graphs = [
                node for node in _walk(cards) if node.get("type") == "Graph"
            ]
            assert len(graphs) == 1
            assert (
                graphs[0]["props"]["figure"]["data"][0]["type"] == "densitymap"
            )

    location_key = next(
        key for key in app.callback_map if "location-message.children" in key
    )
    location_callback = app.callback_map[location_key]
    location_inputs = [
        {
            **item,
            "value": {
                "refresh": 0,
                "incident-types": ["Medical"],
                "unit-mode": "participation",
            }.get(item["id"]),
        }
        for item in location_callback["inputs"]
    ]
    location_response = client.post(
        "/_dash-update-component",
        json={
            "output": location_key,
            "outputs": [
                {"id": "location-detail", "property": "options"},
                {"id": "location-detail", "property": "value"},
                {"id": "location-message", "property": "children"},
            ],
            "inputs": location_inputs,
            "state": [
                {
                    "id": "location-detail",
                    "property": "value",
                    "value": "1 SAFE ST",
                }
            ],
            "changedPropIds": ["incident-types.value"],
        },
    )
    assert location_response.status_code == 200
    location_output = location_response.json["response"]
    assert location_output["location-detail"]["value"] is None
    assert "cleared" in location_output["location-message"]["children"]

    options_key = next(
        key for key in app.callback_map if "incident-types.options" in key
    )
    option_ids = [
        "shifts",
        "apparatus",
        "companies",
        "dispatch-types",
        "incident-types",
        "property-types",
        "statuses",
        "locations",
    ]
    options_response = client.post(
        "/_dash-update-component",
        json={
            "output": options_key,
            "outputs": [
                {"id": item, "property": "options"} for item in option_ids
            ],
            "inputs": [
                {"id": "refresh", "property": "n_intervals", "value": 0}
            ],
            "state": [],
            "changedPropIds": ["refresh.n_intervals"],
        },
    )
    assert options_response.status_code == 200
    assert {
        item["value"]
        for item in options_response.json["response"]["incident-types"][
            "options"
        ]
    } == {"Alarm", "Medical"}


def test_heatmap_uses_weighted_incidents_and_roads() -> None:
    figure = _location_map(
        [
            {
                "label": "1 SAFE ST",
                "latitude": 41.4,
                "longitude": -73.45,
                "count": 3,
            },
            {
                "label": "2 SAFE ST",
                "latitude": 41.41,
                "longitude": -73.44,
                "count": 1,
            },
            {
                "label": "UNLOCATED",
                "latitude": None,
                "longitude": None,
                "count": 7,
            },
        ]
    )
    assert figure.layout.map.style == "open-street-map"
    assert figure.data[0].type == "densitymap"
    assert list(figure.data[0].z) == [3, 1]
    assert figure.data[0].zmin == 0
    assert figure.data[0].zmax == 10
    assert figure.data[0].radius == 10
    assert figure.data[0].colorscale[0][1] == "rgb(3, 5, 18)"
    assert figure.data[0].colorscale[-1][1] == "rgb(234, 252, 253)"


def test_empty_database_and_spreadsheet_safe_export(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty.sqlite3"
    app = create_app(empty_path)
    assert app.server.test_client().get("/_dash-layout").status_code == 200
    with connect(empty_path) as connection:
        empty = load_snapshot(connection)
    assert summary(empty, Filters())["incidents"] == 0
    assert summary(empty, Filters())["mapping_percent"] == 0

    source = tmp_path / "formula.csv"
    write_csv(source, [row("F-1", **{"INCIDENT LOCATION": "=2+2"})])
    with connect(tmp_path / "formula.sqlite3") as connection:
        import_file(connection, source, coords={})
        snapshot = load_snapshot(connection)
    import io
    import zipfile

    with zipfile.ZipFile(
        io.BytesIO(export_package(snapshot, Filters()))
    ) as archive:
        assert "'=2+2" in archive.read("incidents.csv").decode("utf-8-sig")


def test_summary_export_discloses_missing_fields_without_personnel(
    tmp_path: Path,
) -> None:
    import io
    import json
    import zipfile

    source = tmp_path / "incident_reports 22.csv"
    write_csv(source, [summary_row("S-1")], SUMMARY_FIELDS)
    with connect(tmp_path / "test.sqlite3") as connection:
        import_file(connection, source, coords={})
        snapshot = load_snapshot(connection)
    with zipfile.ZipFile(
        io.BytesIO(export_package(snapshot, Filters()))
    ) as archive:
        metadata = json.loads(archive.read("metadata.json"))
        coverage = metadata["field_completeness"]
        assert coverage["incidents_without_participation_list"] == 1
        assert coverage["incidents_without_incident_type"] == 1
        assert coverage["incidents_without_property_type"] == 1
        incidents = archive.read("incidents.csv").decode("utf-8-sig")
        assert "S-1" in incidents
        assert "Example Officer" not in incidents
        assert "Example User" not in incidents
        assert "OFFICER IN CHARGE" not in incidents
        assert (
            archive.read("unit_responses.csv").decode("utf-8-sig").count("S-1")
            == 0
        )
