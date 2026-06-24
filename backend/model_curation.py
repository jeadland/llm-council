"""Reviewable model curation drafts for curated council presets."""

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import storage
from .openrouter import (
    MODEL_PRESETS,
    estimate_council_costs,
    fetch_openrouter_model_catalog,
    query_model,
    resolve_model_presets,
    use_openrouter_account_scope,
)

CURATION_MODEL = os.getenv("MODEL_CURATION_MODEL", "openai/gpt-5.5")
DEFAULT_MAX_USD = float(os.getenv("MODEL_CURATION_MAX_USD", "2.00"))
SOURCE_URLS = [
    "https://openrouter.ai/docs/api/api-reference/models/get-models",
    "https://openrouter.ai/docs/cookbook/administration/usage-accounting",
    "https://artificialanalysis.ai/leaderboards/models",
    "https://arena.ai/leaderboard/text",
]


def _price_for_model(model: Dict[str, Any], input_tokens: int, output_tokens: int) -> Optional[float]:
    pricing = model.get("pricing") or {}
    prompt = pricing.get("prompt_per_million")
    completion = pricing.get("completion_per_million")
    if prompt is None or completion is None:
        return None
    return (prompt * input_tokens / 1_000_000) + (completion * output_tokens / 1_000_000)


def _estimate_curation_llm_cost(catalog: List[Dict[str, Any]], prompt: str) -> Optional[float]:
    model = next((item for item in catalog if item["id"] == CURATION_MODEL), None)
    if not model:
        return None
    input_tokens = int(len(prompt.split()) * 1.35)
    return _price_for_model(model, input_tokens=input_tokens, output_tokens=1_500)


def _compact_catalog(catalog: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    interesting_providers = {"Anthropic", "Openai", "Google", "X Ai", "Deepseek", "Qwen", "Z Ai", "Meta Llama", "Mistralai", "Moonshotai"}
    candidates = [
        model for model in catalog
        if model.get("provider") in interesting_providers
        or any(tag in {"Recommended", "Frontier", "Reasoning", "Cheap", "Efficient"} for tag in model.get("recommendation_tags", []))
    ]
    candidates = sorted(
        candidates,
        key=lambda model: (
            "Recommended" not in model.get("recommendation_tags", []),
            "Frontier" not in model.get("recommendation_tags", []),
            model.get("created") or 0,
        ),
        reverse=True,
    )
    return [
        {
            "id": model["id"],
            "name": model["name"],
            "provider": model["provider"],
            "price_tier": model["price_tier"],
            "context_length": model.get("context_length"),
            "tags": model.get("recommendation_tags", []),
            "pricing": {
                "prompt_per_million": model.get("pricing", {}).get("prompt_per_million"),
                "completion_per_million": model.get("pricing", {}).get("completion_per_million"),
            },
        }
        for model in candidates[:80]
    ]


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


async def create_model_curation_draft(trigger: str, owner_email: Optional[str]) -> Dict[str, Any]:
    catalog = await fetch_openrouter_model_catalog(force_refresh=True)
    resolved_presets = resolve_model_presets(catalog)
    model_map = {model["id"]: model for model in catalog}

    prompt_payload = {
        "task": "Review the LLM Council curated model groups and suggest any changes.",
        "constraints": [
            "Keep the groups practical for a private single-owner deliberation app.",
            "Do not include unavailable model ids.",
            "Preserve an ultra-premium frontier group and an open-source/open-weights group.",
            "Use at most one model per provider/lab in each curated group.",
            "For frontier groups, pick the lab's strongest representative model instead of multiple variants from the same lab.",
            "Recommend one chairman per group.",
            "Return concise JSON with notes, risks, and next_curation_model.",
        ],
        "current_presets": resolved_presets,
        "catalog_candidates": _compact_catalog(catalog),
    }
    prompt = json.dumps(prompt_payload, indent=2)
    estimated_llm_cost = _estimate_curation_llm_cost(catalog, prompt)

    llm_review = None
    llm_json: Dict[str, Any] = {}
    status = "ready"
    if estimated_llm_cost is not None and estimated_llm_cost <= DEFAULT_MAX_USD:
        with use_openrouter_account_scope(owner_email, api_key=storage.get_openrouter_api_key(owner_email)):
            result = await query_model(
                CURATION_MODEL,
                [
                    {
                        "role": "system",
                        "content": "You curate model presets for LLM Council. Return concise JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                timeout=180.0,
            )
        if result and result.get("content"):
            llm_review = result["content"]
            llm_json = _extract_json_object(llm_review)
        else:
            status = "ready_with_warnings"
    elif estimated_llm_cost is not None:
        status = "skipped_cost_cap"

    draft_id = str(uuid.uuid4())
    draft = {
        "id": draft_id,
        "status": status,
        "trigger": trigger,
        "created_at": datetime.utcnow().isoformat(),
        "owner_email": owner_email,
        "curation_model": CURATION_MODEL,
        "next_curation_model": llm_json.get("next_curation_model") or CURATION_MODEL,
        "estimated_llm_cost": round(estimated_llm_cost, 4) if estimated_llm_cost is not None else None,
        "max_llm_cost": DEFAULT_MAX_USD,
        "sources": SOURCE_URLS,
        "notes": llm_json.get("notes") or "Draft generated from the live OpenRouter catalog and current preset rules.",
        "risks": llm_json.get("risks") or [
            "External leaderboards and provider catalogs can change after this draft is generated.",
            "Cost estimates exclude optional web-search and provider surcharges.",
        ],
        "preset_definitions": MODEL_PRESETS,
        "resolved_presets": resolved_presets,
        "llm_review": llm_review,
    }

    for preset in draft["resolved_presets"]:
        preset["estimated_costs"] = estimate_council_costs(
            preset.get("models", []),
            preset.get("chairman_model"),
            model_map,
        )

    return storage.save_model_curation_draft(draft)
