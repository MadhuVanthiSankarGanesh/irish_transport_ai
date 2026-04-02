import gtfs_kit as gk
import pandas as pd
import os

GTFS_FOLDER = "data/raw/gtfs/"
CLEAN_PATH = "data/clean/"

def load_all_gtfs():

    all_stops = []
    all_routes = []
    all_trips = []
    all_stop_times = []

    for file in os.listdir(GTFS_FOLDER):
        if file.endswith(".zip"):
            print(f"Loading {file}...")
            feed = gk.read_feed(os.path.join(GTFS_FOLDER, file), dist_units="km")

            # Add operator name for traceability
            operator = file.replace(".zip", "")

            feed.stops["operator"] = operator
            feed.routes["operator"] = operator
            feed.trips["operator"] = operator
            feed.stop_times["operator"] = operator

            all_stops.append(feed.stops)
            all_routes.append(feed.routes)
            all_trips.append(feed.trips)
            all_stop_times.append(feed.stop_times)

    # Merge all operators
    stops = pd.concat(all_stops, ignore_index=True)
    routes = pd.concat(all_routes, ignore_index=True)
    trips = pd.concat(all_trips, ignore_index=True)
    stop_times = pd.concat(all_stop_times, ignore_index=True)

    # Save clean consolidated files
    stops.to_csv(os.path.join(CLEAN_PATH, "stops.csv"), index=False)
    routes.to_csv(os.path.join(CLEAN_PATH, "routes.csv"), index=False)
    trips.to_csv(os.path.join(CLEAN_PATH, "trips.csv"), index=False)
    stop_times.to_csv(os.path.join(CLEAN_PATH, "stop_times.csv"), index=False)

    print("All GTFS feeds merged successfully.")

if __name__ == "__main__":
    load_all_gtfs()