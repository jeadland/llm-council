"""MCP server that lets Codex call local LLM Council research runs."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import dotenv_values
from mcp.server.fastmcp import FastMCP


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_URL = os.getenv("LLM_COUNCIL_AGENT_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
HEALTH_URL = f"{BACKEND_URL}/api/health"
SECRET_PATH = Path(os.getenv("LLM_COUNCIL_AGENT_SECRET_FILE", "~/.codex/secrets/llm-council-agent.env")).expanduser()
RUNTIME_DIR = REPO_ROOT / "data" / "agent-runtime"
PID_PATH = RUNTIME_DIR / "backend.pid"
LOG_PATH = RUNTIME_DIR / "backend.log"

mcp = FastMCP("llm-council")


def _load_agent_token() -> str:
    values = dotenv_values(SECRET_PATH)
    token = (values.get("LLM_COUNCIL_AGENT_TOKEN") or os.getenv("LLM_COUNCIL_AGENT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            f"LLM Council agent token is missing. Set LLM_COUNCIL_AGENT_TOKEN in {SECRET_PATH}."
        )
    return token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_load_agent_token()}"}


def _port_is_open(host: str = "127.0.0.1", port: int = 8001) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _health_payload() -> Optional[dict[str, Any]]:
    try:
        response = httpx.get(HEALTH_URL, timeout=2.0)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    if payload.get("app") != "llm-council":
        raise RuntimeError(f"Port 8001 is not serving LLM Council: {payload!r}")
    return payload


def _start_backend() -> None:
    if _port_is_open() and _health_payload() is None:
        raise RuntimeError("Port 8001 is occupied but is not serving LLM Council.")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "BACKEND_HOST": "127.0.0.1",
        "BACKEND_PORT": "8001",
    })
    log = open(LOG_PATH, "a", encoding="utf-8")
    process = subprocess.Popen(
        ["uv", "run", "python", "-m", "backend.main"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_PATH.write_text(str(process.pid), encoding="utf-8")


def ensure_backend() -> None:
    if _health_payload() is not None:
        return
    _start_backend()
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if _health_payload() is not None:
            return
        time.sleep(0.5)
    raise RuntimeError(f"LLM Council backend did not become healthy. See {LOG_PATH}.")


def _post(path: str, payload: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    ensure_backend()
    response = httpx.post(f"{BACKEND_URL}{path}", headers=_headers(), json=payload, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"LLM Council API error {response.status_code}: {response.text}")
    return response.json()


def _get(path: str, timeout: float = 60.0) -> dict[str, Any]:
    ensure_backend()
    response = httpx.get(f"{BACKEND_URL}{path}", headers=_headers(), timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"LLM Council API error {response.status_code}: {response.text}")
    return response.json()


@mcp.tool()
def prepare_council_research(
    question: str,
    evidence: Optional[str] = None,
    research_depth: str = "hard",
    max_cost_usd: Optional[float] = None,
) -> dict[str, Any]:
    """Prepare a no-spend LLM Council research run and return approval details."""
    return _post(
        "/api/agent/research/prepare",
        {
            "question": question,
            "evidence": evidence,
            "research_depth": research_depth,
            "max_cost_usd": max_cost_usd,
        },
    )


@mcp.tool()
def run_council_research(approval_id: str, approved_cost_cap_usd: float) -> dict[str, Any]:
    """Run an approved paid LLM Council research request."""
    return _post(
        "/api/agent/research/run",
        {
            "approval_id": approval_id,
            "approved_cost_cap_usd": approved_cost_cap_usd,
        },
        timeout=900.0,
    )


@mcp.tool()
def get_council_research_result(run_id: str) -> dict[str, Any]:
    """Fetch a previous LLM Council research result by run id."""
    return _get(f"/api/agent/research/runs/{run_id}", timeout=60.0)


if __name__ == "__main__":
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    mcp.run()
