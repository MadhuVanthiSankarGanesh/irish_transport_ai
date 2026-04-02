import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.llm.tools import (
    get_events_tool,
    plan_route_tool,
    geocode_tool,
    get_accommodations_tool,
    get_attractions_tool,
    get_walk_path_tool,
)

PORT = int(os.getenv("MCP_PORT", "8765"))
_jobs = {}
_jobs_lock = threading.Lock()

TOOLS = {
    "events.search": {
        "description": "Search events",
        "params": ["date_range", "location", "limit"],
        "handler": get_events_tool,
    },
    "otp.plan_route": {
        "description": "Plan route using OTP",
        "params": ["origin", "destination", "datetime_str", "preference"],
        "handler": plan_route_tool,
    },
    "geo.resolve": {
        "description": "Resolve a place name to coordinates",
        "params": ["place"],
        "handler": geocode_tool,
    },
    "failte.accommodations": {
        "description": "Fetch accommodations from Failte Ireland",
        "params": ["limit"],
        "handler": get_accommodations_tool,
    },
    "failte.attractions": {
        "description": "Fetch attractions from Failte Ireland",
        "params": ["limit"],
        "handler": get_attractions_tool,
    },
    "walk.path": {
        "description": "Get a walking path using GraphHopper locally, with OTP fallback",
        "params": ["origin_lat", "origin_lon", "dest_lat", "dest_lon"],
        "handler": get_walk_path_tool,
    },
}


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class MCPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/tools":
            tools = {k: {"description": v["description"], "params": v["params"]} for k, v in TOOLS.items()}
            return _json_response(self, 200, {"tools": tools})
        if path.startswith("/result"):
            query = urlparse(self.path).query
            job_id = None
            for part in query.split("&"):
                if part.startswith("id="):
                    job_id = part.split("=", 1)[1]
                    break
            if not job_id:
                return _json_response(self, 400, {"error": "missing_id"})
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                return _json_response(self, 404, {"error": "unknown_job"})
            return _json_response(self, 200, job)
        return _json_response(self, 404, {"error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ["/call", "/call_async"]:
            return _json_response(self, 404, {"error": "not_found"})
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except Exception:
            return _json_response(self, 400, {"error": "invalid_json"})
        name = payload.get("name")
        args = payload.get("arguments", {})
        if name not in TOOLS:
            return _json_response(self, 400, {"error": "unknown_tool", "name": name})

        if path == "/call":
            try:
                self.server.timeout = 120
                result = TOOLS[name]["handler"](**args)
                return _json_response(self, 200, {"ok": True, "result": result})
            except Exception as e:
                return _json_response(self, 500, {"ok": False, "error": str(e)})

        # async
        job_id = f"{int(time.time()*1000)}-{threading.get_ident()}"

        def _run():
            try:
                result = TOOLS[name]["handler"](**args)
                payload = {"ok": True, "result": result, "done": True}
            except Exception as e:
                payload = {"ok": False, "error": str(e), "done": True}
            with _jobs_lock:
                _jobs[job_id] = payload

        with _jobs_lock:
            _jobs[job_id] = {"ok": True, "done": False}
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return _json_response(self, 200, {"ok": True, "job_id": job_id})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    print(f"MCP tool server running on http://localhost:{PORT}")
    server.serve_forever()
