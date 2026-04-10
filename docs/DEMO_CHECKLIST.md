# Demo Checklist

Use this checklist before an interview demo.

## Service Checks

Run:

```bash
docker compose ps
```

Confirm:

- `app` is up
- `mcp` is up
- `otp` is up
- `graphhopper` is up
- `ollama` is up, if using Ollama

## Browser Check

Open:

```text
http://localhost:8501
```

Confirm:

- app loads cleanly
- no blank screen after asking a question
- map renders after route planning

## Recommended Demo Flows

### Flow 1: Event Discovery to Route

1. Ask: `What events are happening this weekend?`
2. Select an event
3. Give a starting location
4. Show the route and walking path

### Flow 2: Address-Based Journey

1. Choose or reference an event
2. Provide a real address as origin
3. Show that the planner can route from an address, not just a stop

### Flow 3: Attractions Replan

1. Ask for attractions near the selected event
2. Select one
3. Show that the route replans to the attraction instead of reusing the previous destination

## Talking Points

Use these points during the demo:

- the app is not a generic chatbot; it orchestrates real routing engines
- OTP is used for transit itineraries
- GraphHopper is used for walking segments
- LangGraph manages the conversational state
- MCP/tooling isolates service access from the UI
- the full stack is containerized for local and AWS EC2 deployment

## Backup Plan

If Ollama is memory-constrained:

- switch to a smaller configured model
- or use OpenAI API for the interview demo

If a service is slow:

- keep one or two prepared demo prompts
- avoid rebuilding graphs live during the interview
