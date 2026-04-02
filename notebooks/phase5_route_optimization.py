from pathlib import Path
import pickle

import folium
import networkx as nx
import pandas as pd

project_root = Path(__file__).resolve().parents[1]

graph_candidates = [
    project_root / "dublin_transport_graph_weighted.gpickle",
    project_root / "data" / "clean" / "dublin_transport_graph_weighted.gpickle",
]
clusters_candidates = [
    project_root / "dublin_stops_accessibility_clusters.csv",
    project_root / "data" / "clean" / "dublin_stops_accessibility_clusters.csv",
]
stops_candidates = [
    project_root / "data" / "clean" / "dublin_stops_clean.csv",
    project_root / "dublin_stops_clean.csv",
]

graph_file = next((p for p in graph_candidates if p.exists()), graph_candidates[0])
clusters_file = next((p for p in clusters_candidates if p.exists()), clusters_candidates[0])
stops_file = next((p for p in stops_candidates if p.exists()), stops_candidates[0])

# -----------------------------
# 1) Load Weighted Graph and Clusters
# -----------------------------
with open(graph_file, "rb") as f:
    G = pickle.load(f)

clusters_df = pd.read_csv(clusters_file)
stops = pd.read_csv(stops_file)

# -----------------------------
# 2) Identify Underserved Stops
# -----------------------------
underserved_cluster = clusters_df.groupby("cluster")["reachable_45min_norm"].mean().idxmin()
underserved_stops = clusters_df[clusters_df["cluster"] == underserved_cluster]["stop_id"].tolist()

print(f"Number of underserved stops: {len(underserved_stops)}")

# -----------------------------
# 3) Greedy Route Suggestion
# -----------------------------
high_access_stops = clusters_df[clusters_df["cluster"] != underserved_cluster]["stop_id"].tolist()
suggested_routes = []

print("Computing shortest paths from underserved stops to nearest high-access stop...")

for stop in underserved_stops:
    min_time = float("inf")
    best_target = None
    for target in high_access_stops:
        try:
            path_length = nx.dijkstra_path_length(G, stop, target, weight="weight")
            if path_length < min_time:
                min_time = path_length
                best_target = target
        except nx.NetworkXNoPath:
            continue
    if best_target is not None:
        suggested_routes.append((stop, best_target, min_time))

routes_df = pd.DataFrame(
    suggested_routes, columns=["from_stop", "to_stop", "estimated_travel_time_sec"]
)
routes_df = routes_df.merge(
    stops[["stop_id", "stop_lat", "stop_lon"]], left_on="from_stop", right_on="stop_id"
)
routes_df = routes_df.rename(columns={"stop_lat": "from_lat", "stop_lon": "from_lon"}).drop(
    columns=["stop_id"]
)
routes_df = routes_df.merge(
    stops[["stop_id", "stop_lat", "stop_lon"]], left_on="to_stop", right_on="stop_id"
)
routes_df = routes_df.rename(columns={"stop_lat": "to_lat", "stop_lon": "to_lon"}).drop(
    columns=["stop_id"]
)

routes_df.to_csv(project_root / "dublin_suggested_routes.csv", index=False)
print("Suggested routes saved as dublin_suggested_routes.csv")

# -----------------------------
# 4) Interactive Folium Map
# -----------------------------
dublin_map = folium.Map(location=[53.3498, -6.2603], zoom_start=12)

colors = ["green", "blue", "orange", "red"]
for _, row in clusters_df.iterrows():
    folium.CircleMarker(
        location=[row["stop_lat"], row["stop_lon"]],
        radius=3,
        color=colors[int(row["cluster"]) % len(colors)],
        fill=True,
        fill_color=colors[int(row["cluster"]) % len(colors)],
        fill_opacity=0.7,
    ).add_to(dublin_map)

for _, row in routes_df.iterrows():
    folium.PolyLine(
        locations=[[row["from_lat"], row["from_lon"]], [row["to_lat"], row["to_lon"]]],
        color="purple",
        weight=3,
        opacity=0.6,
    ).add_to(dublin_map)

dublin_map.save(project_root / "dublin_suggested_routes_map.html")
print("Interactive map saved as dublin_suggested_routes_map.html")
