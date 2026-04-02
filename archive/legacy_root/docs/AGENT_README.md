# 🚀 AI Smart Mobility Planner - LangGraph Agent Implementation

Full agentic AI system for Dublin transportation with conversational event discovery and intelligent route planning.

## 📋 Overview

This implementation provides a production-ready LangGraph-based agent that enables:

1. **Conversational Travel Planning** - Natural language input for event and route queries
2. **Event Discovery** - Search and filter Dublin events by date and location
3. **Intelligent Route Planning** - Multi-modal routing via OpenTripPlanner
4. **Context-Aware Interaction** - Maintains state across conversation turns
5. **Structured, Reliable Outputs** - Formatted responses with travel metrics

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│ Streamlit Chat Interface (dashboard/chat.py)            │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│ Agent Runner (src/llm/agent_runner.py)                  │
│ - Manages conversation state                            │
│ - Orchestrates graph execution                          │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│ LangGraph State Machine (src/llm/graph.py)              │
│ ┌──────────────┐                                        │
│ │ Intent       │ ──→ Route to appropriate node          │
│ │ Classifier   │                                        │
│ └──────┬───────┘                                        │
│        │                                                │
│   ┌────┴─────────┬──────────────┬────────────────┐    │
│   │              │              │                │    │
│   ▼              ▼              ▼                ▼    │
│ Event        Event Selection  Route              Response
│ Search       Handler          Planner           Generator
│   └──────────────────────────────────────────┬────────┘
└─────────────────────────────────────────────┼──────────┘
                                              │
┌─────────────────────────────────────────────▼──────────┐
│ Tool Wrappers (src/llm/tools.py)                       │
├──────────────────┬──────────────────┬──────────────────┤
│ get_events_tool  │ plan_route_tool  │  geocode_tool    │
└──────────────────┴──────────────────┴──────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
    GTFS DB    OTP Server   Nominatim
   (Events)   (Routing)     (Geocoding)
```

### State Management

```python
AgentState:
  - messages: list[dict]              # Conversation history
  - intent: str                       # Current intent
  - last_user_input: str              # Last user message
  - search_results: list[Event]       # Event search results
  - selected_event: Optional[Event]   # Selected event
  - origin: str                       # Starting location
  - destination: str                  # Destination (event location)
  - datetime_preference: str          # Preferred date/time
  - travel_preference: str            # balanced|fastest|least_transfers
  - planned_route: Optional[Route]    # Current route
  - response: str                     # Assistant response
```

## 🔄 Intent Flow

```
User Input
    ↓
[Intent Classifier] → Determines user intent
    ↓
┌─────────────────────────────────────────┐
│ EVENT_DISCOVERY?                        │
│ └→ [Event Search] → Find relevant events│
│                                         │
│ EVENT_SELECTION?                        │
│ └→ [Event Selection] → User picks event │
│                                         │
│ ROUTE_PLANNING?                         │
│ └→ [Route Planner] → Plan route via OTP │
│                                         │
│ FOLLOW_UP?                              │
│ └→ Uses existing state                  │
└─────────────────────────────────────────┘
    ↓
[Response Generator] → Format output
    ↓
Conversational Response
```

## 🛠️ Tools

### 1. get_events_tool
```python
Input:
  - date_range: "this_weekend" | "next_week" | "2026-03-28" | "2026-03-28:2026-04-04"
  - location: Optional[str]
  - limit: int (default=10)

Output:
{
  "success": bool,
  "events": [
    {
      "name": str,
      "location": str,
      "datetime": str,
      "lat": float,
      "lon": float,
      "stop_id": str,
      "stop_name": str
    }
  ],
  "error": Optional[str]
}
```

### 2. plan_route_tool
```python
Input:
  - origin: "53.35,-6.25" | "location_name"
  - destination: "53.38,-6.27" | "location_name"
  - datetime_str: Optional["2026-03-28 08:00"]
  - preference: "balanced" | "fastest" | "least_transfers"

Output:
{
  "success": bool,
  "route": {
    "travel_time": float,           # minutes
    "walking_time": float,          # minutes
    "transfers": int,
    "steps": [str],                 # Directions
    "departure": str,               # HH:MM
    "arrival": str                  # HH:MM
  },
  "error": Optional[str]
}
```

### 3. geocode_tool
```python
Input:
  - location: "location_name"

Output:
{
  "success": bool,
  "lat": float,
  "lon": float,
  "error": Optional[str]
}
```

## 📦 Installation

### 1. Install Dependencies
```bash
pip install -r requirements-agent.txt
```

### 2. Choose LLM Backend

#### Option A: Ollama (Local, Free)
```bash
# Install Ollama from https://ollama.ai
# Pull a model
ollama pull mistral

# Leave running in background
ollama serve
```

#### Option B: OpenAI (API Key Required)
```bash
export OPENAI_API_KEY="sk-..."
```

### 3. Start OTP Server (already done if configured)
```bash
cd otp
java -Xmx4G -jar otp-shaded.jar --build graphs/ --serve
# Runs on localhost:8080
```

## 🚀 Usage

### Launch Chat Interface
```bash
streamlit run dashboard/chat.py
```

### Example Conversations

#### Scenario 1: Event Discovery → Route Planning
```
User: What's happening this weekend?
Assistant: [Shows 5 events]

User: I want to go to the concert at #2
Assistant: Selected event, asks for origin

User: Starting from Ranelagh
Assistant: Plans route from Ranelagh to concert

User: When should I leave?
Assistant: Recommends departure time based on route
```

#### Scenario 2: Direct Route Planning
```
User: Plan a trip from Merrion Square to Croke Park
Assistant: Plans route and shows:
  - Travel time: 28 min
  - Walking: 5 min
  - Transfers: 1
  - Steps: [detailed directions]
  - Departure: 14:30
```

## 📂 Project Structure

```
src/llm/
├── state.py                 # State schema & dataclasses
├── tools.py                 # Tool wrappers (events, routing, geocoding)
├── graph.py                 # LangGraph nodes & edges
├── agent_runner.py          # Agent orchestrator & API
└── __pycache__/

dashboard/
├── app.py                   # Original comprehensive app
├── chat.py                  # NEW: LangGraph chat interface
├── ui.py                    # Original UI components
└── __pycache__/
```

## 🔧 Configuration

### Environment Variables
```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For local paths (optional)
export OTP_URL="http://localhost:8080/otp/routers/default"
export EVENTS_PATH="/path/to/event_demand.csv"
```

### LLM Settings
- **Temperature**: 0.2 (deterministic responses)
- **Model**: mistral (Ollama) or gpt-4o-mini (OpenAI)
- **Max Tokens**: Default (depends on model)

## 📊 Example Output

### Event Search
```
📅 Available Events:

1. Cork International Choral Festival
   📍 Eglinton Street, Cork | 🕒 2026-04-29

2. Waterford Festival of Food 2026
   📍 John Street, Waterford | 🕒 2026-04-24

3. Earagail Arts Festival
   📍 Letterkenny Bus Station | 🕒 2026-07-10

Reply with the event number or name to plan your trip!
```

### Route Planning
```
🚀 Route Summary
⏱ Travel Time: 28 min
🚶 Walking: 5 min
🔁 Transfers: 1
🕒 Leave at: 14:30 → Arrive 14:58

📍 Steps:
1. Walk: Straight ahead for 200m (3 min)
2. Take Bus 15 from Merrion Square to Connolly Station
3. Walk: Turn left for 150m (2 min)
```

## 🐛 Troubleshooting

### LLM Connection Issues
```python
# Check Ollama
curl http://localhost:11434/api/models

# Check OpenAI
python -c "from langchain_openai import ChatOpenAI; ChatOpenAI().invoke('test')"
```

### OTP Server Issues
```bash
# Verify OTP is running
curl http://localhost:8080/otp/routers/default/plan

# Check logs
tail -f otp/logs/otp-0.log
```

### Event Data Not Loading
```python
# Verify CSV paths
import pandas as pd
events = pd.read_csv("data/features/event_demand.csv")
print(f"Events loaded: {len(events)}")
```

## 🎯 Key Features

✅ **Multi-turn Conversation** - Maintains context across interactions
✅ **Intent Classification** - Automatically routes to appropriate handlers
✅ **Event Discovery** - Search events by date range
✅ **Intelligent Routing** - Multi-modal routing with OTP
✅ **State Persistence** - Remembers user preferences and selections
✅ **Error Handling** - Graceful degradation with helpful messages
✅ **Modular Design** - Easy to extend with new tools
✅ **Production Ready** - Structured logging, type hints, docstrings

## 🚀 Next Steps

### Enhancements
1. **Add Real-time Updates** - Live congestion data integration
2. **Personalization** - User preferences and favorites
3. **Alternative Routes** - Show multiple route options
4. **Calendar Integration** - Sync with user calendars
5. **Accessibility Features** - Wheelchair-friendly routes
6. **Mobile App** - React Native/Flutter adaptation

### Integration Points
1. **GTFS Realtime** - Live transit updates
2. **Weather API** - Weather-based recommendations
3. **Accessibility DB** - Accessibility data integration
4. **User Authentication** - Save preferences & history
5. **Analytics** - Track popular routes/events

## 📝 Notes

- **OTP Config**: Make sure `otp-config.json` has `routingDefaults` set appropriately
- **Event Data**: Freshness depends on `event_demand.csv` update frequency
- **LLM Quality**: Different models have different response quality; test various prompts
- **Performance**: Cache events/stops in memory; consider Redis for scale
- **Cost**: Ollama is free; OpenAI charges per token (~$0.01-0.05 per conversation)

## 🔗 References

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [LangChain Docs](https://python.langchain.com/)
- [OpenTripPlanner](http://openplanner.org/)
- [Streamlit Docs](https://docs.streamlit.io/)

## 📄 License

Part of the Irish Transport AI project.
