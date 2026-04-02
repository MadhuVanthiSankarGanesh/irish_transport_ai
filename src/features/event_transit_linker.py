import pandas as pd
import os
from sklearn.neighbors import KDTree
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

events_path = os.path.join(BASE_DIR, "data", "events", "failte_events.csv")
stops_path = os.path.join(BASE_DIR, "data", "clean", "stops.csv")

print("Loading datasets...")

events = pd.read_csv(events_path)
stops = pd.read_csv(stops_path)

print("Events:", len(events))
print("Transit stops:", len(stops))

# Remove events without coordinates
events = events.dropna(subset=["latitude", "longitude"])

print("Events with coordinates:", len(events))

# Build KDTree from stop coordinates
stop_coords = stops[["stop_lat", "stop_lon"]].values
tree = KDTree(stop_coords, metric="euclidean")

print("KDTree built")

# Query nearest stop for each event
event_coords = events[["latitude", "longitude"]].values
distances, indices = tree.query(event_coords, k=1)

results = []

for i, event in events.iterrows():

    idx = indices[i][0]
    stop = stops.iloc[idx]

    results.append({
        "event_name": event["event_name"],
        "event_lat": event["latitude"],
        "event_lon": event["longitude"],
        "stop_id": stop["stop_id"],
        "stop_name": stop["stop_name"],
        "stop_lat": stop["stop_lat"],
        "stop_lon": stop["stop_lon"],
        "distance": distances[i][0]
    })

df = pd.DataFrame(results)

os.makedirs(os.path.join(BASE_DIR, "data", "features"), exist_ok=True)

output = os.path.join(BASE_DIR, "data", "features", "event_stop_links.csv")

df.to_csv(output, index=False)

print("Saved:", output)
print("Total links:", len(df))
