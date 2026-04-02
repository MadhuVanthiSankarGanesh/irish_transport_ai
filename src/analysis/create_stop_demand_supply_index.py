import pandas as pd

STOPS_POP_PATH = r"E:\irish_transport_ai\data\processed\dublin_stops_with_population.csv"
SERVICE_FREQ_PATH = r"E:\irish_transport_ai\data\processed\stop_service_frequency.csv"

OUTPUT_PATH = r"E:\irish_transport_ai\data\processed\dublin_transit_demand_supply.csv"


print("Loading datasets...")

stops = pd.read_csv(STOPS_POP_PATH)
freq = pd.read_csv(SERVICE_FREQ_PATH)


print("Cleaning population...")
stops["population"] = pd.to_numeric(
    stops["population"],
    errors="coerce"
)


print("Merging datasets...")

df = stops.merge(
    freq,
    on="stop_id",
    how="left"
)

df["service_frequency_score"] = df[
    "service_frequency_score"
].fillna(0)


print("Filtering stops with population...")

df = df[df["population"] > 0]


print("Creating demand-supply ratio...")

df["demand_supply_ratio"] = (
    df["population"] /
    (df["service_frequency_score"] + 1)
)


df = df.sort_values(
    "demand_supply_ratio",
    ascending=False
)


print("Saving output...")

df.to_csv(OUTPUT_PATH, index=False)

print("\nSaved to:")
print(OUTPUT_PATH)

print("\nDataset summary:")
print("Total stops analysed:", len(df))

print("\nTop underserved stops:")
print(df[[
    "stop_id",
    "stop_name",
    "population",
    "service_frequency_score",
    "demand_supply_ratio"
]].head(10))