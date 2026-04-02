import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Use Feb 23, 2026 (Monday) when services are definitely active
query = """
{
  plan(
    fromPlace: "WGS84(-6.2661,53.3436)"
    toPlace: "WGS84(-6.2766,53.3418)"
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
        print(f"✓ Got {len(itineraries)} routes")
        print(json.dumps(result, indent=2))
    
except Exception as e:
    print(f"Error: {e}")
