#!/usr/bin/env python3
"""Test OTP connectivity and route retrieval."""
import requests
import sys

try:
    print("Testing OTP on localhost:8080...")
    
    r = requests.get(
        'http://localhost:8080/routers/default/plan',
        params={
            'fromPlace': '53.35,-6.25',
            'toPlace': '53.38,-6.27',
            'date': '20260327',
            'time': '14:00'
        },
        timeout=5
    )
    
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        try:
            data = r.json()
            if data.get('plan') and data['plan'].get('itineraries'):
                routes = data['plan']['itineraries']
                print(f"✓ SUCCESS! Found {len(routes)} route(s)")
                print(f"\nFirst route:")
                route = routes[0]
                print(f"  Duration: {route['duration']/60000:.0f} minutes")
                print(f"  Legs: {len(route['legs'])}")
                sys.exit(0)
            else:
                print("✗ Empty itineraries - plan is null or has no routes")
                sys.exit(1)
        except Exception as e:
            print(f"✗ Error parsing response: {e}")
            sys.exit(1)
    else:
        print(f"✗ HTTP {r.status_code} - OTP server error")
        sys.exit(1)
        
except requests.exceptions.ConnectionError:
    print("✗ Connection refused - OTP not running on localhost:8080")
    sys.exit(1)
except requests.exceptions.Timeout:
    print("✗ Request timeout - OTP not responding")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
