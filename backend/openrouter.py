"""OpenRouter API client for making LLM requests."""

import json
import os
import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL, PREMIER_MODELS


def _normalize_openrouter_model_id(model: str) -> str:
    """Normalize model ids from OpenClaw-style ids to OpenRouter ids."""
    if model.startswith("openrouter/"):
        return model[len("openrouter/"):]
    return model


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
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
        print(f"Error querying model {model}: {e}")
        return None


def _read_openclaw_installed_models() -> List[str]:
    """Read model ids configured in local OpenClaw config.

    This represents models installed/known to that OpenClaw deployment.
    """
    config_path = os.getenv("OPENCLAW_CONFIG_PATH") or os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)

        models = set()

        defaults = (cfg.get("agents") or {}).get("defaults") or {}
        default_models = defaults.get("models") or {}
        models.update(default_models.keys())

        default_primary = ((defaults.get("model") or {}).get("primary"))
        if default_primary:
            models.add(default_primary)

        for agent in (cfg.get("agents") or {}).get("list") or []:
            primary = ((agent.get("model") or {}).get("primary"))
            if primary:
                models.add(primary)
            for fb in ((agent.get("model") or {}).get("fallbacks") or []):
                if fb:
                    models.add(fb)

        return sorted(m for m in models if isinstance(m, str) and m.strip())
    except Exception as e:
        print(f"Error reading OpenClaw model config: {e}")
        return []


async def fetch_available_models() -> List[str]:
    """Return models from this OpenClaw deployment's configured model library."""
    installed = _read_openclaw_installed_models()
    if installed:
        return installed

    return [f"openrouter/{m}" for m in PREMIER_MODELS]


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
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
