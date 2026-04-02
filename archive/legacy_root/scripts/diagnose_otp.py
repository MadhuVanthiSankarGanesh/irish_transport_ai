#!/usr/bin/env python3
"""Comprehensive OTP diagnostic."""
import requests
import json
import subprocess

print("=" * 70)
print("OTP DIAGNOSTIC REPORT")
print("=" * 70)

# Check if Java process exists
print("\n1. Checking Java processes...")
try:
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq java.exe'], 
                          capture_output=True, text=True, timeout=5)
    if 'java.exe' in result.stdout:
        print("   ✓ Java process is running")
        # Count lines (each java process is one line)
        count = result.stdout.count('java.exe')
        print(f"   Amount: {count} Java process(es)")
    else:
        print("   ✗ No Java process found")
except Exception as e:
    print(f"   ? Could not check: {e}")

# Try connecting to OTP
print("\n2. Testing OTP connectivity...")
try:
    r = requests.get('http://localhost:8080/routers/default', timeout=3)
    print(f"   ✓ Connected to OTP")
    print(f"   HTTP Status: {r.status_code}")
    print(f"   Response length: {len(r.text)} bytes")
    if r.text[:50]:
        print(f"   Response start: {r.text[:100]}")
except requests.exceptions.ConnectionError:
    print(f"   ✗ Cannot connect to localhost:8080 - port not open")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Try the plan endpoint
print("\n3. Testing /plan endpoint...")
try:
    r = requests.get(
        'http://localhost:8080/routers/default/plan',
        params={
            'fromPlace': '53.35,-6.25',
            'toPlace': '53.38,-6.27',
            'date': '20250627',
            'time': '14:00'
        },
        timeout=5
    )
    
    print(f"   HTTP Status: {r.status_code}")
    print(f"   Content-Type: {r.headers.get('content-type', 'N/A')}")
    print(f"   Response length: {len(r.text)} bytes")
    print(f"   Response content:")
    print(f"   {repr(r.text[:200])}")
    
    if not r.text:
        print("\n   ⚠️  EMPTY RESPONSE BODY - OTP is likely:")
        print("      - Crashing on requests")
        print("      - Hanging/stuck")
        print("      - Running out of memory")
        print("      - Service calendar issue")
    elif r.status_code == 200:
        try:
            data = r.json()
            print(f"\n   ✓ Valid JSON response")
            if data.get('plan') and data['plan'].get('itineraries'):
                print(f"   ✓✓ Found {len(data['plan']['itineraries'])} routes!")
            else:
                print(f"   ✗ No routes in response (null plan or empty itineraries)")
        except json.JSONDecodeError as e:
            print(f"\n   ✗ Invalid JSON: {e}")
    
except requests.exceptions.Timeout:
    print("   ✗ Request timed out - OTP is slow/hanging")
except requests.exceptions.ConnectionError:
    print("   ✗ Connection refused - OTP not responding")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 70)
print("RECOMMENDATIONS:")
print("=" * 70)

print("\nIf OTP is returning empty responses:")
print("  1. Restart OTP server:")
print("     - Kill: taskkill /IM java.exe /F")
print("     - Then re-run START_OTP_SERVER.bat")
print("")
print("  2. Check OTP logs in otp/graphs/default/")
print("  3. Ensure you have 10GB free RAM")
print("  4. Try with walktransit=True parameter")
print("")
print("For now, your chatbot uses DEMO_MODE (sample routes work fine!)")
