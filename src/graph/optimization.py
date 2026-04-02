import pickle
import pandas as pd
import networkx as nx
import folium
import numpy as np
from pathlib import Path


def _resolve_existing_path(path_value, fallback_candidates):
    path_obj = Path(path_value)
    if path_obj.exists():
        return path_obj

    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate

    searched = [str(path_obj)] + [str(c) for c in fallback_candidates]
    raise FileNotFoundError(
        "Could not find required input file. Searched:\n"
        + "\n".join(f" - {s}" for s in searched)
    )


def suggest_routes(
    graph_path,
    clusters_path,
    stops_path,
    output_csv,
    output_map,
    percentile=95
):
    project_root = Path(__file__).resolve().parents[2]

    graph_file = _resolve_existing_path(
        graph_path,
        [
            project_root / "dublin_transport_graph_weighted.gpickle",
            project_root / "data" / "clean" / "dublin_transport_graph_weighted.gpickle",
        ],
    )
    clusters_file = _resolve_existing_path(
        clusters_path,
        [
            project_root / "dublin_stops_accessibility_clusters.csv",
            project_root / "data" / "clean" / "dublin_stops_accessibility_clusters.csv",
        ],
    )
    stops_file = _resolve_existing_path(
        stops_path,
        [
            project_root / "dublin_stops_clean.csv",
            project_root / "data" / "clean" / "dublin_stops_clean.csv",
        ],
    )

    output_csv_path = Path(output_csv)
    if not output_csv_path.is_absolute():
        output_csv_path = project_root / output_csv_path
    output_map_path = Path(output_map)
    if not output_map_path.is_absolute():
        output_map_path = project_root / output_map_path

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_map_path.parent.mkdir(parents=True, exist_ok=True)

    print("Loading weighted graph...")
    with open(graph_file, "rb") as f:
        G = pickle.load(f)

    clusters_df = pd.read_csv(clusters_file)
    stops_df = pd.read_csv(stops_file)

    print("Identifying underserved cluster...")
    underserved_cluster = (
        clusters_df.groupby("cluster")["reachable_45min_norm"]
        .mean()
        .idxmin()
    )

    underserved_stops = clusters_df[
        clusters_df["cluster"] == underserved_cluster
    ]["stop_id"].tolist()

    high_access_stops = clusters_df[
        clusters_df["cluster"] != underserved_cluster
    ]["stop_id"].tolist()

    print(f"Total underserved stops: {len(underserved_stops)}")
    print("Running multi-source Dijkstra (FAST)...")

    distances, paths = nx.multi_source_dijkstra(
        G,
        sources=high_access_stops,
        weight="weight"
    )

    print("Computing severity scores...")

    suggestions = []

    for stop in underserved_stops:
        if stop in distances:
            suggestions.append({
                "from_stop": stop,
                "travel_time_sec": distances[stop],
                "path": paths[stop]
            })

    routes_df = pd.DataFrame(suggestions)

    # -----------------------
    # Severity Ranking
    # -----------------------
    threshold = np.percentile(routes_df["travel_time_sec"], percentile)

    critical_df = routes_df[
        routes_df["travel_time_sec"] >= threshold
    ].copy()

    critical_df = critical_df.sort_values(
        "travel_time_sec",
        ascending=False
    )

    print(f"Worst {100 - percentile}% threshold: {threshold:.2f} seconds")
    print(f"Critical stops selected: {len(critical_df)}")

    # Merge origin coordinates
    critical_df = critical_df.merge(
        stops_df[["stop_id", "stop_lat", "stop_lon"]],
        left_on="from_stop",
        right_on="stop_id",
        how="left"
    ).rename(columns={
        "stop_lat": "from_lat",
        "stop_lon": "from_lon"
    }).drop(columns=["stop_id"])

    critical_df.to_csv(output_csv_path, index=False)
    print(f"Saved ranked critical routes to {output_csv_path}")

    # -----------------------
    # Generate Map
    # -----------------------
    print("Generating interactive strategic map...")

    dublin_map = folium.Map(location=[53.3498, -6.2603], zoom_start=12)

    # Plot critical stops
    for _, row in critical_df.iterrows():
        folium.CircleMarker(
            location=[row["from_lat"], row["from_lon"]],
            radius=6,
            color="red",
            fill=True,
            fill_opacity=0.9,
            popup=f"Stop: {row['from_stop']}<br>Travel Time: {row['travel_time_sec']:.1f} sec"
        ).add_to(dublin_map)

    # Draw route paths
    for _, row in critical_df.iterrows():

        path_nodes = row["path"]
        coords = []

        for node in path_nodes:
            node_data = stops_df[stops_df["stop_id"] == node]
            if not node_data.empty:
                lat = node_data.iloc[0]["stop_lat"]
                lon = node_data.iloc[0]["stop_lon"]
                coords.append((lat, lon))

        if len(coords) > 1:
            folium.PolyLine(
                locations=coords,
                weight=3,
                opacity=0.6,
                popup="Proposed Connectivity Route"
            ).add_to(dublin_map)

    dublin_map.save(output_map_path)
    print(f"Strategic map saved to {output_map_path}")

    print("Optimization complete.")


if __name__ == "__main__":

    suggest_routes(
        graph_path="dublin_transport_graph_weighted.gpickle",
        clusters_path="dublin_stops_accessibility_clusters.csv",
        stops_path="dublin_stops_clean.csv",
        output_csv="outputs/suggested_routes_ranked.csv",
        output_map="outputs/maps/strategic_routes_map.html",
        percentile=95  # worst 5%
    )
