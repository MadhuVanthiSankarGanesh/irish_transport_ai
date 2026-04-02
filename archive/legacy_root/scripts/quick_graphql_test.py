import requests
import json

query = '{plan(fromPlace:"WGS84(53.3377,-6.2611)" toPlace:"WGS84(53.3246,-6.2592)" date:"2026-03-24" time:"12:09:00" modes:[TRANSIT,WALK] first:1) {itineraries {duration legs {mode distance}}}}'

print("Testing GraphQL endpoint /index/graphql...")
try:
    r = requests.post(
        'http://localhost:8080/index/graphql',
        json={'query': query},
        timeout=5
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        if 'data' in data:
            print("SUCCESS! Got data back")
            print(json.dumps(data, indent=2)[:1500])
        else:
            print(json.dumps(data, indent=2)[:1500])
    else:
        print(f"Error {r.status_code}: {r.text[:300]}")
except Exception as e:
    print(f"Exception: {e}")
