#!/usr/bin/env python3
"""Test OTP with different dates to find working calendar"""
import requests
import json

dates_to_test = [
    '20250301', '20250310', '20250315', '20250320',  # March 2025
    '20250401', '20250410',  # April 2025
    '20250501', '20250510',  # May 2025
    '20250601', '20250610',  # June 2025  
    '20250625', '20250627',  # Late June 2025 (originally requested)
    '20260101', '20260310',  # Early 2026
]

print("Testing OTP with different dates to find working calendar...\n")
print(f"{'Date':<12} {'Status':<8} {'Result':<50}")
print("=" * 70)

working_dates = []

for date in dates_to_test:
    try:
        r = requests.get('http://localhost:8080/routers/default/plan', 
            params={
                'fromPlace': '53.35,-6.25',
                'toPlace': '53.38,-6.27',
                'date': date,
                'time': '14:00'
            }, timeout=5)
        
        if not r.text or len(r.text.strip()) == 0:
            print(f"{date:<12} {'EMPTY':<8} Zero-byte response body")
        else:
            try:
                data = r.json()
                if 'plan' in data and data['plan'] and 'itineraries' in data['plan']:
                    routes = len(data['plan']['itineraries'])
                    print(f"{date:<12} {'OK':<8} Found {routes} routes [WORKS!]")
                    working_dates.append(date)
                elif 'error' in data:
                    msg = data['error'].get('message', 'Unknown error')[:40]
                    print(f"{date:<12} {'ERROR':<8} {msg}")
                else:
                    print(f"{date:<12} {'OK':<8} Response has no itineraries")
            except json.JSONDecodeError:
                print(f"{date:<12} {'INVALID':<8} Response is not valid JSON")
    except requests.Timeout:
        print(f"{date:<12} {'TIMEOUT':<8} Request took too long")
    except Exception as e:
        print(f"{date:<12} {'FAIL':<8} {str(e)[:40]}")

print("\n" + "=" * 70)
if working_dates:
    print(f"\n✓ WORKING DATES FOUND: {', '.join(working_dates)}")
    print(f"\nUse any of these dates in your chatbot queries:")
    print(f"  - Example: 'Route from Connolly to Dublin Airport on {working_dates[0]}'")
else:
    print("\n✗ NO WORKING DATES FOUND")
    print("\nPossible causes:")
    print("  1. GTFS calendar has limited date coverage (only specific months)")
    print("  2. GTFS data is old or outdated")
    print("  3. No service scheduled for weekends/holidays")
    print("\nTry a weekday in the future (e.g., next Monday)")
