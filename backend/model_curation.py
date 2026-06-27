"""Reviewable model curation drafts for curated council presets."""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import storage
from .openrouter import (
    MODEL_PRESETS,
    estimate_council_costs,
    fetch_openrouter_model_catalog,
    normalize_model_id,
    query_model,
    resolve_model_presets,
    use_openrouter_account_scope,
)

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


def _normalize_curation_model(model: Optional[str]) -> Optional[str]:
    if not isinstance(model, str):
        return None
    raw = model.strip()
    if not raw:
        return None
    if raw == "openrouter/auto":
        return raw
    if raw.startswith("openrouter/openrouter/"):
        return raw[len("openrouter/"):]
    if raw.startswith("openrouter/") and raw.count("/") >= 2:
        return raw[len("openrouter/"):]
    normalized = normalize_model_id(raw)
    if normalized and "/" in normalized:
        return normalized
    return None


def _is_router_model(model: Optional[str]) -> bool:
    return model in {"openrouter/auto", "openrouter/free"}


def _estimate_curation_llm_cost(catalog: List[Dict[str, Any]], prompt: str, curation_model: str) -> Optional[float]:
    model = next((item for item in catalog if item["id"] == curation_model), None)
    if not model:
        return None
    input_tokens = int(len(prompt.split()) * 1.35)
    return _price_for_model(model, input_tokens=input_tokens, output_tokens=1_500)


def _extract_preset_definitions(llm_json: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    candidates = (
        llm_json.get("proposed_preset_definitions")
        or llm_json.get("curated_model_presets")
        or llm_json.get("preset_definitions")
        or llm_json.get("presets")
    )
    if not isinstance(candidates, list):
        return None
    valid = [
        preset for preset in candidates
        if isinstance(preset, dict) and preset.get("id") and preset.get("slots")
    ]
    return valid or None


def validate_next_curation_model(
    model: Optional[str],
    catalog: List[Dict[str, Any]],
    prompt: str,
    max_usd: float = DEFAULT_MAX_USD,
) -> Dict[str, Any]:
    normalized = _normalize_curation_model(model)
    validation = {
        "candidate": model,
        "normalized_model": normalized,
        "ok": False,
        "reason": None,
        "estimated_cost": None,
    }
    if not normalized:
        validation["reason"] = "Model id is empty or not routable."
        return validation

    catalog_model = next((item for item in catalog if item["id"] == normalized), None)
    if catalog_model is None and not _is_router_model(normalized):
        validation["reason"] = "Model id is not present in the OpenRouter text catalog."
        return validation

    estimated = _estimate_curation_llm_cost(catalog, prompt, normalized)
    validation["estimated_cost"] = round(estimated, 4) if estimated is not None else None
    if estimated is not None and estimated > max_usd:
        validation["reason"] = "Estimated curation cost exceeds the configured cap."
        return validation

    validation["ok"] = True
    validation["reason"] = "Validated against OpenRouter catalog and cost cap."
    if _is_router_model(normalized) and estimated is None:
        validation["reason"] = "Router model allowed; pricing is resolved by OpenRouter at request time."
    return validation


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


def _stringify_review_value(value: Any, fallback: str = "") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(
            item for item in (_stringify_review_value(item) for item in value) if item
        ) or fallback
    try:
        return json.dumps(value, sort_keys=True)
    except Exception:
        return fallback


def _stringify_review_list(value: Any, fallback: List[str]) -> List[str]:
    if value is None or value == "":
        return fallback
    values = value if isinstance(value, list) else [value]
    converted = [_stringify_review_value(item) for item in values]
    return [item for item in converted if item] or fallback


async def create_model_curation_draft(trigger: str, owner_email: Optional[str]) -> Dict[str, Any]:
    curation_state = storage.get_model_curation_state()
    curation_model = curation_state["current_curation_model"]
    catalog = await fetch_openrouter_model_catalog(force_refresh=True)
    current_validation = validate_next_curation_model(curation_model, catalog, "{}")
    if not current_validation["ok"]:
        fallback_model = curation_state.get("fallback_curation_model") or storage.DEFAULT_CURATION_MODEL
        fallback_validation = validate_next_curation_model(fallback_model, catalog, "{}")
        curation_model = fallback_validation["normalized_model"] if fallback_validation["ok"] else storage.DEFAULT_CURATION_MODEL
        storage.save_model_curation_state({"current_curation_model": curation_model})
    settings = storage.get_settings()
    current_preset_definitions = settings.get("curated_model_presets") or MODEL_PRESETS
    current_resolved_presets = resolve_model_presets(catalog, preset_definitions=current_preset_definitions)
    model_map = {model["id"]: model for model in catalog}

    prompt_payload = {
        "task": "Review the LLM Council curated model groups and suggest any changes.",
        "constraints": [
            "Keep the groups practical for a private BYOK deliberation app.",
            "Do not include unavailable model ids.",
            "Preserve an ultra-premium frontier group and an open-source/open-weights group.",
            "Use at most one model per provider/lab in each curated group.",
            "For frontier groups, pick the lab's strongest representative model instead of multiple variants from the same lab.",
            "Recommend one chairman per group.",
            "Return concise JSON with notes, risks, recommended_next_curation_model, and optional proposed_preset_definitions.",
        ],
        "current_presets": current_resolved_presets,
        "catalog_candidates": _compact_catalog(catalog),
    }
    prompt = json.dumps(prompt_payload, indent=2)
    estimated_llm_cost = _estimate_curation_llm_cost(catalog, prompt, curation_model)

    llm_review = None
    llm_json: Dict[str, Any] = {}
    status = "ready"
    if estimated_llm_cost is None or estimated_llm_cost <= DEFAULT_MAX_USD:
        with use_openrouter_account_scope(owner_email, api_key=storage.get_openrouter_api_key(owner_email)):
            result = await query_model(
                curation_model,
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

    proposed_preset_definitions = _extract_preset_definitions(llm_json) or current_preset_definitions
    resolved_presets = resolve_model_presets(catalog, preset_definitions=proposed_preset_definitions)
    recommended_next = (
        llm_json.get("recommended_next_curation_model")
        or llm_json.get("next_curation_model")
        or curation_model
    )
    next_validation = validate_next_curation_model(recommended_next, catalog, prompt)
    next_status = "promoted" if status == "ready" and next_validation["ok"] else "not_promoted"

    draft_id = str(uuid.uuid4())
    fallback_notes = "Draft generated from the live OpenRouter catalog and current preset rules."
    fallback_risks = [
        "External leaderboards and provider catalogs can change after this draft is generated.",
        "Cost estimates exclude optional web-search and provider surcharges.",
    ]

    draft = {
        "id": draft_id,
        "status": status,
        "trigger": trigger,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_email": owner_email,
        "curation_model": curation_model,
        "curation_model_used": curation_model,
        "next_curation_model": recommended_next,
        "recommended_next_curation_model": recommended_next,
        "next_curator_status": next_status,
        "next_curator_validation": next_validation,
        "estimated_llm_cost": round(estimated_llm_cost, 4) if estimated_llm_cost is not None else None,
        "max_llm_cost": DEFAULT_MAX_USD,
        "sources": SOURCE_URLS,
        "notes": _stringify_review_value(llm_json.get("notes"), fallback_notes),
        "risks": _stringify_review_list(llm_json.get("risks"), fallback_risks),
        "current_preset_definitions": current_preset_definitions,
        "proposed_preset_definitions": proposed_preset_definitions,
        "preset_definitions": proposed_preset_definitions,
        "resolved_presets": resolved_presets,
        "llm_review": llm_review,
    }

    for preset in draft["resolved_presets"]:
        preset["estimated_costs"] = estimate_council_costs(
            preset.get("models", []),
            preset.get("chairman_model"),
            model_map,
        )

    saved = storage.save_model_curation_draft(draft)
    state_patch: Dict[str, Any] = {
        "last_draft_id": draft_id,
        "last_success_at": saved["created_at"],
        "failure_count": 0 if status == "ready" else curation_state.get("failure_count", 0) + 1,
    }
    if next_status == "promoted":
        previous_model = curation_state["current_curation_model"]
        promoted_model = next_validation["normalized_model"]
        state_patch.update({
            "current_curation_model": promoted_model,
            "last_promoted_at": saved["created_at"],
            "promotion_history": [
                *curation_state.get("promotion_history", []),
                {
                    "draft_id": draft_id,
                    "from": previous_model,
                    "to": promoted_model,
                    "promoted_at": saved["created_at"],
                    "trigger": trigger,
                },
            ],
        })
    storage.save_model_curation_state(state_patch)
    return saved


def is_draft_pending_review(
    draft: Optional[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
    owner_email: Optional[str] = None,
) -> bool:
    """Return True when the latest draft still needs owner review."""
    if not draft:
        return False
    if draft.get("approved_at"):
        return False
    if draft.get("status") != "ready":
        return False
    if settings is None:
        settings = storage.get_settings(owner_email)
    if draft.get("id") == settings.get("last_approved_curation_id"):
        return False
    return True


def mark_model_curation_draft_approved(draft: Dict[str, Any], owner_email: Optional[str]) -> Dict[str, Any]:
    approved = {
        **draft,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": owner_email,
    }
    return storage.save_model_curation_draft(approved)
