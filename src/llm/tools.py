"""
Tool wrappers for the travel planning agent.

Interfaces with OTP, event database, and other project services.
"""

import os
import json
import io
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from geopy.geocoders import Nominatim
from src.llm.state import Event, Route
import logging

logger = logging.getLogger(__name__)
ROUTE_TOOL_VERSION = "schema_v3_labeled_only"

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVENTS_PATH = os.path.join(BASE_DIR, "data/features/event_demand.csv")
STOPS_PATH = os.path.join(BASE_DIR, "data/clean/stops.csv")
OTP_URL = os.getenv("OTP_BASE_URL", "http://localhost:8080")
OTP_GRAPHQL_URL = os.getenv("OTP_GRAPHQL_URL", "http://localhost:8080/otp/gtfs/v1")
OTP_ROUTER = os.getenv("OTP_ROUTER", "default")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes"}
GRAPHHOPPER_URL = os.getenv("GRAPHHOPPER_URL", "http://localhost:8989")
GRAPHHOPPER_PROFILE = os.getenv("GRAPHHOPPER_PROFILE", "foot")
GRAPHHOPPER_TIMEOUT = int(os.getenv("GRAPHHOPPER_TIMEOUT_SECONDS", "15"))

# Failte Ireland Open Data APIs
FAILTE_BASE = os.getenv("FAILTE_BASE_URL", "https://failteireland.azure-api.net/opendata-api/v2")
FAILTE_ACCOM_URL = os.getenv("FAILTE_ACCOM_URL", f"{FAILTE_BASE}/accommodation")
FAILTE_ATTRACTIONS_URL = os.getenv("FAILTE_ATTRACTIONS_URL", f"{FAILTE_BASE}/attractions/csv")
FAILTE_TIMEOUT = int(os.getenv("FAILTE_TIMEOUT", "30"))
FAILTE_CACHE_TTL = int(os.getenv("FAILTE_CACHE_TTL_SECONDS", "21600"))
OSM_GEOCODE_TIMEOUT = int(os.getenv("OSM_GEOCODE_TIMEOUT_SECONDS", "8"))
ACCOM_CACHE_PATH = os.getenv(
    "ACCOM_CACHE_PATH",
    os.path.join(BASE_DIR, "data", "cache", "accommodations_geocoded.csv"),
)
ATTRACTIONS_CACHE_PATH = os.getenv(
    "ATTRACTIONS_CACHE_PATH",
    os.path.join(BASE_DIR, "data", "cache", "attractions_geocoded.csv"),
)

_events_cache = None
_stops_cache = None
_geocoder = None
_geocode_cache: Dict[str, Optional[Tuple[float, float]]] = {}
_geocode_osm_cache: Dict[str, Optional[Tuple[float, float]]] = {}
_reverse_geocode_cache: Dict[Tuple[float, float], Optional[Dict[str, Any]]] = {}
_otp_schema_cache: Dict[str, List[str]] = {}
_service_bbox = None
_routes_cache = None
_agency_cache = None
_accom_cache: Optional[List[Dict[str, Any]]] = None
_accom_cache_time: Optional[float] = None
_attractions_cache: Optional[List[Dict[str, Any]]] = None
_attractions_cache_time: Optional[float] = None
_gtfs_cache: Dict[str, Any] = {}


def _decode_polyline(encoded: str) -> list[tuple[float, float]]:
    if not encoded:
        return []
    coords: list[tuple[float, float]] = []
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


def _get_service_bbox() -> Optional[Tuple[float, float, float, float]]:
    """Compute service area bounding box from stops."""
    global _service_bbox
    if _service_bbox is not None:
        return _service_bbox
    stops = _load_stops()
    if stops.empty:
        return None
    try:
        min_lat = float(stops["stop_lat"].min())
        max_lat = float(stops["stop_lat"].max())
        min_lon = float(stops["stop_lon"].min())
        max_lon = float(stops["stop_lon"].max())
        _service_bbox = (min_lat, min_lon, max_lat, max_lon)
        return _service_bbox
    except Exception:
        return None


def _within_service_area(coords: Tuple[float, float], padding_deg: float = 0.15) -> bool:
    bbox = _get_service_bbox()
    if not bbox:
        return True
    lat, lon = coords
    min_lat, min_lon, max_lat, max_lon = bbox
    return (min_lat - padding_deg) <= lat <= (max_lat + padding_deg) and (min_lon - padding_deg) <= lon <= (max_lon + padding_deg)


def _load_events() -> pd.DataFrame:
    global _events_cache
    if _events_cache is None:
        try:
            _events_cache = pd.read_csv(EVENTS_PATH, engine="python", encoding_errors="replace")
        except Exception as e:
            logger.error(f"Failed to load events: {e}")
            return pd.DataFrame()
    return _events_cache


def _load_stops() -> pd.DataFrame:
    global _stops_cache
    if _stops_cache is None:
        try:
            _stops_cache = pd.read_csv(STOPS_PATH)
        except Exception as e:
            logger.error(f"Failed to load stops: {e}")
            return pd.DataFrame()
    return _stops_cache


def _load_gtfs_tables() -> Dict[str, pd.DataFrame]:
    if _gtfs_cache:
        return _gtfs_cache
    base = BASE_DIR
    candidates = [
        os.path.join(base, "data", "GTFS_All_extracted"),
        os.path.join(base, "otp", "graphs", "default", "GTFS_All_extracted"),
    ]
    folder = None
    for c in candidates:
        if os.path.exists(c):
            folder = c
            break
    if not folder:
        _gtfs_cache["stops"] = _load_stops()
        _gtfs_cache["trips"] = pd.DataFrame()
        _gtfs_cache["stop_times"] = pd.DataFrame()
        _gtfs_cache["shapes"] = pd.DataFrame()
        return _gtfs_cache
    def read_csv(name: str) -> pd.DataFrame:
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    _gtfs_cache["stops"] = read_csv("stops.txt")
    _gtfs_cache["trips"] = read_csv("trips.txt")
    _gtfs_cache["stop_times"] = read_csv("stop_times.txt")
    _gtfs_cache["shapes"] = read_csv("shapes.txt")
    return _gtfs_cache


def _nearest_stop_id(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    if lat is None or lon is None:
        return None
    tables = _load_gtfs_tables()
    stops = tables.get("stops")
    if stops is None or stops.empty:
        return None
    try:
        stops = stops.copy()
        stops["dist"] = (stops["stop_lat"].astype(float) - float(lat)) ** 2 + (stops["stop_lon"].astype(float) - float(lon)) ** 2
        row = stops.sort_values("dist").iloc[0]
        return str(row["stop_id"])
    except Exception:
        return None


def _stop_id_for_name(stop_name: Optional[str]) -> Optional[str]:
    if not stop_name:
        return None
    tables = _load_gtfs_tables()
    stops = tables.get("stops")
    if stops is None or stops.empty:
        return None
    name_lower = str(stop_name).strip().lower()
    try:
        match = stops[stops["stop_name"].str.lower() == name_lower]
        if not match.empty:
            return str(match.iloc[0]["stop_id"])
        contains = stops[stops["stop_name"].str.lower().str.contains(name_lower, na=False)]
        if not contains.empty:
            return str(contains.iloc[0]["stop_id"])
    except Exception:
        return None
    return None


def _shape_points_for_leg(
    route_gtfs_id: Optional[str],
    from_stop: Optional[str],
    to_stop: Optional[str],
    from_lat: Optional[float] = None,
    from_lon: Optional[float] = None,
    to_lat: Optional[float] = None,
    to_lon: Optional[float] = None,
) -> Optional[List[Tuple[float, float]]]:
    if not route_gtfs_id:
        return None
    tables = _load_gtfs_tables()
    trips = tables.get("trips")
    stop_times = tables.get("stop_times")
    shapes = tables.get("shapes")
    stops_df = tables.get("stops")
    if trips is None or stop_times is None or shapes is None:
        return None
    if trips.empty or stop_times.empty or shapes.empty:
        return None
    route_id = route_gtfs_id.split(":")[-1]
    from_id = _stop_id_for_name(from_stop) or _nearest_stop_id(from_lat, from_lon)
    to_id = _stop_id_for_name(to_stop) or _nearest_stop_id(to_lat, to_lon)
    try:
        trip_ids = trips[trips["route_id"].astype(str) == route_id]["trip_id"].astype(str).tolist()
    except Exception:
        return None
    if not trip_ids:
        return None

    def _stop_coords(stop_id: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        if not stop_id or stops_df is None or stops_df.empty:
            return None, None
        try:
            row = stops_df[stops_df["stop_id"].astype(str) == str(stop_id)]
            if row.empty:
                return None, None
            return float(row.iloc[0]["stop_lat"]), float(row.iloc[0]["stop_lon"])
        except Exception:
            return None, None

    def _shape_slice_by_nearest(shp: pd.DataFrame, start_lat: Optional[float], start_lon: Optional[float],
                                end_lat: Optional[float], end_lon: Optional[float]) -> Optional[List[Tuple[float, float]]]:
        if shp is None or shp.empty:
            return None
        if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
            return None
        try:
            shp = shp.sort_values("shape_pt_sequence")
        except Exception:
            pass
        try:
            pts = list(zip(shp["shape_pt_lat"].astype(float), shp["shape_pt_lon"].astype(float)))
        except Exception:
            return None
        if len(pts) < 2:
            return None
        def nearest_idx(lat: float, lon: float) -> int:
            best_i = 0
            best_d = None
            for i, (plat, plon) in enumerate(pts):
                d = (plat - lat) ** 2 + (plon - lon) ** 2
                if best_d is None or d < best_d:
                    best_d = d
                    best_i = i
            return best_i
        i_from = nearest_idx(float(start_lat), float(start_lon))
        i_to = nearest_idx(float(end_lat), float(end_lon))
        if i_from == i_to:
            return None
        if i_from > i_to:
            i_from, i_to = i_to, i_from
        sliced = pts[i_from:i_to + 1]
        return sliced if sliced else None

    def stop_sequence_points(st, idx_from, idx_to):
        if stops_df is None or stops_df.empty:
            return None
        seq_ids = st["stop_id"].astype(str).tolist()[idx_from:idx_to + 1]
        pts = []
        for sid in seq_ids:
            row = stops_df[stops_df["stop_id"].astype(str) == sid]
            if row.empty:
                continue
            try:
                pts.append((float(row.iloc[0]["stop_lat"]), float(row.iloc[0]["stop_lon"])))
            except Exception:
                continue
        return pts if pts else None

    for trip_id in trip_ids[:200]:
        st = stop_times[stop_times["trip_id"].astype(str) == trip_id]
        if st.empty:
            continue
        try:
            st = st.sort_values("stop_sequence")
        except Exception:
            pass
        stop_list = st["stop_id"].astype(str).tolist()
        idx_from = stop_list.index(from_id) if from_id in stop_list else None
        idx_to = stop_list.index(to_id) if to_id in stop_list else None
        if idx_from is not None and idx_to is not None and idx_from >= idx_to:
            continue
        trip_row = trips[trips["trip_id"].astype(str) == trip_id]
        if trip_row.empty:
            continue
        shape_id = str(trip_row.iloc[0].get("shape_id") or "")
        if not shape_id:
            if idx_from is not None and idx_to is not None:
                pts = stop_sequence_points(st, idx_from, idx_to)
                if pts:
                    return pts
            continue
        shp = shapes[shapes["shape_id"].astype(str) == shape_id]
        if shp.empty:
            if idx_from is not None and idx_to is not None:
                pts = stop_sequence_points(st, idx_from, idx_to)
                if pts:
                    return pts
            continue
        try:
            shp = shp.sort_values("shape_pt_sequence")
        except Exception:
            pass
        dist_slice = None
        if idx_from is not None and idx_to is not None and "shape_dist_traveled" in st.columns and "shape_dist_traveled" in shp.columns:
            try:
                from_dist = float(st.iloc[idx_from]["shape_dist_traveled"])
                to_dist = float(st.iloc[idx_to]["shape_dist_traveled"])
                if to_dist < from_dist:
                    from_dist, to_dist = to_dist, from_dist
                dist_slice = shp[(shp["shape_dist_traveled"] >= from_dist) & (shp["shape_dist_traveled"] <= to_dist)]
            except Exception:
                dist_slice = None

        if dist_slice is not None and not dist_slice.empty:
            pts = []
            for _, row in dist_slice.iterrows():
                try:
                    pts.append((float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
                except Exception:
                    continue
            if len(pts) >= 2:
                return pts

        # Prefer slicing the shape between the actual stop coordinates.
        start_lat, start_lon = _stop_coords(from_id)
        end_lat, end_lon = _stop_coords(to_id)
        if start_lat is None or start_lon is None:
            start_lat, start_lon = from_lat, from_lon
        if end_lat is None or end_lon is None:
            end_lat, end_lon = to_lat, to_lon
        pts = _shape_slice_by_nearest(shp, start_lat, start_lon, end_lat, end_lon)
        if pts:
            return pts

        if idx_from is not None and idx_to is not None:
            pts = stop_sequence_points(st, idx_from, idx_to)
            if pts:
                return pts
    return None


def _load_routes() -> pd.DataFrame:
    global _routes_cache
    if _routes_cache is not None:
        return _routes_cache
    routes_paths = [
        os.path.join(BASE_DIR, "data/GTFS_All_extracted/routes.txt"),
        os.path.join(BASE_DIR, "otp/graphs/default/GTFS_All_extracted/routes.txt"),
        os.path.join(BASE_DIR, "data/clean/routes.csv"),
    ]
    for path in routes_paths:
        if os.path.exists(path):
            try:
                _routes_cache = pd.read_csv(path)
                return _routes_cache
            except Exception:
                continue
    _routes_cache = pd.DataFrame()
    return _routes_cache


def _load_agency() -> pd.DataFrame:
    global _agency_cache
    if _agency_cache is not None:
        return _agency_cache
    agency_paths = [
        os.path.join(BASE_DIR, "data/GTFS_All_extracted/agency.txt"),
        os.path.join(BASE_DIR, "otp/graphs/default/GTFS_All_extracted/agency.txt"),
    ]
    for path in agency_paths:
        if os.path.exists(path):
            try:
                _agency_cache = pd.read_csv(path)
                return _agency_cache
            except Exception:
                continue
    _agency_cache = pd.DataFrame()
    return _agency_cache


def _load_accommodation_cache() -> Optional[pd.DataFrame]:
    path = ACCOM_CACHE_PATH
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _load_attractions_cache() -> Optional[pd.DataFrame]:
    path = ATTRACTIONS_CACHE_PATH
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _service_label_for_route(route_gtfs_id: Optional[str]) -> Optional[str]:
    if not route_gtfs_id:
        return None
    route_id = route_gtfs_id.split(":")[-1]
    routes = _load_routes()
    if routes.empty:
        return None
    row = routes[routes.get("route_id", "") == route_id]
    if row.empty:
        return None
    row = row.iloc[0]
    operator = str(row.get("operator", "")).strip().lower()
    agency_id = str(row.get("agency_id", "")).strip()
    # Prefer agency name if available (more specific)
    if agency_id:
        agency = _load_agency()
        if not agency.empty and "agency_id" in agency.columns:
            match = agency[agency["agency_id"].astype(str) == agency_id]
            if not match.empty:
                name = str(match.iloc[0].get("agency_name", "")).strip()
                if name:
                    name_lower = name.lower()
                    if "dublin express" in name_lower or "express" in name_lower:
                        return "Dublin Express"
                    if "dublin bus" in name_lower:
                        return "Dublin Bus"
                    if "luas" in name_lower:
                        return "Luas"
                    return name
                return None
    # Friendly operator names (fallback)
    if operator == "dublin_bus":
        return "Dublin Bus"
    if operator == "luas":
        return "Luas"
    return None


def _get_geocoder():
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(user_agent="dublin_transport_ai")
    return _geocoder


def geocode_cached(query: str) -> Optional[Tuple[float, float]]:
    q = (query or "").strip().lower()
    if not q:
        return None
    if q in _geocode_cache:
        return _geocode_cache[q]
    coords = _resolve_coordinates(query)
    _geocode_cache[q] = coords
    return coords


def geocode_osm(query: str) -> Optional[Tuple[float, float]]:
    """OSM-only geocode without GTFS stop override (for accommodations/attractions)."""
    q = (query or "").strip()
    if not q:
        return None
    key = q.lower()
    if key in _geocode_osm_cache:
        return _geocode_osm_cache[key]
    try:
        geocoder = _get_geocoder()
        loc = geocoder.geocode(
            q,
            timeout=OSM_GEOCODE_TIMEOUT,
            country_codes="ie",
            bounded=False,
        )
        if loc:
            lat, lon = loc.latitude, loc.longitude
            if 51.0 <= lat <= 56.0 and -11.0 <= lon <= -4.0:
                _geocode_osm_cache[key] = (lat, lon)
                return (lat, lon)
    except Exception:
        _geocode_osm_cache[key] = None
        return None
    _geocode_osm_cache[key] = None
    return None


def reverse_geocode_osm(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    key = (round(lat, 6), round(lon, 6))
    if key in _reverse_geocode_cache:
        return _reverse_geocode_cache[key]
    try:
        geocoder = _get_geocoder()
        loc = geocoder.reverse(
            (lat, lon),
            timeout=OSM_GEOCODE_TIMEOUT,
            addressdetails=True,
        )
        if not loc:
            _reverse_geocode_cache[key] = None
            return None
        address = loc.raw.get("address", {}) if hasattr(loc, "raw") else {}
        result = {
            "county": address.get("county") or address.get("state") or address.get("region"),
            "city": address.get("city") or address.get("town") or address.get("village"),
            "suburb": address.get("suburb") or address.get("neighbourhood"),
            "road": address.get("road"),
        }
        _reverse_geocode_cache[key] = result
        return result
    except Exception:
        _reverse_geocode_cache[key] = None
        return None


def _get_otp_input_fields(type_name: str) -> List[str]:
    if type_name in _otp_schema_cache:
        return _otp_schema_cache[type_name]
    try:
        query = """
        query($name: String!) {
          __type(name: $name) {
            inputFields { name }
          }
        }
        """
        resp = requests.post(
            OTP_GRAPHQL_URL,
            json={"query": query, "variables": {"name": type_name}},
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if not resp.ok:
            _otp_schema_cache[type_name] = []
            return []
        data = resp.json()
        fields = data.get("data", {}).get("__type", {}).get("inputFields", [])
        names = [f.get("name") for f in fields if f.get("name")]
        if not names and type_name == "PlanCoordinateInput":
            try:
                resp_alt = requests.post(
                    OTP_GRAPHQL_URL,
                    json={"query": query, "variables": {"name": "CoordinateValue"}},
                    timeout=10,
                    headers={"Content-Type": "application/json"},
                )
                if resp_alt.ok:
                    data_alt = resp_alt.json()
                    fields_alt = data_alt.get("data", {}).get("__type", {}).get("inputFields", [])
                    names = [f.get("name") for f in fields_alt if f.get("name")]
            except Exception:
                pass
        _otp_schema_cache[type_name] = names
        return names
    except Exception:
        _otp_schema_cache[type_name] = []
        return []


def _build_coordinate_value(coords: Tuple[float, float], fields: List[str]) -> Dict[str, float]:
    lat, lon = coords
    if "lat" in fields and "lon" in fields:
        return {"lat": lat, "lon": lon}
    if "latitude" in fields and "longitude" in fields:
        return {"latitude": lat, "longitude": lon}
    if "x" in fields and "y" in fields:
        return {"x": lon, "y": lat}
    if "lng" in fields and "lat" in fields:
        return {"lng": lon, "lat": lat}
    if "longitude" in fields and "latitude" in fields:
        return {"longitude": lon, "latitude": lat}
    # Default to latitude/longitude
    return {"latitude": lat, "longitude": lon}


def _build_plan_location_input(coords: Tuple[float, float], location_fields: List[str], coord_fields: List[str]) -> Dict[str, Any]:
    # PlanLocationInput is a OneOf: choose exactly one key
    if "coordinate" in location_fields:
        return {"coordinate": _build_coordinate_value(coords, coord_fields)}
    if "stopLocation" in location_fields:
        return {"stopLocation": None}
    return {"coordinate": _build_coordinate_value(coords, coord_fields)}


def _build_plan_labeled_location(coords: Tuple[float, float], label: str, labeled_fields: List[str], location_fields: List[str], coord_fields: List[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if "label" in labeled_fields:
        payload["label"] = label
    if "location" in labeled_fields:
        payload["location"] = _build_plan_location_input(coords, location_fields, coord_fields)
    return payload


def _build_datetime_input(dt: datetime, fields: List[str]) -> Dict[str, Any]:
    # Use ISO 8601 with UTC offset
    dt_iso = dt.isoformat()
    if dt.tzinfo is None:
        dt_iso = dt.replace(tzinfo=datetime.now().astimezone().tzinfo).isoformat()
    if "earliestDeparture" in fields:
        return {"earliestDeparture": dt_iso}
    if "latestArrival" in fields:
        return {"latestArrival": dt_iso}
    return {"earliestDeparture": dt_iso}


def _otp_graphql_urls(prefer_index: bool = False) -> List[str]:
    base = OTP_URL.rstrip("/")
    router = OTP_ROUTER
    urls: List[str] = []
    if OTP_GRAPHQL_URL:
        urls.append(OTP_GRAPHQL_URL.rstrip("/"))
    if prefer_index:
        urls.extend([
            f"{base}/otp/routers/{router}/index/graphql",
            f"{base}/routers/{router}/index/graphql",
            f"{base}/otp/index/graphql",
            f"{base}/index/graphql",
        ])
    urls.extend([
        f"{base}/otp/gtfs/v1",
        f"{base}/gtfs/v1",
        f"{base}/otp/routers/{router}/gtfs/v1",
        f"{base}/routers/{router}/gtfs/v1",
        f"{base}/otp/transmodel/v3",
        f"{base}/otp/routers/{router}/transmodel/index/graphql",
        f"{base}/routers/{router}/transmodel/index/graphql",
    ])
    seen = set()
    out = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _otp_rest_plan_points(origin_coords: Tuple[float, float], dest_coords: Tuple[float, float], dt: datetime) -> Optional[List[Tuple[float, float]]]:
    base_url = OTP_URL.rstrip("/")
    router = OTP_ROUTER
    if base_url.lower().endswith("/otp"):
        base_url = base_url[:-4]
    url_candidates = [
        f"{base_url}/otp/routers/{router}/plan",
        f"{base_url}/routers/{router}/plan",
        f"{base_url}/otp/plan",
        f"{base_url}/plan",
    ]
    date_str = dt.date().isoformat()
    time_str = dt.strftime("%H:%M:%S")
    params = {
        "fromPlace": f"{origin_coords[0]},{origin_coords[1]}",
        "toPlace": f"{dest_coords[0]},{dest_coords[1]}",
        "date": date_str,
        "time": time_str,
        "mode": "WALK,TRANSIT",
        "numItineraries": 1,
        "showIntermediateStops": "true",
        "additionalFields": "legGeometry",
    }
    headers = {"Accept": "application/json"}
    for url in url_candidates:
        try:
            resp = requests.get(url, params=params, timeout=15, headers=headers)
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
        legs = itineraries[0].get("legs") or []
        points: list[Tuple[float, float]] = []
        def add_point(lat, lon):
            if lat is None or lon is None:
                return
            pt = (float(lat), float(lon))
            if not points or points[-1] != pt:
                points.append(pt)
        for leg in legs:
            geom = (leg.get("legGeometry") or {}).get("points")
            if geom:
                for lat, lon in _decode_polyline(geom):
                    add_point(lat, lon)
                continue
            frm = leg.get("from") or {}
            to = leg.get("to") or {}
            add_point(frm.get("lat"), frm.get("lon"))
            for stop in leg.get("intermediateStops") or []:
                add_point(stop.get("lat"), stop.get("lon"))
            add_point(to.get("lat"), to.get("lon"))
        if points:
            return points
    return None


def _plan_route_rest(
    origin_coords: Tuple[float, float],
    dest_coords: Tuple[float, float],
    dt: datetime,
) -> Dict[str, Any]:
    base_url = OTP_URL.rstrip("/")
    router = OTP_ROUTER
    if base_url.lower().endswith("/otp"):
        base_url = base_url[:-4]
    url_candidates = [
        f"{base_url}/otp/routers/{router}/plan",
        f"{base_url}/routers/{router}/plan",
        f"{base_url}/otp/plan",
        f"{base_url}/plan",
    ]
    date_str = dt.date().isoformat()
    time_str = dt.strftime("%H:%M:%S")
    params = {
        "fromPlace": f"{origin_coords[0]},{origin_coords[1]}",
        "toPlace": f"{dest_coords[0]},{dest_coords[1]}",
        "date": date_str,
        "time": time_str,
        "mode": "WALK,TRANSIT",
        "numItineraries": 1,
        "showIntermediateStops": "true",
        "additionalFields": "legGeometry",
    }
    headers = {"Accept": "application/json"}
    last_error = None
    for url in url_candidates:
        try:
            resp = requests.get(url, params=params, timeout=20, headers=headers)
        except Exception as exc:
            last_error = f"REST request error: {exc}"
            continue
        if not resp.ok:
            last_error = f"REST server error ({resp.status_code})"
            continue
        try:
            data = resp.json()
        except Exception:
            last_error = "REST returned invalid JSON"
            continue
        plan = data.get("plan") or {}
        itineraries = plan.get("itineraries") or []
        if not itineraries:
            last_error = "No itineraries returned"
            continue
        itinerary = itineraries[0]
        route_points = _otp_rest_plan_points(origin_coords, dest_coords, dt)
        route_debug = f"rest:{len(route_points)}" if route_points else "rest:none"
        stop_points: list[Tuple[float, float]] = []
        total_time = itinerary.get("duration", 0) / 60.0
        legs = itinerary.get("legs", []) or []
        for leg in legs:
            mode = leg.get("mode", "UNKNOWN")
            frm = leg.get("from", {}) or {}
            to = leg.get("to", {}) or {}
            if mode != "WALK":
                if frm.get("lat") is not None and frm.get("lon") is not None:
                    stop_points.append((float(frm.get("lat")), float(frm.get("lon"))))
                for stop in leg.get("intermediateStops") or []:
                    if stop.get("lat") is not None and stop.get("lon") is not None:
                        stop_points.append((float(stop.get("lat")), float(stop.get("lon"))))
                if to.get("lat") is not None and to.get("lon") is not None:
                    stop_points.append((float(to.get("lat")), float(to.get("lon"))))
        walking_time, transfers, steps, service_types = _build_route_steps_from_legs(legs)
        seen = set()
        stop_points = [pt for pt in stop_points if not ((round(pt[0], 6), round(pt[1], 6)) in seen or seen.add((round(pt[0], 6), round(pt[1], 6))))]
        start_time_ms = itinerary.get("startTime", 0)
        end_time_ms = itinerary.get("endTime", 0)
        try:
            departure_time = datetime.fromtimestamp(start_time_ms / 1000)
            arrival_time = datetime.fromtimestamp(end_time_ms / 1000)
        except Exception:
            departure_time = datetime.now()
            arrival_time = datetime.now()
        return {
            "success": True,
            "route": {
                "travel_time": total_time,
                "walking_time": walking_time,
                "transfers": transfers,
                "steps": steps,
                "departure": departure_time.strftime("%H:%M"),
                "arrival": arrival_time.strftime("%H:%M"),
                "service_types": service_types,
                "route_points": route_points or [],
                "stop_points": stop_points,
                "legs": legs,
                "route_debug": route_debug,
            },
            "error": None,
        }
    return {"success": False, "route": None, "error": last_error or "REST route request failed"}


def _otp_rest_walk_points(origin_coords: Tuple[float, float], dest_coords: Tuple[float, float], dt: Optional[datetime] = None) -> Optional[List[Tuple[float, float]]]:
    base_url = OTP_URL.rstrip("/")
    router = OTP_ROUTER
    if base_url.lower().endswith("/otp"):
        base_url = base_url[:-4]
    url_candidates = [
        f"{base_url}/otp/routers/{router}/plan",
        f"{base_url}/routers/{router}/plan",
        f"{base_url}/otp/plan",
        f"{base_url}/plan",
    ]
    if dt is None:
        dt = datetime.now()
    date_str = dt.date().isoformat()
    time_str = dt.strftime("%H:%M:%S")
    params = {
        "fromPlace": f"{origin_coords[0]},{origin_coords[1]}",
        "toPlace": f"{dest_coords[0]},{dest_coords[1]}",
        "date": date_str,
        "time": time_str,
        "mode": "WALK",
        "numItineraries": 1,
        "showIntermediateStops": "true",
        "additionalFields": "legGeometry",
    }
    headers = {"Accept": "application/json"}
    for url in url_candidates:
        try:
            resp = requests.get(url, params=params, timeout=10, headers=headers)
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
        legs = itineraries[0].get("legs") or []
        points: list[Tuple[float, float]] = []

        def add_point(lat, lon):
            if lat is None or lon is None:
                return
            pt = (float(lat), float(lon))
            if not points or points[-1] != pt:
                points.append(pt)

        for leg in legs:
            geom = (leg.get("legGeometry") or {}).get("points")
            if geom:
                for lat, lon in _decode_polyline(geom):
                    add_point(lat, lon)
                continue
            frm = leg.get("from") or {}
            to = leg.get("to") or {}
            add_point(frm.get("lat"), frm.get("lon"))
            for stop in leg.get("intermediateStops") or []:
                add_point(stop.get("lat"), stop.get("lon"))
            add_point(to.get("lat"), to.get("lon"))
        if points:
            return points
    return None


def _graphhopper_walk_points(
    origin_coords: Tuple[float, float],
    dest_coords: Tuple[float, float],
) -> Optional[List[Tuple[float, float]]]:
    base_url = GRAPHHOPPER_URL.rstrip("/")
    url_candidates = [
        f"{base_url}/route",
        f"{base_url}/api/1/route",
    ]
    params = [
        ("profile", GRAPHHOPPER_PROFILE),
        ("point", f"{origin_coords[0]},{origin_coords[1]}"),
        ("point", f"{dest_coords[0]},{dest_coords[1]}"),
        ("points_encoded", "false"),
        ("details", "street_name"),
    ]
    headers = {"Accept": "application/json"}
    for url in url_candidates:
        try:
            resp = requests.get(url, params=params, timeout=GRAPHHOPPER_TIMEOUT, headers=headers)
        except Exception:
            continue
        if not resp.ok:
            continue
        try:
            data = resp.json()
        except Exception:
            continue
        paths = data.get("paths") or []
        if not paths:
            continue
        coords = (((paths[0].get("points") or {}).get("coordinates")) or [])
        if not coords:
            continue
        try:
            # GraphHopper returns [lon, lat]
            return [(float(lat), float(lon)) for lon, lat in coords]
        except Exception:
            continue
    return None


def get_walk_path_tool(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> Dict[str, Any]:
    origin = (float(origin_lat), float(origin_lon))
    dest = (float(dest_lat), float(dest_lon))
    points = _graphhopper_walk_points(origin, dest)
    source = None
    if points:
        source = "graphhopper"
    if not points:
        points = _otp_rest_walk_points(origin, dest)
        if points:
            source = "otp"
    if not points:
        return {"success": False, "points": [], "source": None, "error": "No walking path returned"}
    return {"success": True, "points": points, "source": source, "error": None}


def _densify_with_street(points: List[Tuple[float, float]]) -> Optional[List[Tuple[float, float]]]:
    if not points or len(points) < 2:
        return None
    densified: list[Tuple[float, float]] = []
    max_pairs = 25
    for i in range(min(len(points) - 1, max_pairs)):
        a = points[i]
        b = points[i + 1]
        segment = _otp_rest_walk_points(a, b)
        if segment:
            if densified and segment and densified[-1] == segment[0]:
                densified.extend(segment[1:])
            else:
                densified.extend(segment)
        else:
            if not densified or densified[-1] != a:
                densified.append(a)
            densified.append(b)
    return densified if densified else None


def _plan_route_legacy_graphql(urls: List[str], origin_coords: Tuple[float, float], dest_coords: Tuple[float, float], dt: datetime, arrive_by: bool = False) -> Dict[str, Any]:
    lat1, lon1 = origin_coords
    lat2, lon2 = dest_coords
    date_str = dt.date().isoformat()
    time_str = dt.strftime("%H:%M:%S")
    from_place = f"WGS84({lon1},{lat1})"
    to_place = f"WGS84({lon2},{lat2})"
    arrive_by_clause = "arriveBy: true" if arrive_by else ""
    query = f"""
    {{
      plan(
        fromPlace: \"{from_place}\"
        toPlace: \"{to_place}\"
        date: \"{date_str}\"
        time: \"{time_str}\"
        {arrive_by_clause}
        modes: [TRANSIT, WALK]
        first: 3
      ) {{
        itineraries {{
          duration
          startTime
          endTime
          walkDistance
          legs {{
            mode
            distance
            duration
            startTime
            endTime
            from {{ name lat lon }}
            to {{ name lat lon }}
            intermediateStops {{ name lat lon }}
            route {{ gtfsId shortName longName }}
          }}
        }}
      }}
    }}
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    last_error = None
    for url in urls:
        try:
            resp = requests.post(url, json={"query": query}, headers=headers, timeout=20)
        except Exception as exc:
            last_error = f"GraphQL request error: {exc}"
            continue
        if not resp.ok:
            last_error = f"OTP server error ({resp.status_code})"
            continue
        try:
            data = resp.json()
        except Exception:
            last_error = "OTP returned invalid JSON"
            continue
        if data.get("errors"):
            last_error = f"OTP error: {data['errors']}"
            continue
        itineraries = data.get("data", {}).get("plan", {}).get("itineraries", [])
        if not itineraries:
            last_error = "No itineraries returned"
            continue
        itinerary = itineraries[0]
        route_points = _otp_rest_plan_points(origin_coords, dest_coords, dt)
        stop_points: list[Tuple[float, float]] = []
        route_debug = None
        if route_points:
            route_debug = f"rest:{len(route_points)}"
        if not route_points:
            points: list[Tuple[float, float]] = []
            def add_point(lat, lon):
                if lat is None or lon is None:
                    return
                pt = (float(lat), float(lon))
                if not points or points[-1] != pt:
                    points.append(pt)
            for leg in itinerary.get("legs", []):
                frm = leg.get("from", {})
                to = leg.get("to", {})
                mode = leg.get("mode")
                route_info = leg.get("route") or {}
                if mode and mode != "WALK":
                    if frm.get("lat") is not None and frm.get("lon") is not None:
                        stop_points.append((float(frm.get("lat")), float(frm.get("lon"))))
                    for stop in leg.get("intermediateStops") or []:
                        if stop.get("lat") is not None and stop.get("lon") is not None:
                            stop_points.append((float(stop.get("lat")), float(stop.get("lon"))))
                    if to.get("lat") is not None and to.get("lon") is not None:
                        stop_points.append((float(to.get("lat")), float(to.get("lon"))))
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
                        for lat, lon in shape_pts:
                            add_point(lat, lon)
                        continue
                add_point(frm.get("lat"), frm.get("lon"))
                add_point(to.get("lat"), to.get("lon"))
            if points:
                route_points = points
                route_debug = "gtfs:{}".format(len(points))
        if route_debug is None:
            route_debug = "none"
        if route_points and route_debug.startswith("stops"):
            street_pts = _densify_with_street(route_points)
            if street_pts:
                route_points = street_pts
                route_debug = f"street:{len(street_pts)}"
        if stop_points:
            seen = set()
            deduped = []
            for lat, lon in stop_points:
                key = (round(lat, 6), round(lon, 6))
                if key not in seen:
                    seen.add(key)
                    deduped.append((lat, lon))
            stop_points = deduped
        total_time = itinerary.get("duration", 0) / 60.0
        walking_time, transfers, steps, service_types = _build_route_steps_from_legs(itinerary.get("legs", []))

        start_time_ms = itinerary.get("legs", [{}])[0].get("startTime", 0)
        end_time_ms = itinerary.get("legs", [{}])[-1].get("endTime", 0)
        try:
            departure_time = datetime.fromtimestamp(start_time_ms / 1000)
            arrival_time = datetime.fromtimestamp(end_time_ms / 1000)
        except Exception:
            departure_time = datetime.now()
            arrival_time = datetime.now()

        return {
            "success": True,
            "route": {
                "travel_time": total_time,
                "walking_time": walking_time,
                "transfers": transfers,
                "steps": steps,
                "departure": departure_time.strftime("%H:%M"),
                "arrival": arrival_time.strftime("%H:%M"),
                "service_types": service_types,
                "route_points": route_points or [],
                "stop_points": stop_points,
                "legs": itinerary.get("legs", []),
                "route_debug": route_debug,
            },
            "error": None,
        }

    return {"success": False, "route": None, "error": last_error or "OTP GraphQL request failed"}


def _resolve_coordinates(place: str) -> Optional[Tuple[float, float]]:
    if not place:
        return None
    raw = place.strip()
    # Prefer local GTFS stop names to avoid geocoding to the wrong town
    try:
        stops = _load_stops()
        if not stops.empty:
            name_col = "stop_name"
            if name_col in stops.columns:
                raw_lower = raw.lower()
                exact = stops[stops[name_col].str.lower() == raw_lower]
                if not exact.empty:
                    row = exact.iloc[0]
                    return (float(row["stop_lat"]), float(row["stop_lon"]))
                contains = stops[stops[name_col].str.lower().str.contains(raw_lower, na=False)]
                if not contains.empty:
                    row = contains.iloc[0]
                    return (float(row["stop_lat"]), float(row["stop_lon"]))
    except Exception:
        pass
    if "," in raw:
        parts = raw.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                return (lat, lon)
            except Exception:
                pass
    query_variants = [raw]
    raw_lower = raw.lower()
    if "ireland" not in raw_lower:
        query_variants.append(f"{raw}, Ireland")
    if "dublin" in raw_lower and "ireland" not in raw_lower:
        query_variants.append(f"{raw}, Dublin, Ireland")
    # Try progressively simpler address fragments so full campus/business addresses
    # still resolve to a useful area that can be snapped to transit.
    if "," in raw:
        fragments = [p.strip() for p in raw.split(",") if p.strip()]
        for i in range(len(fragments)):
            fragment = ", ".join(fragments[i:])
            if fragment and fragment not in query_variants:
                query_variants.append(fragment)
            if "ireland" not in fragment.lower() and f"{fragment}, Ireland" not in query_variants:
                query_variants.append(f"{fragment}, Ireland")
        for fragment in fragments:
            if fragment not in query_variants:
                query_variants.append(fragment)
            if "ireland" not in fragment.lower() and f"{fragment}, Ireland" not in query_variants:
                query_variants.append(f"{fragment}, Ireland")
    # Also try road/postal district style fragments.
    token_variants = []
    for token in [t.strip() for t in raw.replace(",", " ").split() if t.strip()]:
        if token.lower() in {"road", "rd", "street", "st", "dublin", "ireland"}:
            continue
        token_variants.append(token)
    if len(token_variants) >= 2:
        for width in range(min(4, len(token_variants)), 1, -1):
            fragment = " ".join(token_variants[:width])
            if fragment not in query_variants:
                query_variants.append(fragment)
            if f"{fragment}, Dublin, Ireland" not in query_variants:
                query_variants.append(f"{fragment}, Dublin, Ireland")
    try:
        geocoder = _get_geocoder()
        for query in query_variants:
            loc = geocoder.geocode(
                query,
                timeout=10,
                country_codes="ie",
                bounded=False,
                addressdetails=True,
            )
            if not loc:
                continue
            lat, lon = loc.latitude, loc.longitude
            if 51.0 <= lat <= 56.0 and -11.0 <= lon <= -4.0:
                return (lat, lon)
    except Exception:
        return None
    # Final fallback: match address fragments against stop names, then snap to that stop.
    try:
        stops = _load_stops()
        if not stops.empty and "stop_name" in stops.columns:
            fragments = [frag.strip().lower() for frag in raw.replace(",", " ").split() if len(frag.strip()) >= 4]
            preferred = []
            for frag in fragments:
                if frag in {"road", "nangor", "business", "campus", "dublin", "ireland"}:
                    continue
                matched = stops[stops["stop_name"].str.lower().str.contains(frag, na=False)]
                if not matched.empty:
                    preferred.append(matched.iloc[0])
            if preferred:
                row = preferred[0]
                return (float(row["stop_lat"]), float(row["stop_lon"]))
    except Exception:
        pass
    return None


# ============================================================================
# TOOL 1: Event Search
# ============================================================================

def get_events_tool(date_range: str, location: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    try:
        events_df = _load_events()
        if events_df.empty:
            return {"success": False, "events": [], "error": "No events available"}

        today = datetime.now().date()
        if date_range == "this_weekend":
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            start_date = today + timedelta(days=days_ahead)
            end_date = start_date + timedelta(days=2)
        elif date_range == "next_week":
            start_date = today + timedelta(days=7)
            end_date = start_date + timedelta(days=7)
        elif ":" in date_range:
            parts = date_range.split(":")
            start_date = datetime.fromisoformat(parts[0]).date()
            end_date = datetime.fromisoformat(parts[1]).date()
        else:
            start_date = datetime.fromisoformat(date_range).date()
            end_date = start_date + timedelta(days=1)

        events_df["start_date"] = pd.to_datetime(events_df["start_date"], errors="coerce")
        events_df["start_date_date"] = events_df["start_date"].dt.date
        filtered = events_df[(events_df["start_date_date"] >= start_date) & (events_df["start_date_date"] <= end_date)]
        if filtered.empty:
            return {"success": True, "events": [], "error": f"No events found for {date_range}"}

        filtered = filtered.nlargest(limit, "demand_score")
        events = []
        seen = set()
        for _, row in filtered.iterrows():
            event_key = (row["event_name"], row["event_lat"], row["event_lon"])
            if event_key not in seen:
                seen.add(event_key)
                start_dt = pd.to_datetime(row.get("start_date"), errors="coerce")
                if pd.isna(start_dt):
                    start_dt = datetime.combine(start_date, datetime.min.time())
                # Normalize midnight to 09:00 local for better routing defaults
                if start_dt.hour == 0 and start_dt.minute == 0 and start_dt.second == 0:
                    start_dt = start_dt.replace(hour=9, minute=0, second=0)
                events.append(Event(
                    name=str(row["event_name"]),
                    location=str(row.get("stop_name", "Dublin")),
                    datetime=str(start_dt),
                    lat=float(row["event_lat"]),
                    lon=float(row["event_lon"]),
                    stop_id=str(row.get("stop_id", "")),
                    stop_name=str(row.get("stop_name", "")),
                ))
        return {
            "success": True,
            "events": [
                {
                    "name": e.name,
                    "location": e.location,
                    "datetime": e.datetime,
                    "lat": e.lat,
                    "lon": e.lon,
                    "stop_id": e.stop_id,
                    "stop_name": e.stop_name,
                }
                for e in events[:limit]
            ],
            "error": None,
        }
    except Exception as e:
        logger.error(f"Error in get_events_tool: {e}")
        return {"success": False, "events": [], "error": str(e)}


# ============================================================================
# TOOL 2: Route Planning (OTP)
# ============================================================================

def _generate_demo_route(origin: str, destination: str, datetime_str: str = None) -> Dict[str, Any]:
    import random
    bus_routes = ["1", "4", "7", "15", "46A", "77A", "123", "747"]
    travel_time = random.randint(25, 120)
    walking_time = random.randint(5, 25)
    transfers = random.randint(0, 3)
    steps = [
        f"Walk to {origin.split(',')[0][:20]} stop (5 min)",
        f"Take Bus {random.choice(bus_routes)} towards city center (15 min)",
    ]
    if transfers > 0:
        for _ in range(transfers):
            steps.append(f"Transfer to Bus {random.choice(bus_routes)} (5 min wait)")
            steps.append(f"Take bus {random.choice(bus_routes)} (10 min)")
    steps.append("Walk to destination (5 min)")

    if datetime_str:
        try:
            dt = datetime.fromisoformat(datetime_str)
        except Exception:
            dt = datetime.now()
    else:
        dt = datetime.now()
        if dt.hour < 6:
            dt = dt.replace(hour=8, minute=0)

    departure = dt.strftime("%H:%M")
    arrival = (dt + timedelta(minutes=travel_time)).strftime("%H:%M")
    return {
        "success": True,
        "route": {
            "travel_time": travel_time,
            "walking_time": walking_time,
            "transfers": transfers,
            "steps": steps,
            "departure": departure,
            "arrival": arrival,
        },
        "error": None,
    }


def plan_route_tool(origin: str, destination: str, datetime_str: Optional[str] = None, preference: str = "balanced") -> Dict[str, Any]:
    try:
        origin_coords = _resolve_coordinates(origin)
        dest_coords = _resolve_coordinates(destination)
        if not origin_coords or not dest_coords:
            return {"success": False, "route": None, "error": "Could not resolve coordinates"}
        if not _within_service_area(origin_coords):
            return {"success": False, "route": None, "error": "Origin is outside the OTP service area."}
        if not _within_service_area(dest_coords):
            return {"success": False, "route": None, "error": "Destination is outside the OTP service area."}

        arrive_by = False
        if datetime_str:
            dt_text = datetime_str.strip()
            if "T" not in dt_text and " " not in dt_text and len(dt_text) == 10:
                dt_text = f"{dt_text}T09:00:00"
            else:
                arrive_by = True
            dt = datetime.fromisoformat(dt_text)
        else:
            dt = datetime.now()
            if dt.hour < 6:
                dt = dt.replace(hour=8, minute=0)

        rest_result = _plan_route_rest(origin_coords, dest_coords, dt)
        if rest_result["success"]:
            rest_result["source"] = "otp"
            return rest_result

        legacy_urls = _otp_graphql_urls(prefer_index=True)
        legacy_result = _plan_route_legacy_graphql(legacy_urls, origin_coords, dest_coords, dt, arrive_by=arrive_by)
        if legacy_result["success"]:
            legacy_result["source"] = "otp"
            return legacy_result

        labeled_fields = _get_otp_input_fields("PlanLabeledLocationInput")
        location_fields = _get_otp_input_fields("PlanLocationInput")
        coordinate_fields = _get_otp_input_fields("PlanCoordinateInput")
        datetime_fields = _get_otp_input_fields("PlanDateTimeInput")

        origin_input = _build_plan_labeled_location(origin_coords, "Origin", labeled_fields, location_fields, coordinate_fields)
        dest_input = _build_plan_labeled_location(dest_coords, "Destination", labeled_fields, location_fields, coordinate_fields)
        dt_input = _build_datetime_input(dt, datetime_fields)

        graphql_query = """
        query Plan($origin: PlanLabeledLocationInput!, $destination: PlanLabeledLocationInput!, $dateTime: PlanDateTimeInput!, $modes: PlanModesInput, $locale: Locale) {
          planConnection(origin: $origin, destination: $destination, dateTime: $dateTime, modes: $modes, locale: $locale) {
            edges {
              node {
                duration
                startTime
                endTime
                walkDistance
        legs {
          mode
          distance
          duration
          startTime
          endTime
          from { name lat lon }
          to { name lat lon }
          intermediateStops { name lat lon }
          route { gtfsId shortName longName }
        }
              }
            }
          }
        }
        """

        modes_fields = _get_otp_input_fields("PlanModesInput")
        modes_input = None
        if modes_fields:
            modes_input = {}
            if "accessMode" in modes_fields:
                modes_input["accessMode"] = "WALK"
            if "egressMode" in modes_fields:
                modes_input["egressMode"] = "WALK"
            if "directMode" in modes_fields:
                modes_input["directMode"] = "WALK"
            if "transferMode" in modes_fields:
                modes_input["transferMode"] = "WALK"
            if "transitModes" in modes_fields:
                modes_input["transitModes"] = [{"mode": "BUS"}, {"mode": "TRAM"}, {"mode": "RAIL"}]
            if "mode" in modes_fields:
                modes_input["mode"] = "TRANSIT"

        response = requests.post(
            OTP_GRAPHQL_URL,
            json={"query": graphql_query, "variables": {"origin": origin_input, "destination": dest_input, "dateTime": dt_input, "modes": modes_input, "locale": "en"}},
            timeout=30,
            headers={"Content-Type": "application/json"},
        )

        if not response.ok:
            snippet = (response.text or "").strip()
            if snippet:
                snippet = snippet[:300]
            return {
                "success": False,
                "route": None,
                "error": f"OTP server error ({response.status_code}) [tool={ROUTE_TOOL_VERSION} url={OTP_GRAPHQL_URL}] {snippet}",
            }

        try:
            data = response.json()
        except Exception:
            return {
                "success": False,
                "route": None,
                "error": f"OTP returned invalid JSON. Check OTP server logs. [tool={ROUTE_TOOL_VERSION} url={OTP_GRAPHQL_URL}]",
            }
        if data.get("errors"):
            return {
                "success": False,
                "route": None,
                "error": f"OTP error: {data['errors']} [tool={ROUTE_TOOL_VERSION} url={OTP_GRAPHQL_URL}]",
            }

        edges = data.get("data", {}).get("planConnection", {}).get("edges", [])
        if not edges:
            try:
                dist_km = _haversine_km(origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1])
            except Exception:
                dist_km = None
            if dist_km is not None and dist_km > 80:
                return {
                    "success": False,
                    "route": None,
                    "error": "No itineraries returned. The destination looks outside the current OTP service area.",
                }
            return {"success": False, "route": None, "error": "No itineraries returned"}

        itinerary = edges[0]["node"]
        legs_for_points = itinerary.get("legs", [])
        route_points = _otp_rest_plan_points(origin_coords, dest_coords, dt)
        stop_points: list[Tuple[float, float]] = []
        route_debug = None
        if route_points:
            route_debug = f"rest:{len(route_points)}"
        if not route_points and legs_for_points:
            points: list[Tuple[float, float]] = []
            used_shape = False
            def add_point(lat, lon):
                if lat is None or lon is None:
                    return
                pt = (float(lat), float(lon))
                if not points or points[-1] != pt:
                    points.append(pt)
            for leg in legs_for_points:
                frm = leg.get("from") or {}
                to = leg.get("to") or {}
                mode = leg.get("mode")
                route_info = leg.get("route") or {}
                if mode and mode != "WALK":
                    if frm.get("lat") is not None and frm.get("lon") is not None:
                        stop_points.append((float(frm.get("lat")), float(frm.get("lon"))))
                    for stop in leg.get("intermediateStops") or []:
                        if stop.get("lat") is not None and stop.get("lon") is not None:
                            stop_points.append((float(stop.get("lat")), float(stop.get("lon"))))
                    if to.get("lat") is not None and to.get("lon") is not None:
                        stop_points.append((float(to.get("lat")), float(to.get("lon"))))
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
                        used_shape = True
                        for lat, lon in shape_pts:
                            add_point(lat, lon)
                        continue
                add_point(frm.get("lat"), frm.get("lon"))
                for stop in leg.get("intermediateStops") or []:
                    add_point(stop.get("lat"), stop.get("lon"))
                add_point(to.get("lat"), to.get("lon"))
            if points:
                route_points = points
                if used_shape:
                    route_debug = "gtfs:{}".format(len(points))
                else:
                    route_debug = "stops:{}".format(len(points))
        if route_debug is None:
            route_debug = "none"
        if route_points and route_debug.startswith("stops"):
            street_pts = _densify_with_street(route_points)
            if street_pts:
                route_points = street_pts
                route_debug = f"street:{len(street_pts)}"
        if not stop_points:
            for leg in legs_for_points:
                if leg.get("mode") == "WALK":
                    continue
                frm = leg.get("from") or {}
                to = leg.get("to") or {}
                if frm.get("lat") is not None and frm.get("lon") is not None:
                    stop_points.append((float(frm.get("lat")), float(frm.get("lon"))))
                for stop in leg.get("intermediateStops") or []:
                    if stop.get("lat") is not None and stop.get("lon") is not None:
                        stop_points.append((float(stop.get("lat")), float(stop.get("lon"))))
                if to.get("lat") is not None and to.get("lon") is not None:
                    stop_points.append((float(to.get("lat")), float(to.get("lon"))))
        if stop_points:
            seen = set()
            deduped = []
            for lat, lon in stop_points:
                key = (round(lat, 6), round(lon, 6))
                if key not in seen:
                    seen.add(key)
                    deduped.append((lat, lon))
            stop_points = deduped
        total_time = itinerary.get("duration", 0) / 60.0
        walking_time, transfers, steps, service_types = _build_route_steps_from_legs(itinerary.get("legs", []))

        start_time_ms = itinerary.get("legs", [{}])[0].get("startTime", 0)
        end_time_ms = itinerary.get("legs", [{}])[-1].get("endTime", 0)
        try:
            departure_time = datetime.fromtimestamp(start_time_ms / 1000)
            arrival_time = datetime.fromtimestamp(end_time_ms / 1000)
        except Exception:
            departure_time = datetime.now()
            arrival_time = datetime.now()

        route = Route(
            origin=origin,
            destination=destination,
            travel_time=total_time,
            walking_time=walking_time,
            transfers=transfers,
            steps=steps,
            departure=departure_time.strftime("%H:%M"),
            arrival=arrival_time.strftime("%H:%M"),
            service_types=service_types,
            route_points=route_points or [],
            route_debug=route_debug,
        )

        result = {
            "success": True,
            "route": {
                "travel_time": route.travel_time,
                "walking_time": route.walking_time,
                "transfers": route.transfers,
                "steps": route.steps,
                "departure": route.departure,
                "arrival": route.arrival,
                "service_types": route.service_types,
                "route_points": route.route_points,
                "legs": itinerary.get("legs", []),
                "route_debug": route.route_debug,
            },
            "error": None,
        }
        result["source"] = "otp"
        return result

    except Exception as e:
        logger.error(f"Error in plan_route_tool: {e}")
        if DEMO_MODE:
            demo = _generate_demo_route(origin, destination, datetime_str)
            demo["source"] = "llm"
            return demo
        return {"success": False, "route": None, "error": str(e)}


# ============================================================================
# TOOL 3: Geocode helper
# ============================================================================

def geocode_tool(place: str) -> Dict[str, Any]:
    coords = _resolve_coordinates(place)
    if not coords:
        return {"success": False, "lat": None, "lon": None, "error": "Location not found"}
    nearest = get_nearest_stop(coords[0], coords[1])
    matched_name = None
    if nearest.get("success") and nearest.get("stop"):
        matched_name = nearest["stop"].get("stop_name")
    return {
        "success": True,
        "lat": coords[0],
        "lon": coords[1],
        "matched_name": matched_name,
        "error": None,
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _build_route_steps_from_legs(legs: List[dict]) -> Tuple[float, int, List[str], List[str]]:
    walking_time = 0.0
    transfers = 0
    steps: List[str] = []
    service_types: List[str] = []
    previous_transit_to: Optional[Tuple[dict, str]] = None

    for leg in legs or []:
        mode = str(leg.get("mode", "UNKNOWN")).upper()
        frm = leg.get("from", {}) or {}
        to = leg.get("to", {}) or {}

        if mode == "WALK":
            leg_duration = leg.get("duration", 0) / 60.0
            walking_time += leg_duration
            distance = leg.get("distance", 0)
            steps.append(f"Walk: {distance:.0f}m ({leg_duration:.1f} min)")
            previous_transit_to = None
            continue

        if previous_transit_to is not None:
            prev_to, prev_mode = previous_transit_to
            try:
                prev_lat = float(prev_to.get("lat"))
                prev_lon = float(prev_to.get("lon"))
                cur_lat = float(frm.get("lat"))
                cur_lon = float(frm.get("lon"))
                transfer_km = _haversine_km(prev_lat, prev_lon, cur_lat, cur_lon)
                transfer_m = transfer_km * 1000.0
                if transfer_m >= 35:
                    walk_minutes = max(1.0, transfer_m / 78.0)
                    walking_time += walk_minutes
                    steps.append(f"Walk transfer: {transfer_m:.0f}m ({walk_minutes:.1f} min)")
            except Exception:
                pass

        route_info = leg.get("route", {}) or {}
        route_name = (
            route_info.get("shortName")
            or route_info.get("longName")
            or leg.get("routeShortName")
            or leg.get("routeLongName")
            or mode
        )
        service_label = _service_label_for_route(route_info.get("gtfsId") or leg.get("routeId") or leg.get("gtfsId"))
        if service_label:
            route_name = f"{route_name} ({service_label})"
        from_name = frm.get("name", "Stop")
        to_name = to.get("name", "Stop")
        icon = "🚌" if mode == "BUS" else "🚊" if mode in {"TRAM", "TRAMWAY"} else "🚆" if mode in {"RAIL", "TRAIN"} else "🚍"
        steps.append(f"{icon} Take {route_name} from {from_name} to {to_name}")
        if service_label and service_label not in service_types:
            service_types.append(service_label)
        transfers += 1
        previous_transit_to = (to, mode)

    return walking_time, max(0, transfers - 1), steps, service_types


# ============================================================================
# TOOL 4: Nearest stop
# ============================================================================

def get_nearest_stop(lat: float, lon: float) -> Dict[str, Any]:
    stops = _load_stops()
    if stops.empty:
        return {"success": False, "stop": None, "error": "Stops data unavailable"}

    stops = stops.copy()
    stops["dist"] = ((stops["stop_lat"] - lat) ** 2 + (stops["stop_lon"] - lon) ** 2) ** 0.5
    row = stops.sort_values("dist").iloc[0]
    return {
        "success": True,
        "stop": {
            "stop_id": row.get("stop_id"),
            "stop_name": row.get("stop_name"),
            "stop_lat": row.get("stop_lat"),
            "stop_lon": row.get("stop_lon"),
        },
        "error": None,
    }


# ============================================================================
# TOOL 5: Failte Ireland Open Data APIs
# ============================================================================

def get_accommodations_tool(limit: int = 100) -> Dict[str, Any]:
    try:
        global _accom_cache, _accom_cache_time
        now_ts = datetime.now().timestamp()
        if _accom_cache is not None and _accom_cache_time is not None:
            if (now_ts - _accom_cache_time) <= FAILTE_CACHE_TTL:
                return {"success": True, "results": _accom_cache[:limit], "error": None}
        # Prefer precomputed cache (fast, accurate, no OSM calls)
        cache_df = _load_accommodation_cache()
        if cache_df is not None and not cache_df.empty:
            results = []
            for _, row in cache_df.iterrows():
                results.append({
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "address": row.get("address"),
                    "locality": row.get("locality"),
                    "region": row.get("region"),
                    "postalCode": row.get("postalCode"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "geocode_source": row.get("geocode_source"),
                })
            _accom_cache = results
            _accom_cache_time = now_ts
            return {"success": True, "results": results[:limit], "error": None}
        resp = requests.get(FAILTE_ACCOM_URL, headers={"Cache-Control": "no-cache"}, timeout=FAILTE_TIMEOUT)
        if not resp.ok:
            return {"success": False, "results": [], "error": f"HTTP {resp.status_code}"}
        data = resp.json()
        items = data.get("value", [])
        results = []
        for item in items:
            addr = item.get("address", {}) if isinstance(item, dict) else {}
            results.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "type": item.get("additionalType"),
                "address": addr.get("streetAddress"),
                "locality": addr.get("addressLocality"),
                "region": addr.get("addressRegion"),
                "postalCode": addr.get("postalCode"),
            })
        _accom_cache = results
        _accom_cache_time = now_ts
        return {"success": True, "results": results[:limit], "error": None}
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}


def get_attractions_tool(limit: int = 200) -> Dict[str, Any]:
    try:
        global _attractions_cache, _attractions_cache_time
        now_ts = datetime.now().timestamp()
        if _attractions_cache is not None and _attractions_cache_time is not None:
            if (now_ts - _attractions_cache_time) <= FAILTE_CACHE_TTL:
                return {"success": True, "results": _attractions_cache[:limit], "error": None}
        cache_df = _load_attractions_cache()
        if cache_df is not None and not cache_df.empty:
            results = []
            for _, row in cache_df.iterrows():
                results.append({
                    "name": row.get("name"),
                    "url": row.get("url"),
                    "telephone": row.get("telephone"),
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                    "address": row.get("address"),
                    "county": row.get("county"),
                    "photo": row.get("photo"),
                    "tags": row.get("tags"),
                })
            _attractions_cache = results
            _attractions_cache_time = now_ts
            return {"success": True, "results": results[:limit], "error": None}
        resp = requests.get(FAILTE_ATTRACTIONS_URL, headers={"Cache-Control": "no-cache"}, timeout=FAILTE_TIMEOUT)
        if not resp.ok:
            return {"success": False, "results": [], "error": f"HTTP {resp.status_code}"}
        text = resp.text
        df = pd.read_csv(io.StringIO(text), encoding_errors="replace")
        results = []
        for _, row in df.head(limit).iterrows():
            results.append({
                "name": row.get("Name"),
                "url": row.get("Url"),
                "telephone": row.get("Telephone"),
                "latitude": row.get("Latitude"),
                "longitude": row.get("Longitude"),
                "address": row.get("Address"),
                "county": row.get("County"),
                "photo": row.get("Photo"),
                "tags": row.get("Tags"),
            })
        return {"success": True, "results": results, "error": None}
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}
