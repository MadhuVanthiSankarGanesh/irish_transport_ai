import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

events_path = os.path.join(BASE_DIR, "data", "events", "failte_events.csv")
links_path = os.path.join(BASE_DIR, "data", "features", "event_stop_links.csv")

print("Loading datasets...")

events = pd.read_csv(events_path)
links = pd.read_csv(links_path)

print("Events:", len(events))
print("Linked stops:", len(links))


# Merge event metadata with stop links
df = pd.merge(
    links,
    events[["event_name", "start_date", "end_date"]],
    on="event_name",
    how="left"
)

print("Merged dataset:", len(df))


# Simple demand model
def estimate_demand(event_name):

    name = str(event_name).lower()

    if "festival" in name:
        return 2000

    if "concert" in name:
        return 1500

    if "music" in name:
        return 1200

    if "sports" in name:
        return 1800

    return 500


df["estimated_passengers"] = df["event_name"].apply(estimate_demand)


# Demand weight based on distance to stop
df["distance_weight"] = 1 / (df["distance"] + 0.001)


# Final demand score
df["demand_score"] = df["estimated_passengers"] * df["distance_weight"]


output_path = os.path.join(BASE_DIR, "data", "features", "event_demand.csv")

df.to_csv(output_path, index=False)

print("Demand dataset saved:", output_path)
print("Total rows:", len(df))