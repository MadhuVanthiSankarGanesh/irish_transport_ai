import requests
import json
from datetime import datetime, timedelta

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Use current date or nearby date - GTFS data has service dates
# Try multiple dates
dates_to_try = [
    "2024-03-24",  # Try current year
    "2025-05-15",  # Mid 2025
    "2025-12-15",  # End of 2025
]

# Known Dublin coordinates: Temple Bar to Connolly Station (real places)
from_lat, from_lon = 53.3436, -6.2661  # Temple Bar area
to_lat, to_lon = 53.3523, -6.2421      # Connolly Station area

for test_date in dates_to_try:
    print(f"\nTesting date: {test_date}")
    print("=" * 60)
    
    query = """
    {
      plan(
        fromPlace: "WGS84(""" + str(from_lon) + """,""" + str(from_lat) + """)"
        toPlace: "WGS84(""" + str(to_lon) + """,""" + str(to_lat) + """)"
        date: \"""" + test_date + """"
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
            print(f"Errors: {result['errors'][0].get('message', 'Unknown')}")
        elif "data" in result and result["data"]["plan"]["itineraries"]:
            print(f"✓ Found {len(result['data']['plan']['itineraries'])} itineraries!")
            print(json.dumps(result, indent=2))
        else:
            print("No itineraries found")
            
    except Exception as e:
        print(f"Error: {e}")
