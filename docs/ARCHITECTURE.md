# Architecture Guide

## System Overview

The project is a conversational mobility planner that combines:

- LLM-based intent handling
- structured tool use
- transit planning
- walking route planning
- event and destination discovery

The design goal is to keep each responsibility explicit:

- the UI handles chat and maps
- the agent handles conversation state and flow
- the tool layer handles service calls
- OTP handles transit
- GraphHopper handles walking

## Runtime Components

### 1. Streamlit App

Path:

- `dashboard/chat.py`

Responsibilities:

- render the chat UI
- display route maps
- initialize the configured LLM
- hold session state for conversation and route context

### 2. Agent Layer

Paths:

- `src/llm/agent_runner.py`
- `src/llm/graph.py`
- `src/llm/state.py`

Responsibilities:

- classify user intent
- manage multi-turn state
- route requests to the correct tool flow
- format responses for the UI

### 3. MCP / Tool Gateway

Paths:

- `src/mcp_server.py`
- `src/llm/tool_gateway.py`
- `src/llm/tools.py`

Responsibilities:

- expose tools in a consistent way
- talk to routing services
- handle geocoding and route formatting
- provide fallback logic when individual services fail

### 4. OTP

Path:

- `otp/`

Responsibilities:

- public transport itinerary planning
- stop and leg information for transit journeys

### 5. GraphHopper

Path:

- `deploy/graphhopper/`

Responsibilities:

- walking path routing on the street network
- avoiding unrealistic straight-line walking paths

## Data Flow

Typical event-to-route flow:

1. user asks about events
2. agent classifies intent as event discovery
3. event tool returns matching events
4. user selects an event
5. agent stores destination context
6. user gives an origin
7. tool layer calls OTP for transit itinerary
8. GraphHopper is used for walking segments where appropriate
9. route text and map data are returned to Streamlit

## Why OTP + GraphHopper

This split is deliberate:

- OTP is strong for multimodal transit planning
- GraphHopper improves pedestrian path realism

That division also makes the architecture easy to explain in interviews.

## Deployment Model

Current supported deployment:

- Docker Compose
- local machine for development
- two AWS EC2 instances for the cloud deployment:
  - app instance for Streamlit and MCP
  - routing instance for OTP and GraphHopper

Why this model:

- easier to reason about than Kubernetes for a demo
- keeps all service boundaries explicit
- stronger portfolio story than a single-host demo because the routing workload is separated from the app tier

## Repo Design Notes

The repository intentionally keeps:

- source code and deployment logic in Git
- large runtime artifacts outside normal Git tracking

That makes the repo easier for recruiters to review while still supporting the full demo runtime on EC2.
