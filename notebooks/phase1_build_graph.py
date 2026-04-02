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

print("Loading cleaned stops...")
stops = pd.read_csv(stops_file)

print("Loading network edges...")
edges = pd.read_csv(edges_file)


# --------------------------------------------------
# STEP 1 — Create Graph
# --------------------------------------------------

print("\nCreating graph...")
G = nx.DiGraph()  # Directed graph (transport is directional)


# --------------------------------------------------
# STEP 2 — Add Nodes
# --------------------------------------------------

print("Adding nodes...")
for _, row in stops.iterrows():
    G.add_node(
        row["stop_id"],
        lat=row["stop_lat"],
        lon=row["stop_lon"]
    )

print("Total nodes:", G.number_of_nodes())


# --------------------------------------------------
# STEP 3 — Add Edges
# --------------------------------------------------

print("Adding edges...")
for _, row in edges.iterrows():
    G.add_edge(row["from_stop"], row["to_stop"])

print("Total edges:", G.number_of_edges())


# --------------------------------------------------
# STEP 4 — Basic Connectivity Test
# --------------------------------------------------

print("\nIs graph weakly connected?")
print(nx.is_weakly_connected(G))

components = list(nx.weakly_connected_components(G))
print("Number of components:", len(components))

largest_component = max(components, key=len)
print("Largest component size:", len(largest_component))


# --------------------------------------------------
# STEP 5 — Save Graph (Optional)
# --------------------------------------------------

with open("../dublin_transport_graph.gpickle", "wb") as f:
    pickle.dump(G, f)

print("\nGraph saved as dublin_transport_graph.gpickle")