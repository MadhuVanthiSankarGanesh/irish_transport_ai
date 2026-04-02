import pandas as pd
import networkx as nx
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

graph_path = os.path.join(BASE_DIR, "data/graph/ml_optimized_graph.gpickle")
congestion_path = os.path.join(BASE_DIR, "data/features/realtime_congestion.csv")

G = nx.read_gpickle(graph_path)

congestion = pd.read_csv(congestion_path)


def estimate_travel_time(route):

    # Assume average transit hop ~4 minutes
    return len(route) * 4


def predict_delay(route):

    stops = set(route)

    affected = congestion[congestion["stop_id"].isin(stops)]

    if len(affected) == 0:
        return 0

    return affected["congestion_score"].mean() * 2


def compute_departure_time(origin, destination, event_time):

    route = nx.shortest_path(G, source=origin, target=destination, weight="weight")

    travel_time = estimate_travel_time(route)

    delay = predict_delay(route)

    buffer = 15

    total_minutes = travel_time + delay + buffer

    event_dt = datetime.strptime(event_time, "%Y-%m-%d %H:%M")

    departure = event_dt - timedelta(minutes=total_minutes)

    return route, travel_time, delay, departure