import pandas as pd
import dash
from dash import html, dcc, Output, Input
import dash_bootstrap_components as dbc
from Incident_Data import IncidentData
from dashboard_components import DashboardComponents

# DFD list of Career Division fire companies
companies = ['ALL', 'C30', 'T1', 'TAC1', 'SQ21', 'E22', 'E23', 'E24', 'E25', 'E26']

# list of times for dropdown menus
times = ['--']
times.extend([f'0{x}:00:00' if x < 10 else f'{x}:00:00' for x in range(24)])

hours = ['--']
hours.extend([f'0{x}:00 hrs' if x < 10 else f'{x}:00 hrs' for x in range(24)])

hours_dict = {x: y for x, y in zip(hours, times)}

# list of month's to use in dictionary for dropdown menus
monthname = ['--', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
             'September', 'October', 'November', 'December']
months = {m: int(i) for m, i in zip(monthname, list(range(0, 13)))}

# Initialize Data and Components
data_manager = IncidentData('', '', 0)
components_manager = DashboardComponents(companies, times, monthname)

# Initial data for sidebar tables
df1 = data_manager.all()
# Clean location for display in tables
if not df1.empty:
    df1['LOCATION_CLEAN'] = df1.LOCATION.apply(lambda x: str(x)[:-11] if len(str(x)) > 11 else str(x))
else:
    df1['LOCATION_CLEAN'] = pd.Series(dtype='str')

dfu = data_manager.unit_df()
dfu.index.name = 'Incident Date & Time'

total_calls_series = pd.Series([dfu[x].sum() for x in dfu.columns], index=dfu.columns)
total_calls_series.index.name = 'Unit'

loc_count = df1['LOCATION'].value_counts()[df1['LOCATION'].value_counts() > 14]
loc_count.index.name = 'Location'
loc_count_dict = {k: v for k, v in zip(loc_count.index, range(len(loc_count.index)))}

type_count = df1['TYPE'].value_counts()[df1['TYPE'].value_counts() > 14]
type_count.index.name = 'Response Type'

# ~~~~~ DASH APP INITIALIZATION ~~~~~
app = dash.Dash(__name__,
                prevent_initial_callbacks=False,
                external_stylesheets=[dbc.themes.SUPERHERO])

app.layout = dbc.Container([
    html.Div([
        dbc.Row([
            dbc.Col(lg=1),
            dbc.Col(
                dbc.Stack([  # Header
                    html.H1("DANBURY FIRE DEPARTMENT RESPONSE DASHBOARD",
                            style={'color': '#df6919'}),
                    html.P(  # dashboard description
                        """
                        This is a dashboard application to showcase Fire Department response data 
                        for the City of Danbury. Select parameters to show response data for various
                        time periods, month, and/or DFD Career Division unit. The City has a 
                        Shift Commander/Command Car, 5 engine companies, 1 Squad/Rescue, 1 Truck company, 
                        and 1 Tactical Unit.
                        """,
                        style={'color': '#abb6c2'}),
                ]), lg=8, style={'textAlign': 'center'},
            ),
            dbc.Col(lg=1),
        ], class_name='p-3', justify='between'),
    ]),
    # ~~~~~ DROP DOWN MENUS ~~~~~
    html.Div([
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Select a Start Time"), style={'textAlign': 'center'}),
                    dbc.CardBody(
                        dcc.Dropdown(options=hours, value=hours[0], clearable=False, id='time1'),
                        class_name='text-dark'),
                ], class_name='bg-primary border-rounded'), lg=2, width={'offset': 1}),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Select an End Time"), style={'textAlign': 'center'}),
                    dbc.CardBody(
                        dcc.Dropdown(options=hours, value=hours[0], clearable=False, id='time2'),
                        class_name='text-dark'),
                ], class_name='bg-primary border-rounded'), lg=2),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Select a Month"), style={'textAlign': 'center'}),
                    dbc.CardBody(
                        dcc.Dropdown(options=monthname, value=monthname[0], clearable=False, id='month'),
                        class_name='text-dark'),
                ], class_name='bg-primary border-rounded'), lg=2),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5("Select a DFD Unit"), style={'textAlign': 'center'}),
                    dbc.CardBody(
                        dcc.Dropdown(options=companies, value=companies[0], clearable=False, id='company'),
                        class_name='text-dark'),
                ], class_name='bg-primary border-rounded'), lg=2),
        ], justify='center'),
    ]),
    html.Div([
        dbc.Row([
            dbc.Col(  # Card Stack
                dbc.Stack([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Total Responses by Unit"), class_name='text-body'),
                        dbc.CardBody(
                            dbc.Table.from_dataframe(
                                total_calls_series.to_frame(), striped=True, bordered=True, hover=True, index=True
                            ),
                            class_name='bg-light'),
                    ], class_name='card-text-body bg-primary card-header'),
                    dbc.Card([
                        dbc.CardHeader(html.H5("Top 7 Response Locations"), class_name='text-body'),
                        dbc.CardBody(
                            dbc.Table.from_dataframe(
                                loc_count.head(7).to_frame(), striped=True, bordered=True, hover=True, index=True
                            ),
                            class_name='bg-light'),
                    ], class_name='card-text-body bg-primary card-header'),
                    dbc.Card([
                        dbc.CardHeader(html.H5("Top 7 Response Types"), class_name='text-body'),
                        dbc.CardBody(
                            dbc.Table.from_dataframe(
                                type_count.head(7).to_frame(), striped=True, bordered=True, hover=True, index=True
                            ),
                            class_name='bg-light'),
                    ], class_name='card-text-body bg-primary card-header'),
                ], gap=2), lg=2),
            dbc.Col(  # main panel
                dbc.Row([
                    dbc.Col(  # Graphs
                        dbc.Stack([
                            dcc.Graph(id="densitymap"),
                            dcc.Graph(id='incidentlocation'),
                            dbc.Row(
                                dbc.Col(
                                    dbc.Card([
                                        dbc.CardHeader(
                                            html.H5("Select one of the Frequently Responded Locations",
                                                    style={'textAlign': 'center'}),
                                            class_name='card-text-body bg-primary'),
                                        dbc.CardBody([
                                            dcc.Dropdown(options=loc_count.index,
                                                         value=loc_count.index[0] if not loc_count.empty else None,
                                                         clearable=False, maxHeight=105, id='freq_loc'),
                                            html.Br(),
                                            html.H6("""
                                            Each of the above locations has had at least 15 Fire Department
                                            responses over the past year. Select a location to view the 
                                            breakdown and number of specific incident types.""",
                                                    style={'color': 'rgb(255,255,255)'}),
                                        ], class_name='text-dark bg-primary'),
                                    ]), lg=10, width={'offset': 1}, class_name='pt-5 border-primary'),
                            ),
                            dbc.Row(
                                dbc.Col([
                                    dbc.CardGroup([
                                        dbc.Card(
                                            dbc.CardBody([
                                                html.P(
                                                    "Total Number of Incidents at",
                                                    style={'textAlign': 'center', 'fontSize': 20}
                                                ),
                                                html.P(
                                                    id='total_calls_loc',
                                                    style={'textAlign': 'center', 'fontSize': 22}
                                                )
                                            ], class_name='m-3 card-text-body bg-dark'),
                                            class_name='bg-primary border-primary',
                                        ),
                                        dbc.Card(
                                            dbc.CardBody([
                                                html.Br(),
                                                html.P(
                                                    id='total_incidents',
                                                    style={'fontSize': 54, 'fontWeight': 'bold', 'textAlign': 'center'}
                                                ),
                                            ], class_name='m-3 bg-dark'),
                                            class_name='bg-primary text-body border-primary',
                                        ),
                                    ], class_name='border-primary',
                                    ),
                                ], lg=10, width={'offset': 1}),
                                class_name='pt-2 border-primary',
                            ),
                        ]), lg=5),
                    dbc.Col(
                        dbc.Stack([
                            dcc.Graph(id='incidenttype'),
                            dcc.Graph(id='timeperiod'),
                            dcc.Graph(id='pie_freq_loc_type'),
                        ]), lg=5, width={'offset': 1}),
                ]),
            ),
        ]),
    ]),
], fluid=True)

# ~~~~~ CALLBACKS ~~~~~
@app.callback(
    Output('densitymap', 'figure'),
    [
        Input('time1', 'value'),
        Input('time2', 'value'),
        Input('month', 'value'),
        Input('company', 'value')
     ]
)
def update_density_map(t1, t2, mon, comp):
    data = IncidentData(hours_dict.get(t1,'--'), hours_dict.get(t2,'--'), months.get(mon,'--'))
    return components_manager.incident_heat_map(data, comp)

@app.callback(
    Output('incidentlocation', 'figure'),
    [
        Input('time1', 'value'),
        Input('time2', 'value'),
        Input('month', 'value'),
        Input('company', 'value')
    ]
)
def update_incident_location(t1, t2, mon, comp):
    data = IncidentData(hours_dict.get(t1,'--'), hours_dict.get(t2,'--'), months.get(mon,'--'))
    return components_manager.incident_locations(data, comp, t1, t2, mon)

@app.callback(
    Output('incidenttype', 'figure'),
    [
        Input('time1', 'value'),
        Input('time2', 'value'),
        Input('month', 'value'),
        Input('company', 'value')
    ]
)
def update_incident_type(t1, t2, mon, comp):
    data = IncidentData(hours_dict.get(t1,'--'), hours_dict.get(t2,'--'), months.get(mon,'--'))
    return components_manager.incident_type_total(data, comp)

@app.callback(
    Output('timeperiod', 'figure'),
    [
        Input('time1', 'value'),
        Input('time2', 'value'),
        Input('month', 'value'),
        Input('company', 'value')
    ]
)
def update_time_period(t1, t2, mon, comp):
    data = IncidentData(hours_dict.get(t1,'--'), hours_dict.get(t2,'--'), months.get(mon,'--'))
    return components_manager.time_period_totals(data, comp, t1, t2, mon)

@app.callback(
    Output('total_calls_loc', 'children'),
    Input('freq_loc', 'value'))
def update_total_calls_loc(freqloc):
    return freqloc

@app.callback(
    Output('total_incidents', 'children'),
    Input('freq_loc', 'value'))
def update_number_total_loc(freqloc):
    if freqloc in loc_count:
        return loc_count[freqloc]
    return 0

@app.callback(
    Output('pie_freq_loc_type', 'figure'),
    Input('freq_loc', 'value'))
def update_freq_loc_type(freqloc):
    if freqloc in loc_count:
        idx = list(loc_count.index).index(freqloc)
        return components_manager.pie_location(idx, data_manager)
    return {}

if __name__ == '__main__':
    app.run(debug=True)
