import json
import os

import networkx as nx
import pickle

INPUT_FILE = "data/processed/transit_knowledge_base.json"
OUTPUT_FILE = "data/processed/transit_graph.gpickle"

print("Loading transit knowledge base...")

if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError("Transit knowledge base not found.")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Records loaded:", len(data))

G = nx.Graph()

print("Building transit graph...")

for item in data:

    stop_id = item.get("stop_id")
    stop_name = item.get("stop_name")

    population = item.get("population_near_stop", 0)
    service_score = item.get("service_frequency_score", 0)

    if stop_id is None:
        continue

    G.add_node(
        stop_id,
        name=stop_name,
        population=population,
        service_score=service_score
    )

print("Graph nodes created:", G.number_of_nodes())

with open(OUTPUT_FILE, "wb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

print("Graph saved to:", OUTPUT_FILE)
