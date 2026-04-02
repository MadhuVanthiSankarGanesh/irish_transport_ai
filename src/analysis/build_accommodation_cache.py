"""Build a cached accommodations geocode file for fast lookups."""

import csv
import os
import time
from datetime import datetime

import requests
from geopy.geocoders import Nominatim

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILTE_BASE = os.getenv("FAILTE_BASE_URL", "https://failteireland.azure-api.net/opendata-api/v2")
FAILTE_ACCOM_URL = os.getenv("FAILTE_ACCOM_URL", f"{FAILTE_BASE}/accommodation")
FAILTE_TIMEOUT = int(os.getenv("FAILTE_TIMEOUT", "30"))

CACHE_PATH = os.getenv(
    "ACCOM_CACHE_PATH",
    os.path.join(BASE_DIR, "data", "cache", "accommodations_geocoded.csv"),
)

GEOCODE_TIMEOUT = int(os.getenv("OSM_GEOCODE_TIMEOUT_SECONDS", "8"))
SLEEP_SECONDS = float(os.getenv("OSM_GEOCODE_SLEEP_SECONDS", "1.0"))
MAX_ROWS = int(os.getenv("ACCOM_MAX_ROWS", "0"))  # 0 means all


def ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def fetch_failte_accommodations() -> list[dict]:
    resp = requests.get(FAILTE_ACCOM_URL, headers={"Cache-Control": "no-cache"}, timeout=FAILTE_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", [])


def load_existing_ids(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    ids = set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id"):
                ids.add(row["id"])
    return ids


def geocode_one(geocoder: Nominatim, query: str):
    try:
        loc = geocoder.geocode(query, timeout=GEOCODE_TIMEOUT, country_codes="ie", bounded=False)
        if loc:
            lat, lon = loc.latitude, loc.longitude
            if 51.0 <= lat <= 56.0 and -11.0 <= lon <= -4.0:
                return lat, lon
    except Exception:
        return None
    return None


def build_cache():
    ensure_dir(CACHE_PATH)
    existing_ids = load_existing_ids(CACHE_PATH)
    items = fetch_failte_accommodations()
    if MAX_ROWS > 0:
        items = items[:MAX_ROWS]

    geocoder = Nominatim(user_agent="dublin_transport_ai_cache")

    fieldnames = [
        "id",
        "name",
        "type",
        "address",
        "locality",
        "region",
        "postalCode",
        "lat",
        "lon",
        "geocode_source",
        "updated_at",
    ]

    write_header = not os.path.exists(CACHE_PATH)
    with open(CACHE_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for idx, item in enumerate(items, 1):
            item_id = str(item.get("id"))
            if item_id in existing_ids:
                continue
            addr = item.get("address", {}) if isinstance(item, dict) else {}
            address = addr.get("streetAddress")
            locality = addr.get("addressLocality")
            region = addr.get("addressRegion")
            postal = addr.get("postalCode")
            name = item.get("name")

            queries = [
                ", ".join([p for p in [address, locality, region, "Ireland"] if p]),
                ", ".join([p for p in [locality, region, "Ireland"] if p]),
                name,
            ]
            coords = None
            for q in queries:
                if not q:
                    continue
                coords = geocode_one(geocoder, q)
                if coords:
                    break

            lat = coords[0] if coords else ""
            lon = coords[1] if coords else ""
            writer.writerow(
                {
                    "id": item_id,
                    "name": name,
                    "type": item.get("additionalType"),
                    "address": address,
                    "locality": locality,
                    "region": region,
                    "postalCode": postal,
                    "lat": lat,
                    "lon": lon,
                    "geocode_source": "osm" if coords else "",
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            if idx % 25 == 0:
                print(f"Processed {idx} accommodations...")
            if SLEEP_SECONDS > 0:
                time.sleep(SLEEP_SECONDS)

    print(f"Cache written to {CACHE_PATH}")


if __name__ == "__main__":
    build_cache()
