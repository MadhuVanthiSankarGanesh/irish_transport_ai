import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


DEFAULT_GRAPH_DIR = os.path.join("otp", "graphs", "default")
DEFAULT_JAR_CANDIDATES = [
    os.path.join("otp", "otp-shaded-2.8.1.jar"),
    os.path.join("otp", "otp-shaded.jar"),
    os.path.join("..", "OpenTripPlanner", "otp-shaded", "target", "otp-shaded-2.8.1.jar"),
]


def _abs_path(path: str) -> str:
    return os.path.abspath(path)


def find_otp_jar(explicit: str | None = None) -> str | None:
    if explicit and os.path.exists(explicit):
        return _abs_path(explicit)
    env_path = os.getenv("OTP_JAR", "").strip()
    if env_path and os.path.exists(env_path):
        return _abs_path(env_path)
    for candidate in DEFAULT_JAR_CANDIDATES:
        if os.path.exists(candidate):
            return _abs_path(candidate)
    return None


def graph_obj_path(graph_dir: str) -> str:
    return os.path.join(graph_dir, "graph.obj")


def graph_age_hours(graph_dir: str) -> float | None:
    path = graph_obj_path(graph_dir)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    age_sec = time.time() - mtime
    return age_sec / 3600.0


def graph_is_fresh(graph_dir: str, ttl_hours: float) -> bool:
    age = graph_age_hours(graph_dir)
    if age is None:
        return False
    return age <= ttl_hours


def otp_server_running(base_url: str) -> bool:
    if requests is None:
        return False
    try:
        url = base_url.rstrip("/") + "/otp/routers"
        resp = requests.get(url, timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def run_java(args: list[str]) -> int:
    return subprocess.call(args)


def build_graph(jar: str, graph_dir: str, xmx: str) -> int:
    graph_dir = _abs_path(graph_dir)
    return run_java(["java", f"-Xmx{xmx}", "-jar", jar, "--build", "--save", graph_dir])


def serve_graph(jar: str, graph_dir: str, xmx: str) -> int:
    graph_dir = _abs_path(graph_dir)
    return run_java(["java", f"-Xmx{xmx}", "-jar", jar, "--load", "--serve", graph_dir])


def ensure_graph(jar: str, graph_dir: str, ttl_hours: float, xmx: str) -> bool:
    if graph_is_fresh(graph_dir, ttl_hours):
        return True
    code = build_graph(jar, graph_dir, xmx)
    return code == 0


def ensure_and_serve(jar: str, graph_dir: str, ttl_hours: float, xmx: str) -> int:
    ok = ensure_graph(jar, graph_dir, ttl_hours, xmx)
    if not ok:
        return 1
    return serve_graph(jar, graph_dir, xmx)


def spawn_background(args: list[str]) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="OTP graph manager")
    parser.add_argument("--graph-dir", default=DEFAULT_GRAPH_DIR)
    parser.add_argument("--jar", default="")
    parser.add_argument("--ttl-hours", type=float, default=float(os.getenv("OTP_GRAPH_TTL_HOURS", "168")))
    parser.add_argument("--xmx", default=os.getenv("OTP_JAVA_XMX", "10G"))
    parser.add_argument("--ensure", action="store_true", help="Build graph if missing or stale")
    parser.add_argument("--serve", action="store_true", help="Serve graph")
    parser.add_argument("--ensure-and-serve", action="store_true", help="Ensure graph then serve")

    args = parser.parse_args()

    jar = find_otp_jar(args.jar)
    if not jar:
        print("OTP jar not found. Set OTP_JAR or place otp-shaded-2.8.1.jar in ./otp")
        return 2

    if args.ensure_and_serve:
        return ensure_and_serve(jar, args.graph_dir, args.ttl_hours, args.xmx)
    if args.ensure:
        ok = ensure_graph(jar, args.graph_dir, args.ttl_hours, args.xmx)
        return 0 if ok else 1
    if args.serve:
        return serve_graph(jar, args.graph_dir, args.xmx)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
