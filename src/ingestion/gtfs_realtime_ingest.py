import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

load_dotenv()

API_KEY = os.environ.get("TFI_API_KEY")
if not API_KEY:
    raise RuntimeError("TFI_API_KEY is not set. Export your Transport for Ireland API key.")

BASE_URL = os.environ.get("TFI_GTFSR_BASE_URL", "https://api.nationaltransport.ie/gtfsr/v2")
FEED = os.environ.get("TFI_GTFSR_FEED", "Vehicles")
VEHICLE_URL = f"{BASE_URL.rstrip('/')}/{FEED}"

print("Fetching realtime vehicle positions...")

headers = {
    "x-api-key": API_KEY,
    "Cache-Control": "no-cache",
}

response = requests.get(VEHICLE_URL, headers=headers, timeout=30)
if not response.ok:
    raise RuntimeError(
        f"TFI API request failed: {response.status_code} {response.reason}. "
        f"Body (first 200 bytes): {response.content[:200]!r}"
    )

feed = gtfs_realtime_pb2.FeedMessage()
try:
    feed.ParseFromString(response.content)
except Exception as exc:
    content_type = response.headers.get("Content-Type", "")
    raise RuntimeError(
        "Failed to parse GTFS-Realtime protobuf. "
        f"Content-Type={content_type!r}, Body (first 200 bytes)={response.content[:200]!r}"
    ) from exc

vehicles = []

for entity in feed.entity:

    if entity.HasField("vehicle"):

        vehicle = entity.vehicle

        timestamp = vehicle.timestamp or int(time.time())

        vehicles.append({
            "vehicle_id": vehicle.vehicle.id,
            "trip_id": vehicle.trip.trip_id,
            "route_id": vehicle.trip.route_id,
            "latitude": vehicle.position.latitude,
            "longitude": vehicle.position.longitude,
            "timestamp": timestamp
        })

df = pd.DataFrame(vehicles)

print("Vehicles fetched:", len(df))

os.makedirs("data/realtime", exist_ok=True)

output = "data/realtime/vehicle_positions.csv"

df.to_csv(output, index=False)

print("Saved realtime vehicle data:", output)

history_output = "data/realtime/vehicle_history.csv"
if not df.empty:
    df.to_csv(
        history_output,
        mode="a",
        index=False,
        header=not os.path.exists(history_output),
    )
    print("Appended to vehicle history:", history_output)
