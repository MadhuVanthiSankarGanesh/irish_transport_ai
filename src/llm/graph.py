"""
LangGraph implementation for the travel planning agent.

Defines graph nodes, edges, and the main agent logic.
"""

import re
import os
from typing import Optional, Literal, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from src.llm.state import AgentState, Event, Route
from src.llm.tool_gateway import (
    get_events_tool,
    plan_route_tool,
    geocode_tool,
    get_nearest_stop,
    get_accommodations_tool,
    get_attractions_tool,
    _haversine_km,
    geocode_cached,
    geocode_osm,
    reverse_geocode_osm
)
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY: Extract text from LLM response
# ============================================================================

def _extract_text(response: Any) -> str:
    """
    Extract text from LLM response.
    Handles both string responses (Ollama) and message objects (OpenAI).
    """
    if isinstance(response, str):
        return response
    elif isinstance(response, BaseMessage):
        return response.content
    elif hasattr(response, 'content'):
        return response.content
    else:
        return str(response)


# ============================================================================
# NODE: Intent Classifier
# ============================================================================

def intent_classifier(state: AgentState, llm: Any) -> AgentState:
    """
    Classify user intent into one of: 
    EVENT_DISCOVERY, EVENT_SELECTION, ROUTE_PLANNING, FOLLOW_UP, ORIGIN_PROVIDED, ACCOMMODATION, ATTRACTION, ATTRACTION_SELECT
    """
    try:
        user_input = state.last_user_input or ""
        user_input_lower = user_input.lower().strip()
        
        # PRIORITY 1: Context-aware classification for waiting states
        # If we're waiting for origin (selected event, no valid origin yet)
        if state.selected_event and not state.origin:
            logger.info(f"Context: Event selected, awaiting origin. Input: {user_input[:50]}")
            state.intent = "ORIGIN_PROVIDED"
            state.origin = user_input
            return state
        
        # PRIORITY 2: If we just got geocoding error, still waiting for origin
        if state.intent == "AWAIT_ORIGIN" and state.selected_event:
            logger.info(f"Context: Retrying origin after geocoding error. Input: {user_input[:50]}")
            state.intent = "ORIGIN_PROVIDED"
            state.origin = user_input
            return state
        
        # PRIORITY 3: Heuristic-based classification for common patterns (avoid LLM for obvious cases)
        if state.accommodations:
            if re.match(r'^\s*\d+\s*$', user_input):
                state.intent = "ACCOMMODATION_SELECT"
                return state
            user_clean = re.sub(r"[^a-z0-9 ]+", " ", user_input_lower).strip()
            user_clean = re.sub(r"\s+", " ", user_clean)
            for item in state.accommodations:
                name = str(item.get("name") or "").lower()
                name_clean = re.sub(r"[^a-z0-9 ]+", " ", name).strip()
                name_clean = re.sub(r"\s+", " ", name_clean)
                if name_clean and (name_clean in user_clean or user_clean in name_clean):
                    state.intent = "ACCOMMODATION_SELECT"
                    return state
        if state.attractions:
            if re.match(r'^\s*\d+\s*$', user_input):
                state.intent = "ATTRACTION_SELECT"
                return state
            user_clean = re.sub(r"[^a-z0-9 ]+", " ", user_input_lower).strip()
            user_clean = re.sub(r"\s+", " ", user_clean)
            for item in state.attractions:
                name = str(item.get("name") or "").lower()
                name_clean = re.sub(r"[^a-z0-9 ]+", " ", name).strip()
                name_clean = re.sub(r"\s+", " ", name_clean)
                if name_clean and (name_clean in user_clean or user_clean in name_clean):
                    state.intent = "ATTRACTION_SELECT"
                    return state
        if any(term in user_input_lower for term in ["accommodation", "hotel", "stay", "lodging", "hostel", "bnb"]):
            state.intent = "ACCOMMODATION"
            return state
        if any(term in user_input_lower for term in ["attraction", "things to do", "places to visit", "sight", "tour"]):
            state.intent = "ATTRACTION"
            return state
        # Check for event selection patterns: number, event name
        if state.search_results and not state.selected_event:  # Only if we haven't selected yet
            # Check if input is just a number (e.g., "1", "2")
            if re.match(r'^\d+$', user_input.strip()):
                logger.info(f"Heuristic: Detected number selection: {user_input}")
                state.intent = "EVENT_SELECTION"
                return state
            
            # Check if input matches an event name
            user_lower = user_input_lower
            user_clean = re.sub(r"[^a-z0-9 ]+", " ", user_lower).strip()
            user_clean = re.sub(r"\s+", " ", user_clean)
            for event in state.search_results:
                event_clean = re.sub(r"[^a-z0-9 ]+", " ", event.name.lower()).strip()
                event_clean = re.sub(r"\s+", " ", event_clean)
                loc_clean = re.sub(r"[^a-z0-9 ]+", " ", str(event.location).lower()).strip()
                loc_clean = re.sub(r"\s+", " ", loc_clean)
                date_clean = re.sub(r"[^0-9-]+", " ", str(event.datetime)).strip()
                combined = f"{event_clean} {loc_clean} {date_clean}".strip()
                if event_clean in user_clean or user_clean in event_clean or user_clean in combined:
                    logger.info(f"Heuristic: Matched event name: {event.name}")
                    state.intent = "EVENT_SELECTION"
                    return state
        
        # PRIORITY 4: Use LLM for complex intent classification
        classification_prompt = f"""
Classify the user's intent into ONE of these categories:
1. EVENT_DISCOVERY - asking about events (e.g., "What's happening this weekend?", "Show me events")
2. EVENT_SELECTION - selecting or referencing an event from search results (e.g., "Take me to #1", "I want to go to the concert")
3. ROUTE_PLANNING - asking for a route/directions (e.g., "Plan my trip", "How do I get to X from Y")
4. ACCOMMODATION - asking for hotels/accommodation near the event
5. ATTRACTION - asking for attractions or things to do near the event
6. FOLLOW_UP - follow-up question about previous results (e.g., "When should I leave?", "What about transfers?")

User input: "{user_input}"

Previous context:
- Selected event: {state.selected_event}
- Search results count: {len(state.search_results)}

Respond with ONLY the intent category (e.g., "EVENT_DISCOVERY") and nothing else.
"""
        
        response = llm.invoke([HumanMessage(content=classification_prompt)])
        intent_text = _extract_text(response).strip().upper()
        
        # Parse intent
        if "ACCOMMODATION" in intent_text:
            state.intent = "ACCOMMODATION"
        elif "ATTRACTION" in intent_text:
            state.intent = "ATTRACTION"
        elif "DISCOVERY" in intent_text:
            state.intent = "EVENT_DISCOVERY"
        elif "SELECTION" in intent_text:
            state.intent = "EVENT_SELECTION"
        elif "ROUTE" in intent_text or "PLANNING" in intent_text:
            state.intent = "ROUTE_PLANNING"
        else:
            state.intent = "FOLLOW_UP"
        
        logger.info(f"Classified intent: {state.intent}")
    
    except Exception as e:
        logger.error(f"Error in intent_classifier: {e}")
        state.intent = "FOLLOW_UP"
    
    return state


# ============================================================================
# NODE: Event Search
# ============================================================================

def event_search(state: AgentState, llm: Any) -> AgentState:
    """
    Search for events based on user input.
    Extract date range and query from user message.
    """
    try:
        user_input = state.last_user_input or ""
        
        # Use LLM to extract date range from natural language
        extraction_prompt = f"""
Extract the date range from this user query:
"{user_input}"

Possible formats:
- "this_weekend"
- "next_week"
- "2026-03-28" (specific date)
- "2026-03-28:2026-04-04" (date range)

Respond with ONLY the date range (e.g., "this_weekend") and nothing else.
If unclear, default to "this_weekend".
"""
        
        response = llm.invoke([HumanMessage(content=extraction_prompt)])
        response_text = _extract_text(response).strip().replace('"', '')
        
        # Extract date range from response - look for keywords first
        date_range = None
        normalized_response = re.sub(r"[^a-z0-9:\- ]+", " ", response_text.lower()).strip()
        normalized_response = re.sub(r"\s+", " ", normalized_response)
        if "this_weekend" in normalized_response or "this weekend" in normalized_response:
            date_range = "this_weekend"
        elif "next_week" in normalized_response or "next week" in normalized_response:
            date_range = "next_week"
        else:
            # Try to extract date pattern (YYYY-MM-DD)
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', response_text)
            if date_match:
                date_range = date_match.group(0)
        
        # Default to this_weekend if extraction failed
        if not date_range:
            logger.warning(f"Could not extract date range from LLM response: {response_text[:100]}")
            date_range = "this_weekend"
        
        logger.info(f"Extracted date range: {date_range}")
        
        # Call tools to get events
        result = get_events_tool(date_range, limit=5)
        
        if result["success"] and result["events"]:
            state.search_results = [
                Event(**event) for event in result["events"]
            ]
            state.response = _format_event_results(state.search_results)
        else:
            state.error_message = result.get("error", "No events found")
            state.response = f"❌ {state.error_message}"
        
        logger.info(f"Found {len(state.search_results)} events")
    
    except Exception as e:
        logger.error(f"Error in event_search: {e}")
        state.error_message = str(e)
        state.response = f"❌ Error searching for events: {e}"
    
    return state


# ============================================================================
# NODE: Event Selection Handler
# ============================================================================

def event_selection_handler(state: AgentState, llm: Any) -> AgentState:
    """
    Handle event selection from search results.
    Extract event number or name from user input.
    """
    try:
        user_input = state.last_user_input or ""
        
        if not state.search_results:
            state.error_message = "No events to select from. Please search first."
            state.response = state.error_message
            return state
        
        # Extract selection (number or name)
        selection = _extract_event_selection(user_input, state.search_results)
        
        if selection is not None:
            state.selected_event = state.search_results[selection]
            state.destination = f"{state.selected_event.lat},{state.selected_event.lon}"
            state.datetime_preference = state.selected_event.datetime
            
            # Ask for origin
            state.response = f"""
✅ Selected: **{state.selected_event.name}**
📍 Location: {state.selected_event.location}
🕒 Date: {state.selected_event.datetime}

Where are you starting from? (location or stop name)
"""
            state.intent = "AWAIT_ORIGIN"
        else:
            state.error_message = "Could not identify event selection"
            state.response = f"❌ {state.error_message}\n\nPlease reply with a number (1-{len(state.search_results)}) or event name."
    
    except Exception as e:
        logger.error(f"Error in event_selection_handler: {e}")
        state.error_message = str(e)
        state.response = f"❌ Error handling selection: {e}"
    
    return state


# ============================================================================
# NODE: Route Planner
# ============================================================================

def route_planner(state: AgentState, llm: Any) -> AgentState:
    """
    Plan a route using OTP.
    Requires origin and destination to be set.
    """
    try:
        # Determine origin and destination
        origin = state.origin
        destination = state.destination
        
        # If we're still waiting for origin (selected_event but no valid origin)
        if state.selected_event and not origin:
            state.response = "Please provide a starting location (e.g., 'Merrion Square', 'O'Connell Street', 'Heuston Station')"
            state.intent = "AWAIT_ORIGIN"
            return state
        
        if not origin or not destination:
            state.error_message = "Missing origin or destination"
            state.response = f"❌ {state.error_message}"
            state.intent = "AWAIT_ORIGIN"
            return state
        
        # Resolve coordinates if needed
        if not _is_coordinates(origin):
            geo_result = geocode_tool(origin)
            if geo_result["success"]:
                origin = f"{geo_result['lat']},{geo_result['lon']}"
                if geo_result.get("matched_name"):
                    logger.info(f"Fuzzy matched origin: {origin} -> {geo_result.get('matched_name')}")
            else:
                # Geocoding failed - suggest alternatives
                example_stops = _get_example_stops()
                stop_list = "\n".join([f"• {s}" for s in example_stops])
                state.error_message = f"Could not find location: {origin}"
                state.response = f"❌ Location not found: **{origin}**\n\n" \
                               f"Try one of these major stops:\n{stop_list}\n\n" \
                               f"or any Dublin district/suburb name"
                # Keep intent as AWAIT_ORIGIN so user can retry
                state.intent = "AWAIT_ORIGIN"
                return state
        
        if not _is_coordinates(destination):
            geo_result = geocode_tool(destination)
            if geo_result["success"]:
                destination = f"{geo_result['lat']},{geo_result['lon']}"
            else:
                state.error_message = f"Could not find location: {destination}"
                state.response = state.error_message
                return state
        
        # Plan route
        route_result = plan_route_tool(
            origin=origin,
            destination=destination,
            datetime_str=state.datetime_preference,
            preference=state.travel_preference
        )
        
        if route_result["success"]:
            state.planned_route = Route(
                origin=state.origin,
                destination=state.destination,
                travel_time=route_result["route"]["travel_time"],
                walking_time=route_result["route"]["walking_time"],
                transfers=route_result["route"]["transfers"],
                steps=route_result["route"]["steps"],
                departure=route_result["route"]["departure"],
                arrival=route_result["route"]["arrival"],
                service_types=route_result["route"].get("service_types", []),
                route_points=route_result["route"].get("route_points", []),
                route_debug=route_result["route"].get("route_debug"),
                stop_points=route_result["route"].get("stop_points", []),
                legs=route_result["route"].get("legs", []),
            )
            state.response = _format_route_result(state.planned_route, route_result.get("source"))
        else:
            state.error_message = route_result.get("error", "Failed to plan route")
            # Include helpful instructions in response
            if ("OTP" in state.error_message or "server" in state.error_message) and "service area" not in state.error_message.lower():
                state.response = f"""❌ {state.error_message}

**How to start OTP:**

1. Download OpenTripPlanner: https://github.com/opentripplanner/OpenTripPlanner/releases
2. Place otp-2.x.x-shaded.jar in the project root
3. Run: `java -jar otp-shaded.jar --build otp/graphs/default --load`

**For now:** You can still:
- 🔍 Search for events
- 📍 View event locations  
- 📋 Set origin and destination locations

Route details will work once OTP is running!
"""
            else:
                state.response = f"❌ {state.error_message}"
        
        logger.info(f"Route planned: {state.planned_route}")
    
    except Exception as e:
        logger.error(f"Error in route_planner: {e}")
        state.error_message = str(e)
        state.response = f"❌ Error planning route: {e}"
    
    return state


# ============================================================================
# NODE: Accommodation Search
# ============================================================================

def accommodation_search(state: AgentState, llm: Any) -> AgentState:
    """
    Find accommodations near the selected event.
    """
    try:
        if not state.selected_event:
            state.response = "Tell me which event you're going to, and I’ll find nearby accommodation."
            return state

        results = get_accommodations_tool(limit=200)
        if not results.get("success"):
            state.response = f"❌ Couldn’t load accommodation data: {results.get('error')}"
            return state

        items = results.get("results", [])[:200]
        event_coords = (state.selected_event.lat, state.selected_event.lon)
        enriched = []
        geo_memo: dict[str, Optional[tuple[float, float]]] = {}
        # Prefilter by region/locality tokens to reduce geocoding volume
        event_loc = (state.selected_event.location or "").lower()
        event_region = None
        region_info = reverse_geocode_osm(event_coords[0], event_coords[1])
        if region_info:
            event_region = (region_info.get("county") or region_info.get("city") or "").lower()
        prefiltered = []
        if event_loc:
            for item in items:
                locality = (item.get("locality") or "").lower()
                region = (item.get("region") or "").lower()
                if event_loc in locality or event_loc in region:
                    prefiltered.append(item)
        if event_region:
            for item in items:
                locality = (item.get("locality") or "").lower()
                region = (item.get("region") or "").lower()
                if event_region and (event_region in locality or event_region in region):
                    prefiltered.append(item)
        if prefiltered:
            items = prefiltered
        # Limit geocoding workload
        max_geocode = int(os.getenv("ACCOM_MAX_GEOCODE", "80"))
        items = items[:max_geocode]
        def _geo_first(queries):
            for query in filter(None, queries):
                key = str(query).strip().lower()
                if not key:
                    continue
                if key in geo_memo:
                    return geo_memo[key]
                coords = geocode_osm(str(query))
                geo_memo[key] = coords
                if coords is not None and coords[0] is not None and coords[1] is not None:
                    return coords
            return None

        for item in items:
            coords = None
            if item.get("lat") is not None and item.get("lon") is not None:
                try:
                    coords = (float(item.get("lat")), float(item.get("lon")))
                except Exception:
                    coords = None
            if coords is None:
                coords = _geo_first([item.get("address"), item.get("locality"), item.get("region"), item.get("name")])
            if not coords:
                dist_km = None
            else:
                dist_km = _haversine_km(event_coords[0], event_coords[1], coords[0], coords[1])
            item["_dist_km"] = dist_km
            enriched.append((dist_km, item))
            # Early exit once we have enough nearby candidates
            if len([d for d, _ in enriched if d is not None and d <= 30]) >= 10:
                break

        # Filter to a nearby radius if possible
        nearby = [item for dist, item in enriched if dist is not None and dist <= 30]
        if nearby:
            filtered = nearby
        else:
            # Fall back to closest known distances
            enriched = [e for e in enriched if e[0] is not None]
            enriched.sort(key=lambda x: x[0])
            filtered = [item for _, item in enriched[:10]] if enriched else items[:10]

        state.accommodations = filtered[:10]

        lines = [
            f"Here are some places to stay near **{state.selected_event.location}**:",
            ""
        ]
        for i, item in enumerate(state.accommodations, 1):
            name = item.get("name") or "Accommodation"
            locality = item.get("locality") or ""
            region = item.get("region") or ""
            address = item.get("address") or ""
            where = ", ".join([p for p in [address, locality, region] if p])
            dist_km = item.get("_dist_km")
            dist_txt = f" ({dist_km:.1f} km)" if dist_km is not None else ""
            lines.append(f"{i}. **{name}** — {where}{dist_txt}".strip())

        if state.origin and state.destination:
            lines.append("")
            lines.append("Want me to plan the route to one of these? Just tell me the number.")

        state.response = "\n".join(lines)
        return state

    except Exception as e:
        logger.error(f"Error in accommodation_search: {e}")
        state.response = f"❌ Error finding accommodation: {e}"
        return state


def accommodation_selection(state: AgentState, llm: Any) -> AgentState:
    """
    Select an accommodation by number and plan route from it to event.
    """
    try:
        if not state.selected_event or not state.accommodations:
            state.response = "Please ask for accommodations first, then pick a number."
            return state

        raw = (state.last_user_input or "").strip()
        idx = None
        try:
            idx = int(raw) - 1
        except Exception:
            raw_lower = raw.lower()
            for i, item in enumerate(state.accommodations):
                name = str(item.get("name") or "").lower()
                if name and (name in raw_lower or raw_lower in name):
                    idx = i
                    break
        if idx is None:
            state.response = "Please choose an accommodation number or name from the list."
            return state
        if idx < 0 or idx >= len(state.accommodations):
            state.response = "That number is out of range. Please pick a valid accommodation number."
            return state

        selected = state.accommodations[idx]
        state.selected_accommodation = selected

        address = ", ".join([p for p in [
            selected.get("address"),
            selected.get("locality"),
            selected.get("region"),
        ] if p])
        if not address:
            address = selected.get("name") or ""

        state.origin = address
        state.destination = f"{state.selected_event.lat},{state.selected_event.lon}"

        return route_planner(state, llm)

    except Exception as e:
        logger.error(f"Error in accommodation_selection: {e}")
        state.response = f"❌ Error selecting accommodation: {e}"
        return state


# ============================================================================
# NODE: Attraction Search
# ============================================================================

def attraction_search(state: AgentState, llm: Any) -> AgentState:
    """
    Find attractions near the selected event.
    """
    try:
        if not state.selected_event:
            state.response = "Tell me which event you're going to, and I’ll find nearby attractions."
            return state

        results = get_attractions_tool(limit=200)
        if not results.get("success"):
            state.response = f"❌ Couldn’t load attraction data: {results.get('error')}"
            return state

        event_coords = (state.selected_event.lat, state.selected_event.lon)
        items = results.get("results", [])
        filtered = []
        for item in items:
            lat = item.get("latitude")
            lon = item.get("longitude")
            try:
                lat_f = float(lat) if lat is not None else None
                lon_f = float(lon) if lon is not None else None
            except Exception:
                lat_f, lon_f = None, None
            if lat_f is None or lon_f is None:
                continue
            dist_km = _haversine_km(event_coords[0], event_coords[1], lat_f, lon_f)
            if dist_km <= 30:
                item["_dist_km"] = dist_km
                filtered.append(item)

        if not filtered:
            filtered = items[:10]

        state.attractions = filtered[:10]

        lines = [
            f"Here are a few attractions near **{state.selected_event.location}**:",
            ""
        ]
        for i, item in enumerate(state.attractions, 1):
            name = item.get("name") or "Attraction"
            address = item.get("address") or ""
            county = item.get("county") or ""
            where = ", ".join([p for p in [address, county] if p])
            dist_km = item.get("_dist_km")
            dist_txt = f" ({dist_km:.1f} km)" if dist_km is not None else ""
            lines.append(f"{i}. **{name}** — {where}{dist_txt}".strip())

        state.response = "\n".join(lines)
        return state

    except Exception as e:
        logger.error(f"Error in attraction_search: {e}")
        state.response = f"❌ Error finding attractions: {e}"
        return state


def attraction_selection(state: AgentState, llm: Any) -> AgentState:
    """
    Select an attraction by number or name and plan route from current origin to it.
    """
    try:
        if not state.attractions:
            state.response = "Please ask for attractions first, then pick a number or name."
            return state

        raw = (state.last_user_input or "").strip()
        idx = None
        try:
            idx = int(raw) - 1
        except Exception:
            raw_lower = raw.lower()
            for i, item in enumerate(state.attractions):
                name = str(item.get("name") or "").lower()
                if name and (name in raw_lower or raw_lower in name):
                    idx = i
                    break

        if idx is None:
            state.response = "Please choose an attraction number or name from the list."
            return state
        if idx < 0 or idx >= len(state.attractions):
            state.response = "That number is out of range. Please pick a valid attraction number."
            return state

        selected = state.attractions[idx]
        lat = selected.get("latitude")
        lon = selected.get("longitude")
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            lat_f = None
            lon_f = None

        if lat_f is not None and lon_f is not None:
            state.destination = f"{lat_f},{lon_f}"
        else:
            address = ", ".join([p for p in [selected.get("address"), selected.get("county")] if p])
            state.destination = address or str(selected.get("name") or "")

        if not state.origin:
            state.response = f"Selected **{selected.get('name') or 'attraction'}**. Where are you starting from?"
            state.intent = "AWAIT_ORIGIN"
            return state

        state = route_planner(state, llm)
        if state.planned_route and (not state.response or not state.response.strip()):
            state.response = _format_route_result(state.planned_route, "otp")
        return state

    except Exception as e:
        logger.error(f"Error in attraction_selection: {e}")
        state.response = f"❌ Error selecting attraction: {e}"
        return state


# ============================================================================
# NODE: Response Generator
# ============================================================================

def response_generator(state: AgentState, llm: Any) -> AgentState:
    """
    Generate a helpful conversational response.
    Uses LLM to enhance structured outputs.
    """
    try:
        # Always refresh suggested actions based on current state
        state.suggested_actions = _build_suggested_actions(state)

        # If response is already formatted, keep it
        if state.response:
            if state.response.startswith(("✅", "❌", "🚀")):
                return state
            # If response already exists and is not empty, keep it
            if len(state.response.strip()) > 0:
                return state
        
        # Otherwise, generate response based on state
        context = ""
        if state.planned_route:
            context = _format_route_result(state.planned_route)
        elif state.search_results:
            context = _format_event_results(state.search_results)
        
        if context:
            state.response = context
        else:
            # Default friendly response
            state.response = "👋 Hi! I'm your Dublin transport assistant. I can help you:\n\n" \
                           "1. 🎭 Find events happening around Dublin\n" \
                           "2. 🚌 Plan routes from any location\n" \
                           "3. ⏱️ Get travel times and transfer info\n\n" \
                           "Try asking: 'What events are happening this weekend?'"

    except Exception as e:
        logger.error(f"Error in response_generator: {e}")
        state.response = f"An error occurred: {e}"
    
    return state


# ============================================================================
# CONDITIONAL EDGE: Route to Next Node
# ============================================================================

def route_to_next_node(state: AgentState) -> Literal["event_search", "event_selection_handler", "route_planner", "accommodation_search", "accommodation_selection", "attraction_search", "attraction_selection", "response_generator"]:
    """
    Route to the appropriate next node based on intent and context.
    """
    if state.intent == "EVENT_DISCOVERY":
        return "event_search"
    elif state.intent == "EVENT_SELECTION":
        return "event_selection_handler"
    elif state.intent in ["ROUTE_PLANNING", "AWAIT_ORIGIN", "ORIGIN_PROVIDED"]:
        return "route_planner"
    elif state.intent == "ACCOMMODATION":
        return "accommodation_search"
    elif state.intent == "ACCOMMODATION_SELECT":
        return "accommodation_selection"
    elif state.intent == "ATTRACTION":
        return "attraction_search"
    elif state.intent == "ATTRACTION_SELECT":
        return "attraction_selection"
    else:
        return "response_generator"


# ============================================================================
# CONDITIONAL EDGE: Should Continue?
# ============================================================================

def should_continue_after_event_select(state: AgentState) -> Literal["__end__", "await_origin"]:
    """
    Check if we should wait for origin after event selection.
    """
    if state.intent == "AWAIT_ORIGIN" and not state.origin:
        return "await_origin"
    return "__end__"


# ============================================================================
# BUILD GRAPH
# ============================================================================

def build_graph(llm: Any) -> tuple:
    """
    Build the LangGraph state machine.
    
    Returns:
        (graph, app) where app is the compiled runnable
    """
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Create nodes - bind LLM to each node
    def intent_classifier_node(state: AgentState) -> AgentState:
        return intent_classifier(state, llm)
    
    def event_search_node(state: AgentState) -> AgentState:
        return event_search(state, llm)
    
    def event_selection_node(state: AgentState) -> AgentState:
        return event_selection_handler(state, llm)
    
    def route_planner_node(state: AgentState) -> AgentState:
        return route_planner(state, llm)
    def accommodation_search_node(state: AgentState) -> AgentState:
        return accommodation_search(state, llm)
    def accommodation_selection_node(state: AgentState) -> AgentState:
        return accommodation_selection(state, llm)
    def attraction_search_node(state: AgentState) -> AgentState:
        return attraction_search(state, llm)
    def attraction_selection_node(state: AgentState) -> AgentState:
        return attraction_selection(state, llm)
    
    def response_generator_node(state: AgentState) -> AgentState:
        return response_generator(state, llm)
    
    # Add nodes
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("event_search", event_search_node)
    workflow.add_node("event_selection_handler", event_selection_node)
    workflow.add_node("route_planner", route_planner_node)
    workflow.add_node("accommodation_search", accommodation_search_node)
    workflow.add_node("accommodation_selection", accommodation_selection_node)
    workflow.add_node("attraction_search", attraction_search_node)
    workflow.add_node("attraction_selection", attraction_selection_node)
    workflow.add_node("response_generator", response_generator_node)
    
    # Set entry point
    workflow.set_entry_point("intent_classifier")
    
    # Add edges
    workflow.add_conditional_edges(
        "intent_classifier",
        route_to_next_node,
        {
            "event_search": "event_search",
            "event_selection_handler": "event_selection_handler",
            "route_planner": "route_planner",
            "accommodation_search": "accommodation_search",
            "accommodation_selection": "accommodation_selection",
            "attraction_search": "attraction_search",
            "attraction_selection": "attraction_selection",
            "response_generator": "response_generator"
        }
    )
    
    # Events → Response
    workflow.add_edge("event_search", "response_generator")
    
    # Selection → Response (will ask for origin)
    workflow.add_edge("event_selection_handler", "response_generator")
    
    # Route → Response
    workflow.add_edge("route_planner", "response_generator")
    workflow.add_edge("accommodation_search", "response_generator")
    workflow.add_edge("accommodation_selection", "response_generator")
    workflow.add_edge("attraction_search", "response_generator")
    workflow.add_edge("attraction_selection", "response_generator")
    
    # Response → End
    workflow.add_edge("response_generator", END)
    
    # Compile
    app = workflow.compile()
    
    return workflow, app


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_event_results(events: list[Event]) -> str:
    """Format event search results for display."""
    if not events:
        return "No events found."

    lines = ["Here are a few events you can choose from:", ""]
    for i, event in enumerate(events, 1):
        lines.append(f"{i}. **{event.name}**")
        lines.append(f"   Location: {event.location} | Time: {event.datetime}")

    lines.append("")
    lines.append("Tell me the event number or name and I'll plan the route.")

    return "\n".join(lines)



def _format_route_result(route: Route, source: str | None = None) -> str:
    """Format a route for display."""
    tag = ""
    if source == "otp":
        tag = " (OTP)"
    elif source == "llm":
        tag = " (LLM)"
    service_line = ""
    if route.service_types:
        service_line = f"Service: **{', '.join(route.service_types)}**"
    debug_line = f"Map debug: **{route.route_debug}**" if route.route_debug else None
    lines = [
        f"Here's a route that should work well{tag}:",
        f"Travel time: **{route.travel_time:.0f} min**",
        f"Walking: **{route.walking_time:.0f} min**",
        f"Transfers: **{route.transfers}**",
        service_line if service_line else None,
        debug_line,
        f"Leave at **{route.departure}** -> Arrive **{route.arrival}**",
        "",
        "Steps:",
    ]
    lines = [line for line in lines if line]

    for i, step in enumerate(route.steps, 1):
        lines.append(f"{i}. {step}")

    return "\n".join(lines)


def _get_example_stops() -> list[str]:
    """Get a list of example stop names for suggestions."""
    try:
        import pandas as pd
        stops_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data/clean/stops.csv")
        stops_df = pd.read_csv(stops_path)
        preferred = [
            "Merrion Square",
            "O'Connell Street",
            "Heuston Station",
            "Connolly Station",
            "St Stephen's Green",
            "Park West",
            "Tallaght",
            "Dundrum",
        ]
        available = {str(s).strip() for s in stops_df["stop_name"].dropna().unique() if len(str(s).strip()) > 3}
        picks = [name for name in preferred if name in available]
        if len(picks) >= 4:
            return picks[:5]
        fallback = sorted([s for s in available if any(token in s.lower() for token in ("dublin", "connolly", "heuston", "green", "square", "park west"))])
        merged = []
        for name in picks + fallback:
            if name not in merged:
                merged.append(name)
        return merged[:5] if merged else preferred[:5]
    except Exception as e:
        logger.warning(f"Could not load example stops: {e}")
        return ["Merrion Square", "O'Connell Street", "Heuston Station", "Connolly Station"]


def _extract_event_selection(user_input: str, events: list[Event]) -> Optional[int]:
    """
    Extract event selection (number or name) from user input.
    Returns the index of the selected event or None.
    """
    user_input_lower = user_input.lower()
    # If the user pasted the full line with separators, keep it intact for matching
    raw_clean = re.sub(r"\s+", " ", user_input_lower).strip()
    user_clean = re.sub(r"[^a-z0-9 ]+", " ", user_input_lower).strip()
    user_clean = re.sub(r"\s+", " ", user_clean)
    
    # Try to match by number (only if the input starts with a list index like "1" or "1.")
    num_match = re.match(r'^\s*(\d+)(?:[\).\s-].*)?$', user_input.strip())
    if num_match:
        try:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(events):
                return idx
        except ValueError:
            pass
    
    # Try to match by event name/location/date
    best_idx = None
    best_score = 0
    best_ratio = 0.0
    for i, event in enumerate(events):
        name_clean = re.sub(r"[^a-z0-9 ]+", " ", event.name.lower()).strip()
        name_clean = re.sub(r"\s+", " ", name_clean)
        loc_clean = re.sub(r"[^a-z0-9 ]+", " ", str(event.location).lower()).strip()
        loc_clean = re.sub(r"\s+", " ", loc_clean)
        date_clean = re.sub(r"[^0-9-]+", " ", str(event.datetime)).strip()
        combined = f"{name_clean} {loc_clean} {date_clean}".strip()
        # Strong name match: all name tokens present in user input
        name_tokens = [t for t in name_clean.split() if len(t) > 2]
        user_tokens = set(user_clean.split())
        if name_tokens and all(t in user_tokens for t in name_tokens):
            return i
        # Full-line match (name + location + date)
        if raw_clean and (raw_clean in combined or combined in raw_clean):
            return i
        if loc_clean and (loc_clean in user_clean or user_clean in loc_clean):
            # Only accept direct location match if name isn't strongly mismatched
            if name_clean in user_clean or user_clean in name_clean or len(user_clean.split()) <= 3:
                return i
        if name_clean in user_clean or user_clean in name_clean:
            return i
        # token overlap scoring
        tokens_user = set(user_clean.split())
        tokens_event = set(combined.split())
        score = len(tokens_user & tokens_event)
        if score > best_score:
            best_score = score
            best_idx = i
        try:
            import difflib
            ratio = difflib.SequenceMatcher(None, user_clean, combined).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                if ratio >= 0.55:
                    best_idx = i
        except Exception:
            pass

    if best_idx is not None and (best_score >= 2 or best_ratio >= 0.55):
        return best_idx

    return None


def _is_coordinates(location: str) -> bool:
    """Check if a location string is in lat,lon format."""
    try:
        parts = location.split(",")
        if len(parts) == 2:
            float(parts[0])
            float(parts[1])
            return True
        return False
    except (ValueError, IndexError):
        return False


def _build_suggested_actions(state: AgentState) -> list[dict]:
    actions: list[dict] = []
    event = state.selected_event
    if event:
        location = event.location or "the event"
        actions.append({
            "id": "route",
            "label": f"🧭 Route to {location}",
            "command": "Plan the route to the selected event."
        })
        actions.append({
            "id": "stay",
            "label": f"🏨 Stays near {location}",
            "command": "Find accommodations near the selected event."
        })
        actions.append({
            "id": "attractions",
            "label": f"📍 Things to do near {location}",
            "command": "Show attractions near the selected event."
        })
    elif state.search_results:
        actions.append({
            "id": "select",
            "label": "Pick an event",
            "command": "Select event 1."
        })
    return actions
