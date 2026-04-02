#!/usr/bin/env python3
"""Test various OTP API endpoints to find working ones."""
import requests
import json

base_url = "http://localhost:8080"

endpoints = [
    "/routers/default/plan",
    "/otp/routers",
    "/otp/routers/default",
    "/plan",
    "/api/v1/plan",
    "/graphql",
    "/otp",
    "/otp/routers/default/plan"
]

print("Testing OTP endpoints:")
print("=" * 60)

for path in endpoints:
    try:
        r = requests.get(f"{base_url}{path}", timeout=2)
        print(f"✓ {path:40} → {r.status_code}")
        if r.status_code == 200 and len(r.text) < 500:
            print(f"  Response: {r.text[:200]}")
    except Exception as e:
        print(f"✗ {path:40} → Error: {str(e)[:50]}")

print("\n" + "=" * 60)
print("Testing /plan with coordinates:")
print("=" * 60)

# Test with query params
params = {
    "fromPlace": "53.35,-6.25",
    "toPlace": "53.38,-6.27",
    "date": "20260323",
    "time": "14:00"
}

for path in ["/otp/routers/default/plan", "/routers/default/plan", "/plan"]:
    try:
        r = requests.get(f"{base_url}{path}", params=params, timeout=2)
        print(f"\n{path}?fromPlace=...&toPlace=...:")
        print(f"  Status: {r.status_code}")
        print(f"  Response: {r.text[:300]}")
    except Exception as e:
        print(f"{path}: Error: {e}")
