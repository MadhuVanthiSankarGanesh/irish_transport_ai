#!/usr/bin/env python3
import requests
import json

try:
    print("Connecting to OTP at localhost:8080...")
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
    
    print(f"\n✓ Connection successful!")
    print(f"HTTP Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Response length: {len(r.text)} bytes")
    
    if r.text:
        print(f"\nFirst 300 chars of response:")
        print(r.text[:300])
        
        if r.text.strip().startswith('{'):
            data = r.json()
            print(f"\n✓ Valid JSON response!")
            print(f"Response keys: {list(data.keys())}")
            
            if 'plan' in data:
                plan = data['plan']
                if plan is None:
                    print("⚠️  Plan is NULL - no routes available")
                elif isinstance(plan, dict) and 'itineraries' in plan:
                    itins = plan['itineraries']
                    if itins:
                        print(f"\n✓✓✓ SUCCESS! Found {len(itins)} routes!")
                        for i, itin in enumerate(itins[:1], 1):
                            print(f"\nRoute {i}:")
                            print(f"  Duration: {itin['duration']/60000:.0f} min")
                            print(f"  Legs: {len(itin['legs'])}")
                            for j, leg in enumerate(itin['legs'][:3], 1):
                                mode = leg.get('mode', 'WALK')
                                print(f"    {j}. {mode}")
                    else:
                        print("✗ Plan has empty itineraries list")
        else:
            print(f"\n✗ Not JSON - response is HTML or error page")
            print(f"Starts with: {r.text[:50]}")
    else:
        print("\n✗ Empty response body")
        
except requests.exceptions.ConnectionError as e:
    print(f"✗ Connection refused: OTP not running")
    print(f"   Error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
