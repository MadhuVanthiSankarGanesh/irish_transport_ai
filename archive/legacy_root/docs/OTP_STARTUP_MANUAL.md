# MANUAL OTP STARTUP INSTRUCTIONS

## Problem Identified
✗ OTP server crashed (`/routers` endpoint returning 404)
✗ Graph not loaded into memory (788MB graph.obj file exists but OTP didn't load it)

## Solution: Manually Start OTP

### Step 1: Open Command Prompt
Press `Win + R`, type `cmd`, press Enter

### Step 2: Copy & Paste This Command
```
cd /d e:\irish_transport_ai\otp && java -Xmx10G -jar otp-shaded-2.8.1.jar --load --serve .
```

### Step 3: Wait for OTP to Load
- You should see java startup messages
-After ~30-120 seconds, you should see:
  ```
  Graph service for routers/default is running
  ```
- Leave this CMD window OPEN

### Step 4: Test OTP is Working
Open PowerShell and run:
```powershell
python e:\irish_transport_ai\deep_diagnose_otp.py
```

You should see:
```
[OK] Connection successful
[OK] Found N routes [OK]
```

If you see errors like:
- "[FAIL] Cannot connect" → OTP not started yet
- "[WARNING] EMPTY RESPONSE BODY" → OTP crashed, restart it
- "[OK] Found 3 routes [OK]" → SUCCESS! Go to Step 5

### Step 5: Run the Chatbot
Once OTP is working:
```powershell
cd e:\irish_transport_ai
streamlit run dashboard/chat.py
```

This opens the Dublin Transit Chatbot at `http://localhost:5501`

## Troubleshooting

### OTP Takes Too Long
- The graph is 788MB and must load from disk into RAM
- First startup can take 1-2 minutes
- Subsequent runs are faster (graph stays cached)

### Java Not Found
- Download Java JDK 17 or higher: https://www.oracle.com/java/technologies/downloads/
- Restart your computer after installing

### Cannot Connect Error in Diagnostic
- Check the CMD window running OTP for errors
- Look for messages like "Graph loading" or "IOException"
- If you see exceptions, restart OTP

### Empty Response Body
- OTP is running but graph failed to load
- Kill the CMD window (Ctrl+C)
- Restart with the command above

## Files Involved
- OTP Jar: `e:\irish_transport_ai\otp\otp-shaded-2.8.1.jar` (177 MB)
- Graph: `e:\irish_transport_ai\otp\graphs\default\graph.obj` (788 MB)
- Bus Data: `e:\irish_transport_ai\otp\graphs\default\dublin_bus.gtfs.zip`
- Tram Data: `e:\irish_transport_ai\otp\graphs\default\luas.gtfs.zip`
- Map Data: `e:\irish_transport_ai\otp\graphs\default\ireland-and-northern-ireland-260318.osm.pbf`

## What's Happening
1. OTP loads the graph.obj into memory (~2.6M transit nodes)
2. OTP starts HTTP server on port 8080
3. Chatbot sends requests to `/routers/default/plan` with:
   - Origin & destination coordinates
   - Date, time, transport mode
4. OTP returns real Dublin Bus & Luas routes
5. Chatbot displays routes in conversation

---

Once OTP is running in a CMD window, the chatbot will automatically use real Dublin transit routing. The system gracefully falls back to demo/simulated routes if OTP is unavailable.
