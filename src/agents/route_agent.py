import networkx as nx
import pickle

GRAPH_PATH = "data/processed/transit_graph.gpickle"


def load_graph():

    print("Loading graph...")
    with open(GRAPH_PATH, "rb") as f:
        # NetworkX 3 removed gpickle helpers; use pickle directly.
        return pickle.load(f)


def find_route(start_stop, end_stop):

    G = load_graph()

    if start_stop not in G.nodes:
        return "Start stop not found"

    if end_stop not in G.nodes:
        return "End stop not found"

    try:

        path = nx.shortest_path(G, start_stop, end_stop)

        return path

    except nx.NetworkXNoPath:

        return "No route available"


if __name__ == "__main__":

    start = input("Start stop ID: ")
    end = input("End stop ID: ")

    route = find_route(start, end)

    print("\nRoute result:\n")
    print(route)
