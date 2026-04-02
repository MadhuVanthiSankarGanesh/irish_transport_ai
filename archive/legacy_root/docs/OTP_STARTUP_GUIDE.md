# OTP Server Startup Instructions

## Quick Start - 3 Steps

### Step 1: Open a NEW CMD Window
- **Windows Key + R** → type `cmd` → Enter
- OR open Command Prompt from Start Menu

### Step 2: Run the OTP Server
```batch
cd E:\irish_transport_ai\otp\graphs\default
java -Xmx10G -jar E:\OpenTripPlanner\otp-shaded\target\otp-shaded-2.8.1.jar --load --serve .
```

**OR use the batch file:**
```batch
E:\irish_transport_ai\START_OTP_SERVER.bat
```

### Step 3: Wait for Ready Message
Watch the logs for:
```
OTP UPDATERS INITIALIZED - OTP 2.8.1 is ready for routing!
```

This takes ~30-60 seconds. You'll see progress like:
- "Graph loaded" 
- "Transit loaded"
- "Index street model"
- "Linking transit stops"

Once you see "ready for routing!", OTP is working.

---

## Then Test the Chatbot

In **another PowerShell/Terminal window** (while OTP runs):

```powershell
cd E:\irish_transport_ai
streamlit run dashboard/chat.py
```

The chatbot will now use **REAL OTP routes** instead of demo routes.

**Test it:**
1. "What's happening this weekend?"
2. "1" (select first event)
3. "Dublin City Center" (or any location)
4. Should get real routes with actual Dublin buses/trams

---

## Verify OTP is Working

While OTP is running, test in another PowerShell window:

```powershell
python -c "import requests; r = requests.get('http://localhost:8080/routers/default/plan', params={'fromPlace': '53.35,-6.25', 'toPlace': '53.38,-6.27', 'date': '20260327', 'time': '14:00'}, timeout=5); data = r.json(); print(f'✓ Routes: {len(data[\"plan\"][\"itineraries\"])}' if data.get('plan') and data['plan'].get('itineraries') else '✗ No routes')"
```

Expected output: `✓ Routes: 3`

---

## If You Have Issues

**Port 8080 already in use?**
```powershell
Get-Process | Where-Object {$_.ProcessName -like "*java*"} | Stop-Process -Force
```

**OTP crashes?**
- Check available disk space in `E:\irish_transport_ai\`
- Make sure 10GB RAM is available
- Try starting without `--load --serve`, just `--build` first

**Empty routes?**
- Date might be outside GTFS calendar (try dates in 2025-2026)
- Coordinates might not be on Dublin transit network
- Try: `53.35,-6.25` to `53.38,-6.27` (known Dublin coordinates)

---

## Architecture

```
User Input
    ↓
[Streamlit Chat] ← Port 5501
    ↓
[LangGraph Agent] (src/llm/graph.py)
    ↓
[Route Planner] (plan_route_tool in src/llm/tools.py)
    ↓
Try OTP (localhost:8080/routers/default/plan)
    ├─ If OK: Return real itineraries ✓
    └─ If fails: Fall back to DEMO_MODE (realistic sample routes)
```

The system is designed to work with OR without OTP!
- **With OTP**: Real Dublin buses/trams/routes
- **Without OTP**: Realistic demo routes (for testing)

---

## Keep OTP Running

OTP needs to stay running while you use the chatbot. You have two windows:
1. **CMD Window**: OTP Server (stateful background service)
2. **PowerShell Window**: `streamlit run dashboard/chat.py`

Both need to be open for real routing to work.
