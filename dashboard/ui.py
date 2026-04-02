"""
Dublin Transport Intelligence - Clean Compact UI
Optimized for minimal scrolling + better UX
"""

import streamlit as st
import html


# ---------------------------------------------------
# BASE STYLES (CLEAN + COMPACT)
# ---------------------------------------------------

def apply_base_styles():
    st.markdown("""
    <style>
    :root {
        --primary: #4f46e5;
        --bg-dark: #0f172a;
        --bg-card: #1e293b;
        --text-primary: #f1f5f9;
        --text-secondary: #cbd5e1;
        --border: #334155;
    }

    html, body, [class*="st-"] {
        background-color: var(--bg-dark) !important;
        color: var(--text-primary);
        font-family: system-ui;
    }

    .block-container {
        padding: 1rem 2rem !important;
        max-width: 100% !important;
    }

    /* Header */
    .header {
        font-size: 20px;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 10px;
    }

    /* Compact Metrics */
    .metrics {
        display: flex;
        gap: 10px;
        margin-bottom: 10px;
    }

    .metric {
        background: var(--bg-card);
        padding: 10px;
        border-radius: 6px;
        text-align: center;
        flex: 1;
    }

    .metric-label {
        font-size: 10px;
        color: var(--text-secondary);
    }

    .metric-value {
        font-size: 16px;
        font-weight: bold;
        color: var(--primary);
    }

    /* Steps */
    .step {
        background: var(--bg-card);
        padding: 8px;
        border-radius: 5px;
        margin-bottom: 6px;
        font-size: 13px;
        border-left: 3px solid var(--primary);
    }

    /* Buttons */
    .stButton > button {
        background: var(--primary) !important;
        color: white !important;
        border-radius: 6px !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------
# HEADER
# ---------------------------------------------------

def render_header():
    st.markdown('<div class="header">🚌 Dublin Transport Intelligence</div>', unsafe_allow_html=True)


# ---------------------------------------------------
# INPUT BAR (TOP)
# ---------------------------------------------------

def render_inputs():
    from datetime import time

    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1.5])

    with col1:
        origin = st.text_input("From", placeholder="Ranelagh")

    with col2:
        destination = st.text_input("To", placeholder="Croke Park")

    with col3:
        date = st.date_input("Date")

    with col4:
        time_val = st.time_input("Time", value=time(9, 0))

    with col5:
        preference = st.selectbox(
            "Optimize",
            ["Balanced", "Fastest", "Least walking", "Fewest transfers"]
        )

    search = st.button("Search Route", use_container_width=True)

    return origin, destination, date, time_val, preference, search


# ---------------------------------------------------
# SUMMARY TAB
# ---------------------------------------------------

def render_summary(travel_time, walking_time, transfers, departure, crowding):

    st.markdown('<div class="metrics">', unsafe_allow_html=True)

    def metric(label, value):
        st.markdown(f"""
        <div class="metric">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """, unsafe_allow_html=True)

    metric("Time", f"{travel_time:.0f}m")
    metric("Walk", f"{walking_time:.0f}m")
    metric("Transfers", transfers)

    st.markdown('</div>', unsafe_allow_html=True)

    st.write(f"🕒 Leave at: **{departure}**")
    st.write(f"🧍 Crowd: **{crowding}**")


# ---------------------------------------------------
# DIRECTIONS TAB
# ---------------------------------------------------

def render_directions(steps):

    if not steps:
        st.info("No directions available")
        return

    show_all = st.checkbox("Show full route")

    display_steps = steps if show_all else steps[:5]

    for i, step in enumerate(display_steps, 1):
        st.markdown(f"""
        <div class="step">
            <strong>{i}.</strong> {html.escape(str(step))}
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------
# ALTERNATIVES TAB
# ---------------------------------------------------

def render_alternatives(alternatives):

    if len(alternatives) <= 1:
        st.info("No alternatives available")
        return

    for i, alt in enumerate(alternatives):

        m = alt.get("metrics", {})

        st.markdown(f"""
        <div class="metric">
            Route {i+1} → {m.get('travel_time_min',0):.0f}m | Walk {m.get('walking_time_min',0):.0f}m
        </div>
        """, unsafe_allow_html=True)

        if st.button(f"Select Route {i+1}", key=f"alt{i}"):
            st.session_state.selected_route = i
            st.rerun()


# ---------------------------------------------------
# MAIN DETAILS PANEL (TABS)
# ---------------------------------------------------

def render_details(travel_time, walking_time, transfers, departure, crowding, steps, alternatives):

    tab1, tab2, tab3 = st.tabs(["📊 Summary", "🧭 Directions", "🔁 Routes"])

    with tab1:
        render_summary(travel_time, walking_time, transfers, departure, crowding)

    with tab2:
        render_directions(steps)

    with tab3:
        render_alternatives(alternatives)


# ---------------------------------------------------
# EMPTY STATE
# ---------------------------------------------------

def render_empty():
    st.info("Enter locations and click 'Search Route'")


# ---------------------------------------------------
# MAIN APP LAYOUT
# ---------------------------------------------------

def render_app(map_component, route_data=None):

    apply_base_styles()
    render_header()

    origin, destination, date, time_val, pref, search = render_inputs()

    # Layout: MAP LEFT + DETAILS RIGHT
    col_map, col_details = st.columns([2, 1])

    with col_map:
        st.subheader("Map")
        map_component()

    with col_details:

        if route_data:
            render_details(
                route_data["travel_time"],
                route_data["walking_time"],
                route_data["transfers"],
                route_data["departure"],
                route_data.get("crowding", "Medium"),
                route_data.get("steps", []),
                route_data.get("alternatives", [])
            )
        else:
            render_empty()

    return origin, destination, date, time_val, pref, search