from pathlib import Path
import pickle
import time

import networkx as nx
import pandas as pd

project_root = Path(__file__).resolve().parents[1]

graph_candidates = [
    project_root / "dublin_transport_graph_weighted.gpickle",
    project_root / "data" / "clean" / "dublin_transport_graph_weighted.gpickle",
]
stops_candidates = [
    project_root / "data" / "clean" / "dublin_stops_clean.csv",
    project_root / "dublin_stops_clean.csv",
]

graph_file = next((p for p in graph_candidates if p.exists()), graph_candidates[0])
stops_file = next((p for p in stops_candidates if p.exists()), stops_candidates[0])

# -----------------------------
# 1) Load Weighted Graph
# -----------------------------
print("Loading weighted Dublin transport graph...")
with open(graph_file, "rb") as f:
    G = pickle.load(f)

stops = pd.read_csv(stops_file)
stop_ids = list(G.nodes)
print(f"Total stops in graph: {len(stop_ids)}")

# -----------------------------
# 2) Define Accessibility Thresholds (seconds)
# -----------------------------
thresholds = [900, 1800, 2700]  # 15, 30, 45 minutes
threshold_labels = {900: "15min", 1800: "30min", 2700: "45min"}

# -----------------------------
# 3) Compute Network-Based Accessibility
# -----------------------------
accessibility_data = {"stop_id": stop_ids}

for cutoff in thresholds:
    reachable_list = []
    start_time = time.time()
    print(f"\nComputing reachable stops for cutoff = {cutoff // 60} minutes...")

    for stop_id in stop_ids:
        lengths = nx.single_source_dijkstra_path_length(
            G, stop_id, cutoff=cutoff, weight="weight"
        )
        reachable = len(lengths) - 1  # exclude self
        reachable_list.append(reachable)

    accessibility_data[f"reachable_{threshold_labels[cutoff]}"] = reachable_list
    elapsed = time.time() - start_time
    print(f"Done cutoff {cutoff // 60}min in {elapsed:.2f}s")

# -----------------------------
# 4) Merge Coordinates
# -----------------------------
access_df = pd.DataFrame(accessibility_data)
access_df = access_df.merge(stops[["stop_id", "stop_lat", "stop_lon"]], on="stop_id", how="left")

# -----------------------------
# 5) Optional: Normalize Accessibility Scores
# -----------------------------
for label in threshold_labels.values():
    access_df[f"reachable_{label}_norm"] = (
        access_df[f"reachable_{label}"] / access_df[f"reachable_{label}"].max()
    )

# -----------------------------
# 6) Save Results
# -----------------------------
access_df.to_csv(project_root / "dublin_stops_accessibility_full.csv", index=False)
print("\nSaved full network-based accessibility to dublin_stops_accessibility_full.csv")

# -----------------------------
# Summary Stats
# -----------------------------
for label in threshold_labels.values():
    print(
        f"{label}: min {access_df[f'reachable_{label}'].min()}, "
        f"max {access_df[f'reachable_{label}'].max()}, "
        f"mean {access_df[f'reachable_{label}'].mean():.2f}"
    )
