import os
import pickle

import networkx as nx
import pandas as pd
from pathlib import Path
from sklearn.neighbors import KDTree
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

stops_path = os.path.join(BASE_DIR, "data", "clean", "stops.csv")
stop_times_path = os.path.join(BASE_DIR, "data", "clean", "stop_times.csv")
trips_path = os.path.join(BASE_DIR, "data", "clean", "trips.csv")
routes_path = os.path.join(BASE_DIR, "data", "clean", "routes.csv")

print("Loading GTFS data...")

with Path(stops_path).open("r", encoding="utf-8") as f:
    stops = pd.read_csv(f)
with Path(trips_path).open("r", encoding="utf-8") as f:
    trips = pd.read_csv(f, usecols=["trip_id", "route_id", "direction_id"])
with Path(routes_path).open("r", encoding="utf-8") as f:
    routes = pd.read_csv(f, usecols=["route_id", "route_type"])

routes = routes[routes["route_type"].isin([0, 2, 3])]
trips = trips.merge(routes, on="route_id", how="inner")

# Use a representative trip per route to keep the graph small/fast
if "direction_id" in trips.columns:
    trips = trips.sort_values(["route_id", "direction_id"]).groupby(
        ["route_id", "direction_id"], as_index=False
    ).first()
else:
    trips = trips.sort_values(["route_id"]).groupby(
        ["route_id"], as_index=False
    ).first()

# Dublin bounding box filter
stops = stops[
    (stops["stop_lat"] >= 53.2)
    & (stops["stop_lat"] <= 53.45)
    & (stops["stop_lon"] >= -6.45)
    & (stops["stop_lon"] <= -6.1)
].copy()

trip_id_set = set(trips["trip_id"].astype(str))

stop_times_chunks = []
with Path(stop_times_path).open("r", encoding="utf-8") as f:
    for chunk in pd.read_csv(
        f,
        usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
        chunksize=500000,
    ):
        chunk["trip_id"] = chunk["trip_id"].astype(str)
        chunk = chunk[chunk["trip_id"].isin(trip_id_set)]
        if not chunk.empty:
            stop_times_chunks.append(chunk)

if stop_times_chunks:
    stop_times = pd.concat(stop_times_chunks, ignore_index=True)
else:
    stop_times = pd.DataFrame(columns=["trip_id", "stop_id", "stop_sequence"])

stop_times = stop_times.merge(trips[["trip_id", "route_id", "route_type"]], on="trip_id", how="inner")
stop_times = stop_times.merge(stops[["stop_id"]], on="stop_id", how="inner")

print("Stops:", len(stops))
print("Stop times:", len(stop_times))

# Create graph
G = nx.DiGraph()

# Add nodes
for _, stop in stops.iterrows():
    G.add_node(
        stop["stop_id"],
        name=stop["stop_name"],
        lat=stop["stop_lat"],
        lon=stop["stop_lon"]
    )

print("Nodes added:", G.number_of_nodes())

# Sort stop_times by trip and sequence
stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])

# Add edges
def time_to_seconds(t):
    if pd.isna(t):
        return None
    try:
        h, m, s = map(int, str(t).split(":"))
        return h * 3600 + m * 60 + s
    except Exception:
        return None

STEP = 3

for trip_id, group in stop_times.groupby("trip_id"):

    group = group.sort_values("stop_sequence")
    for i in range(0, len(group) - STEP, STEP):
        row1 = group.iloc[i]
        row2 = group.iloc[i + STEP]

        stop_a = row1["stop_id"]
        stop_b = row2["stop_id"]
        route_type = row1["route_type"]

        t1 = time_to_seconds(row1["departure_time"])
        t2 = time_to_seconds(row2["arrival_time"])

        if t1 is None or t2 is None:
            travel_time = 120
        else:
            travel_time = t2 - t1

        if travel_time <= 0 or travel_time > 1200:
            continue

        travel_time = max(travel_time, 30)
        travel_time = min(travel_time, 600)

        mode = "bus"
        factor = 1.2
        if route_type == 0:
            mode = "luas"
            factor = 0.6
        elif route_type == 2:
            mode = "rail"
            factor = 0.85
        elif route_type == 3:
            mode = "bus"
            factor = 1.2

        weight = travel_time * factor

        G.add_edge(
            stop_a,
            stop_b,
            weight=weight,
            travel_time_sec=travel_time,
            route_id=row1["route_id"],
            route_type=route_type,
            mode=mode,
        )

print("Edges added:", G.number_of_edges())

# Add walking connections between nearby stops
print("Adding walking connections...")

coords = stops[["stop_lat", "stop_lon"]].values
stop_ids = stops["stop_id"].values

tree = KDTree(coords)
radius = 0.005  # ~500 meters

for i, coord in enumerate(coords):
    indices = tree.query_radius([coord], r=radius)[0]
    for j in indices:
        if i == j:
            continue
        stop_a = stop_ids[i]
        stop_b = stop_ids[j]

        distance_deg = np.linalg.norm(coords[i] - coords[j])
        distance_m = distance_deg * 111000
        walking_time = distance_m / 1.4  # seconds

        walking_time = max(walking_time, 60)
        if walking_time < 600:  # max 10 min walk
            G.add_edge(
                stop_a,
                stop_b,
                weight=walking_time,
                travel_time_sec=walking_time,
                mode="walk",
            )

print("Edges added with walking:", G.number_of_edges())

weights = [d.get("weight", 0) for _, _, d in G.edges(data=True)]
if weights:
    print("Min weight (sec):", min(weights))
    print("Max weight (sec):", max(weights))
    print("Avg weight (sec):", sum(weights) / len(weights))

# Save graph
output = os.path.join(BASE_DIR, "data", "graph", "transit_graph.gpickle")

os.makedirs(os.path.join(BASE_DIR, "data", "graph"), exist_ok=True)

with open(output, "wb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

print("Graph saved:", output)
