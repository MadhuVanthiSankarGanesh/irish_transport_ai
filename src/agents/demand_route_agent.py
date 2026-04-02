import os
import pickle

import networkx as nx
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

graph_path = os.path.join(BASE_DIR, "data", "graph", "transit_graph.gpickle")
demand_path = os.path.join(BASE_DIR, "data", "features", "event_demand.csv")

print("Loading transit graph...")
with open(graph_path, "rb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    G = pickle.load(f)

print("Graph nodes:", G.number_of_nodes())
print("Graph edges:", G.number_of_edges())

print("Loading event demand data...")
demand = pd.read_csv(demand_path)

print("Demand rows:", len(demand))

# Increase weights near busy stops
print("Applying demand impact...")

for _, row in demand.iterrows():

    stop_id = row["stop_id"]
    demand_score = row["demand_score"]

    if stop_id in G:

        for neighbor in G.neighbors(stop_id):

            current_weight = G[stop_id][neighbor]["weight"]

            # Increase weight based on demand
            new_weight = current_weight + (demand_score / 10000)

            G[stop_id][neighbor]["weight"] = new_weight


print("Demand applied to graph")

# Example route test
nodes = list(G.nodes())

source = nodes[0]
target = nodes[500]

print("Testing route from", source, "to", target)

route = nx.shortest_path(G, source=source, target=target, weight="weight")

print("Route length:", len(route))

# Save updated graph
output_path = os.path.join(BASE_DIR, "data", "graph", "demand_transit_graph.gpickle")

with open(output_path, "wb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

print("Demand-aware graph saved:", output_path)
