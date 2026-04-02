import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Dublin landmarks with coordinates
locations = {
    "Connolly Station": ("53.3523", "-6.2421"),  # Dublin's main train station
    "Heuston Station": ("53.6443", "-6.2920"),  # Dublin's west train station  
    "Temple Bar": ("53.3436", "-6.2661"),       # City center
    "O'Connell Street": ("53.3506", "-6.2597"), # Main street
    "RDS (South side)": ("53.3356", "-6.2143"), # Royal Dublin Society
}

# Test a few routes
test_pairs = [
    ("Connolly Station", "Heuston Station"),
    ("Temple Bar", "O'Connell Street"),
    ("Connolly Station", "RDS (South side)"),
]

for from_name, to_name in test_pairs:
    from_lat, from_lon = locations[from_name]
    to_lat, to_lon = locations[to_name]
    
    print(f"\n{from_name} → {to_name}")
    print("=" * 60)
    
    query = """
    {
      plan(
        fromPlace: "WGS84(""" + from_lon + """,""" + from_lat + """)"
        toPlace: "WGS84(""" + to_lon + """,""" + to_lat + """)"
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
            print(f"Error: {result['errors'][0]['message'][:80]}")
        else:
            itins = result.get("data", {}).get("plan", {}).get("itineraries", [])
            if itins:
                print(f"✓ Found {len(itins)} route(s)")
                for itin in itins[:2]:
                    print(f"  Duration: {itin['duration']}ms ({itin['duration']/60000:.1f} min)")
                    for leg in itin['legs']:
                        print(f"    {leg['mode']}: {leg['from']['name']} → {leg['to']['name']}")
            else:
                print("No routes found")
                
    except Exception as e:
        print(f"Exception: {e}")
