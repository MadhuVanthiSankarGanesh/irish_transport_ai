#!/usr/bin/env python3
"""Get real stop coordinates for testing."""
import pandas as pd

stops = pd.read_csv('data/clean/stops.csv')
print(f'Total stops in network: {len(stops)}')
print(f'\nFirst 10 stops:')
print(stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']].head(10).to_string())

# Get Dublin city center stops
print(f'\n\nSearching for city center/major stops:')
keywords = ['Connolly', 'Heuston', 'Tara', 'Trinity', 'Dame', 'College', 'Liffey', 'Bridge']
for keyword in keywords:
    matches = stops[stops['stop_name'].str.contains(keyword, case=False, na=False)]
    if len(matches) > 0:
        print(f'\n{keyword}:')
        for idx, row in matches.head(2).iterrows():
            print(f'  {row["stop_name"]}: {row["stop_lat"]:.5f},{row["stop_lon"]:.5f}')
