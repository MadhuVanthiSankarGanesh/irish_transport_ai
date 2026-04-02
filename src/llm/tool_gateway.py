import os
from typing import Any, Callable

from src.llm import tools as local_tools
from src.mcp_client import call_mcp_tool

USE_MCP = os.getenv("USE_MCP", "").lower() in {"1", "true", "yes"}


def _call_mcp_or_local(
    tool_name: str,
    payload: dict[str, Any],
    local_fn: Callable[..., Any],
    *local_args: Any,
    **local_kwargs: Any,
):
    if not USE_MCP:
        return local_fn(*local_args, **local_kwargs)
    try:
        result = call_mcp_tool(tool_name, payload)
        if tool_name == "otp.plan_route" and isinstance(result, dict):
            error_text = str(result.get("error") or "")
            if result.get("success") is False and (
                "OTP server error" in error_text
                or "OTP error:" in error_text
                or "schema_v3_labeled_only" in error_text
            ):
                local_result = local_fn(*local_args, **local_kwargs)
                if isinstance(local_result, dict) and "error" not in local_result:
                    local_result["mcp_error"] = error_text
                return local_result
        return result
    except Exception as exc:
        # Fall back locally to keep chat usable if MCP is down.
        result = local_fn(*local_args, **local_kwargs)
        if isinstance(result, dict) and "error" not in result:
            result["mcp_error"] = str(exc)
        return result


def get_events_tool(date_range: str, location: str | None = None, limit: int = 10):
    return _call_mcp_or_local(
        "events.search",
        {"date_range": date_range, "location": location, "limit": limit},
        local_tools.get_events_tool,
        date_range,
        location,
        limit,
    )


def plan_route_tool(origin: str, destination: str, datetime_str: str | None = None, preference: str = "balanced"):
    return _call_mcp_or_local(
        "otp.plan_route",
        {
            "origin": origin,
            "destination": destination,
            "datetime_str": datetime_str,
            "preference": preference,
        },
        local_tools.plan_route_tool,
        origin,
        destination,
        datetime_str,
        preference,
    )


def geocode_tool(place: str):
    return _call_mcp_or_local(
        "geo.resolve",
        {"place": place},
        local_tools.geocode_tool,
        place,
    )


def get_accommodations_tool(limit: int = 100):
    return _call_mcp_or_local(
        "failte.accommodations",
        {"limit": limit},
        local_tools.get_accommodations_tool,
        limit,
    )


def get_attractions_tool(limit: int = 200):
    return _call_mcp_or_local(
        "failte.attractions",
        {"limit": limit},
        local_tools.get_attractions_tool,
        limit,
    )


def get_nearest_stop(lat: float, lon: float):
    # keep local for now
    return local_tools.get_nearest_stop(lat, lon)


def get_walk_path_tool(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float):
    return _call_mcp_or_local(
        "walk.path",
        {
            "origin_lat": origin_lat,
            "origin_lon": origin_lon,
            "dest_lat": dest_lat,
            "dest_lon": dest_lon,
        },
        local_tools.get_walk_path_tool,
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return local_tools._haversine_km(lat1, lon1, lat2, lon2)


def geocode_osm(query: str):
    return local_tools.geocode_osm(query)


def geocode_cached(query: str):
    return local_tools.geocode_cached(query)


def reverse_geocode_osm(lat: float, lon: float):
    return local_tools.reverse_geocode_osm(lat, lon)
