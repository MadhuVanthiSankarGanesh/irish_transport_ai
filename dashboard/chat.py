"""
Streamlit chat interface for the AI travel planning agent.
Provides a conversational interface for event discovery and route planning.
"""

import os
import sys
import subprocess
import json
import folium
from streamlit_folium import st_folium
import streamlit as st
import requests
from datetime import datetime
import traceback
import csv
import html

# Add src to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Import agent components
from src.llm.agent_runner import create_agent
from src.llm.state import create_initial_state
from src.graph.otp_manager import graph_age_hours, otp_server_running
from src.llm.tools import geocode_cached, _shape_points_for_leg
from src.llm.tool_gateway import get_walk_path_tool

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai" if os.getenv("OPENAI_API_KEY") else "ollama").strip().lower()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

ChatOpenAI = None
Ollama = None
if LLM_PROVIDER == "openai":
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
        LLM_AVAILABLE = True
    except ImportError:
        LLM_AVAILABLE = False
else:
    try:
        from langchain_ollama import OllamaLLM as Ollama  # type: ignore
        LLM_AVAILABLE = True
    except ImportError:
        try:
            from langchain_community.llms import Ollama  # type: ignore
            LLM_AVAILABLE = True
        except ImportError:
            LLM_AVAILABLE = False


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Dublin Smart Mobility Planner",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS
st.markdown("""
    <style>
        .chat-message {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            display: flex;
            gap: 1rem;
        }
        .user-message {
            background-color: #e3f2fd;
            flex-direction: row-reverse;
        }
        .assistant-message {
            background-color: #f5f5f5;
        }
        .event-card {
            border-left: 4px solid #1976d2;
            padding: 1rem;
            margin: 0.5rem 0;
            background-color: #fafafa;
            border-radius: 0.25rem;
        }
        .route-card {
            border-left: 4px solid #388e3c;
            padding: 1rem;
            margin: 0.5rem 0;
            background-color: #fafafa;
            border-radius: 0.25rem;
        }
        .action-panel {
            margin: 0.75rem 0 0.25rem 0;
            padding: 0.75rem;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 0.5rem;
        }
        .action-title {
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# INITIALIZATION
# ============================================================================

@st.cache_resource
def get_llm():
    """Initialize and cache LLM."""
    if not LLM_AVAILABLE:
        st.error("No compatible LLM client is installed for the selected provider.")
        return None

    try:
        if LLM_PROVIDER == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                st.warning("OPENAI_API_KEY not set. Please configure it.")
                return None
            return ChatOpenAI(model=OPENAI_MODEL, temperature=LLM_TEMPERATURE)
        return Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=LLM_TEMPERATURE)
    except Exception as e:
        st.error(f"Failed to initialize LLM: {e}")
        return None


@st.cache_resource
def get_agent(_llm):
    """Initialize and cache agent."""
    if _llm is None:
        return None
    try:
        return create_agent(_llm)
    except Exception as e:
        st.error(f"Failed to initialize agent: {e}")
        return None


# Initialize session state
if "agent" not in st.session_state:
    llm = get_llm()
    st.session_state.agent = get_agent(llm)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_state" not in st.session_state:
    st.session_state.agent_state = create_initial_state()


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_header():
    """Render page header."""
    col1, col2 = st.columns([1, 1])
    with col1:
        st.title("Dublin Smart Mobility Planner")
        st.markdown("Conversational event discovery and journey planning")
    with col2:
        st.info("""
        Quick Start:
        1. Ask about events (e.g., "What's happening this weekend?")
        2. Select an event
        3. Provide your starting location
        4. Get instant route planning
        """)


def render_chat_message(role: str, content: str):
    """Render a chat message."""
    if content is None:
        rendered_content = ""
    elif isinstance(content, str):
        rendered_content = content
    else:
        try:
            rendered_content = json.dumps(content, ensure_ascii=False, indent=2)
        except Exception:
            rendered_content = str(content)
    safe_content = html.escape(rendered_content).replace("\n", "<br>")
    chat_role = "user" if role == "user" else "assistant"
    with st.chat_message(chat_role):
        st.markdown(safe_content, unsafe_allow_html=True)


def render_conversation():
    """Render conversation history."""
    for msg in st.session_state.messages:
        render_chat_message(
            str(msg.get("role", "assistant")),
            msg.get("content", ""),
        )


def launch_otp_background(ttl_hours: float) -> None:
    """Spawn OTP build/load in a detached background process."""
    args = [
        sys.executable,
        "-m",
        "src.graph.otp_manager",
        "--ensure-and-serve",
        "--ttl-hours",
        str(int(ttl_hours)),
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def graphhopper_server_running() -> bool:
    base_url = os.getenv("GRAPHHOPPER_URL", "http://localhost:8989").rstrip("/")
    for url in (f"{base_url}/info", f"{base_url}/route?profile=foot&point=53.3498,-6.2603&point=53.3478,-6.2597"):
        try:
            resp = requests.get(url, timeout=3)
            if resp.ok:
                return True
        except Exception:
            continue
    return False


def render_sidebar():
    """Render sidebar with context."""
    with st.sidebar:
        st.header("Context")

        # Current event
        if st.session_state.agent_state.selected_event:
            st.subheader("Selected Event")
            event = st.session_state.agent_state.selected_event
            st.write(f"{event.name}")
            st.write(f"Location: {event.location}")
            st.write(f"Time: {event.datetime}")

            if st.button("Clear Event"):
                st.session_state.agent_state.selected_event = None
                st.rerun()

        # Current origin
        if st.session_state.agent_state.origin:
            st.subheader("Starting Location")
            st.write(f"{st.session_state.agent_state.origin}")

            if st.button("Clear Origin"):
                st.session_state.agent_state.origin = None
                st.rerun()

        # Travel preference
        st.subheader("Travel Preference")
        pref = st.radio(
            "Optimize for:",
            ["balanced", "fastest", "least_transfers"],
            index=0,
        )
        st.session_state.agent_state.travel_preference = pref

        # OTP server controls
        st.subheader("OTP Server")
        base_url = os.getenv("OTP_BASE_URL", "http://localhost:8080")
        graph_dir = os.getenv(
            "OTP_GRAPH_DIR",
            os.path.join(BASE_DIR, "otp", "graphs", "default"),
        )
        running = otp_server_running(base_url)
        st.write(f"Status: {'Running' if running else 'Not running'}")
        age_hours = graph_age_hours(graph_dir)
        if age_hours is None:
            st.write("Graph: missing")
        else:
            st.write(f"Graph age: {age_hours:.1f} hours")
        ttl_default = float(os.getenv("OTP_GRAPH_TTL_HOURS", "168"))
        ttl_hours = st.number_input(
            "Graph TTL (hours)",
            min_value=1,
            max_value=720,
            value=int(ttl_default),
            step=1,
        )
        st.caption("OTP will rebuild only if the graph is older than this TTL.")
        if st.button("Start OTP (build if stale)"):
            launch_otp_background(ttl_hours)
            st.success("Starting OTP in the background. It can take a minute to be ready.")

        st.subheader("Walk Router")
        gh_url = os.getenv("GRAPHHOPPER_URL", "http://localhost:8989")
        gh_running = graphhopper_server_running()
        st.write(f"GraphHopper: {'Running' if gh_running else 'Not running'}")
        st.caption(f"URL: {gh_url}")

        # Clear conversation
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            st.session_state.agent_state = create_initial_state()
            if st.session_state.agent:
                st.session_state.agent.reset()
            st.rerun()

        # Diagnostics
        with st.expander("GTFS/OTP Diagnostics"):
            if st.button("Check Dublin Express shapes"):
                st.session_state.gtfs_diag = run_gtfs_diag()
            diag = st.session_state.get("gtfs_diag")
            if diag:
                st.write(diag)


def render_action_panel() -> None:
    actions = st.session_state.agent_state.suggested_actions or []
    if not actions:
        return
    st.markdown(
        """
        <div class="action-panel">
            <div class="action-title">Suggested next actions</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(min(3, len(actions)))
    for idx, action in enumerate(actions):
        col = cols[idx % len(cols)]
        label = action.get("label") or "Action"
        command = action.get("command") or ""
        with col:
            if st.button(label, use_container_width=True):
                st.session_state.queued_input = command


def render_route_map() -> None:
    state = st.session_state.agent_state
    if not state.planned_route or not state.origin or not state.destination:
        return
    try:
        route_points = state.planned_route.route_points if state.planned_route else []
        stop_points = state.planned_route.stop_points if state.planned_route else []
        legs = state.planned_route.legs if state.planned_route else []
        if route_points:
            center_lat = sum(p[0] for p in route_points) / len(route_points)
            center_lon = sum(p[1] for p in route_points) / len(route_points)
            m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

            def leg_color(leg: dict) -> str:
                mode = (leg.get("mode") or "WALK").upper()
                if mode == "WALK":
                    return "#6b7280"
                if mode == "BUS":
                    return "#f59e0b"
                if mode in {"TRAM", "TRAMWAY"}:
                    route = leg.get("route") or {}
                    name = " ".join(
                        [
                            str(route.get("shortName") or ""),
                            str(route.get("longName") or ""),
                            str(leg.get("headsign") or ""),
                        ]
                    ).lower()
                    if "red" in name:
                        return "#e11d48"
                    if "green" in name:
                        return "#16a34a"
                    return "#10b981"
                if mode in {"RAIL", "TRAIN"}:
                    return "#1f2937"
                return "#6366f1"

            all_points = []
            walk_sources = []
            if legs:
                last_endpoint = None
                for idx, leg in enumerate(legs):
                    points = []
                    frm = leg.get("from") or {}
                    to = leg.get("to") or {}
                    frm_pt = (float(frm.get("lat")), float(frm.get("lon"))) if frm.get("lat") is not None and frm.get("lon") is not None else None
                    to_pt = (float(to.get("lat")), float(to.get("lon"))) if to.get("lat") is not None and to.get("lon") is not None else None
                    if frm_pt is None:
                        frm_pt = last_endpoint
                    if frm_pt is None and idx == 0:
                        frm_pt = geocode_cached(state.origin)
                    if to_pt is None and idx < len(legs) - 1:
                        nxt = legs[idx + 1].get("from") or {}
                        if nxt.get("lat") is not None and nxt.get("lon") is not None:
                            to_pt = (float(nxt.get("lat")), float(nxt.get("lon")))
                    if to_pt is None and idx == len(legs) - 1:
                        to_pt = geocode_cached(state.destination)
                    mode = (leg.get("mode") or "WALK").upper()
                    if mode == "WALK":
                        if frm_pt and to_pt:
                            walk_result = get_walk_path_tool(frm_pt[0], frm_pt[1], to_pt[0], to_pt[1])
                            if walk_result.get("success"):
                                points = walk_result.get("points") or []
                                walk_sources.append(walk_result.get("source") or "unknown")
                            else:
                                walk_sources.append("straight_fallback")
                    else:
                        route_info = leg.get("route") or {}
                        shape_pts = _shape_points_for_leg(
                            route_info.get("gtfsId"),
                            frm.get("name"),
                            to.get("name"),
                            frm.get("lat"),
                            frm.get("lon"),
                            to.get("lat"),
                            to.get("lon"),
                        )
                        if shape_pts:
                            points = shape_pts
                    if not points:
                        if frm_pt:
                            points.append(frm_pt)
                        for stop in leg.get("intermediateStops") or []:
                            if stop.get("lat") is not None and stop.get("lon") is not None:
                                points.append((float(stop.get("lat")), float(stop.get("lon"))))
                        if to_pt:
                            points.append(to_pt)
                    if len(points) >= 2:
                        dash = "6 6" if mode == "WALK" else None
                        weight = 4 if mode == "WALK" else 6
                        folium.PolyLine(points, color=leg_color(leg), weight=weight, opacity=0.9, dash_array=dash).add_to(m)
                        all_points.extend(points)
                        last_endpoint = points[-1]
            else:
                folium.PolyLine(route_points, color="#2563eb", weight=5, opacity=0.9).add_to(m)
                all_points = list(route_points)
            stop_markers = []
            if legs:
                transit_legs = [leg for leg in legs if (leg.get("mode") or "WALK").upper() != "WALK"]
                for idx, leg in enumerate(transit_legs):
                    color = leg_color(leg)
                    frm = leg.get("from") or {}
                    to = leg.get("to") or {}
                    if frm.get("lat") is not None and frm.get("lon") is not None:
                        stop_markers.append((float(frm.get("lat")), float(frm.get("lon")), color, "board"))
                    if idx < len(transit_legs) - 1 and to.get("lat") is not None and to.get("lon") is not None:
                        stop_markers.append((float(to.get("lat")), float(to.get("lon")), color, "transfer"))
                    elif to.get("lat") is not None and to.get("lon") is not None:
                        stop_markers.append((float(to.get("lat")), float(to.get("lon")), color, "alight"))
            elif stop_points:
                for lat, lon in stop_points:
                    stop_markers.append((lat, lon, "#b91c1c", "stop"))
            if stop_markers:
                seen = set()
                for lat, lon, color, marker_type in stop_markers:
                    key = (round(lat, 6), round(lon, 6), color, marker_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    radius = 4 if marker_type in {"board", "alight"} else 5
                    folium.CircleMarker(
                        location=(lat, lon),
                        radius=radius,
                        color="#ffffff",
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.95,
                        weight=2,
                        opacity=1.0,
                    ).add_to(m)
                st.caption(f"Stop markers: {len(seen)}")
            if walk_sources:
                st.caption(f"Walk router: {', '.join(walk_sources)}")
            if route_points:
                folium.Marker(route_points[0], popup="Start", icon=folium.Icon(color="green")).add_to(m)
                folium.Marker(route_points[-1], popup="Destination", icon=folium.Icon(color="red")).add_to(m)
            if all_points:
                m.fit_bounds(all_points)
            else:
                m.fit_bounds(route_points)
            st_folium(m, height=400, width=None)
            if state.planned_route and state.planned_route.route_debug:
                st.caption(f"Route debug: {state.planned_route.route_debug}")
            return
        origin_coords = geocode_cached(state.origin)
        dest_coords = geocode_cached(state.destination)
        if not origin_coords or not dest_coords:
            return
        center_lat = (origin_coords[0] + dest_coords[0]) / 2
        center_lon = (origin_coords[1] + dest_coords[1]) / 2
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
        folium.Marker(origin_coords, popup="Start", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(dest_coords, popup="Destination", icon=folium.Icon(color="red")).add_to(m)
        folium.PolyLine([origin_coords, dest_coords], color="#2563eb", weight=5, opacity=0.9).add_to(m)
        m.fit_bounds([origin_coords, dest_coords])
        st_folium(m, height=400, width=None)
        if state.planned_route and state.planned_route.route_debug:
            st.caption(f"Route debug: {state.planned_route.route_debug}")
    except Exception as e:
        st.warning(f"Map rendering error: {e}")


def run_gtfs_diag() -> dict:
    base = BASE_DIR
    candidates = [
        os.path.join(base, "data", "GTFS_All_extracted"),
        os.path.join(base, "otp", "graphs", "default", "GTFS_All_extracted"),
    ]
    folder = next((c for c in candidates if os.path.exists(c)), None)
    if not folder:
        return {"error": "GTFS_All_extracted folder not found"}
    routes_path = os.path.join(folder, "routes.txt")
    trips_path = os.path.join(folder, "trips.txt")
    shapes_path = os.path.join(folder, "shapes.txt")
    stop_times_path = os.path.join(folder, "stop_times.txt")

    diag = {
        "gtfs_folder": folder,
        "routes_exists": os.path.exists(routes_path),
        "trips_exists": os.path.exists(trips_path),
        "shapes_exists": os.path.exists(shapes_path),
        "stop_times_exists": os.path.exists(stop_times_path),
    }

    route_ids = set()
    if os.path.exists(routes_path):
        with open(routes_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                short_name = (row.get("route_short_name") or "").strip()
                long_name = (row.get("route_long_name") or "").strip().lower()
                if short_name == "783" or "dublin express" in long_name:
                    route_ids.add(row.get("route_id"))
        diag["dublin_express_route_ids"] = list(route_ids)

    trip_count = 0
    trip_with_shape = 0
    if route_ids and os.path.exists(trips_path):
        with open(trips_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("route_id") in route_ids:
                    trip_count += 1
                    if row.get("shape_id"):
                        trip_with_shape += 1
    diag["dublin_express_trips"] = trip_count
    diag["dublin_express_trips_with_shape"] = trip_with_shape

    if os.path.exists(shapes_path):
        try:
            with open(shapes_path, encoding="utf-8") as f:
                shape_lines = sum(1 for _ in f) - 1
            diag["shapes_rows"] = max(shape_lines, 0)
        except Exception:
            diag["shapes_rows"] = "error"

    return diag


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main app logic."""
    try:
        # Check LLM
        if st.session_state.agent is None:
            st.error("Agent not initialized. Please check LLM configuration.")
            return

        # Render header and sidebar
        render_header()
        render_sidebar()

        # Main chat area
        st.write("---")

        # Render conversation
        if st.session_state.messages:
            st.subheader("Conversation")
            render_conversation()
        else:
            st.info("Start a conversation below.")

        # Map for current route
        render_route_map()

        # Suggested actions at the bottom near input
        render_action_panel()

        # Chat input
        st.write("---")
        user_input = st.chat_input(
            "Ask about events or plan a trip...",
            key="chat_input",
        )

        queued = st.session_state.pop("queued_input", None)
        if queued and not user_input:
            user_input = queued

        if user_input:
            st.session_state.messages.append({
                "role": "user",
                "content": str(user_input),
            })

            with st.spinner("Processing..."):
                try:
                    state, response = st.session_state.agent.process_input(user_input)
                    st.session_state.agent_state = state
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response if isinstance(response, str) else str(response),
                    })
                except Exception as e:
                    error_msg = f"Error: {str(e)}\n\n``\n{traceback.format_exc()}\n```"
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                    })
                    st.error(error_msg)

            st.rerun()
    except Exception as e:
        st.error(f"Frontend render failed: {e}")
        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
