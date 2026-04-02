import pandas as pd

TRIPS_PATH = r"E:\irish_transport_ai\data\clean\trips.csv"
STOP_TIMES_PATH = r"E:\irish_transport_ai\data\clean\stop_times.csv"
ROUTES_PATH = r"E:\irish_transport_ai\data\clean\routes.csv"

OUTPUT_PATH = r"E:\irish_transport_ai\data\processed\stop_service_frequency.csv"


print("Loading GTFS files...")

trips = pd.read_csv(TRIPS_PATH, usecols=["trip_id", "route_id"])
stop_times = pd.read_csv(STOP_TIMES_PATH, usecols=["trip_id", "stop_id"])
routes = pd.read_csv(ROUTES_PATH, usecols=["route_id", "route_type"])

routes = routes[routes["route_type"].isin([0, 2, 3])]
trips = trips.merge(routes, on="route_id", how="inner")


print("Merging trips with routes...")
trips_routes = trips.copy()


print("Linking stop_times...")
stops_routes = stop_times.merge(
    trips_routes,
    on="trip_id",
    how="left"
)


print("Computing service frequency...")

stop_freq = stops_routes.groupby("stop_id").agg(
    trip_count=("trip_id", "count"),
    route_count=("route_id", "nunique")
).reset_index()

stop_freq["service_frequency_score"] = (
    stop_freq["trip_count"] * stop_freq["route_count"]
)


stop_freq.to_csv(OUTPUT_PATH, index=False)

print("\nSaved to:")
print(OUTPUT_PATH)

print("\nTop 10 busiest stops:")
print(stop_freq.sort_values(
    "service_frequency_score",
    ascending=False
).head(10))
