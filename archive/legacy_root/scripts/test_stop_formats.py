import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Try different stop ID formats
formats = [
    ("8220000150", "8220B100111"),  # Just ID
    ("stop:8220000150", "stop:8220B100111"),  # stop: prefix
    ("GTFS:dublin_bus:8220000150", "GTFS:dublin_bus:8220B100111"),  # GTFS prefix
]

for from_id, to_id in formats:
    print(f"\nTesting format: {from_id}")
    print("=" * 60)
    
    query = """
    {
      plan(
        fromPlace: \"""" + from_id + """"
        toPlace: \"""" + to_id + """"
        date: "2026-02-23"
        time: "12:00:00"
      ) {
        itineraries {
          duration
          legs { mode distance }
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
            err = result['errors'][0].get('message', '')
            if "LOCATION_NOT_FOUND" in err:
                print("❌ Location not found")
            else:
                print(f"❌ Error: {err[:80]}")
        elif result.get("data", {}).get("plan", {}).get("itineraries"):
            print(f"✓ Success! Found routes")
        else:
            print("No routes (empty result)")
    except Exception as e:
        print(f"❌ Exception: {str(e)[:60]}")
