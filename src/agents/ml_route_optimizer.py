import os
import pickle

import joblib
import networkx as nx
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

graph_path = os.path.join(BASE_DIR, "data", "graph", "demand_transit_graph.gpickle")
model_path = os.path.join(BASE_DIR, "data", "models", "demand_predictor.pkl")
event_path = os.path.join(BASE_DIR, "data", "features", "event_demand.csv")
congestion_path = os.path.join(BASE_DIR, "data", "features", "realtime_congestion.csv")

print("Loading graph...")
with open(graph_path, "rb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    G = pickle.load(f)

print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())

print("Loading ML model...")
model = joblib.load(model_path)

events = pd.read_csv(event_path)
congestion = pd.read_csv(congestion_path)

data = events.merge(congestion, on="stop_id", how="left")

data["vehicle_count"] = data["vehicle_count"].fillna(0)
data["congestion_score"] = data["congestion_score"].fillna(0)

# Time features
time_col = None
for c in ["event_time", "start_date", "end_date"]:
    if c in data.columns:
        time_col = c
        break

data["hour"] = pd.to_datetime(data[time_col], errors="coerce").dt.hour
data["day_of_week"] = pd.to_datetime(data[time_col], errors="coerce").dt.dayofweek

data["hour"] = data["hour"].fillna(12)
data["day_of_week"] = data["day_of_week"].fillna(3)

if "event_demand" not in data.columns:
    if "demand_score" in data.columns:
        data["event_demand"] = data["demand_score"]
    elif "estimated_passengers" in data.columns:
        data["event_demand"] = data["estimated_passengers"]
    else:
        raise KeyError("No demand column found. Expected event_demand, demand_score, or estimated_passengers.")

features = [
    "event_demand",
    "vehicle_count",
    "congestion_score",
    "hour",
    "day_of_week"
]

print("Predicting demand...")

data["predicted_demand"] = model.predict(data[features])

# Apply predicted demand to graph
for _, row in data.iterrows():

    stop = row["stop_id"]

    if stop in G.nodes:

        demand = row["predicted_demand"]

        for neighbor in G.neighbors(stop):

            if "weight" in G[stop][neighbor]:
                G[stop][neighbor]["weight"] += demand * 0.001

print("ML demand applied to graph")

output_path = os.path.join(BASE_DIR, "data", "graph", "ml_optimized_graph.gpickle")

with open(output_path, "wb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

print("Saved optimized graph:", output_path)
