import os
import pickle

import networkx as nx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

graph_path = os.path.join(BASE_DIR, "data", "graph", "ml_optimized_graph.gpickle")

print("Loading optimized graph...")
with open(graph_path, "rb") as f:
    # NetworkX 3 removed gpickle helpers; use pickle directly.
    G = pickle.load(f)

print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())


def find_best_route(origin, destination):

    try:

        route = nx.shortest_path(
            G,
            source=origin,
            target=destination,
            weight="weight"
        )

        return route

    except Exception as e:

        print("Routing error:", e)
        return None


# Example query
origin = "700000014230"
destination = "8220DB000415"

print("Finding smart route...")

route = find_best_route(origin, destination)

if route:
    print("Route found:")
    print(route)
    print("Stops:", len(route))

else:
    print("No route found")
