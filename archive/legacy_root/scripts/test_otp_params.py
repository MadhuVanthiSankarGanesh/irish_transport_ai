#!/usr/bin/env python3
"""Test various OTP parameter combinations to find working configuration."""
import requests
import json

base_url = "http://localhost:8080/routers/default/plan"
origin = "53.35,-6.25"
dest = "53.38,-6.27"

test_cases = [
    {
        "name": "Basic (date + time)",
        "params": {
            "fromPlace": origin,
            "toPlace": dest,
            "date": "2026-03-27",
            "time": "14:00"
        }
    },
    {
        "name": "No time (date only)",
        "params": {
            "fromPlace": origin,
            "toPlace": dest,
            "date": "2026-03-27"
        }
    },
    {
        "name": "With mode parameter",
        "params": {
            "fromPlace": origin,
            "toPlace": dest,
            "date": "2026-03-27",
            "time": "14:00",
            "mode": "TRANSIT"
        }
    },
    {
        "name": "Simple locations (no time)",
        "params": {
            "fromPlace": origin,
            "toPlace": dest
        }
    },
    {
        "name": "Different date (try 2025)",
        "params": {
            "fromPlace": origin,
            "toPlace": dest,
            "date": "2025-03-27",
            "time": "14:00"
        }
    }
]

print("Testing OTP parameter combinations...\n")
print(f"Base URL: {base_url}\n")

for i, test in enumerate(test_cases, 1):
    print(f"{i}. {test['name']}")
    print(f"   Params: {test['params']}")
    
    try:
        r = requests.get(base_url, params=test['params'], timeout=5)
        print(f"   Status: {r.status_code}")
        
        if r.status_code == 200:
            if not r.text:
                print(f"   ✗ Empty response")
            else:
                try:
                    data = r.json()
                    plan = data.get('plan')
                    if plan is None:
                        routes = 0
                    elif isinstance(plan, dict):
                        routes = len(plan.get('itineraries', []))
                    else:
                        routes = 0
                    
                    if routes > 0:
                        print(f"   ✓ SUCCESS! Routes: {routes}")
                    else:
                        print(f"   ✗ No routes (empty itineraries)")
                except json.JSONDecodeError:
                    print(f"   ✗ Invalid JSON response")
        else:
            print(f"   ✗ HTTP {r.status_code} error")
    
    except requests.exceptions.Timeout:
        print(f"   ✗ Timeout")
    except requests.exceptions.ConnectionError:
        print(f"   ✗ Connection refused")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print()
