import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Try a very close pair of points to test walking (Temple Bar to nearby O'Connell Street)
query = """
{
  plan(
    fromPlace: "WGS84(-6.2661,53.3436)"
    toPlace: "WGS84(-6.2597,53.3506)"
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

print("Testing short walk (Temple Bar to O'Connell, ~500m)")
print("=" * 60)

try:
    response = requests.post(
        url,
        json={"query": query},
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    result = response.json()
    
    if "errors" in result:
        print(f"Error: {result['errors'][0]['message']}")
    else:
        itins = result.get("data", {}).get("plan", {}).get("itineraries", [])
        if itins:
            print(f"✓ Got {len(itins)} route(s)")
            for itin in itins:
                print(f"  Duration: {itin['duration']}ms ({itin['duration']/60000:.1f} min)")
                print(f"  Distance: {sum(float(l['distance']) for l in itin['legs'])}m")
                for leg in itin['legs']:
                    print(f"    {leg['mode']}: {leg['distance']}m")
        else:
            print("❌ No routes (even walking)")
            
except Exception as e:
    print(f"Exception: {e}")
