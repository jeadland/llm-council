"""LLM API client — routes through OpenClaw local proxy first, falls back to OpenRouter.

Routing priority:
  1. OpenClaw local gateway (http://127.0.0.1:18789) — no API key required
  2. OpenRouter direct API — requires OPENROUTER_API_KEY in env/.env

Model id format:
  - OpenClaw full ids:   openrouter/anthropic/claude-sonnet-4.6
  - OpenClaw aliases:    sonnet-46
  - OpenRouter bare ids: anthropic/claude-sonnet-4.6  (legacy, still accepted)
"""

import json
import os
import httpx
from typing import List, Dict, Any, Optional

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL, PREMIER_MODELS
from .openclaw import query_openclaw, fetch_openclaw_model_ids, _get_gateway_token


def _normalize_openrouter_model_id(model: str) -> str:
    """Normalize model ids from OpenClaw-style ids to OpenRouter bare ids.

    openrouter/anthropic/claude-sonnet-4.6 -> anthropic/claude-sonnet-4.6
    anthropic/claude-sonnet-4.6            -> anthropic/claude-sonnet-4.6 (unchanged)
    sonnet-46                              -> sonnet-46 (alias, unchanged)
    """
    if model.startswith("openrouter/"):
        return model[len("openrouter/"):]
    return model


def _is_openrouter_model(model: str) -> bool:
    """Return True if this model id is routable via OpenRouter."""
    # Full openclaw id for openrouter provider
    if model.startswith("openrouter/"):
        return True
    # Bare openrouter id (legacy, e.g. "anthropic/claude-sonnet-4.6")
    if "/" in model and not model.startswith(("openai-codex/", "local-ollama/", "amazon-bedrock/")):
        return True
    return False


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model — via OpenClaw local proxy if available, else OpenRouter direct.

    Args:
        model: Model identifier (openclaw full id, alias, or bare openrouter id)
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # --- Try OpenClaw local proxy first ---
    gateway_token = _get_gateway_token()
    if gateway_token:
        result = await query_openclaw(model, messages, timeout=timeout)
        if result is not None:
            return result
        print(f"[openrouter] OpenClaw proxy failed for {model}, trying OpenRouter direct…")

    # --- Fall back to OpenRouter direct API ---
    if not OPENROUTER_API_KEY:
        print(f"[openrouter] No OPENROUTER_API_KEY and local proxy unavailable — cannot query {model}")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    normalized_model = _normalize_openrouter_model_id(model)

    payload = {
        "model": normalized_model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        print(f"[openrouter] Error querying model {model} direct: {e}")
        return None


def _read_openclaw_installed_models() -> List[str]:
    """Read model ids configured in local OpenClaw config.

    Parses:
      - agents.defaults.models  — explicitly configured/aliased models (~20 entries)
      - agents.defaults.model.primary / fallbacks
      - agents.list[*].model.primary / fallbacks
      - models.providers[*].models[*].id  — locally-defined provider models

    Returns full openclaw model ids (e.g. 'openrouter/anthropic/claude-sonnet-4.6').
    This is intentionally limited to explicitly configured models only — NOT the
    full gateway catalog (which can exceed 800 entries).
    """
    config_path = os.getenv("OPENCLAW_CONFIG_PATH") or os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)

        models: set = set()

        # 1. agents.defaults.models — primary source of curated/aliased models
        defaults = (cfg.get("agents") or {}).get("defaults") or {}
        default_models = defaults.get("models") or {}
        models.update(default_models.keys())

        # 2. agents.defaults.model primary + fallbacks
        default_primary = ((defaults.get("model") or {}).get("primary"))
        if default_primary:
            models.add(default_primary)
        for fb in ((defaults.get("model") or {}).get("fallbacks") or []):
            if fb:
                models.add(fb)

        # 3. agents.list[*] model primary + fallbacks
        for agent in (cfg.get("agents") or {}).get("list") or []:
            primary = ((agent.get("model") or {}).get("primary"))
            if primary:
                models.add(primary)
            for fb in ((agent.get("model") or {}).get("fallbacks") or []):
                if fb:
                    models.add(fb)

        # 4. models.providers[*] — locally-defined provider models (e.g. nvidia-kimi, local-ollama)
        for provider_name, provider_cfg in ((cfg.get("models") or {}).get("providers") or {}).items():
            for m in provider_cfg.get("models") or []:
                model_id = m.get("id")
                if model_id:
                    models.add(f"{provider_name}/{model_id}")

        return sorted(m for m in models if isinstance(m, str) and m.strip())
    except Exception as e:
        print(f"Error reading OpenClaw model config: {e}")
        return []


async def fetch_available_models() -> List[str]:
    """Return models available in this deployment.

    Priority (changed from full-catalog-first to curated-first):
      1. Configured/aliased models from openclaw.json  — agents.defaults.models + providers
         This gives ~20-30 explicitly curated models, NOT the full 800+ gateway catalog.
      2. Live query via OpenClaw gateway RPC (models.list) filtered to configured set
         — only used if openclaw.json is missing/empty
      3. Hardcoded PREMIER_MODELS fallback

    Rationale: The gateway RPC returns 800+ models from all providers (AWS Bedrock,
    OpenRouter, etc.). The LLM Council only needs the small set the operator has
    explicitly configured with aliases/settings — same set the main agent uses.
    """
    # 1. Configured/aliased models from openclaw.json (primary — always use this)
    installed = _read_openclaw_installed_models()
    if installed:
        print(f"[openrouter] Using {len(installed)} configured models from openclaw.json")
        return installed

    # 2. Fall back to live RPC — but filter to avoid 800+ catalog overload.
    #    If we have no config at all, grab the RPC list but cap it and warn.
    print("[openrouter] openclaw.json has no configured models — falling back to gateway RPC (filtered)")
    try:
        live_models = await fetch_openclaw_model_ids(filter_openrouter_only=True)
        if live_models:
            # Cap to avoid UI overload in edge case
            return live_models[:50]
    except Exception as e:
        print(f"[openrouter] fetch_openclaw_model_ids failed: {e}")

    # 3. Fallback to PREMIER_MODELS (prefixed for openclaw routing)
    return [f"openrouter/{m}" for m in PREMIER_MODELS]


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
