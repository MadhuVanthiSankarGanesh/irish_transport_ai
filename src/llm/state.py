"""
State schema for the LangGraph-based travel planning agent.

Maintains structured memory across conversational turns.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class Event:
    """Structured event representation."""
    name: str
    location: str
    datetime: str
    lat: float
    lon: float
    stop_id: Optional[str] = None
    stop_name: Optional[str] = None


@dataclass
class RouteStep:
    """A single step in a route."""
    instruction: str
    distance: Optional[float] = None
    time: Optional[float] = None


@dataclass
class Route:
    """Structured route representation."""
    origin: str
    destination: str
    travel_time: float  # minutes
    walking_time: float  # minutes
    transfers: int
    steps: list[str]
    departure: str
    arrival: str
    service_types: list[str] = field(default_factory=list)
    route_points: list[tuple[float, float]] = field(default_factory=list)
    route_debug: Optional[str] = None
    stop_points: list[tuple[float, float]] = field(default_factory=list)
    legs: list[dict] = field(default_factory=list)


@dataclass
class AgentState:
    """
    Main state for the travel planning agent.
    
    Maintains conversation history, current intent, and context for multi-turn interactions.
    """
    # Conversation
    messages: list[dict] = field(default_factory=list)
    
    # Intent & Current Context
    intent: Optional[str] = None  # EVENT_DISCOVERY, EVENT_SELECTION, ROUTE_PLANNING, FOLLOW_UP
    last_user_input: Optional[str] = None
    
    # Event Context
    search_results: list[Event] = field(default_factory=list)
    selected_event: Optional[Event] = None
    
    # Route Context
    origin: Optional[str] = None
    destination: Optional[str] = None
    datetime_preference: Optional[str] = None
    travel_preference: str = "balanced"  # balanced, fastest, least_transfers
    
    # Route Results
    planned_route: Optional[Route] = None
    alternative_routes: list[Route] = field(default_factory=list)

    # POI Results
    accommodations: list[dict] = field(default_factory=list)
    attractions: list[dict] = field(default_factory=list)

    # Selection
    selected_accommodation: Optional[dict] = None
    
    # Generated Response
    response: Optional[str] = None

    # Suggested UI Actions
    suggested_actions: list[dict] = field(default_factory=list)
    
    # System
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def create_initial_state() -> AgentState:
    """Create a new empty state."""
    return AgentState()


def add_message(state: AgentState, role: str, content: str) -> AgentState:
    """Add a message to the conversation history."""
    state.messages.append({"role": role, "content": content})
    return state
