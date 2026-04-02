from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parents[1]

dublin_stops_candidates = [
    project_root / "data" / "clean" / "dublin_stops_clean.csv",
    project_root / "dublin_stops_clean.csv",
]

dublin_stops_file = next((p for p in dublin_stops_candidates if p.exists()), dublin_stops_candidates[0])
stop_times_file = project_root / "data" / "clean" / "stop_times.csv"
trips_file = project_root / "data" / "clean" / "trips.csv"
print("Loading Dublin stops...")
dublin_stops = pd.read_csv(dublin_stops_file)

print("Loading stop_times...")
stop_times = pd.read_csv(stop_times_file)

print("Loading trips...")
trips = pd.read_csv(trips_file)


# --------------------------------------------------
# STEP 1 — Keep Only Dublin stop_ids
# --------------------------------------------------

print("\nFiltering stop_times to Dublin stops...")
dublin_stop_ids = set(dublin_stops["stop_id"])

stop_times = stop_times[stop_times["stop_id"].isin(dublin_stop_ids)]

print("Stop_times remaining:", len(stop_times))


# --------------------------------------------------
# STEP 2 — Sort Stops Within Each Trip
# --------------------------------------------------

print("\nSorting stop_times by trip and sequence...")
stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])


# --------------------------------------------------
# STEP 3 — Create Stop-to-Stop Edges
# --------------------------------------------------

print("\nBuilding network edges...")

edges = []

for trip_id, group in stop_times.groupby("trip_id"):
    stops_list = group["stop_id"].tolist()

    for i in range(len(stops_list) - 1):
        from_stop = stops_list[i]
        to_stop = stops_list[i + 1]

        edges.append((from_stop, to_stop))

edges_df = pd.DataFrame(edges, columns=["from_stop", "to_stop"])

print("Total edges created:", len(edges_df))


# --------------------------------------------------
# STEP 4 — Remove Duplicate Edges
# --------------------------------------------------

edges_df = edges_df.drop_duplicates()

print("Unique edges:", len(edges_df))


# --------------------------------------------------
# STEP 5 — Save Network
# --------------------------------------------------

edges_df.to_csv(project_root / "dublin_network_edges.csv", index=False)

print("\nSaved as: dublin_network_edges.csv")
