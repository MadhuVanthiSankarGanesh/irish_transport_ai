# OTP Rebuild Instructions - WITH GTFS DATA

## Problem Found  
✗ OTP was using `--load` which **skips GTFS data**
✗ Routing endpoints return 404 because no transit data is loaded
✗ Graph exists but without actual Dublin Bus/Luas route information

## Solution: Rebuild OTP WITH GTFS

### Step 1: Open Command Prompt (cmd.exe)
- Press `Win + R`
- Type: `cmd`
- Press Enter

### Step 2: Run OTP Rebuild Command  
Copy & paste this command (it's all one line):

```
cd /d e:\irish_transport_ai\otp && java -Xmx10G -jar otp-shaded-2.8.1.jar --build graphs/default --serve .
```

### Step 3: Wait for Build to Complete
OTP will:
1. Read OSM street data (ireland-and-northern-ireland-260318.osm.pbf) - ~1-2 min
2. Read GTFS data (dublin_bus.gtfs.zip, luas.gtfs.zip) - ~2-3 min
3.  Build routing graph - ~2-5 min
4. Start HTTP server on port 8080

**Total time: 5-15 minutes for first build**

You should see:
```
Graph loaded.   |V|=2,635,957 |E|=6,098,640
Transit loaded. |Stops|=28,036 |Patterns|=6,894
Graph service for routers/default is running
Grizzly server running.
```

⚠️ **Keep this CMD window OPEN** - do not close it

### Step 4: Verify Routing is Working

Open a new PowerShell window and run:

```powershell
python e:\irish_transport_ai\test_graphql_endpoint.py
```

You should see:
```
[SUCCESS] Found N itineraries!
```

Or faster, run this one-liner:
```powershell
python -c "import requests; r = requests.get('http://localhost:8080/routers/default/plan', params={'fromPlace': '53.35,-6.25', 'toPlace': '53.38,-6.27', 'date': '20250301', 'time': '14:00'}, timeout=5); print(f'Status: {r.status_code}, Routes: {len(r.json().get(\"plan\", {}).get(\"itineraries\", []))}' if r.status_code == 200 else f'Status: {r.status_code}')"
```

### Step 5: Run the Chatbot!

Once you see the routing verification succeed, open PowerShell and run:

```powershell
cd e:\irish_transport_ai
streamlit run dashboard/chat.py
```

This opens the Dublin Transit Chatbot at `http://localhost:5501`

**Now it will use REAL Dublin Bus & Luas routes!** 🎉

## Subsequent Startups (Faster!)

After the first build, the graph.obj file has the GTFS data embedded, so you can use the faster load command:

```
cd /d e:\irish_transport_ai\otp && java -Xmx10G -jar otp-shaded-2.8.1.jar --load --serve .
```

This only takes 20-30 seconds instead of 5-15 minutes.

## Troubleshooting

### "Out of memory" error
- Increase Java heap: `-Xmx16G` or `-Xmx20G`
- Or close other applications

### Build seems stuck for 10+ minutes
- OTP is reading GTFS files - this is normal
- Building with 12GB RAM takes time
- Wait 15 minutes before killing it

### Routing still returns 404 after build
- Make sure build completed successfully (check for "Graph service for routers/default")
- Ensure CMD window didn't close
- If not showing the success message, there was a build error
- Check CMD output for errors about GTFS files

### Different dates still return no routes
- GTFS calendar may not have data for future dates
- Use dates from March-June 2025 for testing
- Or reconstruct with fresh GTFS: `gtfsrt/gtfs/` directory

## What We Fixed
- ✅ Updated tools.py to support GraphQL routing (OTP 2.8.1 standard)
- ✅ Fallback to DEMO_MODE if GraphQL fails
- ✅ Proper error handling for GraphQL responses
- ✅ Graph rebuild will include all GTFS data

## Files Involved
- OTP Jar: `e:\irish_transport_ai\otp\otp-shaded-2.8.1.jar` (177 MB)
- Existing graph: `e:\irish_transport_ai\otp\graphs\default\graph.obj` (will be rebuilt)
- Bus GTFS: `e:\irish_transport_ai\otp\graphs\default\dublin_bus.gtfs.zip` (144 MB)
- Tram GTFS: `e:\irish_transport_ai\otp\graphs\default\luas.gtfs.zip` (144 MB)
- Street map: `e:\irish_transport_ai\otp\graphs\default\ireland-and-northern-ireland-260318.osm.pbf` (395 MB)
- OTP Config: `e:\irish_transport_ai\otp\graphs\default\otp-config.json`
- Tools code: `e:\irish_transport_ai\src\llm\tools.py` (FIXED - updated for GraphQL)

---

**Next Action**: Open CMD, paste the rebuild command, and wait for "Graph service for routers/default is running" message.
