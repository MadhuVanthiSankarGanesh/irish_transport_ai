import networkx as nx
import pickle

GRAPH_PATH = "data/processed/transit_graph.gpickle"


def find_underserved(pop_threshold=5000, service_threshold=1):

    print("Loading transit graph...")

    with open(GRAPH_PATH, "rb") as f:
        # NetworkX 3 removed gpickle helpers; use pickle directly.
        G = pickle.load(f)

    underserved = []

    for node, data in G.nodes(data=True):

        population = data.get("population", 0)
        service = data.get("service_score", 0)

        if population > pop_threshold and service < service_threshold:

            underserved.append({
                "stop_id": node,
                "name": data.get("name"),
                "population": population
            })

    print("Underserved stops found:", len(underserved))

    return underserved


if __name__ == "__main__":

    results = find_underserved()

    print("\nSample results:\n")

    for r in results[:10]:
        print(r)
