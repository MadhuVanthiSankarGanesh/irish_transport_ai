import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Use real Dublin stop IDs: Abbey Street to Westland Row
query = """
{
  plan(
    fromPlace: "GTFS:8220000150"
    toPlace: "8220B100111"
    date: "2026-02-23"
    time: "12:00:00"
  ) {
    itineraries {
      duration
      legs {
        mode
        distance
        from { name }
        to { name }
      }
    }
  }
}
"""

try:
    print("Testing routing with real Dublin stops...")
    print("From: Abbey Street → To: Westland Row")
    response = requests.post(
        url,
        json={"query": query},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    result = response.json()
    
    if "errors" in result:
        print(f"GraphQL Error: {result['errors'][0].get('message')}")
    elif "data" in result:
        itineraries = result["data"]["plan"]["itineraries"]
        if itineraries:
            print(f"✓ SUCCESS! Got {len(itineraries)} route(s)\n")
            for i, itin in enumerate(itineraries):
                print(f"Route {i+1}: {itin['duration']}ms travel time")
                for leg in itin['legs']:
                    print(f"  - {leg['mode']}: {leg['from']['name']} → {leg['to']['name']} ({leg['distance']}m)")
        else:
            print("No routes found")
    
except Exception as e:
    print(f"Error: {e}")
