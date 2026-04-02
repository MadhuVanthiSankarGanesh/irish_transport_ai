#!/usr/bin/env python3
"""Test OTP routing with actual Dublin stops."""
import requests
import json

url = 'http://localhost:8080/routers/default/plan'

# Test with Connolly to Heuston
test_cases = [
    {
        'name': 'Connolly → Heuston',
        'fromPlace': '53.35022,-6.25053',  # Connolly Station
        'toPlace': '53.34587,-6.29366',     # Heuston Station
    },
    {
        'name': 'Connolly → Tara Street',
        'fromPlace': '53.35022,-6.25053',   # Connolly Station
        'toPlace': '53.34742,-6.25410',     # Tara Street
    },
]

for test_case in test_cases:
    print(f"\n{'='*60}")
    print(f"Testing: {test_case['name']}")
    print(f"{'='*60}")
    
    params = {
        'fromPlace': test_case['fromPlace'],
        'toPlace': test_case['toPlace'],
        'date': '20260323',
        'time': '14:00',
        'mode': 'TRANSIT,WALK',
    }
    
    print(f"Params: {params}\n")
    
    try:
        r = requests.get(url, params=params, timeout=5)
        print(f"Status: {r.status_code}")
        
        if not r.text:
            print("✗ Empty response body")
            continue
            
        try:
            data = r.json()
            
            if data.get('plan') is None:
                print("✗ Plan is None - no routes found")
                if 'error' in data:
                    print(f"   Error: {data['error']}")
                continue
            
            itins = data['plan'].get('itineraries', [])
            
            if not itins:
                print("✗ No itineraries returned")
                print(f"   Response keys: {list(data['plan'].keys())}")
                print(f"   Full response: {json.dumps(data['plan'], indent=2)[:200]}")
            else:
                print(f"✓ Found {len(itins)} route(s)!\n")
                
                for i, itin in enumerate(itins[:2], 1):
                    duration = itin['duration'] / 60
                    legs = itin['legs']
                    
                    print(f"  Route {i}:")
                    print(f"    Total duration: {duration:.0f} minutes")
                    print(f"    Number of legs: {len(legs)}")
                    
                    for j, leg in enumerate(legs, 1):
                        mode = leg.get('mode', 'WALK')
                        leg_duration = leg.get('duration', 0) / 60
                        if mode == 'WALK':
                            print(f"      Leg {j}: WALK ({leg_duration:.1f} min)")
                        else:
                            route = leg.get('route', 'N/A')
                            print(f"      Leg {j}: {mode} route {route} ({leg_duration:.1f} min)")
                    
        except json.JSONDecodeError as e:
            print(f"✗ JSON parse error: {e}")
            print(f"   Response: {r.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("✗ Timeout - OTP server not responding")
    except Exception as e:
        print(f"✗ Error: {e}")

print(f"\n{'='*60}")
