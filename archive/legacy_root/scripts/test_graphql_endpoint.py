#!/usr/bin/env python3
"""Test OTP 2.8.1 GraphQL endpoint"""
import requests
import json

# Test GraphQL query
query = """{
    plan(
        fromPlace: "WGS84(53.3088645, -6.2195221)"
        toPlace: "WGS84(53.3496, -6.2578)"
        date: "2025-03-01"
        time: "14:00:00"
    ) {
        itineraries {
            duration
            legs {
                mode
                distance
                startTime
                endTime
                from {
                    name
                }
                to {
                    name
                }
                route {
                    shortName
                    longName
                }
            }
        }
    }
}"""

print("Testing OTP 2.8.1 GraphQL endpoint: /index/graphql")
print("=" * 60)

try:
    r = requests.post(
        'http://localhost:8080/index/graphql',
        json={'query': query},
        timeout=10,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f'HTTP Status: {r.status_code}')
    print(f'Content-Type: {r.headers.get("content-type")}')
    
    try:
        data = r.json()
        print(f'\nResponse:\n{json.dumps(data, indent=2)}')
        
        if 'errors' in data and data['errors']:
            print(f"\n[ERROR] GraphQL returned errors:")
            for error in data['errors']:
                print(f"  - {error.get('message', 'Unknown error')}")
        elif 'data' in data:
            plan = data.get('data', {}).get('plan', {})
            itins = plan.get('itineraries', [])
            print(f"\n[SUCCESS] Found {len(itins)} itineraries!")
            if itins:
                first = itins[0]
                print(f"  - Duration: {first.get('duration', 0) / 60000:.1f} minutes")
                print(f"  - Legs: {len(first.get('legs', []))}")
    except json.JSONDecodeError as e:
        print(f"\n[ERROR] Invalid JSON response: {e}")
        print(f"Response: {r.text[:500]}")
        
except requests.Timeout:
    print("[ERROR] Request timeout - OTP may be slow or not responding")
except requests.ConnectionError as e:
    print(f"[ERROR] Connection failed: {e}")
    print("OTP server is not running on port 8080")
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")

print("\n" + "=" * 60)
