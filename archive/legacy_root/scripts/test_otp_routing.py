#!/usr/bin/env python3
"""Test OTP routing with real coordinates."""
import requests
import json

url = 'http://localhost:8080/routers/default/plan'
params = {
    'fromPlace': '53.35,-6.25',
    'toPlace': '53.38,-6.27',
    'date': '20260323',
    'time': '14:00',
    'mode': 'TRANSIT,WALK'
}

print("Testing OTP routing endpoint:")
print(f"URL: {url}")
print(f"Params: {params}\n")

try:
    r = requests.get(url, params=params, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    
    if r.text:
        try:
            data = r.json()
            if 'plan' in data and data['plan'] and 'itineraries' in data['plan']:
                itins = data['plan']['itineraries']
                print(f"\n✓ SUCCESS! Found {len(itins)} itineraries!\n")
                
                for i, itin in enumerate(itins[:3], 1):
                    start_time = itin['startTime']
                    end_time = itin['endTime']
                    duration = itin['duration'] / 60
                    transfers = len([leg for leg in itin['legs'] if leg['mode'] not in ['WALK']])
                    
                    print(f"  Route {i}:")
                    print(f"    Duration: {duration:.0f} minutes")
                    print(f"    Legs: {len(itin['legs'])}")
                    print(f"    Transit legs: {transfers}")
                    print(f"    Start: {start_time}, End: {end_time}")
            elif 'plan' in data and data['plan'] is None:
                print("\n✗ No itineraries found (plan is null)")
                print(f"   This might mean no valid routes exist for these coordinates/time")
            else:
                print(f"\nResponse structure: {list(data.keys())}")
                if 'error' in data:
                    print(f"Error: {data['error']}")
                else:
                    print(json.dumps(data, indent=2)[:500])
        except json.JSONDecodeError:
            print(f"Could not parse JSON response:")
            print(r.text[:500])
    else:
        print("Empty response body")
        
except requests.exceptions.Timeout:
    print("✗ Timeout - OTP server not responding")
except requests.exceptions.ConnectionError as e:
    print(f"✗ Connection error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
