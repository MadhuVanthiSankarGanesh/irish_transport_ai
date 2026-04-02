"""Build a cached attractions file for fast lookups."""

import csv
import os
from datetime import datetime

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILTE_BASE = os.getenv("FAILTE_BASE_URL", "https://failteireland.azure-api.net/opendata-api/v2")
FAILTE_ATTRACTIONS_URL = os.getenv("FAILTE_ATTRACTIONS_URL", f"{FAILTE_BASE}/attractions/csv")
FAILTE_TIMEOUT = int(os.getenv("FAILTE_TIMEOUT", "30"))

CACHE_PATH = os.getenv(
    "ATTRACTIONS_CACHE_PATH",
    os.path.join(BASE_DIR, "data", "cache", "attractions_geocoded.csv"),
)


def ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def build_cache():
    ensure_dir(CACHE_PATH)
    resp = requests.get(FAILTE_ATTRACTIONS_URL, headers={"Cache-Control": "no-cache"}, timeout=FAILTE_TIMEOUT)
    resp.raise_for_status()
    df = pd.read_csv(pd.io.common.StringIO(resp.text), encoding_errors="replace")

    fieldnames = [
        "name",
        "url",
        "telephone",
        "latitude",
        "longitude",
        "address",
        "county",
        "photo",
        "tags",
        "updated_at",
    ]

    with open(CACHE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for _, row in df.iterrows():
            writer.writerow({
                "name": row.get("Name"),
                "url": row.get("Url"),
                "telephone": row.get("Telephone"),
                "latitude": row.get("Latitude"),
                "longitude": row.get("Longitude"),
                "address": row.get("Address"),
                "county": row.get("County"),
                "photo": row.get("Photo"),
                "tags": row.get("Tags"),
                "updated_at": datetime.utcnow().isoformat(),
            })

    print(f"Cache written to {CACHE_PATH}")


if __name__ == "__main__":
    build_cache()
