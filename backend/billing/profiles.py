"""Curated managed-balance council profiles."""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

from ..openrouter import estimate_council_costs, resolve_model_presets


SERVICE_MULTIPLIER_DEFAULT = 1.35


PROFILE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "slug": "quick",
        "display_name": "Quick Council",
        "best_for": "Fast second opinions and lower-risk everyday questions.",
        "preset_id": "efficient-daily",
        "max_user_visible_charge_usd": 0.40,
        "expected_speed": "Fast",
        "sort_order": 10,
    },
    {
        "slug": "balanced",
        "display_name": "Balanced Council",
        "best_for": "Most planning, writing, architecture, and decision questions.",
        "preset_id": "premium-balanced",
        "max_user_visible_charge_usd": 0.90,
        "expected_speed": "Medium",
        "sort_order": 20,
    },
    {
        "slug": "deep",
        "display_name": "Deep Council",
        "best_for": "Harder reasoning, strategy, diligence, and synthesis work.",
        "preset_id": "ultra-premium-frontier",
        "max_user_visible_charge_usd": 1.35,
        "expected_speed": "Slower",
        "sort_order": 30,
    },
    {
        "slug": "ultra",
        "display_name": "Ultra Council",
        "best_for": "Highest-end curated council for high-stakes questions.",
        "preset_id": "ultra-premium-frontier",
        "max_user_visible_charge_usd": 1.75,
        "expected_speed": "Slowest",
        "sort_order": 40,
    },
]


def service_multiplier() -> float:
    try:
        return max(1.0, float(os.getenv("SERVICE_MULTIPLIER_DEFAULT", SERVICE_MULTIPLIER_DEFAULT)))
    except (TypeError, ValueError):
        return SERVICE_MULTIPLIER_DEFAULT


def managed_mode_enabled() -> bool:
    return os.getenv("MANAGED_MODE_ENABLED", "false").strip().lower() == "true"


def package_amount(package_id: str) -> Optional[float]:
    return {
        "starter_5": 5.00,
        "standard_10": 10.00,
        "power_20": 20.00,
    }.get(package_id)


def topup_packages() -> List[Dict[str, Any]]:
    return [
        {"id": "starter_5", "amount_usd": 5.00, "label": "$5", "recommended": False},
        {"id": "standard_10", "amount_usd": 10.00, "label": "$10", "recommended": True},
        {"id": "power_20", "amount_usd": 20.00, "label": "$20", "recommended": False},
    ]


def _questions_per_topup(amount: float, low: Optional[float], high: Optional[float]) -> Optional[str]:
    if not low or not high or low <= 0 or high <= 0:
        return None
    min_questions = max(1, math.floor(amount / high))
    max_questions = max(min_questions, math.floor(amount / low))
    return f"{min_questions}-{max_questions}"


def _format_cost(low: Optional[float], high: Optional[float]) -> str:
    if low is None or high is None:
        return "Pricing unavailable"
    return f"${low:.2f}-${high:.2f}"


def build_profiles(
    catalog: List[Dict[str, Any]],
    preset_definitions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    model_map = {model.get("id"): model for model in catalog if model.get("id")}
    presets = resolve_model_presets(catalog, preset_definitions=preset_definitions)
    presets_by_id = {preset.get("id"): preset for preset in presets}
    multiplier = service_multiplier()
    profiles = []

    for definition in PROFILE_DEFINITIONS:
        preset = presets_by_id.get(definition["preset_id"]) or {}
        models = preset.get("models") or []
        chairman = preset.get("chairman_model")
        estimate = estimate_council_costs(models, chairman, model_map) if models and chairman else {"available": False}
        scenario = ((estimate.get("scenarios") or {}).get("normal") or {})
        raw_low = scenario.get("low") if scenario.get("available") else None
        raw_high = scenario.get("high") if scenario.get("available") else None
        app_low = round(float(raw_low) * multiplier, 2) if raw_low is not None else None
        app_high = round(float(raw_high) * multiplier, 2) if raw_high is not None else None
        cap = float(definition["max_user_visible_charge_usd"])
        reserve_amount = cap

        profiles.append({
            **definition,
            "enabled": bool(models and chairman and not preset.get("missing")),
            "models": models,
            "chairman_model": chairman,
            "model_summary": " + ".join((model.split("/", 1)[-1] for model in models[:4])) if models else "",
            "service_multiplier": multiplier,
            "estimated_raw_cost_low_usd": raw_low,
            "estimated_raw_cost_high_usd": raw_high,
            "estimated_app_cost_low_usd": app_low,
            "estimated_app_cost_high_usd": app_high,
            "estimated_app_cost_display": _format_cost(app_low, app_high),
            "max_user_visible_charge_usd": cap,
            "reserve_amount_usd": reserve_amount,
            "questions_per_5": _questions_per_topup(5.00, app_low, min(app_high, cap) if app_high else None),
            "pricing_available": raw_low is not None and raw_high is not None,
        })

    return sorted(profiles, key=lambda item: item["sort_order"])


def fallback_profiles() -> List[Dict[str, Any]]:
    multiplier = service_multiplier()
    return [
        {
            **definition,
            "enabled": False,
            "models": [],
            "chairman_model": None,
            "model_summary": "",
            "service_multiplier": multiplier,
            "estimated_raw_cost_low_usd": None,
            "estimated_raw_cost_high_usd": None,
            "estimated_app_cost_low_usd": None,
            "estimated_app_cost_high_usd": None,
            "estimated_app_cost_display": "Pricing unavailable",
            "reserve_amount_usd": float(definition["max_user_visible_charge_usd"]),
            "questions_per_5": None,
            "pricing_available": False,
        }
        for definition in PROFILE_DEFINITIONS
    ]


def profile_by_slug(profiles: List[Dict[str, Any]], slug: Optional[str]) -> Optional[Dict[str, Any]]:
    target = slug or "balanced"
    return next((profile for profile in profiles if profile.get("slug") == target), None)
