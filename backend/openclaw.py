"""OpenClaw local gateway client.

Provides OpenAI-compatible API access via the local OpenClaw gateway
(default: http://127.0.0.1:18789/v1/chat/completions).

No external API key required — uses the gateway auth token from openclaw.json.
"""

import json
import os
from typing import List, Dict, Any, Optional

import httpx


def _read_openclaw_config() -> dict:
    """Read and return ~/.openclaw/openclaw.json as a dict, or {}."""
    config_path = os.getenv("OPENCLAW_CONFIG_PATH") or os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[openclaw] Failed to read config: {e}")
        return {}


def _get_gateway_token() -> Optional[str]:
    """Return the OpenClaw gateway auth token, or None if not configured."""
    # Allow override via env (e.g. in tests or CI)
    token = os.getenv("OPENCLAW_GATEWAY_TOKEN")
    if token:
        return token

    cfg = _read_openclaw_config()
    return (cfg.get("gateway") or {}).get("auth", {}).get("token") or None


def _get_gateway_base_url() -> str:
    """Return the OpenClaw gateway base URL (e.g. http://127.0.0.1:18789)."""
    cfg = _read_openclaw_config()
    port = (cfg.get("gateway") or {}).get("port", 18789)
    return f"http://127.0.0.1:{port}"


def _normalize_model_for_gateway(model: str) -> str:
    """Pass model id through as-is — gateway handles openclaw prefixed ids."""
    return model


async def query_openclaw(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
) -> Optional[Dict[str, Any]]:
    """Query the OpenClaw local gateway with an OpenAI-compatible request.

    Args:
        model: Model identifier (openclaw full id like 'openrouter/anthropic/claude-sonnet-4.6',
               an alias, or a bare openrouter id)
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Dict with 'content' and optional 'reasoning_details', or None on failure.
    """
    token = _get_gateway_token()
    if not token:
        return None

    base_url = _get_gateway_base_url()
    endpoint = f"{base_url}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "")

            # Detect gateway-level error responses (rate limit, auth, etc.)
            if content and content.startswith("⚠️"):
                print(f"[openclaw] Gateway error for {model}: {content}")
                return None

            choice = (data.get("choices") or [{}])[0]

            return {
                "content": content,
                "reasoning_details": message.get("reasoning_details"),
                "provider_source": "openclaw",
                "requested_model": model,
                "resolved_model": data.get("model") or model,
                "generation_id": data.get("id"),
                "usage": data.get("usage"),
                "finish_reason": choice.get("finish_reason"),
                "native_finish_reason": choice.get("native_finish_reason"),
            }

    except httpx.HTTPStatusError as e:
        print(f"[openclaw] HTTP error querying {model}: {e.response.status_code} {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[openclaw] Error querying {model}: {e}")
        return None


async def fetch_openclaw_model_ids(
    filter_openrouter_only: bool = False,
) -> List[str]:
    """Return model IDs available via the OpenClaw gateway.

    Uses the gateway's RPC endpoint to list configured models.
    Falls back to reading openclaw.json directly if the RPC fails.

    Args:
        filter_openrouter_only: If True, return only openrouter/* models.

    Returns:
        Sorted list of model id strings.
    """
    token = _get_gateway_token()
    if not token:
        return []

    base_url = _get_gateway_base_url()

    # Try the gateway RPC for model list
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base_url}/rpc",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"method": "models.list", "params": {}},
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("result") or data.get("models") or []
                if isinstance(models, list) and models:
                    ids = [
                        m.get("id") or m if isinstance(m, dict) else m
                        for m in models
                    ]
                    ids = [m for m in ids if isinstance(m, str) and m.strip()]
                    if filter_openrouter_only:
                        ids = [m for m in ids if m.startswith("openrouter/")]
                    return sorted(ids)
    except Exception as e:
        print(f"[openclaw] RPC models.list failed: {e}")

    return []
