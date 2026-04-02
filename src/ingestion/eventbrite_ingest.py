import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("EVENTBRITE_API_KEY")

OUTPUT_FILE = "data/events/dublin_events.json"

BASE_URL = "https://www.eventbriteapi.com/v3"


headers = {
    "Authorization": f"Bearer {API_KEY}"
}


def fetch_dublin_venues():

    url = f"{BASE_URL}/venues/search/"

    params = {
        "location.address": "Dublin",
        "page_size": 10
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print("Venue API error:", response.text)
        return []

    data = response.json()

    venues = []

    for venue in data.get("venues", []):

        venues.append({
            "id": venue.get("id"),
            "name": venue.get("name"),
            "latitude": venue.get("latitude"),
            "longitude": venue.get("longitude")
        })

    return venues


def fetch_events_for_venue(venue_id):

    url = f"{BASE_URL}/venues/{venue_id}/events/"

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    data = response.json()

    events = []

    for event in data.get("events", []):

        events.append({
            "event_id": event.get("id"),
            "name": event.get("name", {}).get("text"),
            "start_time": event.get("start", {}).get("local"),
            "end_time": event.get("end", {}).get("local"),
            "venue_id": venue_id
        })

    return events


def fetch_dublin_events():

    print("Fetching Dublin venues...")

    venues = fetch_dublin_venues()

    all_events = []

    for venue in venues:

        events = fetch_events_for_venue(venue["id"])

        for event in events:

            event["venue_name"] = venue["name"]
            event["latitude"] = venue["latitude"]
            event["longitude"] = venue["longitude"]

            all_events.append(event)

    return all_events


def save_events(events):

    os.makedirs("data/events", exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    print(f"Saved {len(events)} events to {OUTPUT_FILE}")


if __name__ == "__main__":

    events = fetch_dublin_events()

    if events:
        save_events(events)
    else:
        print("No events found.")