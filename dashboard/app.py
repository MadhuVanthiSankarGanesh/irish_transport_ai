import os
import pickle
import sys
from functools import lru_cache
import math
import heapq
import itertools
import time
import statistics
import joblib
import html

import folium
import networkx as nx
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from folium.plugins import TimestampedGeoJson
from sklearn.neighbors import KDTree
import requests
from google.transit import gtfs_realtime_pb2
from dotenv import load_dotenv
from ui import (
    apply_base_styles, render_header, render_inputs,
    render_summary, render_directions, render_details,
    render_alternatives, render_empty, render_app
)

st.set_page_config(
    page_title="Dublin Transport Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.agents.travel_assistant import travel_explanation

# Configure dark theme
st.markdown("""
    <script>
        var theme = {
            primaryColor: "#4f46e5",
            backgroundColor: "#0f172a",
            secondaryBackgroundColor: "#1e293b",
            textColor: "#f1f5f9",
            font: "Sora, sans-serif"
        };
    </script>
""", unsafe_allow_html=True)


# ---------------------------------------------------
# PATH SETUP
# ---------------------------------------------------

events_path = os.path.join(BASE_DIR, "data/features/event_demand.csv")
congestion_path = os.path.join(BASE_DIR, "data/features/realtime_congestion.csv")
vehicles_path = os.path.join(BASE_DIR, "data/realtime/vehicle_positions.csv")
vehicle_history_path = os.path.join(BASE_DIR, "data/realtime/vehicle_history.csv")
graph_path = os.path.join(BASE_DIR, "data/graph/transit_graph.gpickle")
stops_path = os.path.join(BASE_DIR, "data", "clean", "stops.csv")
trips_path = os.path.join(BASE_DIR, "data", "clean", "trips.csv")
routes_path = os.path.join(BASE_DIR, "data", "clean", "routes.csv")
shapes_path = os.path.join(BASE_DIR, "data", "clean", "shapes.csv")
stop_times_path = os.path.join(BASE_DIR, "data", "clean", "stop_times.csv")
gtfs_extracted_dir = os.path.join(BASE_DIR, "data", "GTFS_All_extracted")

MAX_STOP_TIMES = 200000


# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------

@st.cache_data
def load_data():

    try:
        events = pd.read_csv(events_path)
    except Exception:
        # Fallback for Windows parser issues
        events = pd.read_csv(events_path, engine="python", encoding_errors="replace")
    congestion = pd.read_csv(congestion_path)
    stops = pd.read_csv(stops_path)
    trips = pd.read_csv(trips_path)
    routes = pd.read_csv(routes_path)
    stop_times = None
    if os.path.exists(stop_times_path):
        stop_times = pd.read_csv(
            stop_times_path,
            usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
        )
    shapes = None
    if os.path.exists(shapes_path):
        shapes = pd.read_csv(shapes_path)

    gtfs = {"stops": None, "trips": None, "routes": None, "stop_times": None, "shapes": None}
    if os.path.exists(gtfs_extracted_dir):
        try:
            gtfs["stops"] = pd.read_csv(os.path.join(gtfs_extracted_dir, "stops.txt"))
            gtfs["trips"] = pd.read_csv(os.path.join(gtfs_extracted_dir, "trips.txt"))
            gtfs["routes"] = pd.read_csv(os.path.join(gtfs_extracted_dir, "routes.txt"))
            gtfs["stop_times"] = pd.read_csv(
                os.path.join(gtfs_extracted_dir, "stop_times.txt"),
                usecols=["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time", "shape_dist_traveled"],
                low_memory=False,
            )
            gtfs["shapes"] = pd.read_csv(os.path.join(gtfs_extracted_dir, "shapes.txt"))
        except Exception:
            pass

    return events, congestion, stops, trips, routes, stop_times, shapes, gtfs


@st.cache_data
def load_vehicles():
    if os.path.exists(vehicle_history_path):
        return pd.read_csv(vehicle_history_path)
    return pd.read_csv(vehicles_path)


GRAPH_VERSION = "v2_time_weights"

@st.cache_resource
def load_graph(_version):

    with open(graph_path, "rb") as f:
        # NetworkX 3 removed gpickle helpers; use pickle directly.
        return pickle.load(f)


events, congestion, stops, trips, routes, stop_times, shapes, gtfs = load_data()

G = load_graph(GRAPH_VERSION)

# ---------------------------------------------------
# DEMAND + CROWDING SETUP
# ---------------------------------------------------

@st.cache_resource
def load_demand_model():
    model_path = os.path.join(BASE_DIR, "data", "models", "demand_predictor.pkl")
    if not os.path.exists(model_path):
        return None
    try:
        return joblib.load(model_path)
    except Exception:
        return None


def build_stop_name_lookup(stops_df):
    lookup = {}
    for _, row in stops_df.iterrows():
        name = str(row.get("stop_name", "")).strip().lower()
        stop_id = row.get("stop_id")
        if name and stop_id:
            lookup.setdefault(name, stop_id)
    return lookup


def build_stop_name_to_code(stops_df):
    lookup = {}
    for _, row in stops_df.iterrows():
        name = str(row.get("stop_name", "")).strip().lower()
        code = row.get("stop_code")
        if name and pd.notna(code):
            lookup.setdefault(name, str(code))
    return lookup


def normalize_score(value, max_value):
    if value is None or max_value in (None, 0):
        return 0.0
    return max(0.0, min(float(value) / float(max_value), 1.0))


def crowd_label(score_norm):
    if score_norm >= 0.7:
        return "Crowded"
    if score_norm >= 0.4:
        return "Moderate"
    return "Low"


def extract_stop_ids_from_legs(legs, stop_name_to_id):
    stop_ids = []
    for leg in legs:
        from_name = (leg.get("from", {}) or {}).get("name")
        to_name = (leg.get("to", {}) or {}).get("name")
        for name in [from_name, to_name]:
            if not name:
                continue
            stop_id = stop_name_to_id.get(str(name).strip().lower())
            if stop_id:
                stop_ids.append(stop_id)
    return list(dict.fromkeys(stop_ids))


def compute_crowd_score(stop_ids, event_dt, demand_model, events_df, congestion_df):
    if not stop_ids:
        return 0.0, "Low"

    event_score = None
    if "start_date_dt" in events_df.columns and "end_date_dt" in events_df.columns:
        active_events = events_df[
            (events_df["start_date_dt"] <= event_dt.date()) & (events_df["end_date_dt"] >= event_dt.date())
        ]
        active_events = active_events[active_events["stop_id"].isin(stop_ids)]
        if not active_events.empty and "demand_score" in active_events.columns:
            event_score = active_events["demand_score"].median()

    congestion_score = None
    if "congestion_score" in congestion_df.columns:
        match = congestion_df[congestion_df["stop_id"].isin(stop_ids)]
        if not match.empty:
            congestion_score = match["congestion_score"].median()

    event_norm = normalize_score(event_score, EVENT_DEMAND_MAX)
    congestion_norm = normalize_score(congestion_score, CONGESTION_MAX)

    model_norm = 0.0
    if demand_model is not None:
        try:
            base = pd.DataFrame({"stop_id": stop_ids})
            base = base.merge(
                events_df[["stop_id", "demand_score", "estimated_passengers", "distance_weight"]],
                on="stop_id",
                how="left",
            )
            base = base.merge(
                congestion_df[["stop_id", "congestion_score", "vehicle_count"]],
                on="stop_id",
                how="left",
            )
            base = base.fillna(0.0)
            if hasattr(demand_model, "feature_names_in_"):
                features = [f for f in demand_model.feature_names_in_ if f in base.columns]
                if features:
                    preds = demand_model.predict(base[features])
                    pred_score = float(pd.Series(preds).median())
                    model_norm = normalize_score(pred_score, EVENT_DEMAND_MAX or 1.0)
        except Exception:
            model_norm = 0.0

    crowd_norm = 0.5 * model_norm + 0.3 * event_norm + 0.2 * congestion_norm
    return crowd_norm, crowd_label(crowd_norm)


def summarize_itinerary(legs, duration_sec):
    walk_sec = 0.0
    transit_legs = 0
    for leg in legs:
        mode = leg.get("mode", "WALK")
        if mode == "WALK":
            walk_sec += float(leg.get("duration", 0) or 0.0)
        else:
            transit_legs += 1
    transfers = max(transit_legs - 1, 0)
    return {
        "travel_time_min": (duration_sec or 0) / 60.0,
        "walking_time_min": walk_sec / 60.0,
        "transfers": transfers,
    }


def build_steps_from_otp_legs(legs, stop_name_to_code_map):
    steps = []
    for leg in legs:
        mode = leg.get("mode", "WALK")
        from_name = (leg.get("from", {}) or {}).get("name", "start")
        to_name = (leg.get("to", {}) or {}).get("name", "end")
        duration = leg.get("duration", 0)
        if mode == "WALK":
            to_code = stop_name_to_code_map.get(str(to_name).strip().lower())
            suffix = f" (Stop ID: {to_code})" if to_code else ""
            steps.append(f"Walk {format_minutes(duration)} to {to_name}{suffix}")
        else:
            route = None
            route_obj = leg.get("route") or {}
            route = route_obj.get("shortName") or route_obj.get("longName")
            route = route or leg.get("routeShortName") or leg.get("routeLongName") or "Transit"
            headsign = leg.get("headsign")
            if headsign:
                route = f"{route} → {headsign}"
            from_code = stop_name_to_code_map.get(str(from_name).strip().lower())
            to_code = stop_name_to_code_map.get(str(to_name).strip().lower())
            from_suffix = f" (Stop ID: {from_code})" if from_code else ""
            to_suffix = f" (Stop ID: {to_code})" if to_code else ""
            steps.append(f"{mode.title()} {route} -> {from_name}{from_suffix} to {to_name}{to_suffix}")
    return steps


def extract_leg_stop_list(leg):
    stops = []
    for stop in leg.get("intermediateStops", []) or []:
        name = stop.get("name")
        if name:
            stops.append(name)
    return stops


def _coords_for_stop_name(stop_name, stop_name_to_id_map, stops_df):
    if not stop_name:
        return None
    stop_id = stop_name_to_id_map.get(str(stop_name).strip().lower())
    if not stop_id:
        return None
    row = stops_df[stops_df["stop_id"] == stop_id]
    if row.empty:
        return None
    return (float(row.iloc[0]["stop_lat"]), float(row.iloc[0]["stop_lon"]))


def _coords_for_stop_obj(stop_obj, stop_name_to_id_map, stops_df):
    if not stop_obj:
        return None
    stop_id = stop_obj.get("stopId") or stop_obj.get("gtfsId") or stop_obj.get("id")
    if stop_id:
        stop_id = str(stop_id).split(":")[-1]
        row = stops_df[stops_df["stop_id"] == stop_id]
        if not row.empty:
            return (float(row.iloc[0]["stop_lat"]), float(row.iloc[0]["stop_lon"]))
    name = stop_obj.get("name")
    return _coords_for_stop_name(name, stop_name_to_id_map, stops_df)


def _shape_points_for_leg(route_gtfs_id, from_stop_obj, to_stop_obj, stops_df, trips_df, stop_times_df, shapes_df, stop_name_to_id_map):
    if not route_gtfs_id or trips_df is None or stop_times_df is None or shapes_df is None:
        return None
    if trips_df.empty or stop_times_df.empty or shapes_df.empty:
        return None
    route_id = str(route_gtfs_id).split(":")[-1]
    from_id = None
    to_id = None
    if from_stop_obj:
        from_id = str((from_stop_obj.get("stopId") or from_stop_obj.get("gtfsId") or "")).split(":")[-1] or None
    if to_stop_obj:
        to_id = str((to_stop_obj.get("stopId") or to_stop_obj.get("gtfsId") or "")).split(":")[-1] or None
    from_coords = _coords_for_stop_obj(from_stop_obj, stop_name_to_id_map, stops_df)
    to_coords = _coords_for_stop_obj(to_stop_obj, stop_name_to_id_map, stops_df)

    trip_ids = trips_df[trips_df["route_id"].astype(str) == route_id]["trip_id"].astype(str).tolist()
    if not trip_ids:
        return None

    def slice_by_nearest(shp, start, end):
        if shp is None or shp.empty or not start or not end:
            return None
        shp = shp.sort_values("shape_pt_sequence")
        pts = list(zip(shp["shape_pt_lat"].astype(float), shp["shape_pt_lon"].astype(float)))
        if len(pts) < 2:
            return None
        def nearest_idx(lat, lon):
            best_i = 0
            best_d = None
            for i, (plat, plon) in enumerate(pts):
                d = (plat - lat) ** 2 + (plon - lon) ** 2
                if best_d is None or d < best_d:
                    best_d = d
                    best_i = i
            return best_i
        i_from = nearest_idx(start[0], start[1])
        i_to = nearest_idx(end[0], end[1])
        if i_from > i_to:
            i_from, i_to = i_to, i_from
        return pts[i_from:i_to + 1]

    for trip_id in trip_ids[:200]:
        st = stop_times_df[stop_times_df["trip_id"].astype(str) == trip_id]
        if st.empty:
            continue
        st = st.sort_values("stop_sequence")
        stop_list = st["stop_id"].astype(str).tolist()
        idx_from = stop_list.index(from_id) if from_id in stop_list else None
        idx_to = stop_list.index(to_id) if to_id in stop_list else None
        if idx_from is not None and idx_to is not None and idx_from >= idx_to:
            continue
        trip_row = trips_df[trips_df["trip_id"].astype(str) == trip_id]
        if trip_row.empty:
            continue
        shape_id = str(trip_row.iloc[0].get("shape_id") or "")
        if not shape_id:
            continue
        shp = shapes_df[shapes_df["shape_id"].astype(str) == shape_id]
        if shp.empty:
            continue
        if idx_from is not None and idx_to is not None and "shape_dist_traveled" in st.columns and "shape_dist_traveled" in shp.columns:
            try:
                from_dist = float(st.iloc[idx_from]["shape_dist_traveled"])
                to_dist = float(st.iloc[idx_to]["shape_dist_traveled"])
                if to_dist < from_dist:
                    from_dist, to_dist = to_dist, from_dist
                shp = shp[(shp["shape_dist_traveled"] >= from_dist) & (shp["shape_dist_traveled"] <= to_dist)]
            except Exception:
                pass
        pts = list(zip(shp["shape_pt_lat"].astype(float), shp["shape_pt_lon"].astype(float)))
        if pts:
            return pts
        pts = slice_by_nearest(shp, from_coords, to_coords)
        if pts:
            return pts
    return None


def build_otp_route_coords(legs, stop_name_to_id_map, stops_df, origin_coords, dest_coords):
    coords = []
    if not legs:
        return coords

    def add_point(pt):
        if pt is None:
            return
        if not coords or coords[-1] != pt:
            coords.append(pt)

    last_idx = len(legs) - 1
    for idx, leg in enumerate(legs):
        mode = leg.get("mode", "WALK")
        from_name = (leg.get("from", {}) or {}).get("name")
        to_name = (leg.get("to", {}) or {}).get("name")

        start = _coords_for_stop_obj(leg.get("from", {}), stop_name_to_id_map, stops_df)
        end = _coords_for_stop_obj(leg.get("to", {}), stop_name_to_id_map, stops_df)

        if idx == 0 and origin_coords is not None:
            start = start or origin_coords
        if idx == last_idx and dest_coords is not None:
            end = end or dest_coords

        if mode != "WALK":
            add_point(start)
            for stop in leg.get("intermediateStops", []) or []:
                mid = _coords_for_stop_name(stop.get("name"), stop_name_to_id_map, stops_df)
                add_point(mid)
            add_point(end)
        else:
            add_point(start)
            add_point(end)

    return coords


def score_itinerary(metrics, crowd_norm, preference):
    travel = metrics["travel_time_min"]
    walking = metrics["walking_time_min"]
    transfers = metrics["transfers"]

    if preference == "Fastest":
        return travel
    if preference == "Least crowded":
        return travel + crowd_norm * 20 + transfers * 2
    if preference == "Fewest transfers":
        return travel + transfers * 10 + crowd_norm * 8
    if preference == "Least walking":
        return travel + walking * 2 + crowd_norm * 6
    # Balanced
    return travel + crowd_norm * 15 + transfers * 6 + walking * 0.5


def compute_leave_window(departure_dt, crowd_norm, transfers):
    window_minutes = min(20, max(6, 6 + crowd_norm * 8 + transfers * 2))
    start = departure_dt - timedelta(minutes=window_minutes / 2)
    end = departure_dt + timedelta(minutes=window_minutes / 2)
    return start, end


def detect_disruption(stop_ids, congestion_df, threshold):
    if not stop_ids or threshold is None:
        return False
    match = congestion_df[congestion_df["stop_id"].isin(stop_ids)]
    if match.empty:
        return False
    return float(match["congestion_score"].max()) >= threshold


def top_congestion_stop(stop_ids, congestion_df, stops_df):
    if not stop_ids:
        return None
    match = congestion_df[congestion_df["stop_id"].isin(stop_ids)]
    if match.empty:
        return None
    top_row = match.sort_values("congestion_score", ascending=False).iloc[0]
    stop_row = stops_df[stops_df["stop_id"] == top_row["stop_id"]]
    name = None
    if not stop_row.empty:
        name = stop_row.iloc[0].get("stop_name")
    return {
        "stop_id": top_row["stop_id"],
        "stop_name": name or str(top_row["stop_id"]),
        "score": top_row["congestion_score"],
    }


@st.cache_resource
def prep_demand_model():
    return load_demand_model()

@st.cache_resource
def prep_stop_lookups():
    return build_stop_name_lookup(stops), build_stop_name_to_code(stops)

@st.cache_resource
def prep_event_data():
    evt = events.copy()
    if "start_date" in evt.columns and "end_date" in evt.columns:
        evt["start_date_dt"] = pd.to_datetime(evt["start_date"], errors="coerce").dt.date
        evt["end_date_dt"] = pd.to_datetime(evt["end_date"], errors="coerce").dt.date
    return evt

@st.cache_resource
def prep_congestion_data():
    cong = congestion.copy()
    alert = float(cong["congestion_score"].quantile(0.85)) if "congestion_score" in cong.columns and not cong.empty else None
    return cong, alert

@st.cache_resource
def prep_data_on_load():
    """Pre-prepare all expensive data operations at startup"""
    stop_name_to_id_lookup = build_stop_name_lookup(stops)
    stop_name_to_code_lookup = build_stop_name_to_code(stops)
    gtfs_stop_name_to_id = build_stop_name_lookup(gtfs["stops"]) if gtfs.get("stops") is not None else {}
    demand_model_cached = load_demand_model()
    
    evt = events.copy()
    if "start_date" in evt.columns and "end_date" in evt.columns:
        evt["start_date_dt"] = pd.to_datetime(evt["start_date"], errors="coerce").dt.date
        evt["end_date_dt"] = pd.to_datetime(evt["end_date"], errors="coerce").dt.date
    
    event_demand_max = float(evt["demand_score"].max()) if "demand_score" in evt.columns else 1.0
    congestion_max = float(congestion["congestion_score"].max()) if "congestion_score" in congestion.columns else 1.0
    congestion_alert = (
        float(congestion["congestion_score"].quantile(0.85))
        if "congestion_score" in congestion.columns and not congestion.empty
        else None
    )
    
    return {
        "stop_name_to_id": stop_name_to_id_lookup,
        "stop_name_to_code": stop_name_to_code_lookup,
        "gtfs_stop_name_to_id": gtfs_stop_name_to_id,
        "demand_model": demand_model_cached,
        "event_demand_max": event_demand_max,
        "congestion_max": congestion_max,
        "congestion_alert": congestion_alert,
    }

data_cache = prep_data_on_load()
demand_model = data_cache["demand_model"]
stop_name_to_id = data_cache["stop_name_to_id"]
stop_name_to_code = data_cache["stop_name_to_code"]
gtfs_stop_name_to_id = data_cache["gtfs_stop_name_to_id"]
EVENT_DEMAND_MAX = data_cache["event_demand_max"]
CONGESTION_MAX = data_cache["congestion_max"]
CONGESTION_ALERT = data_cache["congestion_alert"]


# ---------------------------------------------------
# GEOLOCATION SETUP
# ---------------------------------------------------

geolocator = Nominatim(user_agent="ai_smart_mobility_planner", timeout=5)

tree = KDTree(stops[["stop_lat", "stop_lon"]].values)

@lru_cache(maxsize=500)
def osm_geocode(query):
    try:
        location = geolocator.geocode(
            query,
            exactly_one=True,
            country_codes="ie",
            addressdetails=True,
        )
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None


def place_to_coordinates(place):

    if not place:
        return None, None

    try:
        place = place.strip()
        query = f"{place}, Ireland"
        return osm_geocode(query)

    except Exception:
        pass

    return None, None


def search_places(searchterm):

    if not searchterm or len(searchterm) < 3:
        return []

    results = []

    try:
        locations = geolocator.geocode(
            searchterm,
            exactly_one=False,
            limit=5,
            country_codes="ie"
        )

        if locations:
            for loc in locations:
                results.append(f"{loc.address}|{loc.latitude}|{loc.longitude}")

    except Exception:
        pass

    return results


@lru_cache(maxsize=500)
def osm_reverse_geocode(lat, lon):
    try:
        location = geolocator.reverse(
            (lat, lon),
            exactly_one=True,
            addressdetails=True,
        )
        if not location:
            return None
        address = location.raw.get("address", {})
        for key in ["attraction", "amenity", "building", "historic", "tourism", "leisure", "shop", "road", "suburb"]:
            if key in address:
                return address[key]
        return location.address.split(",")[0] if location.address else None
    except Exception:
        return None


def nearest_stops(lat, lon, k=8):

    dist, ind = tree.query([[lat, lon]], k=k)

    results = []
    for idx in ind[0]:
        stop = stops.iloc[idx]
        results.append((stop["stop_id"], stop["stop_lat"], stop["stop_lon"]))

    return results


def build_mode_stop_sets(graph):
    luas = set()
    bus = set()
    for u, v, data in graph.edges(data=True):
        rt = data.get("route_type")
        if rt == 0:
            luas.add(u)
            luas.add(v)
        elif rt == 3:
            bus.add(u)
            bus.add(v)
    return luas, bus


def build_kdtree_for_stop_ids(stop_ids):
    subset = stops[stops["stop_id"].isin(stop_ids)].copy()
    if subset.empty:
        return None, subset
    coords = subset[["stop_lat", "stop_lon"]].values
    return KDTree(coords), subset


def collect_stop_points_from_legs(legs):
    points = []
    for leg in legs or []:
        mode = str(leg.get("mode", "")).upper()
        if mode == "WALK":
            continue
        frm = leg.get("from", {}) or {}
        to = leg.get("to", {}) or {}
        if frm.get("lat") is not None and frm.get("lon") is not None:
            points.append((float(frm.get("lat")), float(frm.get("lon"))))
        for stop in leg.get("intermediateStops") or []:
            if stop.get("lat") is not None and stop.get("lon") is not None:
                points.append((float(stop.get("lat")), float(stop.get("lon"))))
        if to.get("lat") is not None and to.get("lon") is not None:
            points.append((float(to.get("lat")), float(to.get("lon"))))
    seen = set()
    deduped = []
    for lat, lon in points:
        key = (round(lat, 6), round(lon, 6))
        if key not in seen:
            seen.add(key)
            deduped.append((lat, lon))
    return deduped


def nearest_stops_by_subset(lat, lon, subset_df, subset_tree, k):
    if subset_tree is None or subset_df.empty:
        return []
    _, ind = subset_tree.query([[lat, lon]], k=min(k, len(subset_df)))
    results = []
    for idx in ind[0]:
        stop = subset_df.iloc[idx]
        results.append((stop["stop_id"], stop["stop_lat"], stop["stop_lon"]))
    return results


def detect_vehicle_type(route_id):

    if route_id is None:
        return "bus"

    route = str(route_id).lower()

    if "green" in route or "red" in route:
        return "luas"

    if route.startswith("luas"):
        return "luas"

    return "bus"


def create_vehicle_animation(vehicles):

    features = []

    for _, row in vehicles.iterrows():

        trip_id = row.get("trip_id")
        trip_id_str = str(trip_id) if pd.notna(trip_id) else ""
        route_id_str = str(row.get("route_id", "")).strip()

        route_name = trip_to_route.get(trip_id_str)
        if not route_name and route_id_str:
            route_name = route_id_to_label.get(route_id_str)
        if not route_name and route_id_str:
            route_name = route_id_suffix_to_label.get(route_id_str)
        if not route_name and trip_id_str:
            trip_suffix = trip_id_str.split("_")[0]
            route_name = route_id_suffix_to_label.get(trip_suffix)

        vehicle_type = detect_vehicle_type(route_name or route_id_str)

        if vehicle_type == "bus":
            color = "blue"
        else:
            color = "green"

        timestamp = row.get("timestamp")
        if pd.isna(timestamp):
            continue

        if isinstance(timestamp, (int, float)):
            timestamp = datetime.utcfromtimestamp(timestamp).isoformat() + "Z"

        label = route_name or route_id_str or "Unknown"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    row["longitude"],
                    row["latitude"],
                ],
            },
            "properties": {
                "time": timestamp,
                "popup": f"{vehicle_type.title()} {label}",
                "icon": "circle",
                "iconstyle": {
                    "fillColor": color,
                    "fillOpacity": 0.9,
                    "stroke": True,
                    "radius": 5
                },
            },
        }

        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }


def create_vehicle_animation_for_mode(vehicles, mode_filter):
    if vehicles.empty:
        return {"type": "FeatureCollection", "features": []}

    features = []
    for _, row in vehicles.iterrows():
        trip_id = row.get("trip_id")
        trip_id_str = str(trip_id) if pd.notna(trip_id) else ""
        route_id_str = str(row.get("route_id", "")).strip()

        route_name = trip_to_route.get(trip_id_str)
        if not route_name and route_id_str:
            route_name = route_id_to_label.get(route_id_str)
        if not route_name and route_id_str:
            route_name = route_id_suffix_to_label.get(route_id_str)
        if not route_name and trip_id_str:
            trip_suffix = trip_id_str.split("_")[0]
            route_name = route_id_suffix_to_label.get(trip_suffix)

        vehicle_type = detect_vehicle_type(route_name or route_id_str)
        if mode_filter and vehicle_type != mode_filter:
            continue

        timestamp = row.get("timestamp")
        if pd.isna(timestamp):
            continue
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.utcfromtimestamp(timestamp).isoformat() + "Z"

        color = "blue" if vehicle_type == "bus" else "green"
        label = route_name or route_id_str or "Unknown"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    row["longitude"],
                    row["latitude"],
                ],
            },
            "properties": {
                "time": timestamp,
                "popup": f"{vehicle_type.title()} {label}",
                "icon": "circle",
                "iconstyle": {
                    "fillColor": color,
                    "fillOpacity": 0.9,
                    "stroke": True,
                    "radius": 5
                },
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def otp_discover_routers(base_url):

    base_url = base_url.rstrip("/")
    if base_url.lower().endswith("/otp"):
        base_url = base_url[:-4]
    headers = {"Accept": "application/json"}
    for prefix in ["", "/otp"]:
        url = f"{base_url}{prefix}/routers"
        try:
            resp = requests.get(url, timeout=15, headers=headers)
        except Exception:
            continue
        if not resp.ok:
            continue
        try:
            data = resp.json()
        except Exception:
            continue

        routers = []
        if isinstance(data, dict):
            if "routerInfo" in data and isinstance(data["routerInfo"], list):
                routers = [r.get("routerId") for r in data["routerInfo"] if isinstance(r, dict)]
            elif "routers" in data and isinstance(data["routers"], list):
                for r in data["routers"]:
                    if isinstance(r, dict):
                        routers.append(r.get("routerId") or r.get("id"))
                    else:
                        routers.append(str(r))
        elif isinstance(data, list):
            for r in data:
                if isinstance(r, dict):
                    routers.append(r.get("routerId") or r.get("id"))
                else:
                    routers.append(str(r))

        routers = [r for r in routers if r]
        if routers:
            return prefix, routers

    return None, []


def otp_plan(origin_coords, dest_coords, event_time):

    base_url = os.environ.get("OTP_BASE_URL", "http://localhost:8080")
    base_url = base_url.rstrip("/")
    base_prefix_override = ""
    if base_url.lower().endswith("/otp"):
        base_url = base_url[:-4]
        base_prefix_override = "/otp"
    desired_router = os.environ.get("OTP_ROUTER", "default")
    prefix, routers = otp_discover_routers(base_url)
    if routers:
        router = desired_router if desired_router in routers else routers[0]
    else:
        router = desired_router
    base_prefix = base_prefix_override or (prefix or "")
    url_candidates = [
        f"{base_url}{base_prefix}/routers/{router}/plan",
        f"{base_url}/otp/routers/{router}/plan",
        f"{base_url}/routers/{router}/plan",
    ]

    date_str, time_str = event_time.split(" ")
    params = {
        "fromPlace": f"{origin_coords[0]},{origin_coords[1]}",
        "toPlace": f"{dest_coords[0]},{dest_coords[1]}",
        "date": date_str,
        "time": time_str,
        "mode": "WALK,TRANSIT",
        "numItineraries": 5,
        "showIntermediateStops": "true",
        "additionalFields": "legGeometry",
    }

    last_error = None
    response = None
    used_url = None
    headers = {"Accept": "application/json"}
    for url in url_candidates:
        try:
            response = requests.get(url, params=params, timeout=30, headers=headers)
        except requests.exceptions.ReadTimeout:
            last_error = "OTP request timed out"
            continue
        except Exception as exc:
            last_error = f"OTP request error: {exc}"
            continue
        if response.ok:
            last_error = None
            used_url = url
            break
        if response.status_code != 404:
            last_error = f"OTP request failed: {response.status_code} {response.reason}"
            break
        last_error = "OTP endpoint not found"
    rest_error = last_error

    if rest_error is None:
        if not response.content:
            rest_error = f"OTP returned empty response body: {used_url}"

    if rest_error is None:
        try:
            data = response.json()
        except Exception:
            snippet = (response.text or "").strip()[:200]
            content_type = response.headers.get("Content-Type", "")
            length = response.headers.get("Content-Length", str(len(response.text or "")))
            url_info = used_url or "unknown"
            rest_error = (
                "OTP returned non-JSON response: "
                f"{response.status_code} {response.reason}. "
                f"URL: {url_info}. "
                f"Content-Type: {content_type}. "
                f"Length: {length}. "
                f"Body: {snippet}"
            )

    if rest_error is None:
        plan = data.get("plan")
        if plan and plan.get("itineraries"):
            itineraries = []
            for itinerary in plan["itineraries"]:
                legs = itinerary.get("legs", [])
                itineraries.append({
                    "legs": legs,
                    "duration": itinerary.get("duration", 0),
                    "start_time": itinerary.get("startTime", 0),
                    "end_time": itinerary.get("endTime", 0),
                    "walk_distance": itinerary.get("walkDistance", 0),
                })
            return {
                "itineraries": itineraries,
                "raw": plan,
            }, None
        rest_error = rest_error or "OTP returned no itineraries"

    if not st.session_state.get("otp_disable_graphql"):
        gql_result, gql_error = otp_plan_graphql(
            base_url,
            router,
            origin_coords,
            dest_coords,
            event_time,
        )
        if gql_result:
            return gql_result, None

        return None, f"OTP REST failed: {rest_error}. OTP GraphQL failed: {gql_error}"

    return None, f"OTP REST failed: {rest_error}. OTP GraphQL disabled."


def otp_plan_graphql(base_url, router, origin_coords, dest_coords, event_time):

    base_url = base_url.rstrip("/")
    override_url = os.environ.get("OTP_GRAPHQL_URL", "").strip()
    if override_url:
        url_candidates = [override_url.rstrip("/")]
    else:
        url_candidates = [
            f"{base_url}/otp/routers/{router}/index/graphql",
            f"{base_url}/routers/{router}/index/graphql",
            f"{base_url}/otp/index/graphql",
            f"{base_url}/index/graphql",
            f"{base_url}/gtfs/v1",
            f"{base_url}/otp/gtfs/v1",
            f"{base_url}/routers/{router}/gtfs/v1",
            f"{base_url}/otp/routers/{router}/gtfs/v1",
            f"{base_url}/otp/transmodel/v3",
            f"{base_url}/otp/routers/{router}/transmodel/index/graphql",
            f"{base_url}/routers/{router}/transmodel/index/graphql",
        ]

    query_plan_connection = """
    query PlanConnection($from: CoordinateValue!, $to: CoordinateValue!, $dateTime: OffsetDateTime!, $modes: PlanModesInput) {
      planConnection(
        origin: { location: { coordinate: $from } }
        destination: { location: { coordinate: $to } }
        dateTime: { earliestDeparture: $dateTime }
        first: 5
        modes: $modes
      ) {
        edges {
          node {
            duration
            startTime
            endTime
            walkDistance
            legs {
              mode
              duration
              distance
              from { name }
              to { name }
              route { shortName longName }
            }
          }
        }
      }
    }
    """

    query_plan_connection_extended = """
    query PlanConnection($from: CoordinateValue!, $to: CoordinateValue!, $dateTime: OffsetDateTime!, $modes: PlanModesInput) {
      planConnection(
        origin: { location: { coordinate: $from } }
        destination: { location: { coordinate: $to } }
        dateTime: { earliestDeparture: $dateTime }
        first: 5
        modes: $modes
      ) {
        edges {
          node {
            duration
            startTime
            endTime
            walkDistance
            legs {
              mode
              duration
              distance
              headsign
              from { name }
              to { name }
              intermediateStops { name }
              route { shortName longName }
            }
          }
        }
      }
    }
    """

    date_str, time_str = event_time.split(" ")
    date_time = f"{date_str}T{time_str}:00+00:00"
    legacy_from = f"WGS84({origin_coords[1]},{origin_coords[0]})"
    legacy_to = f"WGS84({dest_coords[1]},{dest_coords[0]})"
    legacy_query = f"""
    {{
      plan(
        fromPlace: "{legacy_from}"
        toPlace: "{legacy_to}"
        date: "{date_str}"
        time: "{time_str}:00"
        modes: [TRANSIT, WALK]
        first: 5
      ) {{
        itineraries {{
          duration
          startTime
          endTime
          walkDistance
          legs {{
            mode
            duration
            distance
            headsign
            from {{ name }}
            to {{ name }}
            route {{ shortName longName }}
          }}
        }}
      }}
    }}
    """

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "OTPTimeout": "180000",
    }

    last_error = None
    for url in url_candidates:
        # Introspect to find available root fields
        fields = []
        try:
            introspection = {"query": "{ __schema { queryType { fields { name } } } }"}
            schema_resp = requests.post(url, json=introspection, headers=headers, timeout=30)
            if schema_resp.ok:
                schema_data = schema_resp.json()
                fields = [
                    f.get("name")
                    for f in schema_data.get("data", {})
                        .get("__schema", {})
                        .get("queryType", {})
                        .get("fields", [])
                    if isinstance(f, dict)
                ]
        except Exception:
            fields = []

        if "plan" in fields:
            payload = {"query": legacy_query}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=30)
            except Exception as exc:
                last_error = f"GraphQL request error: {exc}"
                continue
            if not resp.ok:
                last_error = f"GraphQL request failed: {resp.status_code} {resp.reason}"
                continue
            try:
                data = resp.json()
            except Exception:
                last_error = "GraphQL returned non-JSON response"
                continue
            itineraries = data.get("data", {}).get("plan", {}).get("itineraries", [])
            if itineraries:
                return {
                    "itineraries": [
                        {
                            "legs": itin.get("legs", []),
                            "duration": itin.get("duration", 0),
                            "start_time": itin.get("startTime", 0),
                            "end_time": itin.get("endTime", 0),
                            "walk_distance": itin.get("walkDistance", 0),
                        }
                        for itin in itineraries
                    ],
                    "raw": data.get("data", {}),
                }, None
            if data.get("errors"):
                fields_msg = f" Available root fields: {fields}" if fields else ""
                last_error = f"GraphQL errors: {data.get('errors')}.{fields_msg}"
            else:
                fields_msg = f" Available root fields: {fields}" if fields else ""
                last_error = f"GraphQL returned no itineraries.{fields_msg}"

        coord_variants = [
            {"latitude": origin_coords[0], "longitude": origin_coords[1]},
            {"lat": origin_coords[0], "lon": origin_coords[1]},
            {"lat": origin_coords[0], "lng": origin_coords[1]},
        ]
        coord_variants_to = [
            {"latitude": dest_coords[0], "longitude": dest_coords[1]},
            {"lat": dest_coords[0], "lon": dest_coords[1]},
            {"lat": dest_coords[0], "lng": dest_coords[1]},
        ]
        mode_variants = [
            {
                "transit": {
                    "access": ["WALK"],
                    "egress": ["WALK"],
                    "transfer": "WALK",
                    "transit": [{"mode": "BUS"}, {"mode": "TRAM"}, {"mode": "RAIL"}],
                }
            },
            {
                "accessMode": "WALK",
                "egressMode": "WALK",
                "directMode": "WALK",
                "transferMode": "WALK",
                "transitModes": [{"mode": "BUS"}, {"mode": "TRAM"}, {"mode": "RAIL"}],
            },
            None,
        ]
        query_variants = [
            query_plan_connection_extended,
            query_plan_connection_extended.replace("CoordinateValue", "PlanCoordinateInput"),
            query_plan_connection,
            query_plan_connection.replace("CoordinateValue", "PlanCoordinateInput"),
        ]

        for query in query_variants:
            if "plan" in fields and "planConnection" not in fields:
                query = query.replace("planConnection", "plan")
            for idx in range(len(coord_variants)):
                for modes in mode_variants:
                    variables = {
                        "from": coord_variants[idx],
                        "to": coord_variants_to[idx],
                        "dateTime": date_time,
                        "modes": modes,
                    }
                    payload = {"query": query, "variables": variables}
                    try:
                        resp = requests.post(url, json=payload, headers=headers, timeout=30)
                    except Exception as exc:
                        last_error = f"GraphQL request error: {exc}"
                        continue
                    if not resp.ok:
                        last_error = f"GraphQL request failed: {resp.status_code} {resp.reason}"
                        continue
                    try:
                        data = resp.json()
                    except Exception:
                        last_error = "GraphQL returned non-JSON response"
                        continue

                    if not isinstance(data, dict):
                        last_error = "GraphQL returned invalid response format"
                        continue

                    root = data.get("data") or {}
                    if not isinstance(root, dict):
                        root = {}

                    edges = root.get("planConnection", {}) or {}
                    edges = edges.get("edges", []) if isinstance(edges, dict) else []
                    if edges:
                        itineraries = []
                        for edge in edges:
                            node = edge.get("node", {})
                            legs = node.get("legs", [])
                            itineraries.append({
                                "legs": legs,
                                "duration": node.get("duration", 0),
                                "start_time": node.get("startTime", 0),
                                "end_time": node.get("endTime", 0),
                                "walk_distance": node.get("walkDistance", 0),
                            })
                        return {
                            "itineraries": itineraries,
                            "raw": data.get("data", {}),
                        }, None

                    if data.get("errors"):
                        fields_msg = f" Available root fields: {fields}" if fields else ""
                        last_error = f"GraphQL errors: {data.get('errors')}.{fields_msg}"
                    else:
                        fields_msg = f" Available root fields: {fields}" if fields else ""
                        last_error = f"GraphQL returned no itineraries.{fields_msg}"

    return None, last_error or "GraphQL request failed"


def time_to_seconds(time_str):
    if pd.isna(time_str):
        return None
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) < 2:
            return None
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 3600 + m * 60 + s
    except Exception:
        return None


@st.cache_data
def build_schedule_index(stop_times_df, trips_df):

    if stop_times_df is None or stop_times_df.empty:
        return {}

    required_cols = {"trip_id", "stop_id", "departure_time"}
    if not required_cols.issubset(stop_times_df.columns):
        return {}

    stop_times = stop_times_df[["trip_id", "stop_id", "departure_time"]].copy()
    stop_times["trip_id"] = stop_times["trip_id"].astype(str)

    trip_routes = trips_df[["trip_id", "route_id"]].copy()
    trip_routes["trip_id"] = trip_routes["trip_id"].astype(str)
    trip_routes["route_id"] = trip_routes["route_id"].astype(str)

    stop_times = stop_times.merge(trip_routes, on="trip_id", how="left")
    stop_times["departure_sec"] = stop_times["departure_time"].apply(time_to_seconds)
    stop_times = stop_times.dropna(subset=["departure_sec", "route_id", "stop_id"])

    stop_times["departure_mod"] = stop_times["departure_sec"].astype(int) % 86400

    schedule_index = {}
    for (stop_id, route_id), group in stop_times.groupby(["stop_id", "route_id"]):
        times = sorted(group["departure_mod"].astype(int).tolist())
        schedule_index[(stop_id, route_id)] = times

    return schedule_index


schedule_index = build_schedule_index(stop_times, trips)


def fetch_realtime_vehicles():

    load_dotenv()

    api_key = os.environ.get("TFI_API_KEY")
    if not api_key:
        return None, "TFI_API_KEY is not set"

    base_url = os.environ.get("TFI_GTFSR_BASE_URL", "https://api.nationaltransport.ie/gtfsr/v2")
    feed = os.environ.get("TFI_GTFSR_FEED", "Vehicles")
    vehicle_url = f"{base_url.rstrip('/')}/{feed}"

    headers = {
        "x-api-key": api_key,
        "Cache-Control": "no-cache",
    }

    response = requests.get(vehicle_url, headers=headers, timeout=5)
    if not response.ok:
        return None, f"TFI API request failed: {response.status_code} {response.reason}"

    feed_msg = gtfs_realtime_pb2.FeedMessage()
    try:
        feed_msg.ParseFromString(response.content)
    except Exception:
        return None, "Failed to parse GTFS-Realtime response"

    vehicles = []
    for entity in feed_msg.entity:
        if entity.HasField("vehicle"):
            vehicle = entity.vehicle
            timestamp = vehicle.timestamp or int(time.time())
            vehicles.append({
                "vehicle_id": vehicle.vehicle.id,
                "trip_id": vehicle.trip.trip_id,
                "route_id": vehicle.trip.route_id,
                "latitude": vehicle.position.latitude,
                "longitude": vehicle.position.longitude,
                "timestamp": timestamp
            })

    df = pd.DataFrame(vehicles)
    if not df.empty:
        try:
            os.makedirs(os.path.dirname(vehicles_path), exist_ok=True)
            df.to_csv(vehicles_path, index=False)
        except:
            pass
    return df, None


def fetch_trip_updates(trips_df):

    load_dotenv()

    api_key = os.environ.get("TFI_API_KEY")
    if not api_key:
        return None, "TFI_API_KEY is not set"

    base_url = os.environ.get("TFI_GTFSR_BASE_URL", "https://api.nationaltransport.ie/gtfsr/v2")
    feed = os.environ.get("TFI_GTFSR_TRIP_UPDATES_FEED", "TripUpdates")
    trip_url = f"{base_url.rstrip('/')}/{feed}"

    headers = {
        "x-api-key": api_key,
        "Cache-Control": "no-cache",
    }

    response = requests.get(trip_url, headers=headers, timeout=5)
    if not response.ok:
        return None, f"TFI API request failed: {response.status_code} {response.reason}"

    feed_msg = gtfs_realtime_pb2.FeedMessage()
    try:
        feed_msg.ParseFromString(response.content)
    except Exception:
        return None, "Failed to parse GTFS-Realtime TripUpdates response"

    trip_delays = {}

    for entity in feed_msg.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        trip_id = tu.trip.trip_id if tu.trip else None
        if not trip_id:
            continue

        delays = []
        if tu.stop_time_update:
            for stu in tu.stop_time_update:
                if stu.departure and stu.departure.delay is not None:
                    delays.append(stu.departure.delay)
                elif stu.arrival and stu.arrival.delay is not None:
                    delays.append(stu.arrival.delay)
        if not delays and tu.delay is not None:
            delays.append(tu.delay)

        if delays:
            trip_delays[trip_id] = delays

    if not trip_delays:
        return {}, None

    # Map trip delays to route delays using trips_df
    trips_subset = trips_df[["trip_id", "route_id"]].copy()
    trips_subset["trip_id"] = trips_subset["trip_id"].astype(str)
    trips_subset["route_id"] = trips_subset["route_id"].astype(str)

    route_delays = {}
    for trip_id, delays in trip_delays.items():
        route_row = trips_subset[trips_subset["trip_id"] == str(trip_id)]
        if route_row.empty:
            continue
        route_id = route_row.iloc[0]["route_id"]
        route_delays.setdefault(route_id, []).extend(delays)

    route_delay_map = {}
    for route_id, delays in route_delays.items():
        if delays:
            route_delay_map[route_id] = int(statistics.median(delays))

    return route_delay_map, None


def route_related_ids(route_stop_ids, stop_times_df, trips_df):

    if stop_times_df is None or stop_times_df.empty:
        return set(), set()

    stop_times_subset = stop_times_df[stop_times_df["stop_id"].isin(route_stop_ids)]
    if stop_times_subset.empty:
        return set(), set()

    trip_ids = set(stop_times_subset["trip_id"].astype(str).tolist())
    trips_subset = trips_df[trips_df["trip_id"].astype(str).isin(trip_ids)]
    route_ids = set(trips_subset["route_id"].astype(str).tolist())

    return route_ids, trip_ids


def filter_vehicles_for_route(vehicles_df, route_stop_ids, stop_times_df, trips_df):

    if vehicles_df.empty:
        return vehicles_df

    route_ids, trip_ids = route_related_ids(route_stop_ids, stop_times_df, trips_df)

    if not route_ids and not trip_ids:
        return vehicles_df

    route_id_suffixes = {rid.split("_")[-1] for rid in route_ids if rid}
    trip_id_prefixes = {tid.split("_")[0] for tid in trip_ids if tid}

    route_id_series = vehicles_df["route_id"].astype(str)
    trip_id_series = vehicles_df["trip_id"].astype(str)

    route_id_match = route_id_series.isin(route_ids) | route_id_series.str.split("_").str[-1].isin(route_id_suffixes)
    trip_id_match = trip_id_series.isin(trip_ids) | trip_id_series.str.split("_").str[0].isin(trip_id_prefixes)

    filtered = vehicles_df[route_id_match | trip_id_match]

    if filtered.empty:
        return vehicles_df

    return filtered


def get_realtime_vehicles_for_route(route_key, route_stop_ids, stop_times_df, trips_df):
    """Get vehicles with 60-second cache to reduce API load"""
    current_time = datetime.now()
    
    if "realtime_vehicles_df" not in st.session_state:
        st.session_state.realtime_vehicles_df = None
        st.session_state.realtime_route_key = None
        st.session_state.realtime_error = None
        st.session_state.realtime_source = None
        st.session_state.realtime_delay_error = None
        st.session_state.realtime_route_delays = {}
        st.session_state.realtime_last_fetch = None

    # Only fetch if route changed OR 60+ seconds since last fetch
    should_fetch = (
        st.session_state.realtime_route_key != route_key or
        st.session_state.realtime_last_fetch is None or
        (current_time - st.session_state.realtime_last_fetch).total_seconds() > 60
    )
    
    if should_fetch:
        df, err = fetch_realtime_vehicles()
        if df is None or df.empty:
            st.session_state.realtime_error = err
            df = load_vehicles()
            st.session_state.realtime_source = "csv"
        else:
            st.session_state.realtime_error = None
            st.session_state.realtime_source = "api"
        st.session_state.realtime_vehicles_df = df
        st.session_state.realtime_last_fetch = current_time

        route_delay_map, delay_err = fetch_trip_updates(trips_df)
        if route_delay_map is None:
            st.session_state.realtime_delay_error = delay_err
            st.session_state.realtime_route_delays = {}
        else:
            st.session_state.realtime_delay_error = None
            st.session_state.realtime_route_delays = route_delay_map

        st.session_state.realtime_route_key = route_key

    vehicles_df = st.session_state.realtime_vehicles_df
    return filter_vehicles_for_route(vehicles_df, route_stop_ids, stop_times_df, trips_df)


def pick_public_route_name(row):

    short_name = str(row.get("route_short_name", "")).strip()
    long_name = str(row.get("route_long_name", "")).strip()

    if short_name.isdigit() and long_name.isdigit():
        if len(short_name) >= 6 and len(long_name) <= 4:
            return long_name

    def looks_public(value):
        if not value:
            return False
        if len(value) <= 6:
            return True
        if value.isdigit() and len(value) <= 7:
            return True
        return False

    if looks_public(short_name):
        return short_name
    if looks_public(long_name):
        return long_name
    if short_name:
        return short_name
    if long_name:
        return long_name
    return None


def build_trip_route_map(trips_df, routes_df):

    trip_route = trips_df[["trip_id", "route_id"]]
    route_names = routes_df[["route_id", "route_short_name", "route_long_name"]]
    trip_route = trip_route.merge(route_names, on="route_id", how="left")

    route_label = trip_route.apply(pick_public_route_name, axis=1)

    trip_ids = trip_route["trip_id"].astype(str)
    return dict(zip(trip_ids, route_label))


def build_route_id_maps(routes_df):

    route_id_to_label = {}
    route_id_suffix_to_label = {}

    for _, row in routes_df.iterrows():
        route_id = str(row.get("route_id", "")).strip()
        if not route_id:
            continue
        label = pick_public_route_name(row)
        if label:
            route_id_to_label[route_id] = label
            suffix = route_id.split("_")[-1]
            route_id_suffix_to_label.setdefault(suffix, label)

    return route_id_to_label, route_id_suffix_to_label


def get_luas_route_ids(routes_df):

    if "route_long_name" not in routes_df.columns:
        return set()

    luas_routes = routes_df[
        routes_df["route_long_name"].str.contains("luas", case=False, na=False)
    ]

    return set(luas_routes["route_id"].tolist())


trip_to_route = build_trip_route_map(trips, routes)
route_id_to_label, route_id_suffix_to_label = build_route_id_maps(routes)
luas_route_ids = get_luas_route_ids(routes)

@st.cache_resource
def prep_spatial_indices():
    """Prepare spatial indices once at startup"""
    luas_ids, bus_ids = build_mode_stop_sets(G)
    luas_t, luas_s = build_kdtree_for_stop_ids(luas_ids)
    bus_t, bus_s = build_kdtree_for_stop_ids(bus_ids)
    return luas_ids, bus_ids, luas_t, bus_t, luas_s, bus_s

luas_stop_ids, bus_stop_ids, luas_tree, bus_tree, luas_stops, bus_stops = prep_spatial_indices()


# ---------------------------------------------------
# ROUTE + TIME ESTIMATION
# ---------------------------------------------------

def estimate_travel_time(route, graph):
    total = 0.0
    for i in range(len(route) - 1):
        data = graph[route[i]][route[i + 1]]
        total += data.get("weight", 1.0)
    return total / 60.0


def predict_delay(route):

    affected = congestion[congestion["stop_id"].isin(route)]

    if len(affected) == 0:
        return 0

    score = affected["congestion_score"].median()
    if pd.isna(score):
        return 0
    # Scale and cap to keep delay realistic
    return min(score * 0.01, 20)


def expected_wait_seconds(
    stop_id,
    route_id,
    arrival_time_sec,
    schedule_index,
    route_delay_map,
    default_wait_sec=300,
):

    if not schedule_index or route_id is None:
        return default_wait_sec

    route_id_str = str(route_id)
    times = schedule_index.get((stop_id, route_id_str))
    if not times:
        return default_wait_sec

    t = int(arrival_time_sec) % 86400

    # Find the next departure at or after arrival time
    for dep in times:
        if dep >= t:
            wait = dep - t
            delay = route_delay_map.get(route_id_str, 0) if route_delay_map else 0
            return max(wait + delay, 0)

    # Wrap to next day
    wait = (times[0] + 86400) - t
    delay = route_delay_map.get(route_id_str, 0) if route_delay_map else 0
    return max(wait + delay, 0)


def route_cost(
    u,
    v,
    edge_data,
    prev_route,
    prev_mode,
    arrival_time_sec,
    schedule_index,
    route_delay_map,
    walk_distance_m,
):
    base = edge_data.get("weight", 60.0)
    route_id = edge_data.get("route_id")
    mode = edge_data.get("mode", "transit")
    wait_time = 0.0

    is_transit = mode in {"bus", "luas", "rail"}
    is_new_boarding = prev_route is None or prev_route != route_id or prev_mode != mode

    if is_transit and is_new_boarding:
        wait_time = expected_wait_seconds(
            u,
            route_id,
            arrival_time_sec,
            schedule_index,
            route_delay_map,
        )

    if mode == "walk":
        # Hard cap walking segments and discourage long walks between stops
        if base > 600:
            return float("inf"), route_id, mode
        if walk_distance_m is not None:
            if walk_distance_m > 600:
                return float("inf"), route_id, mode
            if walk_distance_m > 300:
                base *= 2.0

    # Mode preference
    if mode == "luas":
        base *= 0.5
    elif mode == "bus":
        base *= 1.3

    # Transfer penalties to discourage excessive switching
    if prev_mode and mode != prev_mode:
        base += 900.0
    if prev_route and route_id and route_id != prev_route:
        base += 300.0
    if prev_mode == "walk" and mode in {"bus", "luas", "rail"}:
        base += 200.0

    # Discourage very short transit hops (often worse than walking)
    if mode in {"bus", "luas", "rail"}:
        edge_sec = edge_data.get("travel_time_sec", edge_data.get("weight", 0.0)) or 0.0
        if edge_sec <= 120:
            base += 600.0

    return base + wait_time, route_id, mode


def find_route_with_penalty(
    graph,
    start,
    end,
    start_time_sec,
    schedule_index,
    route_delay_map,
    dest_coords,
    max_stops=40,
):
    counter = itertools.count()
    queue = [(0.0, next(counter), start, None, None, [])]
    visited = set()

    while queue:
        cost, _, node, prev_route, prev_mode, path = heapq.heappop(queue)
        if (node, prev_route, prev_mode) in visited:
            continue
        visited.add((node, prev_route, prev_mode))
        path = path + [node]

        if node == end:
            return path, cost

        if len(path) > max_stops:
            continue

        for neighbor in graph[node]:
            edge = graph[node][neighbor]
            if prev_mode == "walk" and edge.get("mode") == "walk" and neighbor != "__dest__":
                continue
            arrival_time_sec = start_time_sec + cost
            walk_distance_m = None
            if edge.get("mode") == "walk":
                n1 = graph.nodes.get(node, {})
                n2 = graph.nodes.get(neighbor, {})
                lat1 = n1.get("lat")
                lon1 = n1.get("lon")
                lat2 = n2.get("lat")
                lon2 = n2.get("lon")
                if all(v is not None for v in [lat1, lon1, lat2, lon2]):
                    walk_distance_m = haversine_km(lat1, lon1, lat2, lon2) * 1000
            step_cost, route_id, mode = route_cost(
                node,
                neighbor,
                edge,
                prev_route,
                prev_mode,
                arrival_time_sec,
                schedule_index,
                route_delay_map,
                walk_distance_m,
            )
            if step_cost == float("inf"):
                continue

            # Penalize detours that move away from destination
            if dest_coords:
                n1 = graph.nodes.get(node, {})
                n2 = graph.nodes.get(neighbor, {})
                lat1 = n1.get("lat")
                lon1 = n1.get("lon")
                lat2 = n2.get("lat")
                lon2 = n2.get("lon")
                if all(v is not None for v in [lat1, lon1, lat2, lon2]):
                    curr_dist = haversine_km(lat1, lon1, dest_coords[0], dest_coords[1])
                    next_dist = haversine_km(lat2, lon2, dest_coords[0], dest_coords[1])
                    if next_dist > curr_dist + 0.1:
                        step_cost += 300.0
            heapq.heappush(queue, (cost + step_cost, next(counter), neighbor, route_id, mode, path))

    return None, float("inf")


def compute_departure(
    origin_stop,
    dest_stop,
    event_time,
    graph,
    schedule_index,
    route_delay_map,
    dest_coords,
):

    event_dt = datetime.strptime(event_time, "%Y-%m-%d %H:%M")
    buffer = 15

    # Iteratively estimate departure time with schedule-based waiting
    guess_departure = event_dt - timedelta(minutes=30)

    for _ in range(2):
        start_time_sec = guess_departure.hour * 3600 + guess_departure.minute * 60 + guess_departure.second
        route, cost = find_route_with_penalty(
            graph,
            origin_stop,
            dest_stop,
            start_time_sec=start_time_sec,
            schedule_index=schedule_index,
            route_delay_map=route_delay_map,
            dest_coords=dest_coords,
        )
        if not route:
            raise RuntimeError("No route found")

        travel_time = cost / 60.0

        delay = predict_delay(route)

        total_time = travel_time + delay + buffer
        new_departure = event_dt - timedelta(minutes=total_time)

        if abs((new_departure - guess_departure).total_seconds()) < 60:
            guess_departure = new_departure
            break

        guess_departure = new_departure

    departure = guess_departure

    return route, travel_time, delay, departure


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def format_minutes(seconds):
    minutes = max(int(round(seconds / 60.0)), 1)
    return f"{minutes} min"


def build_route_steps(route, graph, stops_df, origin_coords, dest_coords, route_id_to_label):

    if not route:
        return []

    stop_lookup = stops_df.set_index("stop_id")[["stop_name", "stop_lat", "stop_lon", "stop_code"]]

    def get_stop_row(stop_id):
        if stop_id not in stop_lookup.index:
            return None
        row = stop_lookup.loc[stop_id]
        if isinstance(row, pd.DataFrame):
            return row.iloc[0]
        return row

    steps = []

    # Initial walk from origin to first stop (if available)
    if origin_coords:
        stop_row = get_stop_row(route[0])
    else:
        stop_row = None

    if origin_coords and stop_row is not None:
        walk_km = haversine_km(
            origin_coords[0],
            origin_coords[1],
            stop_row["stop_lat"],
            stop_row["stop_lon"],
        )
        walk_sec = (walk_km * 1000) / 1.4
        stop_code = stop_row.get("stop_code")
        suffix = f" (Stop ID: {stop_code})" if pd.notna(stop_code) else ""
        steps.append(f"Walk {format_minutes(walk_sec)} to {stop_row['stop_name']}{suffix}")

    # Segment the route by mode/route_id
    current = None
    edge_count = 0
    travel_sec = 0.0
    segment_start = None

    def flush_segment(segment_end):
        nonlocal current, edge_count, travel_sec, segment_start
        if not current or edge_count == 0:
            return
        mode = current["mode"]
        route_id = current.get("route_id")
        if mode == "walk":
            stop_row = get_stop_row(segment_end)
            end_name = stop_row["stop_name"] if stop_row is not None else "destination"
            stop_code = stop_row.get("stop_code") if stop_row is not None else None
            suffix = f" (Stop ID: {stop_code})" if pd.notna(stop_code) else ""
            steps.append(f"Walk {format_minutes(travel_sec)} to {end_name}{suffix}")
        else:
            label = None
            if route_id is not None:
                label = route_id_to_label.get(str(route_id))
            label = label or str(route_id) if route_id is not None else "Transit"
            mode_title = "Luas" if mode == "luas" else "Bus" if mode == "bus" else "Rail"
            from_row = get_stop_row(segment_start)
            to_row = get_stop_row(segment_end)
            from_name = from_row["stop_name"] if from_row is not None else "start"
            to_name = to_row["stop_name"] if to_row is not None else "end"
            from_code = from_row.get("stop_code") if from_row is not None else None
            to_code = to_row.get("stop_code") if to_row is not None else None
            from_suffix = f" (Stop ID: {from_code})" if pd.notna(from_code) else ""
            to_suffix = f" (Stop ID: {to_code})" if pd.notna(to_code) else ""
            steps.append(
                f"{mode_title} {label} -> approx. {edge_count} stops ({from_name}{from_suffix} to {to_name}{to_suffix})"
            )
        current = None
        edge_count = 0
        travel_sec = 0.0
        segment_start = None

    for i in range(len(route) - 1):
        u = route[i]
        v = route[i + 1]
        edge = graph.get_edge_data(u, v, default={})
        mode = edge.get("mode", "transit")
        route_id = edge.get("route_id")
        edge_sec = edge.get("travel_time_sec", edge.get("weight", 0.0))

        if current is None:
            current = {"mode": mode, "route_id": route_id}
            segment_start = u
        elif current["mode"] != mode or current.get("route_id") != route_id:
            flush_segment(u)
            current = {"mode": mode, "route_id": route_id}
            segment_start = u

        edge_count += 1
        travel_sec += float(edge_sec or 0.0)

    # flush last segment
    flush_segment(route[-1])

    # Final walk from last stop to destination (if available)
    if dest_coords and (route[-1] != "__dest__"):
        last_stop = None
        for stop_id in reversed(route):
            if stop_id in stop_lookup.index:
                last_stop = stop_id
                break
        if last_stop:
            stop_row = get_stop_row(last_stop)
            if stop_row is None:
                return steps
            walk_km = haversine_km(
                stop_row["stop_lat"],
                stop_row["stop_lon"],
                dest_coords[0],
                dest_coords[1],
            )
            walk_sec = (walk_km * 1000) / 1.4
            steps.append(f"Walk {format_minutes(walk_sec)} to destination")

    return steps


# ---------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------

# Initialize session state for UI
if "show_side_panel" not in st.session_state:
    st.session_state.show_side_panel = False
if "show_bottom_sheet" not in st.session_state:
    st.session_state.show_bottom_sheet = False

# Apply base styles
apply_base_styles()

if "route" not in st.session_state:
    st.session_state.route = None
    st.session_state.travel_time = None
    st.session_state.delay = None
    st.session_state.departure = None
    st.session_state.walk_to_start_km = None
    st.session_state.walk_from_end_km = None
    st.session_state.walk_time_min = None
    st.session_state.origin_coords = None
    st.session_state.dest_coords = None
    st.session_state.temp_graph = None
    st.session_state.otp_used = False
    st.session_state.otp_itinerary = None
    st.session_state.otp_steps = None
    st.session_state.otp_last_error = None
    st.session_state.otp_alternatives = []
    st.session_state.otp_crowd_label = None
    st.session_state.otp_crowd_score = None
    st.session_state.otp_leave_window = None
    st.session_state.otp_disruption = False
    st.session_state.otp_congestion_spot = None
    st.session_state.otp_stop_ids = []
    st.session_state.otp_leg_stops = []
    st.session_state.origin_poi = None
    st.session_state.dest_poi = None
    st.session_state.otp_selected_idx = 0

# Render header
render_header()

# Render search inputs
origin_place, destination_place, event_date, event_time_input, preference, plan_button = render_inputs()

event_time = datetime.combine(event_date, event_time_input).strftime("%Y-%m-%d %H:%M")

# ---------------------------------------------------
# MAP CONTAINER (FULLSCREEN)
# ---------------------------------------------------

m = folium.Map(location=[53.35, -6.26], zoom_start=11, tiles="OpenStreetMap")

route_coords = []
filtered_vehicles = pd.DataFrame()

def get_route_coordinates(route, stops_df):
    coords = []
    for stop_id in route:
        stop = stops_df[stops_df["stop_id"] == stop_id]
        if not stop.empty:
            lat = stop.iloc[0]["stop_lat"]
            lon = stop.iloc[0]["stop_lon"]
            coords.append((lat, lon))

    return coords


def vehicles_near_route(vehicles_df, coords, threshold=0.01):

    if not coords or vehicles_df.empty:
        return vehicles_df.iloc[0:0]

    route_lats = [c[0] for c in coords]
    route_lons = [c[1] for c in coords]

    filtered = []

    for _, v in vehicles_df.iterrows():
        vlat = v.get("latitude")
        vlon = v.get("longitude")
        if pd.isna(vlat) or pd.isna(vlon):
            continue
        for lat, lon in zip(route_lats, route_lons):
            dist = ((vlat - lat) ** 2 + (vlon - lon) ** 2) ** 0.5
            if dist < threshold:
                filtered.append(v)
                break

    if not filtered:
        return vehicles_df.iloc[0:0]

    return pd.DataFrame(filtered)


def pick_leg_color(leg):
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


def build_otp_route_segments(legs, stop_name_to_id_map, stops_df, origin_coords, dest_coords, trips_df=None, stop_times_df=None, shapes_df=None):
    segments = []
    if not legs:
        return segments

    def decode_polyline(encoded):
        if not encoded:
            return []
        coords = []
        index = 0
        lat = 0
        lon = 0
        length = len(encoded)
        while index < length:
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlon = ~(result >> 1) if (result & 1) else (result >> 1)
            lon += dlon
            coords.append((lat / 1e5, lon / 1e5))
        return coords

    def add_point(points, pt):
        if pt is None:
            return
        if not points or points[-1] != pt:
            points.append(pt)

    def otp_walk_points(start_pt, end_pt):
        if not start_pt or not end_pt:
            return []
        base_url = os.environ.get("OTP_BASE_URL", "http://localhost:8080").rstrip("/")
        router = os.environ.get("OTP_ROUTER", "default")
        if base_url.lower().endswith("/otp"):
            base_url = base_url[:-4]
        url_candidates = [
            f"{base_url}/otp/routers/{router}/plan",
            f"{base_url}/routers/{router}/plan",
            f"{base_url}/otp/plan",
            f"{base_url}/plan",
        ]
        params = {
            "fromPlace": f"{start_pt[0]},{start_pt[1]}",
            "toPlace": f"{end_pt[0]},{end_pt[1]}",
            "mode": "WALK",
            "numItineraries": 1,
            "showIntermediateStops": "true",
            "additionalFields": "legGeometry",
        }
        for url in url_candidates:
            try:
                resp = requests.get(url, params=params, timeout=15, headers={"Accept": "application/json"})
            except Exception:
                continue
            if not resp.ok:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            plan = data.get("plan") or {}
            itineraries = plan.get("itineraries") or []
            if not itineraries:
                continue
            legs_walk = itineraries[0].get("legs") or []
            for leg in legs_walk:
                geom = (leg.get("legGeometry") or {}).get("points")
                if geom:
                    return decode_polyline(geom)
        return []

    last_idx = len(legs) - 1
    last_point = None
    for idx, leg in enumerate(legs):
        mode = leg.get("mode", "WALK")
        start = _coords_for_stop_obj(leg.get("from", {}), stop_name_to_id_map, stops_df)
        end = _coords_for_stop_obj(leg.get("to", {}), stop_name_to_id_map, stops_df)

        if idx == 0 and origin_coords is not None:
            start = start or origin_coords
        if idx == last_idx and dest_coords is not None:
            end = end or dest_coords
        if start is None:
            start = last_point
        if end is None and idx < last_idx:
            next_from = (legs[idx + 1].get("from", {}) or {})
            end = _coords_for_stop_obj(next_from, stop_name_to_id_map, stops_df)

        points = []
        mode_upper = str(mode).upper()
        geom = (leg.get("legGeometry") or {}).get("points")
        if geom:
            points = decode_polyline(geom)
        if not points and mode_upper == "WALK":
            points = otp_walk_points(start, end)
        if not points and mode_upper != "WALK":
            shape_pts = _shape_points_for_leg(
                (leg.get("route") or {}).get("gtfsId"),
                leg.get("from"),
                leg.get("to"),
                stops_df,
                trips_df or trips,
                stop_times_df or stop_times,
                shapes_df or shapes,
                stop_name_to_id_map,
            )
            if shape_pts:
                points = shape_pts
        if not points:
            add_point(points, start)
            for stop in leg.get("intermediateStops", []) or []:
                mid = _coords_for_stop_obj(stop, stop_name_to_id_map, stops_df)
                add_point(points, mid)
            add_point(points, end)

        if len(points) >= 2:
            segments.append({"points": points, "leg": leg, "mode": mode})
            last_point = points[-1]

    return segments


def fit_map_to_points(map_obj, points):
    if not points:
        return
    if len(points) == 1:
        map_obj.location = points[0]
        return
    map_obj.fit_bounds(points, padding=(30, 30))


# ---------------------------------------------------
# MAP DATA LAZY LOADING
# ---------------------------------------------------
# Events/congestion markers are NOT plotted on initial load
# They are only shown when a route is selected
# This dramatically speeds up initial app load


# ---------------------------------------------------
# JOURNEY CALCULATION
# ---------------------------------------------------

if plan_button:
    if not origin_place:
        st.error("📍 Please enter a start location")
        st.session_state.route = None
    elif not destination_place:
        st.error("📍 Please enter a destination")
        st.session_state.route = None
    else:
        origin_lat, origin_lon = place_to_coordinates(origin_place)

        dest_lat, dest_lon = place_to_coordinates(destination_place)

        if origin_lat is None:
            st.error("❌ Start location not found - try a different address or postcode")
            st.session_state.route = None

        elif dest_lat is None:
            st.error("❌ Destination not found - try a different address or postcode")
            st.session_state.route = None

        else:
            if origin_lat < 51 or origin_lat > 56:
                st.sidebar.error("Origin is outside Ireland")
                st.session_state.route = None
            elif dest_lat < 51 or dest_lat > 56:
                st.sidebar.error("Destination is outside Ireland")
                st.session_state.route = None
            else:
                use_otp = os.environ.get("USE_OTP", "").strip().lower() in {"1", "true", "yes"}
                otp_done = False
                event_dt = datetime.strptime(event_time, "%Y-%m-%d %H:%M")
                if use_otp:
                    otp_result, otp_err = otp_plan(
                        (origin_lat, origin_lon),
                        (dest_lat, dest_lon),
                        event_time,
                    )
                    if otp_result:
                        st.session_state.otp_last_error = None
                        st.session_state.otp_used = True
                        itineraries = otp_result.get("itineraries", [])
                        ranked = []
                        for itin in itineraries:
                            legs = itin.get("legs", [])
                            metrics = summarize_itinerary(legs, itin.get("duration", 0))
                            stop_ids = extract_stop_ids_from_legs(legs, stop_name_to_id)
                            crowd_norm, crowd_text = compute_crowd_score(
                                stop_ids,
                                event_dt,
                                demand_model,
                                events,
                                congestion,
                            )
                            score = score_itinerary(metrics, crowd_norm, preference)
                            start_time = itin.get("start_time", 0)
                            if isinstance(start_time, (int, float)) and start_time > 10_000_000_000:
                                departure = datetime.fromtimestamp(start_time / 1000.0)
                            else:
                                departure = datetime.fromtimestamp(start_time) if start_time else event_dt
                            steps = build_steps_from_otp_legs(legs, stop_name_to_code)
                            disruption = detect_disruption(stop_ids, congestion, CONGESTION_ALERT)
                            congestion_spot = top_congestion_stop(stop_ids, congestion, stops)
                            ranked.append({
                                "score": score,
                                "steps": steps,
                                "metrics": metrics,
                                "departure": departure,
                                "crowd_norm": crowd_norm,
                                "crowd_label": crowd_text,
                                "legs": legs,
                                "stop_ids": stop_ids,
                                "disruption": disruption,
                                "congestion_spot": congestion_spot,
                                "raw": itin,
                            })

                        if ranked:
                            ranked.sort(key=lambda item: item["score"])
                            best = ranked[0]
                            st.session_state.otp_itinerary = best["raw"]
                            st.session_state.otp_steps = best["steps"]
                            st.session_state.travel_time = best["metrics"]["travel_time_min"]
                            st.session_state.walk_time_min = best["metrics"]["walking_time_min"]
                            st.session_state.departure = best["departure"]
                            st.session_state.otp_alternatives = ranked[:5]
                            st.session_state.otp_crowd_label = best["crowd_label"]
                            st.session_state.otp_crowd_score = best["crowd_norm"]
                            st.session_state.otp_disruption = best["disruption"]
                            st.session_state.otp_leave_window = compute_leave_window(
                                best["departure"],
                                best["crowd_norm"],
                                best["metrics"]["transfers"],
                            )
                            st.session_state.otp_congestion_spot = best.get("congestion_spot")
                            st.session_state.otp_stop_ids = best.get("stop_ids", [])
                            st.session_state.otp_leg_stops = [
                                extract_leg_stop_list(leg) for leg in best.get("legs", [])
                            ]
                            st.session_state.origin_poi = osm_reverse_geocode(origin_lat, origin_lon)
                            st.session_state.dest_poi = osm_reverse_geocode(dest_lat, dest_lon)
                        else:
                            st.session_state.otp_itinerary = otp_result.get("raw")
                            st.session_state.otp_steps = []
                            st.session_state.travel_time = None
                            st.session_state.walk_time_min = None
                            st.session_state.departure = None
                            st.session_state.otp_alternatives = []
                            st.session_state.otp_crowd_label = None
                            st.session_state.otp_crowd_score = None
                            st.session_state.otp_disruption = False
                            st.session_state.otp_leave_window = None
                            st.session_state.otp_congestion_spot = None
                            st.session_state.otp_stop_ids = []
                            st.session_state.otp_leg_stops = []
                            st.session_state.origin_poi = osm_reverse_geocode(origin_lat, origin_lon)
                            st.session_state.dest_poi = osm_reverse_geocode(dest_lat, dest_lon)

                        st.session_state.route = None
                        st.session_state.delay = None
                        st.session_state.origin_coords = (origin_lat, origin_lon)
                        st.session_state.dest_coords = (dest_lat, dest_lon)
                        st.sidebar.success("OTP route calculated")
                        otp_done = True
                    else:
                        st.session_state.otp_last_error = otp_err
                        st.sidebar.warning(f"OTP routing failed, falling back to local routing. ({otp_err})")
                        st.session_state.otp_used = False
                        st.session_state.otp_itinerary = None
                        st.session_state.otp_steps = None
                        st.session_state.otp_alternatives = []
                        st.session_state.otp_crowd_label = None
                        st.session_state.otp_crowd_score = None
                        st.session_state.otp_leave_window = None
                        st.session_state.otp_disruption = False
                        st.session_state.otp_congestion_spot = None
                        st.session_state.otp_stop_ids = []
                        st.session_state.otp_leg_stops = []
                        st.session_state.origin_poi = osm_reverse_geocode(origin_lat, origin_lon)
                        st.session_state.dest_poi = osm_reverse_geocode(dest_lat, dest_lon)

                if not otp_done:
                    origin_candidates = []
                    origin_candidates.extend(
                        nearest_stops_by_subset(origin_lat, origin_lon, bus_stops, bus_tree, k=5)
                    )
                    origin_candidates.extend(
                        nearest_stops_by_subset(origin_lat, origin_lon, luas_stops, luas_tree, k=3)
                    )
                    if not origin_candidates:
                        origin_candidates = nearest_stops(origin_lat, origin_lon, k=8)

                    dest_candidates = []
                    dest_candidates.extend(
                        nearest_stops_by_subset(dest_lat, dest_lon, bus_stops, bus_tree, k=5)
                    )
                    dest_candidates.extend(
                        nearest_stops_by_subset(dest_lat, dest_lon, luas_stops, luas_tree, k=3)
                    )
                    if not dest_candidates:
                        dest_candidates = nearest_stops(dest_lat, dest_lon, k=8)

                    # Build a temp graph with a destination node connected by walking
                    temp_graph = G.copy()
                    dest_node = "__dest__"
                    temp_graph.add_node(dest_node, lat=dest_lat, lon=dest_lon)

                    dest_candidates = nearest_stops(dest_lat, dest_lon, k=8)
                    max_dest_walk_m = 400
                    for stop_id, stop_lat, stop_lon in dest_candidates:
                        dist_km = haversine_km(dest_lat, dest_lon, stop_lat, stop_lon)
                        dist_m = dist_km * 1000
                        if dist_m > max_dest_walk_m:
                            continue
                        walk_time = max(dist_m / 1.4, 60)
                        temp_graph.add_edge(
                            stop_id,
                            dest_node,
                            weight=walk_time,
                            travel_time_sec=walk_time,
                            mode="walk",
                        )

                    best = {"route": None, "cost": float("inf")}
                    best_start = None
                    event_dt = datetime.strptime(event_time, "%Y-%m-%d %H:%M")
                    guess_departure = event_dt - timedelta(minutes=30)
                    start_time_sec = (
                        guess_departure.hour * 3600
                        + guess_departure.minute * 60
                        + guess_departure.second
                    )

                    for origin_stop, stop_lat, stop_lon in origin_candidates:
                        for dest_stop, dest_stop_lat, dest_stop_lon in dest_candidates:
                            if origin_stop == dest_stop:
                                continue
                            route, cost = find_route_with_penalty(
                                temp_graph,
                                origin_stop,
                                dest_node,
                                start_time_sec=start_time_sec,
                                schedule_index=schedule_index,
                                route_delay_map=st.session_state.get("realtime_route_delays", {}),
                                dest_coords=(dest_lat, dest_lon),
                            )
                            if route and cost < best["cost"]:
                                best = {"route": route, "cost": cost}
                                best_start = (origin_stop, stop_lat, stop_lon)

                    if best["route"] is None:
                        st.sidebar.error("No route found between nearby stops")
                        st.session_state.route = None
                    else:
                        origin_stop, stop_lat, stop_lon = best_start
                        if origin_stop is None:
                            st.sidebar.error("No valid start stop found")
                            st.session_state.route = None
                        else:
                            try:
                                route, travel_time, delay, departure = compute_departure(
                                    origin_stop,
                                    dest_node,
                                    event_time,
                                    graph=temp_graph,
                                    schedule_index=schedule_index,
                                    route_delay_map=st.session_state.get("realtime_route_delays", {}),
                                    dest_coords=(dest_lat, dest_lon),
                                )

                                walk_to_start_km = haversine_km(
                                    origin_lat, origin_lon, stop_lat, stop_lon
                                )
                                walk_from_end_km = 0.0
                                last_stop_id = None
                                for stop_id in reversed(route):
                                    if stop_id in stops["stop_id"].values:
                                        last_stop_id = stop_id
                                        break
                                if last_stop_id is not None:
                                    last_stop = stops[stops["stop_id"] == last_stop_id].iloc[0]
                                    walk_from_end_km = haversine_km(
                                        last_stop["stop_lat"],
                                        last_stop["stop_lon"],
                                        dest_lat,
                                        dest_lon,
                                    )

                                walk_edges_sec = 0.0
                                for i in range(len(route) - 1):
                                    u = route[i]
                                    v = route[i + 1]
                                    edge = temp_graph.get_edge_data(u, v, default={})
                                    if edge.get("mode") == "walk":
                                        walk_edges_sec += float(edge.get("travel_time_sec", edge.get("weight", 0.0)) or 0.0)

                                # assume 5 km/h walking speed for off-graph legs
                                walk_to_start_sec = (walk_to_start_km * 1000) / 1.4
                                walk_from_end_sec = (walk_from_end_km * 1000) / 1.4
                                walk_time_min = (walk_edges_sec + walk_to_start_sec + walk_from_end_sec) / 60.0

                                st.session_state.route = route
                                st.session_state.travel_time = travel_time
                                st.session_state.delay = delay
                                st.session_state.departure = departure
                                st.session_state.walk_to_start_km = walk_to_start_km
                                st.session_state.walk_from_end_km = walk_from_end_km
                                st.session_state.walk_time_min = walk_time_min
                                st.session_state.origin_coords = (origin_lat, origin_lon)
                                st.session_state.dest_coords = (dest_lat, dest_lon)
                                st.session_state.temp_graph = temp_graph

                                st.sidebar.success("Route calculated")

                            except Exception as e:

                                st.sidebar.error(f"Routing failed: {e}")
                                st.session_state.route = None


route_coords = []
filtered_vehicles = pd.DataFrame()

# Prepare journey alternatives for display
alternatives = []
if st.session_state.otp_used and st.session_state.otp_steps:
    alternatives = st.session_state.otp_alternatives or []
    if not alternatives:
        alternatives = [
            {
                "steps": st.session_state.otp_steps,
                "metrics": {
                    "travel_time_min": st.session_state.travel_time or 0.0,
                    "walking_time_min": st.session_state.walk_time_min or 0.0,
                    "transfers": 0,
                },
                "crowd_label": st.session_state.otp_crowd_label or "Low",
                "departure": st.session_state.departure,
                "legs": st.session_state.otp_itinerary.get("legs", []) if st.session_state.otp_itinerary else [],
                "stop_ids": st.session_state.otp_stop_ids,
            }
        ]

# Build OTP route on map
if st.session_state.otp_used and st.session_state.otp_steps and alternatives:
    selected_idx = st.session_state.get("otp_selected_idx", 0)
    selected_alt = alternatives[min(selected_idx, len(alternatives) - 1)]
    
    if st.session_state.origin_coords and st.session_state.dest_coords:
        map_stops = gtfs.get("stops") if gtfs.get("stops") is not None and not gtfs.get("stops").empty else stops
        map_trips = gtfs.get("trips") if gtfs.get("trips") is not None and not gtfs.get("trips").empty else trips
        map_stop_times = gtfs.get("stop_times") if gtfs.get("stop_times") is not None and not gtfs.get("stop_times").empty else stop_times
        map_shapes = gtfs.get("shapes") if gtfs.get("shapes") is not None and not gtfs.get("shapes").empty else shapes
        map_stop_name_to_id = gtfs_stop_name_to_id if gtfs_stop_name_to_id else stop_name_to_id

        otp_segments = build_otp_route_segments(
            selected_alt.get("legs", []),
            map_stop_name_to_id,
            map_stops,
            st.session_state.origin_coords,
            st.session_state.dest_coords,
            map_trips,
            map_stop_times,
            map_shapes,
        )
        if otp_segments:
            all_points = []
            for seg in otp_segments:
                if "leg" in seg:
                    color = pick_leg_color(seg["leg"])
                    dash = "6 6" if seg["mode"].upper() == "WALK" else None
                    weight = 5 if seg["mode"].upper() == "WALK" else 6
                else:
                    color = seg.get("color", "#3388ff")
                    dash = None
                    weight = 6
                opacity = 0.85 if seg.get("mode", "").upper() == "WALK" else 0.95
                folium.PolyLine(
                    seg["points"],
                    color=color,
                    weight=weight,
                    opacity=opacity,
                    dash_array=dash,
                ).add_to(m)
                all_points.extend(seg["points"])
            if all_points:
                fit_map_to_points(m, all_points)

        folium.Marker(
            st.session_state.origin_coords,
            popup="Start",
            icon=folium.Icon(color="green")
        ).add_to(m)
        folium.Marker(
            st.session_state.dest_coords,
            popup="Destination",
            icon=folium.Icon(color="red")
        ).add_to(m)

        legs = selected_alt.get("legs", [])

        # Show all route stops as colored dots (prefer leg coords for service-specific colors)
        selected_stop_ids = selected_alt.get("stop_ids", st.session_state.otp_stop_ids)
        stop_points = []
        if legs:
            colored = []
            for leg in legs:
                mode = str(leg.get("mode", "")).upper()
                if mode == "WALK":
                    continue
                color = pick_leg_color(leg)
                frm = leg.get("from", {}) or {}
                to = leg.get("to", {}) or {}
                if frm.get("lat") is not None and frm.get("lon") is not None:
                    colored.append((float(frm.get("lat")), float(frm.get("lon")), color))
                for stop in leg.get("intermediateStops") or []:
                    if stop.get("lat") is not None and stop.get("lon") is not None:
                        colored.append((float(stop.get("lat")), float(stop.get("lon")), color))
                if to.get("lat") is not None and to.get("lon") is not None:
                    colored.append((float(to.get("lat")), float(to.get("lon")), color))
            seen = set()
            for lat, lon, color in colored:
                key = (round(lat, 6), round(lon, 6), color)
                if key in seen:
                    continue
                seen.add(key)
                stop_points.append((lat, lon))
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=7,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.95,
                    popup="Stop",
                ).add_to(m)
        elif selected_stop_ids:
            for stop_id in selected_stop_ids:
                stop_row = stops[stops["stop_id"] == stop_id]
                if stop_row.empty:
                    continue
                lat = stop_row.iloc[0]["stop_lat"]
                lon = stop_row.iloc[0]["stop_lon"]
                stop_points.append((lat, lon))
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=7,
                    color="#b91c1c",
                    fill=True,
                    fill_color="#ef4444",
                    fill_opacity=0.95,
                    popup=str(stop_row.iloc[0].get("stop_name", "stop")),
                ).add_to(m)

        # Highlight transfer points when possible
        prev_transit = False
        for leg in legs:
            mode = leg.get("mode", "WALK")
            if mode == "WALK":
                prev_transit = False
                continue
            if prev_transit:
                from_name = (leg.get("from", {}) or {}).get("name")
                if from_name:
                    stop_id = stop_name_to_id.get(str(from_name).strip().lower())
                    if stop_id:
                        stop_row = stops[stops["stop_id"] == stop_id]
                        if not stop_row.empty:
                            lat = stop_row.iloc[0]["stop_lat"]
                            lon = stop_row.iloc[0]["stop_lon"]
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=6,
                                color="orange",
                                fill=True,
                                fill_opacity=0.9,
                                popup=f"Transfer at {from_name}",
                            ).add_to(m)
            prev_transit = True

        # Highlight congested stops on the selected OTP route
        selected_stop_ids = selected_alt.get("stop_ids", st.session_state.otp_stop_ids)
        if selected_stop_ids and CONGESTION_ALERT is not None:
            congested = congestion[
                (congestion["stop_id"].isin(selected_stop_ids))
                & (congestion["congestion_score"] >= CONGESTION_ALERT)
            ]
            for _, row in congested.iterrows():
                stop_row = stops[stops["stop_id"] == row["stop_id"]]
                if stop_row.empty:
                    continue
                lat = stop_row.iloc[0]["stop_lat"]
                lon = stop_row.iloc[0]["stop_lon"]
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color="red",
                    fill=True,
                    fill_opacity=0.85,
                    popup=f"Congestion near {stop_row.iloc[0].get('stop_name','stop')}",
                ).add_to(m)

elif st.session_state.route:
    # Handle local routing - draw route on map
    route_coords = get_route_coordinates(st.session_state.route, stops)

    if route_coords:
        folium.PolyLine(
            route_coords,
            color="blue",
            weight=6,
            opacity=0.9
        ).add_to(m)
        fit_map_to_points(m, route_coords)

        start_coords = st.session_state.origin_coords or route_coords[0]
        end_coords = st.session_state.dest_coords or route_coords[-1]

        folium.Marker(
            start_coords,
            popup="Start",
            icon=folium.Icon(color="green")
        ).add_to(m)

        folium.Marker(
            end_coords,
            popup="Destination",
            icon=folium.Icon(color="red")
        ).add_to(m)

        for c in route_coords:
            folium.CircleMarker(
                location=c,
                radius=4,
                color="yellow",
                fill=True,
                fill_opacity=0.9
            ).add_to(m)

        # Highlight congested stops on the selected local route
        if CONGESTION_ALERT is not None:
            congested = congestion[
                (congestion["stop_id"].isin(st.session_state.route))
                & (congestion["congestion_score"] >= CONGESTION_ALERT)
            ]
            for _, row in congested.iterrows():
                stop_row = stops[stops["stop_id"] == row["stop_id"]]
                if stop_row.empty:
                    continue
                lat = stop_row.iloc[0]["stop_lat"]
                lon = stop_row.iloc[0]["stop_lon"]
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color="red",
                    fill=True,
                    fill_opacity=0.85,
                    popup=f"Congestion near {stop_row.iloc[0].get('stop_name','stop')}",
                ).add_to(m)

        route_key = (
            origin_place.strip() if origin_place else "",
            destination_place.strip() if destination_place else "",
            event_time,
        )

        vehicles = get_realtime_vehicles_for_route(
            route_key,
            st.session_state.route,
            stop_times,
            trips,
        )

        if st.session_state.get("realtime_error"):
            st.session_state.realtime_error_msg = f"Live GTFS-Realtime unavailable ({st.session_state.realtime_error})"
        else:
            source = st.session_state.get("realtime_source")
            if source == "api":
                st.session_state.realtime_msg = "Live GTFS-Realtime loaded"
            elif source == "csv":
                st.session_state.realtime_msg = "Using cached realtime data"

        filtered_vehicles = vehicles_near_route(vehicles, route_coords)


# ---------------------------------------------------
# ANIMATE VEHICLES & BUILD MAP
# ---------------------------------------------------

if not filtered_vehicles.empty:
    bus_geojson = create_vehicle_animation_for_mode(filtered_vehicles, "bus")
    luas_geojson = create_vehicle_animation_for_mode(filtered_vehicles, "luas")

    if bus_geojson["features"]:
        TimestampedGeoJson(
            bus_geojson,
            period="PT1M",
            add_last_point=True,
            auto_play=True,
            loop=True,
            max_speed=1,
            loop_button=True,
        ).add_to(m)

    if luas_geojson["features"]:
        TimestampedGeoJson(
            luas_geojson,
            period="PT1M",
            add_last_point=True,
            auto_play=True,
            loop=True,
            max_speed=1,
            loop_button=True,
        ).add_to(m)


# ---------------------------------------------------
# TWO-COLUMN LAYOUT (Google Maps Style)
# ---------------------------------------------------

# Create two-column layout: map (left) and details (right)
col_map, col_details = st.columns([0.7, 0.3], gap="small")

# LEFT COLUMN: MAP
with col_map:
    st_folium(m, width=None, height=700)

# RIGHT COLUMN: DETAILS PANEL  
with col_details:
    # Show results or empty state
    if st.session_state.otp_used and st.session_state.otp_steps and alternatives:
        selected_idx = st.session_state.get("otp_selected_idx", 0)
        
        if selected_idx < len(alternatives):
            selected_alt = alternatives[selected_idx]
        elif alternatives:
            selected_alt = alternatives[0]
        else:
            selected_alt = None
        
        if selected_alt:
            metrics = selected_alt.get("metrics", {})
            
            # Journey Details
            render_details(
                travel_time=metrics.get('travel_time_min', 0),
                walking_time=metrics.get('walking_time_min', 0),
                transfers=metrics.get('transfers', 0),
                departure=st.session_state.departure.strftime('%H:%M') if st.session_state.departure else 'N/A',
                crowding=st.session_state.otp_crowd_label or 'Medium',
                steps=selected_alt.get('steps', []),
                alternatives=alternatives
            )
    
    elif st.session_state.route:
        # Local routing results
        render_details(
            travel_time=st.session_state.travel_time,
            walking_time=st.session_state.walk_time_min or 0,
            transfers=0,
            departure=st.session_state.departure.strftime('%H:%M') if st.session_state.departure else 'N/A',
            crowding='Medium',
            steps=[],
            alternatives=[]
        )
    
    else:
        # Empty state
        render_empty()

