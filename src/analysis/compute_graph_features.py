import networkx as nx
import pandas as pd
import os
import pickle

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GRAPH_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "dublin_transit_graph.gpickle")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "dublin_graph_features.csv")

print("Loading transit graph...")
with open(GRAPH_PATH, "rb") as f:
    G = pickle.load(f)

print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())

# -----------------------
# GRAPH METRICS
# -----------------------

print("Computing degree centrality...")
degree = nx.degree_centrality(G)

print("Computing betweenness centrality...")
betweenness = nx.betweenness_centrality(G, k=100, normalized=True)

print("Computing clustering coefficient...")
clustering = nx.clustering(G)

# -----------------------
# BUILD FEATURE TABLE
# -----------------------

rows = []

for node in G.nodes(data=True):

    stop_id = node[0]
    data = node[1]

    rows.append({
        "stop_id": stop_id,
        "stop_name": data.get("stop_name"),
        "population": data.get("population", 0),
        "service_frequency": data.get("service_frequency", 0),
        "demand_supply_ratio": data.get("demand_supply_ratio", 0),
        "degree_centrality": degree.get(stop_id, 0),
        "betweenness_centrality": betweenness.get(stop_id, 0),
        "clustering": clustering.get(stop_id, 0)
    })

df = pd.DataFrame(rows)

# -----------------------
# IDENTIFY NETWORK GAPS
# -----------------------

print("Creating graph underserved score...")

df["graph_gap_score"] = (
    df["population"] /
    (df["service_frequency"] + 1)
) * (1 - df["degree_centrality"])

# -----------------------
# SAVE
# -----------------------

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)

print("\nSaved graph features to:")
print(OUTPUT_PATH)

print("\nTop underserved transit locations:")

print(
    df.sort_values("graph_gap_score", ascending=False)
      [["stop_id","stop_name","population","service_frequency","graph_gap_score"]]
      .head(10)
)
