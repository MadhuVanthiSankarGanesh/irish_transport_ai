import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Simpler query without modes
query = """
{
  plan(
    fromPlace: "WGS84(-6.2661,53.3436)"
    toPlace: "WGS84(-6.2766,53.3418)"
    date: "2026-03-24"
    time: "12:09:00"
  ) {
    itineraries {
      duration
      legs {
        mode
        distance
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
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
