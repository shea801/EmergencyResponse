import pandas as pd
import os
import sys
import glob # regex for finding files
import numpy as np
import json
import re

def lat_lon(df: pd.DataFrame|pd.Series):
    import ssl
    import re
    import certifi
    from geopy.exc import GeocoderUnavailable
    from geopy.geocoders import Nominatim
    from time import sleep

    # make sure the right columns are present
    if 'ADDRESS' not in df.columns:
        if 'LOCATION' not in df.columns:
            raise ValueError("DataFrame must contain 'ADDRESS' or 'LOCATION' column")
        else:
            df['ADDRESS'] = df['LOCATION']

    latlon_dict = {}  # keys will be the addresses, values will be a dict with lat and lon
    add_dict = df.ADDRESS.to_dict()  # keys will be the index (Timestamp), values will be the address
    for idx, address in add_dict.items():
        if address is None:
            continue
        elif address.startswith("7 BACKUS AVE"):
            add = "7 BACKUS AVE DANBURY 06810"
        elif '&' in address:
            add = address.replace('&', 'AND')
        else:
            add = address
        # Use a known CA bundle instead of relying on the machine's default store.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        geolocator = Nominatim(user_agent="emergency_response", ssl_context=ssl_context, timeout=7)

        # Remove the apartment number by replacing it with just "DANBURY" using str.replace (if it's present).
        apartment_number = re.findall(r"\w*\d+ DANBURY\b", add)
        if isinstance(apartment_number, list) and len(apartment_number) > 0:
            is_unit_number = apartment_number[0].split(' ')[0].isdigit()
            if is_unit_number:
                add = add.replace(apartment_number[0], "DANBURY")
        try:
            location = geolocator.geocode(add)
        except GeocoderUnavailable as exc:
            location = None
            print(f"Geocoding service unavailable: {exc}")
            continue
        sleep(1)
        if location is None:
            print("Could not geocode the address right now.")
            continue
        else:
            latlon_dict[address] = {'LATITUDE': location.latitude, 'LONGITUDE': location.longitude}
            print(f"{address}: {location.latitude}, {location.longitude}")
            lat = latlon_dict.get(address)
            lon = latlon_dict.get(address)
            longitude = lon.get('LONGITUDE')
            latitude = lat.get('LATITUDE')
            if latitude is not None and longitude is not None:
                df.loc[idx, 'LATITUDE'] = latitude
                df.loc[idx, 'LONGITUDE'] = longitude
            else:
                df.loc[idx, 'LATITUDE'] = np.nan
                df.loc[idx, 'LONGITUDE'] = np.nan

    return df[['ADDRESS', 'LATITUDE', 'LONGITUDE']]

class IncidentData:
    _cached_df = None  # class-level cache for the full unfiltered dataset

    def __init__(self, start_time='', end_time='', month=0):
        self.start_time = start_time
        self.end_time = end_time
        self.month = month
        if IncidentData._cached_df is None:
            IncidentData._cached_df = self._load_data_raw()
        self.df = self._apply_filters(IncidentData._cached_df.copy())

    def _load_data_raw(self):
        """Load and transform all CSV data once. No filtering applied."""
        path = os.path.join('incident_reports', '*.csv')
        all_files = glob.glob(path)

        if not all_files:
            all_files = glob.glob('Incident Report*.csv')

        li = []
        for filename in all_files:
            df = pd.read_csv(filename, index_col=None, header=0, encoding='utf-8-sig')
            li.append(df)

        if not li:
            return pd.DataFrame()

        full_df = pd.concat(li, axis=0, ignore_index=True)

        rename_map = {
            'INCIDENT DATE/TIME': 'DATE_TIME',
            'INCIDENT LOCATION': 'LOCATION',
            'INCIDENT TYPE': 'TYPE',
            '1ST ARRIVING': 'UNIT',
            'APPARATUS': 'APPARATUS'
        }
        full_df.rename(columns=rename_map, inplace=True)

        full_df['DATE_TIME'] = pd.to_datetime(full_df['DATE_TIME'], errors='coerce')
        full_df = full_df.dropna(subset=['DATE_TIME'])
        full_df.set_index('DATE_TIME', inplace=True, drop=False)

        series = pd.Series(np.zeros(len(full_df.index)), index=full_df.index)
        full_df['ADDRESS'] = full_df.LOCATION
        full_df['LATITUDE'] = series
        full_df['LONGITUDE'] = series

        for idx_val, add in full_df['ADDRESS'].items():
            if add is not None:
                apartment_number = re.findall(r"\w*\d+ DANBURY\b", add)
                if isinstance(apartment_number, list) and len(apartment_number) > 0:
                    is_unit_number = apartment_number[0].split(' ')[0].isdigit()
                    if is_unit_number:
                        cleaned = add.replace(apartment_number[0], "DANBURY")
                        full_df.loc[idx_val, 'ADDRESS'] = cleaned

        with open('latitude_longitude_addresses.json', 'r') as jf:
            data = json.load(jf)
        if data is None:
            raise ValueError("Could not load latitude_longitude_addresses")

        # Build a DataFrame from the JSON for vectorized update instead of row-by-row .loc
        json_records = [
            v for v in data.values()
            if v.get('date') and v.get('ADDRESS')
        ]
        if json_records:
            json_df = pd.DataFrame(json_records)
            json_df['date'] = pd.to_datetime(json_df['date'])
            json_df.set_index('date', inplace=True)
            # Update only rows whose index matches
            common_idx = full_df.index.intersection(json_df.index)
            if not common_idx.empty:
                full_df.loc[common_idx, 'ADDRESS'] = json_df.loc[common_idx, 'ADDRESS']
                full_df.loc[common_idx, 'LATITUDE'] = json_df.loc[common_idx, 'LATITUDE']
                full_df.loc[common_idx, 'LONGITUDE'] = json_df.loc[common_idx, 'LONGITUDE']

        if 'UNIT' not in full_df.columns:
            full_df['UNIT'] = ''
        else:
            full_df['UNIT'] = full_df['UNIT'].fillna('')

        return full_df

    def _apply_filters(self, df):
        """Apply month and time filters to an already-loaded DataFrame."""
        if df.empty:
            return df

        # Ensure the index is a DatetimeIndex after copy
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        if self.month != 0:
            df = df[df.index.month == self.month]

        if self.start_time and self.end_time and self.start_time != '--' and self.end_time != '--':
            df = df.between_time(self.start_time, self.end_time)

        return df

    def all(self):
        return self.df

    def company(self, unit):
        # Filter where the unit is in the APPARATUS string or matches UNIT
        if self.df.empty:
            return self.df
        return self.df[self.df['APPARATUS'].str.contains(unit, na=False) | (self.df['UNIT'] == unit)]

    def unit_df(self):
        # This seems to be used for total_calls per unit
        # dfu = IncidentData('', '', '').unit_df()
        # total_calls = pd.Series([dfu[x].sum() for x in dfu.columns], index=dfu.columns)
        if self.df.empty:
            return pd.DataFrame()
            
        # Create a pivot table or similar that shows counts per unit over time
        # The main.py uses dfu[x].sum() so it expects numeric values, likely 1 for presence
        units = [
            'Car 30',
            'Truck 1',
            'Tac 1',
            'Squad 21',
            'Engine 22',
            'Engine 23',
            'Engine 24',
            'Engine 25',
            'Engine 26'
        ]
        unit_counts = pd.DataFrame(index=self.df.index)
        for u in units:
            unit_counts[u] = self.df['APPARATUS'].str.contains(u, na=False).astype(int)
        return unit_counts
