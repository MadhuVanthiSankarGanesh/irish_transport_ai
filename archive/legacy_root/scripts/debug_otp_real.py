#!/usr/bin/env python3
"""Debug OTP responses with actual chatbot parameters."""
import requests
import json
import pandas as pd
from datetime import datetime

# Load stops to resolve "3Arena"
stops = pd.read_csv('data/clean/stops.csv')

def resolve_location(location):
    """Resolve location name to coordinates."""
    # Try exact match
    match = stops[stops['stop_name'].str.lower() == location.lower()]
    if len(match) > 0:
        row = match.iloc[0]
        return (row['stop_lat'], row['stop_lon']), row['stop_name']
    
    # Try fuzzy match
    from difflib import get_close_matches
    matches = get_close_matches(location.lower(), stops['stop_name'].str.lower(), n=1, cutoff=0.6)
    if matches:
        row = stops[stops['stop_name'].str.lower() == matches[0]].iloc[0]
        return (row['stop_lat'], row['stop_lon']), row['stop_name']
    
    return None, None

# Test parameters (from the chat)
origin = "3Arena"
destination = "Ballydehob"
date = "2026-03-27"
time = "08:00"

# Resolve coordinates
origin_coords, origin_name = resolve_location(origin)
dest_coords, dest_name = resolve_location(destination)

print(f"Origin: {origin} → {origin_name} {origin_coords}")
print(f"Destination: {destination} → {dest_name} {dest_coords}")

if not origin_coords or not dest_coords:
    print("Could not resolve locations")
    exit(1)

# Test with corrected endpoint
url = "http://localhost:8080/routers/default/plan"

params = {
    "fromPlace": f"{origin_coords[0]},{origin_coords[1]}",
    "toPlace": f"{dest_coords[0]},{dest_coords[1]}",
    "date": date,
    "time": time,
    "mode": "TRANSIT,WALK",
    "maxWalkDistance": "1000",
    "numItineraries": 3
}

print(f"\n{'='*70}")
print(f"OTP URL: {url}")
print(f"{'='*70}")
print(f"Params: {json.dumps(params, indent=2)}")

try:
    print(f"\nMaking request...")
    r = requests.get(url, params=params, timeout=5)
    
    print(f"\nStatus: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Response length: {len(r.text)} bytes")
    
    if r.text:
        data = r.json()
        print(f"\nResponse structure:")
        print(f"  Keys: {list(data.keys())}")
        
        if 'plan' in data:
            plan = data['plan']
            print(f"\nPlan details:")
            print(f"  Type: {type(plan)} - {plan}")
            
            if plan is None:
                print(f"  ⚠️  PLAN IS NULL - No routes available")
                print(f"\n  Possible reasons:")
                print(f"    1. No service on 2026-03-27 (check GTFS calendar)")
                print(f"    2. Origin or destination not connected to transit")
                print(f"    3. Date format issue in GTFS")
            elif isinstance(plan, dict):
                if 'itineraries' in plan:
                    itins = plan['itineraries']
                    print(f"  Itineraries: {len(itins)}")
                    if itins:
                        print(f"\n✓ SUCCESS! Found {len(itins)} routes")
                        for itin in itins[:1]:
                            print(f"\n  Route 1:")
                            print(f"    Duration: {itin['duration']/60000:.0f} min")
                            print(f"    Legs: {len(itin['legs'])}")
                else:
                    print(f"  Plan keys: {list(plan.keys())}")
                    print(f"  Full plan: {json.dumps(plan, indent=2)[:500]}")
        else:
            print(f"\nFull response: {json.dumps(data, indent=2)[:800]}")
    else:
        print("✗ Empty response body")
        
except requests.exceptions.ConnectionError as e:
    print(f"✗ Connection error: OTP not running on localhost:8080")
    print(f"  Error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
