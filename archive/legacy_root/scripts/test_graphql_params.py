import requests
import json

url = "http://localhost:8080/otp/routers/default/index/graphql"

# Test 1: Minimal query
print("Test 1: Minimal query (no extra params)") 
query1 = """
{
  plan(
    fromPlace: "WGS84(-6.2661,53.3436)"
    toPlace: "WGS84(-6.2597,53.3506)"
    date: "2026-02-23"
    time: "12:00:00"
  ) {
    itineraries {
      duration
    }
  }
}
"""

response = requests.post(url, json={"query": query1}, timeout=10)
result = response.json()
if "errors" in result:
    print(f"  Error: {result['errors'][0]['message'][:80]}")
else:
    print(f"  Result: {len(result.get('data', {}).get('plan', {}).get('itineraries', []))} itineraries")

# Test 2: With first parameter
print("\nTest 2: With first: 3")
query2 = """
{
  plan(
    fromPlace: "WGS84(-6.2661,53.3436)"
    toPlace: "WGS84(-6.2597,53.3506)"
    date: "2026-02-23"
    time: "12:00:00"
    first: 3
  ) {
    itineraries {
      duration
    }
  }
}
"""

response = requests.post(url, json={"query": query2}, timeout=10)
result = response.json()
if "errors" in result:
    print(f"  Error: {result['errors'][0]['message'][:80]}")
else:
    print(f"  Result: {len(result.get('data', {}).get('plan', {}).get('itineraries', []))} itineraries")

# Test 3: With different date range
print("\nTest 3: Different dates")
for test_date in ["2026-02-22", "2026-02-23", "2026-02-24"]:
    query3 = f"""
    {{
      plan(
        fromPlace: "WGS84(-6.2661,53.3436)"
        toPlace: "WGS84(-6.2597,53.3506)"
        date: "{test_date}"
        time: "12:00:00"
      ) {{
        itineraries {{
          duration
        }}
      }}
    }}
    """
    
    response = requests.post(url, json={"query": query3}, timeout=10)
    result = response.json()
    itins = result.get('data', {}).get('plan', {}).get('itineraries', [])
    print(f"  {test_date}: {len(itins)} itineraries")
