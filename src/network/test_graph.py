import networkx as nx
import pickle

GRAPH_PATH = "data/processed/transit_graph.gpickle"

print("Loading graph...")

with open(GRAPH_PATH, "rb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    G = pickle.load(f)

print("Total stops:", G.number_of_nodes())

sample_nodes = list(G.nodes(data=True))[:5]

print("\nSample stops:\n")

for node in sample_nodes:
    print(node)
