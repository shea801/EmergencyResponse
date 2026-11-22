import plotly.express as px
import pandas as pd

class DashboardComponents:
    def __init__(self, companies, times, monthname):
        self.companies = companies
        self.times = times
        self.monthname = monthname

    def graph_colors(self, df_graph_category, len_df_category, color='red'):
        red = px.colors.n_colors('rgb(165,0,0)', 'rgb(255,0,0)', len_df_category, colortype='rgb')
        blue = px.colors.n_colors('rgb(0,0.001,150)', 'rgb(0,150,150)', len_df_category, colortype='rgb')
        green = px.colors.n_colors('rgb(0,150,.001)', 'rgb(0,125,125)', len_df_category, colortype='rgb')
        yellow = px.colors.n_colors('rgb(255,255,0)', 'rgb(255,125,0)', len_df_category, colortype='rgb')
        dark_blue = px.colors.n_colors('rgb(.001,.001,75)', 'rgb(50,50,200)', len_df_category, colortype='rgb')
        red_blue = px.colors.n_colors('rgb(255,.001,.001)', 'rgb(.001,.001,255)', len_df_category, colortype='rgb')
        green_blue = px.colors.n_colors('rgb(0,255,.001)', 'rgb(0,.001,255)', len_df_category, colortype='rgb')

        color_list = {'red': red, 'blue': blue, 'green': green, 'yellow': yellow, 'dark_blue': dark_blue,
                      'rd_bl': red_blue, 'gr_bl': green_blue}

        mapper = {x: y for x, y in zip(df_graph_category, color_list[color])}
        return mapper

    def incident_heat_map(self, df_dhm, unit):
        district = {
            'HQ': (41.393510, -73.455480),
            'E23': (41.407951, -73.436729),
            'E24': (41.413050, -73.422240),
            'E25': (41.427157, -73.504407),
            'E26': (41.373615, -73.487025),
            'CITY HALL': (41.3918413, -73.4537671),
        }

        if unit not in self.companies[1:]:
            df_final = df_dhm.all()
            t = "Incident Concentrations for the City of Danbury"
        else:
            df_final = df_dhm[df_dhm['STATION' == unit]]
            t = f'Incident Concentration for {unit}'

        if unit not in ['E23', 'E24', 'E25', 'E26']:
            latt = district['HQ'][0]
            long = district['HQ'][1]
            z = 11
            r = 6
        elif unit == 'CITY HALL':
            latt = district['CITY HALL'][0]
            long = district['CITY HALL'][1]
        else:
            latt = district[unit][0]
            long = district[unit][1]
            z = 12
            r = 8

        fig = px.density_mapbox(data_frame=df_final,
                                lat='LATITUDE',
                                lon='LONGITUDE',
                                hover_data=['TYPE', 'LOCATION'],
                                center={'lat': latt, 'lon': long},
                                color_continuous_scale=px.colors.sequential.ice,
                                zoom=z,
                                mapbox_style='open-street-map',
                                radius=r,
                                title=t,
                                height=600,
                                width=800, )
        fig.update_layout(coloraxis_showscale=False,
                          title={'x': .5, 'xref': 'paper', 'xanchor': 'auto'},
                          font={'color': 'rgb(255,255,255)'},
                          paper_bgcolor='#0f2537')
        return fig

    def incident_locations(self, df_lbar, unit, t1, t2, mon):
        if t1 not in self.times[1:] and t2 not in self.times[1:] and mon not in self.monthname[1:]:
            if unit not in self.companies[1:]:
                df_final = df_lbar.all()
                v_c = df_final['LOCATION'].value_counts()[df_final['LOCATION'].value_counts() >= 20]
                t = 'Total Number of Incidents per Location with 20 or more Responses'
            else:
                df_final = df_lbar[df_lbar['STATION'] == unit]
                v_c = df_final['LOCATION'].value_counts()[df_final['LOCATION'].value_counts() >= 5]
                t = f'Total Number of Responses per Location by {unit} with 5 or more Responses'
        else:
            if unit not in self.companies[1:]:
                df_final = df_lbar.all()
                v_c = df_final['LOCATION'].value_counts()
                t = 'Total Number of Responses per Location'
            else:
                df_final = df_lbar[df_lbar['STATION'] == unit]
                v_c = df_final['LOCATION'].value_counts()
                t = f'Total Number of Responses per Location by {unit}'

        fig = px.bar(data_frame=v_c,
                      x=v_c.index,
                      y=v_c,
                      color=v_c.index,
                      color_discrete_map=self.graph_colors(v_c.index, len(v_c.index), color='dark_blue'),
                      title=t,
                      height=600,
                      width=800)
        fig.update_xaxes(tickangle=45,
                          tickfont=dict(size=10))
        fig.update_layout(yaxis_title='Total Incidents to Location',
                           xaxis_title='Location',
                           showlegend=False,
                           title={'x': .5, 'xref': 'paper', 'xanchor': 'auto'},
                           font={'color': 'rgb(255,255,255)'},
                           paper_bgcolor='#0f2537',
                           plot_bgcolor='#abb6c2')
        return fig

    def incident_type_total(self, df_tth, unit):
        if unit in self.companies[1:]:
            df_final = df_tth.company(unit)
            t = f"{unit} Incident Count by Type"
        else:
            df_final = df_tth.all()
            t = "Total Incidents for the Danbury Fire Department"

        fig = px.histogram(data_frame=df_final,
                                  x='TYPE',
                                  color='TYPE',
                                  color_discrete_map=self.graph_colors(
                                      df_final.TYPE.unique(), len(df_final.TYPE.unique()), 'green'
                                  ),
                                  title=t,
                                  height=600,
                                  width=800)
        fig.update_layout(yaxis_title='Number of Incidents',
                                 xaxis_title='Incident Type',
                                 showlegend=False,
                                 title={'x': .5, 'xref': 'paper', 'xanchor': 'auto'},
                                 font={'color': 'rgb(255,255,255)'},
                                 paper_bgcolor='#0f2537',
                                 plot_bgcolor='#abb6c2')
        fig.update_xaxes(tickangle=45,
                                tickfont=dict(size=10))
        return fig

    def time_period_totals(self, df_tpt, unit, t1, t2, mon):
        if unit in self.companies[1:]:
            df_final = df_tpt[df_tpt['STATION'] == unit]
        else:
            df_final = df_tpt.all()

        if mon in self.monthname[1:] and t1 not in self.times[1:] and t2 not in self.times[1:]:
            if unit not in self.companies[1:]:
                t = f"Total Number of Incidents per Hourly Period for the Month of {mon}"
            else:
                t = f"Total Number of Incidents for {unit} per Hourly Period for the Month of {mon}"
        elif mon not in self.monthname[1:] and (t1 not in self.times[1:] or t2 not in self.times[1:]):
            if unit not in self.companies[1:]:
                t = 'Total Number of Incidents per Hourly Period'
            else:
                t = f'Total Number of Incidents per Hourly Period for {unit}'
        else:
            if unit not in self.companies[1:]:
                t = f"Total Number of Incidents per Hourly Period from {t1} to {t2}"
            else:
                t = f"Total Number of Incidents per Hourly Period from {t1} to {t2} for {unit}"

        daytimes = [f'0{x}:00' if x < 10 else f'{x}:00' for x in range(24)]
        hourly = [f'{daytimes[t - 1]}-{daytimes[t]}' for t in range(1, len(daytimes))]
        hourly.append('23:00-00:00')

        periodtotalincidents = []
        for x in range(len(daytimes)):
            if x != 23:
                total_inc = df_final.iloc[
                    df_final.index.indexer_between_time(daytimes[x], daytimes[x + 1], include_end=False)].TYPE.count()
                periodtotalincidents.append(total_inc)
            else:
                total_inc = df_final.iloc[
                    df_final.index.indexer_between_time(daytimes[x], '00:00:00', include_end=False)].TYPE.count()
                periodtotalincidents.append(total_inc)
        periodtotalincidents = pd.Series(periodtotalincidents, index=hourly, name='Total')

        fig = px.bar(data_frame=periodtotalincidents,
                           x=periodtotalincidents.index,
                           y=periodtotalincidents,
                           color=periodtotalincidents.index,
                           color_discrete_map={i: '#cc0000' for i in periodtotalincidents.index},
                           title=t,
                           height=600,
                           width=800, )
        fig.update_layout(xaxis_title='Time Period',
                                yaxis_title='Total Incidents per Period',
                                showlegend=False,
                                title={'x': .5, 'xref': 'paper', 'xanchor': 'auto'},
                                font={'color': 'rgb(255,255,255)'},
                                paper_bgcolor='#0f2537',
                                plot_bgcolor='#abb6c2')
        fig.update_xaxes(tickangle=45,
                               tickfont=dict(size=12))
        return fig

    def pie_location(self, i, incident_data_instance):
        df_pie1 = incident_data_instance.all()
        locations = df_pie1['LOCATION'].value_counts()[df_pie1['LOCATION'].value_counts() > 14]
        loc_type = df_pie1[df_pie1['LOCATION'].str.contains(locations.index[i], na=False)]
        
        fig = px.pie(loc_type,
                         names='TYPE',
                         color='TYPE',
                         color_discrete_sequence=px.colors.sequential.YlOrRd,
                         title=f'Types of Incident Responses to {locations.index[i]}',
                         height=600,
                         width=800)
        fig.update_traces(textinfo='value')
        fig.update_layout(legend_font=dict(size=10),
                              legend_y=.5,
                              font={'color': 'rgb(255,255,255)'},
                              paper_bgcolor='#0f2537')

        return fig
