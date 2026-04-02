import os
import time
import requests

MCP_URL = os.getenv("MCP_URL", "http://localhost:8765").rstrip("/")
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "60"))
MCP_ASYNC_TIMEOUT = int(os.getenv("MCP_ASYNC_TIMEOUT", "120"))
MCP_POLL_INTERVAL = float(os.getenv("MCP_POLL_INTERVAL", "1.0"))


def _poll_result(job_id: str):
    deadline = time.time() + MCP_ASYNC_TIMEOUT
    while time.time() < deadline:
        resp = requests.get(f"{MCP_URL}/result?id={job_id}", timeout=MCP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("done"):
            if not data.get("ok"):
                raise RuntimeError(data.get("error", "mcp_error"))
            return data.get("result")
        time.sleep(MCP_POLL_INTERVAL)
    raise TimeoutError("MCP async call timed out")


def call_mcp_tool(name: str, arguments: dict | None = None):
    payload = {"name": name, "arguments": arguments or {}}
    try:
        resp = requests.post(f"{MCP_URL}/call", json=payload, timeout=MCP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "mcp_error"))
        return data.get("result")
    except requests.exceptions.ReadTimeout:
        # Fall back to async
        resp = requests.post(f"{MCP_URL}/call_async", json=payload, timeout=MCP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            raise RuntimeError("MCP async call failed")
        return _poll_result(job_id)
