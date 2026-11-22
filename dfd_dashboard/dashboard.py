"""Local Dash interface. All visible outputs read one reconciled snapshot and filter."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

from dfd_dashboard.analytics import (
    Filters,
    apply_filters,
    count_by,
    filter_options,
    load_snapshot,
    quality_details,
    summarize,
)
from dfd_dashboard.config import METRIC_VERSION, ROOT, settings
from dfd_dashboard.storage import connect

ORANGE = "#df6919"
BLUE = "#0f2537"
TEXT = "#e7edf4"
MUTED = "#aab8c7"
FILTER_IDS = (
    "dates",
    "hour-start",
    "hour-end",
    "weekdays",
    "months",
    "seasons",
    "shifts",
    "apparatus",
    "companies",
    "unit-mode",
    "dispatch-types",
    "incident-types",
    "property-types",
    "statuses",
    "locations",
    "search",
    "location-detail",
)


def _options(values: list[str] | tuple[str, ...]) -> list[dict]:
    return [
        {"label": "Unknown" if item == "__unknown__" else item, "value": item} for item in values
    ]


def _dropdown(label: str, control_id: str, values: list[str], multi: bool = True) -> dbc.Col:
    return dbc.Col(
        [
            html.Label(label, htmlFor=control_id, className="filter-label"),
            dcc.Dropdown(
                id=control_id,
                options=_options(values),
                multi=multi,
                placeholder="All",
                className="filter-dropdown",
            ),
        ],
        xs=12,
        sm=6,
        lg=3,
        className="mb-3",
    )


def _hour_dropdown(label: str, control_id: str) -> dbc.Col:
    return dbc.Col(
        [
            html.Label(label, htmlFor=control_id, className="filter-label"),
            dcc.Dropdown(
                id=control_id,
                options=[{"label": "Off", "value": ""}]
                + [{"label": f"{hour:02d}:00", "value": hour} for hour in range(24)],
                placeholder="Off",
                className="filter-dropdown",
            ),
        ],
        xs=6,
        lg=3,
        className="mb-3",
    )


def _card(label: str, value: str, detail: str = "") -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(label, className="metric-label"),
                    html.Div(value, className="metric-value"),
                    html.Div(detail, className="metric-detail"),
                ]
            ),
            className="metric-card h-100",
        ),
        xs=6,
        xl=6,
        className="mb-3",
    )


def _table(rows: list[dict], columns: list[tuple[str, str]], table_id: str) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": title, "id": key} for title, key in columns],
        data=[{key: item.get(key) for _, key in columns} for item in rows],
        page_size=12,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "backgroundColor": BLUE,
            "color": TEXT,
            "border": "1px solid #34495e",
            "padding": "9px",
            "minWidth": "95px",
            "maxWidth": "360px",
            "whiteSpace": "normal",
        },
        style_header={"backgroundColor": "#182f45", "fontWeight": "bold", "color": ORANGE},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#173047"}],
    )


def _figure(title: str, rows: list[dict], limit: int | None = None) -> go.Figure:
    shown = rows[:limit] if limit else rows
    if limit and len(rows) > limit:
        shown = [*shown, {"label": "Other", "count": sum(r["count"] for r in rows[limit:])}]
    fig = go.Figure()
    if shown:
        fig.add_bar(
            x=[str(r["label"]) for r in shown],
            y=[r["count"] for r in shown],
            marker_color=ORANGE,
            hovertemplate="%{x}<br>%{y}<extra></extra>",
        )
    else:
        fig.add_annotation(
            text="No incidents match these filters",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font_color=TEXT,
        )
    fig.update_layout(
        title=title,
        paper_bgcolor=BLUE,
        plot_bgcolor="#152e44",
        font_color=TEXT,
        margin={"l": 42, "r": 20, "t": 64, "b": 90},
        height=380,
        xaxis={"tickangle": -35, "automargin": True},
        yaxis={"title": "Count", "rangemode": "tozero"},
    )
    return fig


def _panel(title: str, content: object) -> dbc.Card:
    return dbc.Card(
        [dbc.CardHeader(html.H4(title, className="m-0")), dbc.CardBody(content)],
        className="analysis-card mb-4",
    )


def _count_table(rows: list[dict], table_id: str) -> dash_table.DataTable:
    return _table(
        rows,
        [
            ("Category", "label"),
            ("Count", "count"),
            ("Share of selected group (%)", "share"),
            ("Sample", "sample_note"),
        ],
        table_id,
    )


def _detail_rows(incidents: list[dict]) -> list[dict]:
    return [
        {
            "incident": row["identity_key"],
            "source_time": row["source_timestamp"],
            "status": row["status"],
            "dispatch": row["dispatch_type"],
            "incident_type": row["incident_type"],
            "property_type": row["property_type"],
            "shift": row["shift"],
            "first_unit": row["first_unit"],
            "apparatus": row["apparatus_raw"],
            "station": row["station"],
            "location": row["location_raw"],
            "source": f"{row['source_file']}:{row['source_row']}",
        }
        for row in incidents
    ]


DETAIL_COLUMNS = [
    ("Incident number", "incident"),
    ("Source-reported date/time", "source_time"),
    ("Report status", "status"),
    ("Dispatch type", "dispatch"),
    ("Incident type", "incident_type"),
    ("Property type", "property_type"),
    ("Reported shift", "shift"),
    ("First-arriving apparatus", "first_unit"),
    ("Participating apparatus", "apparatus"),
    ("Source station", "station"),
    ("Location", "location"),
    ("Source file:row", "source"),
]


def _bar_and_table(title: str, rows: list[dict], key: str, limit: int = 12) -> dbc.Card:
    return _panel(
        title,
        [
            dcc.Graph(figure=_figure(title, rows, limit=limit), config={"displaylogo": False}),
            _count_table(rows, f"table-{key}"),
        ],
    )


def _location_map(locations: list[dict]) -> go.Figure:
    located = [
        item for item in locations if item["latitude"] is not None and item["longitude"] is not None
    ]
    fig = go.Figure()
    if located:
        fig.add_trace(
            go.Densitymap(
                lat=[item["latitude"] for item in located],
                lon=[item["longitude"] for item in located],
                z=[item["count"] for item in located],
                customdata=[[item["label"], item["count"]] for item in located],
                zmin=0,
                zmax=10,
                radius=10,
                opacity=0.85,
                colorscale=px.colors.sequential.ice,
                showscale=False,
                hovertemplate="%{customdata[0]}<br>%{customdata[1]} incidents<extra></extra>",
            )
        )
    else:
        fig.add_annotation(
            text="No validated coordinates for this selection",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    fig.update_layout(
        map={"style": "open-street-map", "center": {"lat": 41.4, "lon": -73.45}, "zoom": 11},
        paper_bgcolor=BLUE,
        font_color=TEXT,
        height=420,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    return fig


def _view_content(
    view: str,
    result: dict,
    incidents: list[dict],
    responses: list[dict],
    snapshot: object,
    quality: dict,
    selected_location: str | None,
) -> object:
    if view == "overview":
        return [
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table(
                            "Leading incident types", result["incident_types"], "overview-types"
                        ),
                        lg=6,
                    ),
                    dbc.Col(
                        _bar_and_table(
                            "Monthly incident counts",
                            result["temporal"]["month"],
                            "overview-months",
                            18,
                        ),
                        lg=6,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table("Reported shifts", result["shifts"], "overview-shifts"), lg=6
                    ),
                    dbc.Col(
                        _panel(
                            "Data quality at a glance",
                            html.Div(
                                [
                                    html.P(
                                        f"{snapshot.quality['duplicate_rows']:,} repeated source rows; "
                                        f"{snapshot.quality['unresolved_identities']:,} unresolved identities "
                                        f"across {snapshot.quality['conflict_source_rows']:,} source rows."
                                    ),
                                    html.P(
                                        f"{result['located']:,} of {result['incidents']:,} selected incidents "
                                        f"have validated cached coordinates ({result['mapping_percent']}%)."
                                    ),
                                    html.P(
                                        "Incident date/time is source-reported. Export coverage is not verified."
                                    ),
                                ]
                            ),
                        ),
                        lg=6,
                    ),
                ]
            ),
        ]
    if view == "types":
        pairs = Counter(
            (r["dispatch_type"] or "Unknown", r["incident_type"] or "Unknown") for r in incidents
        )
        comparison = [
            {"dispatch": a, "incident_type": b, "count": n}
            for (a, b), n in sorted(pairs.items(), key=lambda x: (-x[1], x[0]))
        ]
        mapping = settings()["category_mappings"]
        broad = (
            count_by(
                [{"category": mapping.get(r["incident_type"], "Unmapped")} for r in incidents],
                "category",
            )
            if mapping
            else []
        )
        return [
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table(
                            "Reported incident type", result["incident_types"], "types-final"
                        ),
                        lg=6,
                    ),
                    dbc.Col(
                        _bar_and_table("Dispatch type", result["dispatch_types"], "types-dispatch"),
                        lg=6,
                    ),
                ]
            ),
            _bar_and_table("Property type", result["property_types"], "types-property"),
            _panel(
                "Dispatch versus incident classification",
                _table(
                    comparison,
                    [
                        ("Dispatch", "dispatch"),
                        ("Incident type", "incident_type"),
                        ("Incidents", "count"),
                    ],
                    "table-type-comparison",
                ),
            ),
            _panel(
                "Broad categories",
                _count_table(broad, "table-broad")
                if mapping
                else html.P(
                    "No department-approved broad category mapping is configured. Original types remain available above."
                ),
            ),
        ]
    if view == "temporal":
        return [
            html.P(
                "Calendar groupings use source-reported local date/time. Winter is assigned to the year containing January and February."
            ),
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table("Hour of day", result["temporal"]["hour"], "time-hour", 24),
                        lg=6,
                    ),
                    dbc.Col(
                        _bar_and_table("Weekday", result["temporal"]["weekday"], "time-weekday", 7),
                        lg=6,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table("Month", result["temporal"]["month"], "time-month", 24), lg=6
                    ),
                    dbc.Col(
                        _bar_and_table(
                            "Season and year", result["temporal"]["season"], "time-season", 24
                        ),
                        lg=6,
                    ),
                ]
            ),
            _bar_and_table("Calendar year", result["temporal"]["year"], "time-year", 12),
        ]
    if view == "units":
        return [
            html.P(
                "Participation counts can overlap across apparatus and companies. Source-reported first arrival is a count, not a speed measure."
            ),
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table(
                            "Reported shift · incident counts", result["shifts"], "units-shifts"
                        ),
                        lg=6,
                    ),
                    dbc.Col(
                        _bar_and_table(
                            "Apparatus · unit responses", result["units"], "units-response"
                        ),
                        lg=6,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        _bar_and_table(
                            "Source-reported first-arriving apparatus · incidents",
                            result["first_arrivals"],
                            "units-first",
                        ),
                        lg=6,
                    ),
                    dbc.Col(
                        _bar_and_table(
                            "Configured company · participating incidents",
                            result["company_incidents"],
                            "units-company-incidents",
                        ),
                        lg=6,
                    ),
                ]
            ),
            _bar_and_table(
                "Configured company · unit responses",
                result["companies"],
                "units-company-responses",
            ),
            html.P(
                "Company mappings are unverified by default; Unmapped remains visible until approved mappings are configured."
            ),
        ]
    if view == "locations":
        threshold = settings()["repeat_location_threshold"]
        candidates = [row for row in result["locations"] if row["count"] >= threshold]
        chosen = [row for row in incidents if row["location_key"] == selected_location]
        return [
            html.P(
                f"{result['located']:,} of {result['incidents']:,} selected incidents mapped "
                f"({result['mapping_percent']}%). The heatmap above weights each exact normalized "
                "address by distinct incident count; nearby addresses blend within a 30-pixel radius. "
                "Display intensity saturates above ten incidents at one address. "
                "Cached coordinate provenance is unverified."
            ),
            _panel(
                f"Repeat-location candidates · at least {threshold} incidents in active period",
                _table(
                    candidates,
                    [("Address", "label"), ("Incidents", "count"), ("Sample", "sample_note")],
                    "table-repeat-locations",
                ),
            ),
            _bar_and_table(
                "Property types at selected locations",
                result["property_types"],
                "location-properties",
            ),
            _panel(
                "Selected location incident detail",
                _table(_detail_rows(chosen), DETAIL_COLUMNS, "table-location-detail")
                if chosen
                else html.P("Choose a location in More filters to inspect its incidents."),
            ),
            html.P(
                "Repeat locations are candidates for investigation, not official target-hazard designations."
            ),
        ]
    if view == "detail":
        return _panel(
            f"Incident detail · {len(incidents):,} records",
            [
                html.P(
                    "Search with the global text filter; sort and filter columns below. Source references identify the selected canonical row."
                ),
                _table(_detail_rows(incidents), DETAIL_COLUMNS, "table-incidents"),
            ],
        )
    unmapped = count_by(
        [{"unit": r["apparatus_label"]} for r in responses if not r["mapped"]], "unit"
    )
    problems = [
        {**row, "issues": ", ".join(json.loads(row["issues_json"]))} for row in quality["problems"]
    ]
    return [
        dbc.Alert(
            "Response-duration analysis is unavailable: the required First Due timing reports "
            "are outside the project owner's current access. Missing durations are not zero or failed performance.",
            color="warning",
        ),
        _panel(
            "Reconciliation",
            html.Div(
                [
                    html.P(
                        f"Source rows: {snapshot.quality['source_rows']:,}; canonical incidents: "
                        f"{len(snapshot.incidents):,}; repeated normalized rows: "
                        f"{snapshot.quality['duplicate_rows']:,}."
                    ),
                    html.P(
                        f"Unresolved identities: {snapshot.quality['unresolved_identities']:,}; "
                        f"their {snapshot.quality['conflict_source_rows']:,} source rows are excluded "
                        "from canonical totals. Invalid rows: "
                        f"{snapshot.quality['invalid_rows']:,}."
                    ),
                    html.P(
                        f"Selected incidents with no validated coordinates: "
                        f"{result['incidents'] - result['located']:,}. "
                        f"Selected incidents without usable source date/time: {result['missing_timestamps']:,}."
                    ),
                ]
            ),
        ),
        _panel(
            "Unresolved and resolved source versions",
            _table(
                quality["conflicts"],
                [
                    ("Incident", "identity_key"),
                    ("Source row ID", "source_row_id"),
                    ("File", "filename"),
                    ("CSV row", "row_number"),
                    ("Source date/time", "source_timestamp"),
                ],
                "table-conflicts",
            ),
        ),
        _panel(
            "Recent row issues · latest 100",
            _table(
                problems,
                [
                    ("File", "filename"),
                    ("CSV row", "row_number"),
                    ("Incident", "identity_key"),
                    ("Status", "validation_status"),
                    ("Issue", "issues"),
                ],
                "table-issues",
            ),
        ),
        _panel("Unmapped participating apparatus", _count_table(unmapped, "table-unmapped")),
        _panel(
            "Coordinate issues · leading 100 addresses",
            _table(
                quality["coordinates"],
                [
                    ("Address", "display_name"),
                    ("Status", "validation_status"),
                    ("Incidents", "incidents"),
                    ("Coordinate source", "coordinate_source"),
                ],
                "table-coordinate-issues",
            ),
        ),
        _panel(
            "Recent imports",
            _table(
                [
                    {
                        "file": row["filename"],
                        "status": row["status"],
                        "time": row["imported_at"],
                        "source_rows": row["report"]["source_rows"],
                        "new": row["report"]["new_candidates"],
                        "duplicates": row["report"]["duplicates"],
                        "enrichments": row["report"].get("enrichments", 0),
                        "format": row["report"].get("source_format", "detailed"),
                        "conflict": row["report"]["conflict_versions"],
                        "invalid": row["report"]["invalid_rows"],
                        "importer_version": row["importer_version"],
                        "schema_version": row["schema_version"],
                        "config_version": row["config_version"],
                    }
                    for row in quality["batches"]
                ],
                [
                    ("File", "file"),
                    ("Status", "status"),
                    ("Import UTC", "time"),
                    ("Rows", "source_rows"),
                    ("New candidates", "new"),
                    ("Duplicates", "duplicates"),
                    ("Enrichments", "enrichments"),
                    ("Conflict versions", "conflict"),
                    ("Source format", "format"),
                    ("Invalid", "invalid"),
                    ("Importer", "importer_version"),
                    ("Schema", "schema_version"),
                    ("Config", "config_version"),
                ],
                "table-imports",
            ),
        ),
    ]


def _filter_from_values(values: tuple) -> Filters:
    (
        dates,
        start_hour,
        end_hour,
        weekdays,
        months,
        seasons,
        shifts,
        apparatus,
        companies,
        mode,
        dispatch,
        incident_types,
        property,
        statuses,
        locations,
        search,
        location_detail,
    ) = values
    start_hour = None if start_hour == "" else start_hour
    end_hour = None if end_hour == "" else end_hour
    start_date, end_date = dates
    weekdays = tuple(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day)
        for day in (weekdays or [])
    )
    months = tuple(
        [datetime(2000, month, 1).strftime("%B") for month in range(1, 13)].index(name) + 1
        for name in (months or [])
    )
    return Filters(
        start_date=start_date,
        end_date=end_date,
        hour_start=start_hour,
        hour_end=end_hour,
        weekdays=weekdays,
        months=months,
        seasons=tuple(seasons or []),
        shifts=tuple(shifts or []),
        apparatus=tuple(apparatus or []),
        companies=tuple(companies or []),
        mode=mode or "participation",
        dispatch_types=tuple(dispatch or []),
        incident_types=tuple(incident_types or []),
        property_types=tuple(property or []),
        statuses=tuple(statuses or []),
        locations=tuple(locations or []),
        location_detail=location_detail,
        search=search or "",
    )


def _filter_state(values: tuple) -> dict:
    filters = _filter_from_values(values)
    return {key: value for key, value in vars(filters).items() if value}


def _safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _csv_bytes(rows: list[dict], columns: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _safe_cell(row.get(key)) for key in columns})
    return stream.getvalue().encode("utf-8-sig")


def export_package(snapshot: object, filters: Filters) -> bytes:
    incidents, responses = apply_filters(snapshot, filters)
    result = summarize(incidents, responses)
    incident_rows = _detail_rows(incidents)
    response_rows = [
        {
            "incident": row["identity_key"],
            "apparatus": row["apparatus_label"],
            "configured_company": row["company"] or "Unmapped",
        }
        for row in responses
    ]
    summary_rows = [
        {
            "metric": "Distinct incidents",
            "category": "",
            "count": result["incidents"],
            "share_percent": "",
            "denominator": "selected incidents",
        },
        {
            "metric": "Unit responses",
            "category": "",
            "count": result["unit_responses"],
            "share_percent": "",
            "denominator": "selected unit responses",
        },
        {
            "metric": "Mapped incidents",
            "category": "",
            "count": result["located"],
            "share_percent": result["mapping_percent"],
            "denominator": "selected incidents",
        },
    ]
    for metric, key, denominator in (
        ("Incident type", "incident_types", "selected incidents"),
        ("Dispatch type", "dispatch_types", "selected incidents"),
        ("Property type", "property_types", "selected incidents"),
        ("Reported shift", "shifts", "selected incidents"),
        ("Apparatus unit responses", "units", "selected unit responses"),
        ("Company unit responses", "companies", "selected unit responses"),
        ("Company participating incidents", "company_incidents", "selected incidents"),
        ("Source-reported first arrivals", "first_arrivals", "selected incidents"),
    ):
        summary_rows.extend(
            {
                "metric": metric,
                "category": row["label"],
                "count": row["count"],
                "share_percent": row["share"],
                "denominator": denominator,
            }
            for row in result[key]
        )
    summary_rows.extend(
        {
            "metric": "Location incidents",
            "category": row["label"],
            "count": row["count"],
            "share_percent": round(100 * row["count"] / result["incidents"], 1)
            if result["incidents"]
            else 0,
            "denominator": "selected incidents",
        }
        for row in result["locations"]
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "incidents.csv", _csv_bytes(incident_rows, [key for _, key in DETAIL_COLUMNS])
        )
        archive.writestr(
            "unit_responses.csv",
            _csv_bytes(response_rows, ["incident", "apparatus", "configured_company"]),
        )
        archive.writestr(
            "summary.csv",
            _csv_bytes(
                summary_rows, ["metric", "category", "count", "share_percent", "denominator"]
            ),
        )
        archive.writestr(
            "metadata.json",
            json.dumps(
                {
                    "generated_utc": datetime.now(timezone.utc).isoformat(),
                    "data_version": snapshot.version,
                    "metric_version": METRIC_VERSION,
                    "config_version": settings()["version"],
                    "filters": {key: value for key, value in vars(filters).items()},
                    "definitions": {
                        "incidents": "distinct reconciled source identifiers",
                        "unit_responses": "distinct incident-apparatus participations; selected units only in participation mode",
                        "mapped": "incidents with coordinates from an exact normalized address cache match",
                    },
                    "exclusions": {
                        "unresolved_identities": snapshot.quality["unresolved_identities"],
                        "invalid_source_rows": snapshot.quality["invalid_rows"],
                        "time_filter": "records without usable source date/time excluded when temporal filters are active",
                    },
                    "field_completeness": {
                        "incidents_without_participation_list": result["missing_participation"],
                        "incidents_without_incident_type": result["missing_incident_types"],
                        "incidents_without_property_type": result["missing_property_types"],
                        "note": "Summary exports omit these fields. First-arriving apparatus is not a complete participation list; dispatch type is not final incident type.",
                    },
                },
                indent=2,
            ),
        )
    return output.getvalue()


def create_app(path: Path | None = None) -> Dash:
    with closing(connect(path)) as connection:
        snapshot = load_snapshot(connection)
    options = filter_options(snapshot)
    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.SUPERHERO],
        assets_folder=str(ROOT / "assets"),
        title="DFD Incident Analysis",
    )
    app.layout = dbc.Container(
        [
            html.Header(
                [
                    html.Div("DANBURY FIRE DEPARTMENT", className="eyebrow"),
                    html.H1("Emergency Response & Incident Analysis"),
                    html.P(
                        "Explore reconciled First Due incidents, participating apparatus, "
                        "reported classifications, and locations."
                    ),
                ],
                className="hero mb-4",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Row(
                            [
                                dbc.Col(html.H3("Filter incidents", className="m-0")),
                                dbc.Col(
                                    dbc.Button(
                                        "Reset filters", id="reset", color="warning", outline=True
                                    ),
                                    width="auto",
                                ),
                            ],
                            align="center",
                        )
                    ),
                    dbc.CardBody(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Source-reported incident dates",
                                                htmlFor="dates",
                                                className="filter-label",
                                            ),
                                            dcc.DatePickerRange(
                                                id="dates",
                                                display_format="MMM D, YYYY",
                                                minimum_nights=0,
                                                clearable=True,
                                            ),
                                        ],
                                        xs=12,
                                        lg=6,
                                        className="mb-3",
                                    ),
                                    _dropdown("Reported shift", "shifts", options["shifts"]),
                                    _dropdown("Apparatus", "apparatus", options["apparatus"]),
                                ]
                            ),
                            html.Details(
                                [
                                    html.Summary("More filters"),
                                    dbc.Row(
                                        [
                                            _hour_dropdown("From hour", "hour-start"),
                                            _hour_dropdown("To hour (exclusive)", "hour-end"),
                                            _dropdown(
                                                "Weekday",
                                                "weekdays",
                                                [
                                                    "Monday",
                                                    "Tuesday",
                                                    "Wednesday",
                                                    "Thursday",
                                                    "Friday",
                                                    "Saturday",
                                                    "Sunday",
                                                ],
                                            ),
                                            _dropdown(
                                                "Month",
                                                "months",
                                                [
                                                    datetime(2000, month, 1).strftime("%B")
                                                    for month in range(1, 13)
                                                ],
                                            ),
                                            _dropdown(
                                                "Season", "seasons", list(settings()["seasons"])
                                            ),
                                            _dropdown(
                                                "Configured company",
                                                "companies",
                                                options["companies"],
                                            ),
                                            _dropdown(
                                                "Dispatch type",
                                                "dispatch-types",
                                                options["dispatch_types"],
                                            ),
                                            _dropdown(
                                                "Incident type",
                                                "incident-types",
                                                options["incident_types"],
                                            ),
                                            _dropdown(
                                                "Property type",
                                                "property-types",
                                                options["property_types"],
                                            ),
                                            _dropdown(
                                                "Report status", "statuses", options["statuses"]
                                            ),
                                            _dropdown(
                                                "Location (multiple)",
                                                "locations",
                                                options["locations"],
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Label(
                                                        "Location detail",
                                                        htmlFor="location-detail",
                                                        className="filter-label",
                                                    ),
                                                    dcc.Dropdown(
                                                        id="location-detail",
                                                        options=_options(options["locations"]),
                                                        placeholder="Choose a location",
                                                        className="filter-dropdown",
                                                    ),
                                                    html.Small(
                                                        id="location-message",
                                                        className="text-warning",
                                                    ),
                                                ],
                                                xs=12,
                                                sm=6,
                                                lg=3,
                                                className="mb-3",
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Label(
                                                        "Incident search",
                                                        htmlFor="search",
                                                        className="filter-label",
                                                    ),
                                                    dbc.Input(
                                                        id="search",
                                                        placeholder="Number, location, or type",
                                                    ),
                                                ],
                                                xs=12,
                                                sm=6,
                                                lg=3,
                                                className="mb-3",
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Label(
                                                        "Apparatus filter meaning",
                                                        htmlFor="unit-mode",
                                                        className="filter-label",
                                                    ),
                                                    dcc.Dropdown(
                                                        id="unit-mode",
                                                        clearable=False,
                                                        value="participation",
                                                        options=[
                                                            {
                                                                "label": "Participated",
                                                                "value": "participation",
                                                            },
                                                            {
                                                                "label": "Source-reported first arrival",
                                                                "value": "first_arrival",
                                                            },
                                                        ],
                                                        className="filter-dropdown",
                                                    ),
                                                ],
                                                xs=12,
                                                sm=6,
                                                lg=3,
                                                className="mb-3",
                                            ),
                                        ],
                                        className="mt-3",
                                    ),
                                    html.P(
                                        "Filters across dimensions use AND; multiple choices in one dimension "
                                        "use OR. Hour end is exclusive; overnight ranges wrap midnight. "
                                        "Blank controls include all values.",
                                        className="small text-muted mb-0",
                                    ),
                                ],
                                className="advanced-filters",
                            ),
                        ]
                    ),
                ],
                className="filter-card mb-4",
            ),
            dbc.Row(id="cards", className="top-summary g-3 mb-2"),
            html.Div(id="context", className="context-line mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button("Download filtered CSV package", id="export", color="warning"),
                        width="auto",
                    ),
                    dbc.Col(
                        html.Span(
                            "Includes incident, unit-response, summary CSVs and metadata.",
                            className="text-muted",
                        ),
                        className="align-self-center",
                    ),
                ],
                className="mb-4 g-3",
            ),
            dcc.Download(id="download"),
            dcc.Tabs(
                id="view",
                value="overview",
                className="view-tabs",
                children=[
                    dcc.Tab(label="Overview", value="overview"),
                    dcc.Tab(label="Incident types", value="types"),
                    dcc.Tab(label="Temporal trends", value="temporal"),
                    dcc.Tab(label="Shifts & apparatus", value="units"),
                    dcc.Tab(label="Locations", value="locations"),
                    dcc.Tab(label="Incident detail", value="detail"),
                    dcc.Tab(label="Data quality", value="quality"),
                ],
            ),
            dcc.Loading(html.Div(id="view-content", className="pt-4"), type="dot", color=ORANGE),
            dcc.Interval(id="refresh", interval=30_000, n_intervals=0),
            html.Footer(
                "Local exploratory analysis · source-reported timestamps · "
                "response durations unavailable with current First Due access",
                className="py-4 text-muted small",
            ),
        ],
        fluid=True,
        className="dashboard-container px-3 px-lg-5",
    )

    @app.callback(
        Output("dates", "start_date"),
        Output("dates", "end_date"),
        *[Output(item, "value") for item in FILTER_IDS[1:] if item != "location-detail"],
        Input("reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_filters(_clicks: int) -> tuple:
        values = []
        for item in FILTER_IDS[1:]:
            if item == "location-detail":
                continue
            values.append("participation" if item == "unit-mode" else None)
        return (None, None, *values)

    filter_inputs = [
        Input("dates", "start_date"),
        Input("dates", "end_date"),
        *[Input(item, "value") for item in FILTER_IDS[1:]],
    ]

    @app.callback(
        Output("shifts", "options"),
        Output("apparatus", "options"),
        Output("companies", "options"),
        Output("dispatch-types", "options"),
        Output("incident-types", "options"),
        Output("property-types", "options"),
        Output("statuses", "options"),
        Output("locations", "options"),
        Input("refresh", "n_intervals"),
    )
    def refresh_filter_options(_refresh: int) -> tuple:
        try:
            with closing(connect(path)) as connection:
                available = filter_options(load_snapshot(connection))
        except (sqlite3.Error, OSError):
            return tuple(no_update for _ in range(8))
        return tuple(
            _options(available[key])
            for key in (
                "shifts",
                "apparatus",
                "companies",
                "dispatch_types",
                "incident_types",
                "property_types",
                "statuses",
                "locations",
            )
        )

    @app.callback(
        Output("context", "children"),
        Output("cards", "children"),
        Output("view-content", "children"),
        Input("view", "value"),
        Input("refresh", "n_intervals"),
        *filter_inputs,
    )
    def update_view(
        view: str, _refresh: int, start_date: str, end_date: str, *control_values: object
    ) -> tuple:
        values = ((start_date, end_date), *control_values)
        try:
            filters = _filter_from_values(values)
        except ValueError as error:
            return (
                dbc.Alert(str(error), color="danger"),
                [],
                html.P("Adjust the filter to continue."),
            )
        try:
            with closing(connect(path)) as connection:
                current = load_snapshot(connection)
                quality = quality_details(connection) if view == "quality" else {}
        except (sqlite3.Error, OSError) as error:
            return (
                dbc.Alert(f"Database unavailable: {error}", color="danger"),
                [],
                html.P("Check the local database path and permissions."),
            )
        incidents, responses = apply_filters(current, filters)
        result = summarize(incidents, responses)
        observed = [
            row["local_timestamp"][:10] for row in current.incidents if row["local_timestamp"]
        ]
        bounds = f"{min(observed)} to {max(observed)}" if observed else "No dated incidents"
        last_import = (
            datetime.fromisoformat(current.last_import).strftime("%Y-%m-%d %H:%M UTC")
            if current.last_import
            else "Never"
        )
        context = html.Div(
            [
                html.Span(f"Observed dates: {bounds} · Last import: {last_import}"),
                html.Div(
                    f"{result['missing_participation']:,} selected incidents have no participation "
                    f"list; {result['missing_incident_types']:,} have no final incident type; "
                    f"{result['missing_property_types']:,} have no property type. "
                    "New summary exports omit these fields. Unit-response totals include only "
                    "reported participation; use first-arrival mode for reported first units."
                )
                if any(
                    result[key]
                    for key in (
                        "missing_participation",
                        "missing_incident_types",
                        "missing_property_types",
                    )
                )
                else None,
                html.Details(
                    [
                        html.Summary("Data context and active filters"),
                        html.Span(
                            f"Selected: {len(incidents):,} incidents · "
                            f"{len(responses):,} unit responses · data version {current.version}. "
                            "Coverage between observed dates is unverified."
                        ),
                        html.Span(
                            f"Active filters: {json.dumps(_filter_state(values), default=str)}"
                        ),
                    ]
                ),
            ]
        )
        metric_cards = [
            _card("Distinct incidents", f"{result['incidents']:,}", "Reconciled identities"),
            _card(
                "Unit responses",
                f"{result['unit_responses']:,}",
                "All participants in first-arrival mode"
                if filters.mode == "first_arrival"
                else "Matching units in participation mode",
            ),
            _card(
                "Mapped incidents",
                f"{result['mapping_percent']}%",
                f"{result['located']:,} of {result['incidents']:,}",
            ),
            _card(
                "Unresolved identities",
                str(current.quality["unresolved_identities"]),
                "Excluded from canonical totals",
            ),
        ]
        cards = [
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H4("Incident concentration", className="m-0")),
                        dbc.CardBody(
                            dcc.Graph(
                                figure=_location_map(result["locations"]),
                                config={"displaylogo": False, "scrollZoom": False},
                                className="summary-map-graph",
                            ),
                            className="p-0",
                        ),
                        dbc.CardFooter(
                            [
                                html.Div(
                                    [
                                        html.Span("Fewer incidents"),
                                        html.Span(className="heat-gradient"),
                                        html.Span("More incidents"),
                                    ],
                                    className="heat-legend",
                                ),
                                html.Div(
                                    f"{result['located']:,} of {result['incidents']:,} selected "
                                    f"incidents mapped ({result['mapping_percent']}%). Heat is "
                                    "weighted by distinct incidents at each matched address "
                                    "(display capped at ten per address). "
                                    "Road tiles: OpenStreetMap; internet access required."
                                ),
                            ],
                            className="summary-map-note",
                        ),
                    ],
                    className="analysis-card h-100",
                ),
                xs=12,
                lg=8,
            ),
            dbc.Col(dbc.Row(metric_cards, className="g-2"), xs=12, lg=4),
        ]
        return (
            context,
            cards,
            _view_content(
                view,
                result,
                incidents,
                responses,
                current,
                quality,
                filters.location_detail,
            ),
        )

    @app.callback(
        Output("location-detail", "options"),
        Output("location-detail", "value"),
        Output("location-message", "children"),
        Input("refresh", "n_intervals"),
        Input("reset", "n_clicks"),
        *filter_inputs[:-1],
        State("location-detail", "value"),
    )
    def refresh_locations(
        _refresh: int, _reset: int, start_date: str, end_date: str, *values_and_selected: object
    ) -> tuple:
        *other_values, selected = values_and_selected
        if ctx.triggered_id == "reset":
            selected = None
        values = ((start_date, end_date), *other_values, None)
        try:
            filters = _filter_from_values(values)
        except ValueError:
            return [], None, "Location selection cleared while filters are invalid."
        try:
            with closing(connect(path)) as connection:
                current = load_snapshot(connection)
        except (sqlite3.Error, OSError):
            return [], None, "Database unavailable; check local path and permissions."
        incidents, _ = apply_filters(current, filters)
        available = {row["location_key"] for row in incidents if row["location_key"]}
        options = _options(sorted(available))
        if selected and selected not in available:
            return (
                options,
                None,
                "Selected location is unavailable under the current filters and was cleared.",
            )
        return options, selected, ""

    @app.callback(
        Output("download", "data"),
        Input("export", "n_clicks"),
        *[State(item.component_id, item.component_property) for item in filter_inputs],
        prevent_initial_call=True,
    )
    def export(_clicks: int, start_date: str, end_date: str, *control_values: object) -> dict:
        filters = _filter_from_values(((start_date, end_date), *control_values))
        with closing(connect(path)) as connection:
            current = load_snapshot(connection)
        payload = export_package(current, filters)
        return dcc.send_bytes(payload, "dfd-filtered-analysis.zip")

    return app
