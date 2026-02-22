"""OpenClaw local proxy client for LLM requests.

Routes requests through the local OpenClaw gateway (http://127.0.0.1:18789/v1/*)
which acts as an OpenAI-compatible proxy to all configured model providers.

No API key is needed — auth uses the gateway device token from openclaw.json.
"""

import json
import os
import shutil
import subprocess
import httpx
from typing import List, Dict, Any, Optional


# Default OpenClaw gateway base URL
OPENCLAW_PROXY_URL = os.getenv("OPENCLAW_PROXY_URL", "http://127.0.0.1:18789")

# Well-known installation paths for the openclaw CLI binary
_OPENCLAW_KNOWN_PATHS = [
    "/home/pi/.npm-global/bin/openclaw",
    "/usr/local/bin/openclaw",
    "/usr/bin/openclaw",
    os.path.expanduser("~/.npm-global/bin/openclaw"),
    os.path.expanduser("~/.local/bin/openclaw"),
]


def _find_openclaw_binary() -> str:
    """Locate the openclaw CLI binary, searching PATH and known install locations."""
    # 1. Check current PATH
    found = shutil.which("openclaw")
    if found:
        return found

    # 2. Try known paths
    for p in _OPENCLAW_KNOWN_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    # 3. Environment override
    env_path = os.getenv("OPENCLAW_BIN")
    if env_path and os.path.isfile(env_path):
        return env_path

    return "openclaw"  # Last resort — may fail if not in PATH


def _get_gateway_token() -> Optional[str]:
    """Read the gateway device token from openclaw.json."""
    config_path = os.getenv("OPENCLAW_CONFIG_PATH") or os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)
        return cfg.get("gateway", {}).get("auth", {}).get("token")
    except Exception as e:
        print(f"[openclaw] Warning: could not read gateway token: {e}")
        return None


def _build_full_model_id(provider: str, model_id: str) -> str:
    """Construct a fully-qualified model id like 'openrouter/anthropic/claude-sonnet-4.6'."""
    return f"{provider}/{model_id}"


async def fetch_openclaw_models() -> List[Dict[str, Any]]:
    """
    Fetch models available through the local OpenClaw gateway.

    Uses the gateway RPC `models.list` via the CLI (subprocess) since there
    is no direct HTTP endpoint for model listing — only WS RPC.

    Returns:
        List of model dicts with keys: id (full openclaw id), name, provider, alias
    """
    token = _get_gateway_token()
    if token is None:
        return []

    try:
        openclaw_bin = _find_openclaw_binary()
        result = subprocess.run(
            [openclaw_bin, "gateway", "call", "models.list", "--token", token, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            print(f"[openclaw] models.list failed: {result.stderr}")
            return []

        data = json.loads(result.stdout)
        raw_models = data.get("models", [])

        # Build full openclaw model ids: "provider/id"
        models = []
        for m in raw_models:
            provider = m.get("provider", "")
            model_id = m.get("id", "")
            if not provider or not model_id:
                continue
            full_id = _build_full_model_id(provider, model_id)
            models.append({
                "id": full_id,
                "name": m.get("name", full_id),
                "provider": provider,
                "contextWindow": m.get("contextWindow"),
                "reasoning": m.get("reasoning", False),
                "input": m.get("input", ["text"]),
            })

        return models

    except Exception as e:
        print(f"[openclaw] Error fetching models: {e}")
        return []


async def fetch_openclaw_model_ids(filter_openrouter_only: bool = False) -> List[str]:
    """
    Return list of model id strings available through the local OpenClaw gateway.

    Args:
        filter_openrouter_only: If True, only return openrouter/* models.

    Returns:
        Sorted list of full model id strings (e.g. 'openrouter/anthropic/claude-sonnet-4.6')
    """
    models = await fetch_openclaw_models()
    if filter_openrouter_only:
        models = [m for m in models if m["provider"] == "openrouter"]
    return sorted(m["id"] for m in models)


async def query_openclaw(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
) -> Optional[Dict[str, Any]]:
    """
    Query a model through the local OpenClaw gateway proxy.

    Uses POST /v1/chat/completions (OpenAI-compatible API).
    Auth: Bearer token from openclaw.json.

    Args:
        model: Full openclaw model id (e.g. 'openrouter/anthropic/claude-sonnet-4.6')
               or a configured alias (e.g. 'sonnet-46').
        messages: List of message dicts with 'role' and 'content'.
        timeout: Request timeout in seconds.

    Returns:
        Dict with 'content' and optional 'reasoning_details', or None if failed.
    """
    token = _get_gateway_token()
    if token is None:
        print("[openclaw] No gateway token available, cannot use local proxy")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    url = f"{OPENCLAW_PROXY_URL}/v1/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "")

            # Surface API-level errors that the gateway wraps in valid responses
            if content and content.startswith("⚠️"):
                print(f"[openclaw] Gateway returned error response for {model}: {content}")
                return None

            return {
                "content": content,
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:
        print(f"[openclaw] Error querying {model} via local proxy: {e}")
        return None


def is_openclaw_available() -> bool:
    """Quick synchronous check: can we reach the local gateway?"""
    token = _get_gateway_token()
    if token is None:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{OPENCLAW_PROXY_URL}/v1/chat/completions",
            method="OPTIONS",
        )
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=3):
            pass
        return True
    except Exception:
        # 405 Method Not Allowed still means the server is up
        try:
            import urllib.error
        except ImportError:
            pass
        return True  # Any response = server is running
