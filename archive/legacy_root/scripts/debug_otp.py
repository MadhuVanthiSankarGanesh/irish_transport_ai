#!/usr/bin/env python3
"""Debug OTP routing responses in detail."""
import requests
import json

url = 'http://localhost:8080/routers/default/plan'

# Connolly to Heuston
params = {
    'fromPlace': '53.35022,-6.25053',  # Connolly Station
    'toPlace': '53.34587,-6.29366',     # Heuston Station
    'date': '20260323',
    'time': '14:00',
}

print("Debugging OTP request...")
print(f"URL: {url}")
print(f"Params: {params}\n")

try:
    r = requests.get(url, params=params, timeout=5)
    
    print(f"Status Code: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Content-Length: {len(r.content)} bytes")
    print(f"Text length: {len(r.text)} chars")
    print(f"Content: '{r.text}'")
    
    # Try different parameter combinations
    print(f"\n{'='*60}")
    print("Trying without date/time:")
    
    params_no_time = {
        'fromPlace': '53.35022,-6.25053',
        'toPlace': '53.34587,-6.29366',
    }
    r2 = requests.get(url, params=params_no_time, timeout=5)
    print(f"Status: {r2.status_code}, Content length: {len(r2.text)}, Text: '{r2.text[:100]}'")
    
    print(f"\n{'='*60}")
    print("Trying with mode parameter:")
    
    params_mode = {
        'fromPlace': '53.35022,-6.25053',
        'toPlace': '53.34587,-6.29366',
        'mode': 'WALK',
    }
    r3 = requests.get(url, params=params_mode, timeout=5)
    print(f"Status: {r3.status_code}, Content length: {len(r3.text)}, Text: '{r3.text[:100]}'")
    
    print(f"\n{'='*60}")
    print("Trying GET to /plan (short path):")
    url2 = 'http://localhost:8080/plan'
    r4 = requests.get(url2, params={'fromPlace': '53.35022,-6.25053', 'toPlace': '53.34587,-6.29366'}, timeout=5)
    print(f"Status: {r4.status_code}, Content length: {len(r4.text)}, Text: '{r4.text[:100]}'")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
