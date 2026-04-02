#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detailed OTP diagnostics - shows exactly what's happening
"""
import requests
import json

print("=" * 80)
print("DETAILED OTP DIAGNOSTIC")
print("=" * 80)

# Test 1: Basic connectivity
print("\n1. Testing basic connectivity to http://localhost:8080")
try:
    r = requests.get('http://localhost:8080/', timeout=5)
    print(f"   [OK] Connection successful")
    print(f"   Status: {r.status_code}")
    print(f"   Response length: {len(r.text)} bytes")
    print(f"   Content-Type: {r.headers.get('content-type')}")
except Exception as e:
    print(f"   [FAIL] Cannot connect: {e}")
    print(f"   [INFO] OTP is NOT running on port 8080")
    exit(1)

# Test 2: Check routers endpoint
print("\n2. Testing /routers endpoint")
try:
    r = requests.get('http://localhost:8080/routers', timeout=5)
    print(f"   Status: {r.status_code}")
    print(f"   Response length: {len(r.text)} bytes")
    if r.status_code == 200 and r.text:
        print(f"   First 200 chars: {r.text[:200]}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: The problematic /plan endpoint
print("\n3. Testing /routers/default/plan endpoint")
try:
    url = 'http://localhost:8080/routers/default/plan'
    params = {
        'fromPlace': '53.35,-6.25',
        'toPlace': '53.38,-6.27',
        'date': '20250627',
        'time': '14:00'
    }
    
    print(f"   URL: {url}")
    print(f"   Params: {params}")
    
    r = requests.get(url, params=params, timeout=5)
    
    print(f"\n   Status: {r.status_code}")
    print(f"   Content-Type: {r.headers.get('content-type')}")
    print(f"   Response length: {len(r.text)} bytes")
    
    if not r.text:
        print(f"\n   [WARNING] EMPTY RESPONSE BODY")
        print(f"   This means OTP server is:")
        print(f"      - Running but crashing on /plan requests")
        print(f"      - Hanging/timeout without response")
        print(f"      - Memory exhausted")
        print(f"      - Service calendar missing dates")
    else:
        print(f"\n   First 300 chars of response:")
        print(f"   {r.text[:300]}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                if 'plan' in data and data['plan']:
                    itins = data['plan'].get('itineraries', [])
                    print(f"\n   [OK] Valid JSON!")
                    print(f"   [OK] Found {len(itins)} routes!")
                else:
                    print(f"\n   Plan is null or missing itineraries")
            except json.JSONDecodeError as e:
                print(f"\n   JSON Parse Error: {e}")
                print(f"   Response is not valid JSON")
    
except requests.exceptions.Timeout:
    print(f"   [FAIL] Request timed out (OTP is hanging)")
except requests.exceptions.ConnectionError as e:
    print(f"   [FAIL] Connection refused: {e}")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

# Test 4: Try different dates
print("\n4. Testing with different dates")
dates_to_try = [
    '20250601',  # June 2025
    '20250327',  # March 2025
    '20260101',  # Jan 2026
]

for date_str in dates_to_try:
    try:
        params = {
            'fromPlace': '53.35,-6.25',
            'toPlace': '53.38,-6.27',
            'date': date_str,
            'time': '14:00'
        }
        r = requests.get('http://localhost:8080/routers/default/plan', params=params, timeout=5)
        
        status_ok = r.status_code == 200
        has_content = len(r.text) > 0
        
        if status_ok and has_content:
            try:
                data = r.json()
                routes = len(data.get('plan', {}).get('itineraries', []))
                print(f"   Date {date_str}: {r.status_code}, {routes} routes [OK]")
            except:
                print(f"   Date {date_str}: {r.status_code}, invalid JSON")
        else:
            print(f"   Date {date_str}: {r.status_code}, {len(r.text)} bytes response")
    except Exception as e:
        print(f"   Date {date_str}: Error - {str(e)[:50]}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)

print("""
If you see:
  - "[FAIL] Cannot connect" --> OTP is not running
    Run: cmd /c start java -Xmx10G -jar otp-shaded-2.8.1.jar --load --serve .
    
  - "[WARNING] EMPTY RESPONSE BODY" --> OTP is running but crashing
    Check OTP is stable, look at CMD window for errors
    Try restarting OTP
    
  - All dates showing empty --> GTFS calendar issue
    Check which dates OTP actually has service for
    OTP may only have 2025 or specific date range
    
  - "Found N routes [OK]" --> YOU'RE GOOD! OTP is working!
    Run your chatbot: streamlit run dashboard/chat.py
    Routes will use real Dublin transit
""")
