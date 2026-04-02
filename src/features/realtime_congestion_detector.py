import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

vehicle_path = os.path.join(BASE_DIR, "data", "realtime", "vehicle_positions.csv")
stop_path = os.path.join(BASE_DIR, "data", "clean", "stops.csv")

print("Loading realtime vehicles...")
vehicles = pd.read_csv(vehicle_path)

print("Vehicles:", len(vehicles))

print("Loading stops...")
stops = pd.read_csv(stop_path)

print("Stops:", len(stops))

# Merge nearby vehicles with stops (approximate)
vehicles["lat_round"] = vehicles["latitude"].round(2)
vehicles["lon_round"] = vehicles["longitude"].round(2)

stops["lat_round"] = stops["stop_lat"].round(2)
stops["lon_round"] = stops["stop_lon"].round(2)

merged = vehicles.merge(
    stops,
    on=["lat_round", "lon_round"],
    how="inner"
)

print("Vehicle-stop matches:", len(merged))

# Count vehicles per stop
congestion = merged.groupby("stop_id").size().reset_index(name="vehicle_count")

# Simple congestion score
congestion["congestion_score"] = congestion["vehicle_count"] * 10

output = os.path.join(BASE_DIR, "data", "features", "realtime_congestion.csv")

congestion.to_csv(output, index=False)

print("Realtime congestion dataset saved:", output)
print("Stops with congestion:", len(congestion))
