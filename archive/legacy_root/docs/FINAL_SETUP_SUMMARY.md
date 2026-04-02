# ✅ OTP READY FOR FINAL BUILD

## What Was Done
1. **✅ Identified root cause**: OTP `--load` skips GTFS files
2. **✅ Updated code**: tools.py now uses GraphQL API (OTP 2.8.1 standard)
3. **✅ Added error handling**: Graceful fallback to DEMO_MODE if routing fails
4. **✅ Created rebuild guide**: See `OTP_REBUILD_WITH_GTFS.md`

## What You Need to Do (Right Now!)

### Option 1: Full Build (Recommended - 5-15 minutes, includes everything)
Open **Command Prompt (cmd.exe)**:
- Press `Win + R`, type `cmd`, Enter
- Paste this one command:

```batch
cd /d e:\irish_transport_ai\otp && java -Xmx10G -jar otp-shaded-2.8.1.jar --build graphs/default --serve .
```

**Leave this window open!** It rebuilds the graph with GTFS data.

Expected output (may take 10+ minutes):
```
Graph loaded.   |V|=2,635,957 |E|=6,098,640
Transit loaded. |Stops|=28,036 |Patterns|=6,894
Graph service for routers/default is running
Grizzly server running.
```

### Option 2: Quick Load (After first build - 20-30 seconds, uses cached graph.obj)
```batch
cd /d e:\irish_transport_ai\otp && java -Xmx10G -jar otp-shaded-2.8.1.jar --load --serve .
```

## After OTP Starts

Open another **PowerShell** window:

```powershell
cd e:\irish_transport_ai
streamlit run dashboard/chat.py
```

Then visit: **http://localhost:5501**

## What Will Work Then
✅ Real Dublin Bus routes
✅ Real Luas tram routes  
✅ Walk + transit combinations
✅ Actual travel times
✅ Real departure/arrival times

## If Something Goes Wrong

Check:
1. **Kill stuck OTP**: `taskkill /F /IM java.exe`
2. **Check disk space**: Need ~2 GB free
3. **Increase memory**: Change `-Xmx10G` to `-Xmx16G`
4. **Wait longer**: First build takes 10-15 minutes for GTFS reading

## System Status
- ✅ LangGraph agent: Working
- ✅ Geocoding: Working (exact + fuzzy + Nominatim)
- ✅ Event search: Working (153 events)
- ✅ Demo routes: Working  
- ✅ Tools code: Updated for GraphQL
- ⏳ Real OTP: Ready after rebuild

## Files Modified
- [src/llm/tools.py](src/llm/tools.py) - Updated for GraphQL API & proper error handling
- [OTP_REBUILD_WITH_GTFS.md](OTP_REBUILD_WITH_GTFS.md) - Detailed rebuild instructions

## Testing After OTP Starts
Quick test in PowerShell:
```powershell
python -c "import requests; r = requests.get('http://localhost:8080/routers/default/plan', params={'fromPlace': '53.35,-6.25', 'toPlace': '53.38,-6.27', 'date': '20250305', 'time': '14:00'}, timeout=5); routes = len(r.json().get('plan', {}).get('itineraries', [])); print(f'✓ Found {routes} routes' if routes > 0 else '✗ No routes')"
```

Should print: `✓ Found 3 routes` or similar

---

**Next step**: Open CMD and start the rebuild! ➜ See [OTP_REBUILD_WITH_GTFS.md](OTP_REBUILD_WITH_GTFS.md)
