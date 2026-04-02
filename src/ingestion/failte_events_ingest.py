import requests
import pandas as pd
import os

url = "https://failteireland.azure-api.net/opendata-api/v2/events"

headers = {
    "Cache-Control": "no-cache"
}

all_events = []
continuation_token = None

print("Fetching events from Failte Ireland API...")

while True:

    if continuation_token:
        headers["x-ms-continuation"] = continuation_token

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Error:", response.text)
        break

    data = response.json()
    events = data["value"]

    all_events.extend(events)

    print("Fetched", len(events), "events")

    continuation_token = response.headers.get("x-ms-continuation")

    if not continuation_token:
        break


print("Total events collected:", len(all_events))

parsed_events = []

for event in all_events:

    location = event.get("location", {})
    geo = location.get("geo", {})

    parsed_events.append({
        "event_name": event.get("name"),
        "start_date": event.get("startDate"),
        "end_date": event.get("endDate"),
        "venue": location.get("name"),
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "region": location.get("address", {}).get("addressRegion")
    })


df = pd.DataFrame(parsed_events)

os.makedirs("data/events", exist_ok=True)

df.to_csv("data/events/failte_events.csv", index=False)

print("Saved dataset:", len(df), "events")