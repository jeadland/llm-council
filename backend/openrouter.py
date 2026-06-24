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
import time
from contextlib import contextmanager
from contextvars import ContextVar
import httpx
from typing import List, Dict, Any, Optional

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL, PREMIER_MODELS
from .openclaw import query_openclaw, fetch_openclaw_model_ids, _get_gateway_token

OPENROUTER_MODELS_API_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_GENERATION_API_URL = os.getenv("OPENROUTER_GENERATION_API_URL", "https://openrouter.ai/api/v1/generation")
CATALOG_CACHE_TTL_SECONDS = 10 * 60
_CATALOG_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "models": []}
_OPENROUTER_ACCOUNT_SCOPE: ContextVar[Optional[str]] = ContextVar("openrouter_account_scope", default=None)
_OPENROUTER_API_KEY_SCOPE: ContextVar[Optional[str]] = ContextVar("openrouter_api_key_scope", default=None)

MODEL_PRESETS = [
    {
        "id": "ultra-premium-frontier",
        "name": "Ultra Premium Frontier",
        "badge": "Highest quality",
        "cost_tier": "Highest",
        "speed_tier": "Slower",
        "summary": "Latest frontier-lab collection for the hardest strategy, research, and synthesis work.",
        "best_for": "High-stakes decisions, deep research, technical diligence, and complex synthesis.",
        "tradeoff": "Highest cost and latency; use when answer quality matters more than spend.",
        "chairman_candidates": [
            "anthropic/claude-opus-4.8",
            "openai/gpt-5.5",
        ],
        "slots": [
            ["openai/gpt-5.5", "openai/gpt-5.5-pro"],
            ["anthropic/claude-opus-4.8", "anthropic/claude-opus-4.8-fast", "anthropic/claude-opus-4.7"],
            ["google/gemini-2.5-pro"],
            ["x-ai/grok-4.20", "x-ai/grok-4.20-multi-agent"],
        ],
    },
    {
        "id": "premium-balanced",
        "name": "Premium Balanced",
        "badge": "Recommended",
        "cost_tier": "Medium",
        "speed_tier": "Medium",
        "summary": "Balanced depth and breadth for strategy, planning, and complex analysis.",
        "best_for": "Product strategy, market analysis, architecture tradeoffs, and multi-factor decisions.",
        "tradeoff": "Costs more than daily mode but keeps a broad cross-provider panel.",
        "chairman_candidates": [
            "anthropic/claude-sonnet-4.6",
            "openai/gpt-5.4",
        ],
        "slots": [
            ["anthropic/claude-sonnet-4.6"],
            ["openai/gpt-5.4", "openai/gpt-5.4-mini", "openai/gpt-5.2"],
            ["google/gemini-2.5-pro"],
            ["deepseek/deepseek-v4-pro", "z-ai/glm-5.2", "x-ai/grok-4.20"],
        ],
    },
    {
        "id": "efficient-daily",
        "name": "Efficient Daily",
        "badge": "Fast",
        "cost_tier": "Low",
        "speed_tier": "Fast",
        "summary": "Quick answers for everyday questions and operational decisions.",
        "best_for": "Drafting, summarizing, troubleshooting, and lower-risk exploration.",
        "tradeoff": "Less depth and fewer frontier models on unusually difficult questions.",
        "chairman_candidates": [
            "openai/gpt-5.4-mini",
            "openai/gpt-5.4",
            "anthropic/claude-sonnet-4.6",
        ],
        "slots": [
            ["openai/gpt-5.4-mini", "openai/gpt-5.4-nano", "openai/gpt-5.4"],
            ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"],
            ["z-ai/glm-5.2", "qwen/qwen3.7-max", "qwen/qwen3.6-flash"],
            ["x-ai/grok-4.20", "moonshotai/kimi-k2.6"],
        ],
    },
    {
        "id": "open-source-open-weights",
        "name": "Open Source / Open Weights",
        "badge": "Open",
        "cost_tier": "Low",
        "speed_tier": "Variable",
        "summary": "Open-weight-oriented council for independent comparison and low-cost depth.",
        "best_for": "Second opinions, coding checks, transparent alternatives, and vendor-diverse analysis.",
        "tradeoff": "Availability and quality vary more by provider route than frontier lab models.",
        "chairman_candidates": [
            "deepseek/deepseek-v4-pro",
            "qwen/qwen3.7-max",
            "z-ai/glm-5.2",
        ],
        "slots": [
            ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"],
            ["qwen/qwen3.7-max", "qwen/qwen3-max", "qwen/qwen3-235b-a22b"],
            ["z-ai/glm-5.2"],
            ["meta-llama/llama-4-maverick", "meta-llama/llama-3.3-70b-instruct"],
            ["mistralai/mistral-large-2512", "mistralai/mistral-medium-3.1"],
        ],
    },
    {
        "id": "cheap-experimental",
        "name": "Cheap Experimental",
        "badge": "Lowest cost",
        "cost_tier": "Lowest",
        "speed_tier": "Variable",
        "summary": "Low-risk exploration, cheap comparisons, and testing council mechanics.",
        "best_for": "Brainstorming, throwaway checks, prompt testing, and broad model comparisons.",
        "tradeoff": "More variance and weaker answers on nuanced or high-stakes work.",
        "chairman_candidates": [
            "deepseek/deepseek-v4-pro",
            "z-ai/glm-5.2",
            "openrouter/owl-alpha",
        ],
        "slots": [
            ["deepseek/deepseek-v4-flash", "deepseek/deepseek-v3.2"],
            ["qwen/qwen3.7-plus", "qwen/qwen3.6-flash"],
            ["minimax/minimax-m3", "xiaomi/mimo-v2.5"],
            ["openrouter/owl-alpha", "cohere/north-mini-code:free", "google/gemma-4-26b-a4b-it:free"],
        ],
    },
]

ESTIMATE_SCENARIOS = {
    "short": {
        "label": "Short",
        "input_tokens": 1_500,
        "stage1_output_tokens": 700,
        "stage2_output_tokens": 350,
        "stage3_output_tokens": 800,
    },
    "normal": {
        "label": "Normal",
        "input_tokens": 6_000,
        "stage1_output_tokens": 1_200,
        "stage2_output_tokens": 700,
        "stage3_output_tokens": 1_200,
    },
    "long": {
        "label": "Long document",
        "input_tokens": 30_000,
        "stage1_output_tokens": 2_000,
        "stage2_output_tokens": 1_000,
        "stage3_output_tokens": 1_800,
    },
}


@contextmanager
def use_openrouter_account_scope(email: Optional[str], api_key: Optional[str] = None):
    token = _OPENROUTER_ACCOUNT_SCOPE.set(email.lower().strip() if email else None)
    key_token = _OPENROUTER_API_KEY_SCOPE.set(api_key.strip() if api_key else None)
    try:
        yield
    finally:
        _OPENROUTER_ACCOUNT_SCOPE.reset(token)
        _OPENROUTER_API_KEY_SCOPE.reset(key_token)


def _normalize_openrouter_model_id(model: str) -> str:
    """Normalize model ids from OpenClaw-style ids to OpenRouter bare ids.

    openrouter/anthropic/claude-sonnet-4.6 -> anthropic/claude-sonnet-4.6
    anthropic/claude-sonnet-4.6            -> anthropic/claude-sonnet-4.6 (unchanged)
    sonnet-46                              -> sonnet-46 (alias, unchanged)
    """
    if model.startswith("openrouter/"):
        return model[len("openrouter/"):]
    return model


def normalize_model_id(model: str) -> str:
    """Public normalization helper for settings and catalog comparisons."""
    return _normalize_openrouter_model_id(model.strip()) if isinstance(model, str) else ""


def model_lab(model: str) -> str:
    """Return the provider/lab prefix used for curated preset diversity."""
    normalized = normalize_model_id(model)
    if "/" not in normalized:
        return normalized.lower().strip()
    return normalized.split("/", 1)[0].lower().strip()


def _parse_price_per_million(value: Any) -> Optional[float]:
    try:
        return round(float(value) * 1_000_000, 4)
    except (TypeError, ValueError):
        return None


def _price_tier(prompt_per_m: Optional[float], completion_per_m: Optional[float]) -> str:
    prices = [p for p in [prompt_per_m, completion_per_m] if p is not None and p >= 0]
    if not prices:
        return "Unknown"
    if all(p == 0 for p in prices):
        return "Free"
    blended = (prompt_per_m or 0) + (completion_per_m or 0)
    if blended <= 1:
        return "Cheap"
    if blended <= 12:
        return "Efficient"
    if blended <= 40:
        return "Premium"
    return "Expensive"


def _provider_from_id(model_id: str) -> str:
    if "/" not in model_id:
        return "unknown"
    return model_id.split("/", 1)[0].replace("-", " ").title()


def _recommendation_tags(model: Dict[str, Any]) -> List[str]:
    model_id = model.get("id", "")
    provider = model_id.split("/", 1)[0] if "/" in model_id else ""
    tags = set()

    preset_ids = {
        candidate
        for preset in MODEL_PRESETS
        for slot in preset["slots"]
        for candidate in slot
    }
    chairman_ids = {
        candidate
        for preset in MODEL_PRESETS
        for candidate in preset["chairman_candidates"]
    }

    if model_id in preset_ids:
        tags.add("Recommended")
    if model_id in chairman_ids:
        tags.add("Chairman")
    if provider in {"anthropic", "openai", "google", "x-ai"}:
        tags.add("Frontier")

    pricing = model.get("pricing") or {}
    prompt_per_m = _parse_price_per_million(pricing.get("prompt"))
    completion_per_m = _parse_price_per_million(pricing.get("completion"))
    tier = _price_tier(prompt_per_m, completion_per_m)
    if tier in {"Free", "Cheap", "Efficient", "Premium"}:
        tags.add(tier)

    context_length = model.get("context_length") or (model.get("top_provider") or {}).get("context_length")
    if isinstance(context_length, int) and context_length >= 200_000:
        tags.add("Long context")

    supported = set(model.get("supported_parameters") or [])
    if "tools" in supported:
        tags.add("Tools")
    if "reasoning" in supported or "include_reasoning" in supported or model.get("reasoning"):
        tags.add("Reasoning")
    if model_id.endswith(":free"):
        tags.add("Free")

    return sorted(tags)


def _normalize_catalog_model(model: Dict[str, Any]) -> Dict[str, Any]:
    model_id = model.get("id", "")
    pricing = model.get("pricing") or {}
    top_provider = model.get("top_provider") or {}
    architecture = model.get("architecture") or {}
    prompt_per_m = _parse_price_per_million(pricing.get("prompt"))
    completion_per_m = _parse_price_per_million(pricing.get("completion"))

    return {
        "id": model_id,
        "name": model.get("name") or model_id,
        "provider": _provider_from_id(model_id),
        "description": model.get("description") or "",
        "context_length": model.get("context_length") or top_provider.get("context_length"),
        "max_completion_tokens": top_provider.get("max_completion_tokens"),
        "pricing": {
            "prompt_per_million": prompt_per_m,
            "completion_per_million": completion_per_m,
            "request": pricing.get("request"),
            "raw": pricing,
        },
        "price_tier": _price_tier(prompt_per_m, completion_per_m),
        "supported_parameters": model.get("supported_parameters") or [],
        "input_modalities": architecture.get("input_modalities") or [],
        "output_modalities": architecture.get("output_modalities") or [],
        "recommendation_tags": _recommendation_tags(model),
        "created": model.get("created"),
    }


def _format_dollars(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if value < 0.01:
        return f"${value:.4f}"
    return f"${value:.2f}"


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sum_optional(*values: Optional[int]) -> Optional[int]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def normalize_usage(usage: Any) -> Optional[Dict[str, Any]]:
    """Normalize OpenRouter usage shapes from completion and generation APIs."""
    if not isinstance(usage, dict):
        return None

    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}

    prompt_tokens = _coerce_int(_first_present(
        usage.get("prompt_tokens"),
        usage.get("tokens_prompt"),
        usage.get("native_tokens_prompt"),
    ))
    completion_tokens = _coerce_int(_first_present(
        usage.get("completion_tokens"),
        usage.get("tokens_completion"),
        usage.get("native_tokens_completion"),
    ))
    total_tokens = _coerce_int(usage.get("total_tokens"))
    if total_tokens is None:
        total_tokens = _sum_optional(prompt_tokens, completion_tokens)
    reasoning_tokens = _coerce_int(
        _first_present(
            usage.get("reasoning_tokens"),
            usage.get("native_tokens_reasoning"),
            completion_details.get("reasoning_tokens"),
        )
    )
    cached_tokens = _coerce_int(
        _first_present(
            usage.get("cached_tokens"),
            usage.get("native_tokens_cached"),
            prompt_details.get("cached_tokens"),
        )
    )
    cost = _coerce_float(_first_present(
        usage.get("cost_usd"),
        usage.get("cost"),
        usage.get("total_cost"),
        usage.get("usage"),
    ))

    normalized = {
        "cost_usd": cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_tokens": cached_tokens,
        "is_byok": usage.get("is_byok"),
        "cost_details": usage.get("cost_details") or {},
    }

    if not any(value is not None and value != {} for value in normalized.values()):
        return None
    return normalized


def normalize_generation_metadata(payload: Any) -> Dict[str, Any]:
    """Normalize `/api/v1/generation` metadata into the same usage shape."""
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return {"usage": None}

    usage = normalize_usage({
        "prompt_tokens": _first_present(data.get("tokens_prompt"), data.get("native_tokens_prompt")),
        "completion_tokens": _first_present(data.get("tokens_completion"), data.get("native_tokens_completion")),
        "total_tokens": _sum_optional(
            _coerce_int(_first_present(data.get("tokens_prompt"), data.get("native_tokens_prompt"))),
            _coerce_int(_first_present(data.get("tokens_completion"), data.get("native_tokens_completion"))),
        ),
        "reasoning_tokens": data.get("native_tokens_reasoning"),
        "cached_tokens": data.get("native_tokens_cached"),
        "cost": data.get("total_cost") if data.get("total_cost") is not None else data.get("usage"),
        "is_byok": data.get("is_byok"),
        "cost_details": {
            "upstream_inference_cost": data.get("upstream_inference_cost"),
        },
    })

    return {
        "generation_id": data.get("id"),
        "resolved_model": data.get("model"),
        "provider_name": data.get("provider_name"),
        "finish_reason": data.get("finish_reason"),
        "native_finish_reason": data.get("native_finish_reason"),
        "created_at": data.get("created_at"),
        "request_id": data.get("request_id"),
        "usage": usage,
    }


def build_cost_call(
    stage: str,
    call_type: str,
    requested_model: str,
    response: Optional[Dict[str, Any]],
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a compact, non-secret billing record for one model call."""
    response = response or {}
    usage = normalize_usage(response.get("usage"))
    generation_id = response.get("generation_id") or response.get("id")
    cost = usage.get("cost_usd") if usage else None
    call_status = status or ("priced" if cost is not None else "pending" if generation_id else "unpriced")

    return {
        "stage": stage,
        "call_type": call_type,
        "requested_model": requested_model,
        "resolved_model": response.get("resolved_model") or response.get("model") or requested_model,
        "provider_source": response.get("provider_source"),
        "provider_name": response.get("provider_name"),
        "generation_id": generation_id,
        "status": call_status,
        "cost_usd": cost,
        "prompt_tokens": usage.get("prompt_tokens") if usage else None,
        "completion_tokens": usage.get("completion_tokens") if usage else None,
        "total_tokens": usage.get("total_tokens") if usage else None,
        "reasoning_tokens": usage.get("reasoning_tokens") if usage else None,
        "cached_tokens": usage.get("cached_tokens") if usage else None,
        "finish_reason": response.get("finish_reason"),
        "native_finish_reason": response.get("native_finish_reason"),
    }


def build_cost_summary(calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate call-level usage into a run-level cost summary."""
    normalized_calls = []
    total_usd = 0.0
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    reasoning_tokens = 0
    cached_tokens = 0
    priced_count = 0
    unpriced_count = 0
    failed_count = 0

    for call in calls:
        item = dict(call)
        if item.get("cost_usd") is not None:
            item["cost_usd"] = round(float(item["cost_usd"]), 8)
            item["status"] = "priced"
            total_usd += item["cost_usd"]
            priced_count += 1
        elif item.get("status") == "failed":
            failed_count += 1
        else:
            item["status"] = "unpriced"
            unpriced_count += 1

        for key, accumulator in [
            ("total_tokens", "total_tokens"),
            ("prompt_tokens", "prompt_tokens"),
            ("completion_tokens", "completion_tokens"),
            ("reasoning_tokens", "reasoning_tokens"),
            ("cached_tokens", "cached_tokens"),
        ]:
            if item.get(key) is not None:
                if accumulator == "total_tokens":
                    total_tokens += int(item[key])
                elif accumulator == "prompt_tokens":
                    prompt_tokens += int(item[key])
                elif accumulator == "completion_tokens":
                    completion_tokens += int(item[key])
                elif accumulator == "reasoning_tokens":
                    reasoning_tokens += int(item[key])
                elif accumulator == "cached_tokens":
                    cached_tokens += int(item[key])

        normalized_calls.append(item)

    if not normalized_calls:
        status = "unavailable"
    elif unpriced_count == 0 and priced_count > 0:
        status = "complete"
    elif priced_count > 0:
        status = "partial"
    else:
        status = "unavailable"

    return {
        "status": status,
        "total_usd": round(total_usd, 8) if priced_count else None,
        "total_tokens": total_tokens or None,
        "prompt_tokens": prompt_tokens or None,
        "completion_tokens": completion_tokens or None,
        "reasoning_tokens": reasoning_tokens or None,
        "cached_tokens": cached_tokens or None,
        "priced_calls_count": priced_count,
        "unpriced_calls_count": unpriced_count,
        "failed_calls_count": failed_count,
        "calls": normalized_calls,
    }


def _openrouter_attribution_headers() -> Dict[str, str]:
    headers = {"X-OpenRouter-Title": "LLM Council"}
    app_url = (
        os.getenv("OPENROUTER_APP_URL")
        or os.getenv("APP_URL")
        or os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
        or os.getenv("VERCEL_URL")
    )
    if app_url:
        app_url = app_url.strip()
        if app_url and not app_url.startswith(("http://", "https://")):
            app_url = f"https://{app_url}"
        headers["HTTP-Referer"] = app_url
    return headers


def estimate_council_costs(
    model_ids: List[str],
    chairman_model: Optional[str],
    model_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Estimate council cost from OpenRouter per-token pricing.

    The estimate mirrors the app's three-stage flow. It intentionally returns
    rough scenario ranges rather than pretending the exact final cost is known
    before the user asks a question.
    """
    known_models = [model_map[model_id] for model_id in model_ids if model_id in model_map]
    chairman = model_map.get(chairman_model or "") if chairman_model else None
    if not known_models or chairman is None:
        return {
            "available": False,
            "reason": "Missing live pricing for one or more selected models.",
            "scenarios": {},
        }

    def model_cost(model: Dict[str, Any], input_tokens: int, output_tokens: int) -> Optional[float]:
        pricing = model.get("pricing") or {}
        prompt = pricing.get("prompt_per_million")
        completion = pricing.get("completion_per_million")
        if prompt is None or completion is None:
            return None
        return (prompt * input_tokens / 1_000_000) + (completion * output_tokens / 1_000_000)

    scenarios = {}
    for key, scenario in ESTIMATE_SCENARIOS.items():
        n = len(known_models)
        base_input = scenario["input_tokens"]
        stage1_output = scenario["stage1_output_tokens"]
        stage2_output = scenario["stage2_output_tokens"]
        stage3_output = scenario["stage3_output_tokens"]

        total = 0.0
        for model in known_models:
            stage1 = model_cost(model, base_input, stage1_output)
            stage2 = model_cost(model, base_input + (stage1_output * n), stage2_output)
            if stage1 is None or stage2 is None:
                total = None
                break
            total += stage1 + stage2

        if total is not None:
            stage3 = model_cost(
                chairman,
                base_input + (stage1_output * n) + (stage2_output * n),
                stage3_output,
            )
            total = None if stage3 is None else total + stage3

        if total is None:
            scenarios[key] = {"label": scenario["label"], "available": False}
        else:
            low = total * 0.75
            high = total * 1.45
            scenarios[key] = {
                "label": scenario["label"],
                "available": True,
                "low": round(low, 4),
                "high": round(high, 4),
                "display": f"{_format_dollars(low)} - {_format_dollars(high)}",
                "notes": "Excludes optional web-search and provider surcharges.",
            }

    return {"available": True, "scenarios": scenarios}


async def fetch_openrouter_model_catalog(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch and normalize the OpenRouter text model catalog.

    The public catalog endpoint does not require an API key. Keep the cache
    runtime-local so settings persistence stays small and owner choices remain
    just model ids.
    """
    now = time.time()
    if (
        not force_refresh
        and _CATALOG_CACHE["models"]
        and now - _CATALOG_CACHE["fetched_at"] < CATALOG_CACHE_TTL_SECONDS
    ):
        return _CATALOG_CACHE["models"]

    params = {"output_modalities": "text"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(OPENROUTER_MODELS_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        print(f"[openrouter] Error fetching model catalog: {e}")
        if _CATALOG_CACHE["models"]:
            return _CATALOG_CACHE["models"]
        raise

    models = [
        _normalize_catalog_model(model)
        for model in data.get("data", [])
        if isinstance(model, dict) and model.get("id")
    ]
    _CATALOG_CACHE.update({"fetched_at": now, "models": models})
    return models


def resolve_model_presets(
    catalog: List[Dict[str, Any]],
    preset_definitions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Resolve preset candidate slots against the live catalog."""
    catalog_ids = {model["id"] for model in catalog}
    model_map = {model["id"]: model for model in catalog}
    resolved = []

    for preset in preset_definitions or MODEL_PRESETS:
        selected = []
        selected_labs = set()
        missing_slots = []
        for slot in preset["slots"]:
            match = next(
                (
                    candidate
                    for candidate in slot
                    if candidate in catalog_ids and model_lab(candidate) not in selected_labs
                ),
                None,
            )
            if match:
                selected.append(match)
                selected_labs.add(model_lab(match))
            else:
                missing_slots.append(slot[0])

        chairman = next(
            (candidate for candidate in preset["chairman_candidates"] if candidate in selected),
            selected[0] if selected else None,
        )

        resolved.append({
            "id": preset["id"],
            "name": preset["name"],
            "badge": preset.get("badge"),
            "cost_tier": preset["cost_tier"],
            "speed_tier": preset["speed_tier"],
            "summary": preset.get("summary") or preset.get("best_for", ""),
            "best_for": preset["best_for"],
            "tradeoff": preset.get("tradeoff", ""),
            "models": selected,
            "chairman_model": chairman,
            "missing": missing_slots,
            "estimated_costs": estimate_council_costs(selected, chairman, model_map),
            "customizable": True,
        })

    return resolved


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
    scoped_api_key = _OPENROUTER_API_KEY_SCOPE.get()
    direct_api_key = scoped_api_key or OPENROUTER_API_KEY
    if not direct_api_key:
        print(f"[openrouter] No OPENROUTER_API_KEY and local proxy unavailable — cannot query {model}")
        return None

    if not scoped_api_key:
        owner_email = (os.getenv("OPENROUTER_OWNER_EMAIL") or os.getenv("ADMIN_EMAIL") or "").lower().strip()
        active_email = (_OPENROUTER_ACCOUNT_SCOPE.get() or "").lower().strip()
        if owner_email and active_email != owner_email:
            print(f"[openrouter] Direct OpenRouter key is owner-scoped; refusing query for {model}")
            return None

    headers = {
        "Authorization": f"Bearer {direct_api_key}",
        "Content-Type": "application/json",
        **_openrouter_attribution_headers(),
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
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            usage = normalize_usage(data.get("usage"))

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                "provider_source": "openrouter_direct",
                "requested_model": model,
                "resolved_model": data.get("model") or normalized_model,
                "generation_id": data.get("id"),
                "usage": usage,
                "finish_reason": choice.get("finish_reason"),
                "native_finish_reason": choice.get("native_finish_reason"),
            }

    except Exception as e:
        print(f"[openrouter] Error querying model {model} direct: {e}")
        return None


async def fetch_generation_metadata(
    generation_id: str,
    api_key: str,
    timeout: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Fetch post-hoc OpenRouter generation metadata for one generation id."""
    if not generation_id or not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                OPENROUTER_GENERATION_API_URL,
                headers=headers,
                params={"id": generation_id},
            )
            response.raise_for_status()
            return normalize_generation_metadata(response.json())
    except Exception as e:
        print(f"[openrouter] Error fetching generation stats for {generation_id}: {e}")
        return None


async def reconcile_cost_calls(
    calls: List[Dict[str, Any]],
    api_key: Optional[str],
    retries: int = 2,
    delay_seconds: float = 0.8,
) -> List[Dict[str, Any]]:
    """Fill missing costs from OpenRouter generation stats when possible."""
    if not api_key:
        return calls

    reconciled = [dict(call) for call in calls]
    for attempt in range(retries + 1):
        pending = [
            call for call in reconciled
            if call.get("generation_id")
            and call.get("cost_usd") is None
            and call.get("status") != "failed"
        ]
        if not pending:
            break

        for call in pending:
            metadata = await fetch_generation_metadata(call["generation_id"], api_key)
            usage = metadata.get("usage") if metadata else None
            if not usage or usage.get("cost_usd") is None:
                continue
            call.update({
                "resolved_model": metadata.get("resolved_model") or call.get("resolved_model"),
                "provider_name": metadata.get("provider_name") or call.get("provider_name"),
                "status": "priced",
                "cost_usd": usage.get("cost_usd"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "reasoning_tokens": usage.get("reasoning_tokens"),
                "cached_tokens": usage.get("cached_tokens"),
                "finish_reason": metadata.get("finish_reason") or call.get("finish_reason"),
                "native_finish_reason": metadata.get("native_finish_reason") or call.get("native_finish_reason"),
            })

        if attempt < retries and any(
            call.get("generation_id")
            and call.get("cost_usd") is None
            and call.get("status") != "failed"
            for call in reconciled
        ):
            import asyncio
            await asyncio.sleep(delay_seconds)

    return reconciled


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
