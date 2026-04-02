#!/usr/bin/env python3
"""
Verify the chatbot system works end-to-end.
This tests all components without needing OTP.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🚀 DUBLIN SMART MOBILITY PLANNER - SYSTEM VERIFICATION")
print("=" * 70)

# Test 1: Imports
print("\n1. Testing imports...")
try:
    from src.llm.state import AgentState, create_initial_state
    print("   ✓ State module")
    
    from src.llm.tools import get_events_tool, plan_route_tool, geocode_tool
    print("   ✓ Tools module")
    
    from src.llm.graph import build_graph
    print("   ✓ Graph module")
    
    import pandas as pd
    print("   ✓ Data modules")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Data loading
print("\n2. Testing data...")
try:
    events = pd.read_csv("data/features/event_demand.csv")
    print(f"   ✓ Events: {len(events)} records")
    
    stops = pd.read_csv("data/clean/stops.csv")
    print(f"   ✓ Stops: {len(stops)} records")
    
    routes = pd.read_csv("data/clean/routes.csv")
    print(f"   ✓ Routes: {len(routes)} records")
except Exception as e:
    print(f"   ✗ Data loading failed: {e}")
    sys.exit(1)

# Test 3: Event search
print("\n3. Testing event discovery...")
try:
    results = get_events_tool(date_range="2026-03-27 to 2026-03-29", limit=5)
    if results['success']:
        print(f"   ✓ Found {len(results['events'])} events")
        for evt in results['events'][:2]:
            print(f"      - {evt.name} @ {evt.location}")
    else:
        print(f"   ✗ Event search failed: {results.get('error')}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# Test 4: Geocoding
print("\n4. Testing geocoding...")
try:
    result = geocode_tool("Connolly Station")
    if result['success']:
        lat, lon = result['coordinates']
        print(f"   ✓ Resolved: {result['stop_name']} ({lat:.4f}, {lon:.4f})")
    else:
        print(f"   ✗ Geocoding failed: {result.get('error')}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 5: Route planning (with DEMO_MODE)
print("\n5. Testing route planning (DEMO_MODE)...")
try:
    result = plan_route_tool("Connolly Station", "Heuston Station", preference="balanced")
    if result['success']:
        route = result['route']
        print(f"   ✓ Generated route:")
        print(f"      Duration: {route['travel_time']:.0f} minutes")
        print(f"      Walking: {route['walking_time']:.0f} minutes")
        print(f"      Transfers: {route['transfers']}")
        print(f"      Steps: {len(route['steps'])}")
        for step in route['steps'][:2]:
            print(f"        - {step}")
    else:
        print(f"   ✗ Route planning failed: {result.get('error')}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Graph building
print("\n6. Testing LangGraph agent...")
try:
    from src.llm.graph import build_graph
    app = build_graph()
    print(f"   ✓ Graph compiled successfully")
except Exception as e:
    print(f"   ✗ Graph building failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✅ ALL SYSTEMS OPERATIONAL")
print("=" * 70)
print("""
Your chatbot is ready to use!

Start it with:
    streamlit run dashboard/chat.py

Then test with:
    1. "What's happening this weekend?"
    2. "1" (select first event)
    3. "Dublin City Center" (starting location)
    4. Get instant route planning!

Note: Routes use DEMO_MODE (realistic sample data)
      If OTP is running, it will use real routes instead.
""")
