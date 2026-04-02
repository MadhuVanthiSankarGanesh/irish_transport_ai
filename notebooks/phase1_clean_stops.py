import pandas as pd

# --------------------------------------------------
# STEP 1 — LOAD STOPS FILE
# --------------------------------------------------

# CHANGE THIS to your actual filename
file_path = r"E:\irish_transport_ai\data\clean\stops.csv"

print("Loading file...")
stops = pd.read_csv(file_path)

print("Total stops loaded:", len(stops))


# --------------------------------------------------
# STEP 2 — CLEAN COORDINATES
# --------------------------------------------------

print("\nCleaning latitude/longitude...")
stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")

# Remove rows with invalid coordinates
stops = stops.dropna(subset=["stop_lat", "stop_lon"])

print("After removing invalid coords:", len(stops))


# --------------------------------------------------
# STEP 3 — CHECK GEOGRAPHIC EXTENT
# --------------------------------------------------

print("\nLatitude range:", stops["stop_lat"].min(), "to", stops["stop_lat"].max())
print("Longitude range:", stops["stop_lon"].min(), "to", stops["stop_lon"].max())


# --------------------------------------------------
# STEP 4 — FILTER TO DUBLIN BOUNDING BOX
# --------------------------------------------------

print("\nFiltering to Dublin region...")

dublin_stops = stops[
    (stops["stop_lat"] >= 53.2) &
    (stops["stop_lat"] <= 53.5) &
    (stops["stop_lon"] >= -6.5) &
    (stops["stop_lon"] <= -6.0)
]

print("Stops inside Dublin bounding box:", len(dublin_stops))


# --------------------------------------------------
# STEP 5 — REMOVE PARENT STATIONS
# --------------------------------------------------

if "location_type" in dublin_stops.columns:
    print("\nLocation type breakdown:")
    print(dublin_stops["location_type"].value_counts(dropna=False))

    dublin_stops = dublin_stops[
        (dublin_stops["location_type"] == 0) |
        (dublin_stops["location_type"].isna())
    ]

    print("After removing parent stations:", len(dublin_stops))
else:
    print("\nNo location_type column found — skipping this step.")


# --------------------------------------------------
# STEP 6 — CHECK DUPLICATE COORDINATES
# --------------------------------------------------

duplicates = dublin_stops.duplicated(subset=["stop_lat", "stop_lon"])
print("\nDuplicate coordinate count:", duplicates.sum())


# --------------------------------------------------
# STEP 7 — SAVE CLEAN FILE
# --------------------------------------------------

output_file = "dublin_stops_clean.csv"
dublin_stops.to_csv(output_file, index=False)

print("\nSaved cleaned file as:", output_file)
print("Final stop count:", len(dublin_stops))