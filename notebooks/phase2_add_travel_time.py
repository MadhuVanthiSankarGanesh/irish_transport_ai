from pathlib import Path

import pandas as pd
import networkx as nx
import pickle

project_root = Path(__file__).resolve().parents[1]

stops_candidates = [
    project_root / "data" / "clean" / "dublin_stops_clean.csv",
    project_root / "dublin_stops_clean.csv",
]
edges_candidates = [
    project_root / "dublin_network_edges.csv",
    project_root / "data" / "clean" / "dublin_network_edges.csv",
]

stops_file = next((p for p in stops_candidates if p.exists()), stops_candidates[0])
edges_file = next((p for p in edges_candidates if p.exists()), edges_candidates[0])
stop_times_file = project_root / "data" / "clean" / "stop_times.csv"

print("Loading Dublin stops...")
stops = pd.read_csv(stops_file)

print("Loading network edges...")
edges = pd.read_csv(edges_file)

print("Loading stop_times...")
stop_times = pd.read_csv(stop_times_file)

# --------------------------------------------------
# Filter stop_times to Dublin stops
# --------------------------------------------------
dublin_stop_ids = set(stops["stop_id"])
stop_times = stop_times[stop_times["stop_id"].isin(dublin_stop_ids)]
stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])

# --------------------------------------------------
# Helper function to convert HH:MM:SS to seconds
# --------------------------------------------------
def time_to_seconds(t):
    h, m, s = map(int, t.split(":"))
    return h*3600 + m*60 + s

stop_times["arrival_sec"] = stop_times["arrival_time"].apply(time_to_seconds)
stop_times["departure_sec"] = stop_times["departure_time"].apply(time_to_seconds)

# --------------------------------------------------
# Compute travel times for consecutive stops
# --------------------------------------------------
print("Computing travel times for each edge...")

edges_with_time = []

for trip_id, group in stop_times.groupby("trip_id"):
    stops_list = group["stop_id"].tolist()
    dep_list = group["departure_sec"].tolist()
    arr_list = group["arrival_sec"].tolist()

    for i in range(len(stops_list) - 1):
        from_stop = stops_list[i]
        to_stop = stops_list[i + 1]
        travel_time = arr_list[i + 1] - dep_list[i]  # seconds

        if travel_time < 0:
            continue  # skip negative times

        edges_with_time.append((from_stop, to_stop, travel_time))

edges_df = pd.DataFrame(edges_with_time, columns=["from_stop", "to_stop", "weight"])

edges_df = edges_df.groupby(["from_stop","to_stop"])["weight"].mean().reset_index()  # average if multiple trips

print("Edges with travel times:", len(edges_df))

# --------------------------------------------------
# Build weighted graph
# --------------------------------------------------
print("Building weighted graph...")

G = nx.DiGraph()

# Add nodes
for _, row in stops.iterrows():
    G.add_node(row["stop_id"], lat=row["stop_lat"], lon=row["stop_lon"])

# Add edges with travel_time weight
for _, row in edges_df.iterrows():
    G.add_edge(row["from_stop"], row["to_stop"], weight=row["weight"])

print("Graph nodes:", G.number_of_nodes())
print("Graph edges:", G.number_of_edges())

# --------------------------------------------------
# Save weighted graph
# --------------------------------------------------
with open(project_root / "dublin_transport_graph_weighted.gpickle", "wb") as f:
    pickle.dump(G, f)

print("\nWeighted graph saved as dublin_transport_graph_weighted.gpickle")
