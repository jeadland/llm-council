"""High-level managed-balance billing operations."""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

from . import db
from .crypto import decrypt_secret, encrypt_secret, hash_secret, mask_secret
from . import openrouter_management
from .profiles import (
    build_profiles,
    fallback_profiles,
    managed_mode_enabled,
    profile_by_slug,
    service_multiplier,
    topup_packages,
)


def billing_status(user_id: str, *, byok_configured: bool = False) -> Dict[str, Any]:
    profile = db.get_or_create_profile(user_id)
    balance = db.ledger_balance(user_id)
    reserved = db.reserved_balance(user_id)
    managed_key = db.get_managed_key(user_id)
    managed_enabled = managed_mode_enabled()
    mode = profile.get("billing_mode") or "byok"
    return {
        "billing_mode": mode,
        "managed_mode_enabled": managed_enabled,
        "byok_configured": byok_configured,
        "balance_usd": round(balance, 2),
        "reserved_usd": round(reserved, 2),
        "available_balance_usd": round(balance - reserved, 2),
        "service_multiplier": float(profile.get("service_multiplier") or service_multiplier()),
        "managed_key_configured": bool(managed_key and managed_key.get("encrypted_openrouter_key")),
        "managed_key_disabled": bool(managed_key and managed_key.get("disabled")),
        "topup_packages": topup_packages(),
        "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY", "").strip()),
    }


def set_mode(user_id: str, mode: str) -> Dict[str, Any]:
    return db.set_billing_mode(user_id, mode)


def ledger(user_id: str) -> Dict[str, Any]:
    return {
        "balance_usd": round(db.ledger_balance(user_id), 2),
        "reserved_usd": round(db.reserved_balance(user_id), 2),
        "available_balance_usd": round(db.available_balance(user_id), 2),
        "entries": db.list_ledger(user_id),
    }


def get_profiles(catalog: List[Dict[str, Any]], preset_definitions: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    try:
        return build_profiles(catalog, preset_definitions=preset_definitions)
    except Exception:
        return fallback_profiles()


def estimate_for_profile(profiles: List[Dict[str, Any]], profile_slug: Optional[str], prompt: str = "") -> Dict[str, Any]:
    profile = profile_by_slug(profiles, profile_slug)
    if not profile:
        raise ValueError("Unknown managed counsel profile")
    char_input_tokens = max(1, math.ceil(len(prompt or "") / 4))
    estimated_input_modifier = min(1.4, max(0.8, char_input_tokens / 6000))
    low = profile.get("estimated_app_cost_low_usd")
    high = profile.get("estimated_app_cost_high_usd")
    if low is not None and high is not None:
        low = round(float(low) * estimated_input_modifier, 2)
        high = round(float(high) * estimated_input_modifier, 2)
    return {
        "profile": profile,
        "estimated_app_cost_low_usd": low,
        "estimated_app_cost_high_usd": high,
        "max_app_charge_usd": float(profile["max_user_visible_charge_usd"]),
        "estimated_input_tokens": char_input_tokens,
    }


def _raw_allowance(user_id: str) -> float:
    multiplier = service_multiplier()
    if multiplier <= 0:
        return 0.0
    return round(max(0.0, db.ledger_balance(user_id)) / multiplier, 4)


def _key_usage_to_date(user_id: str) -> float:
    record = db.get_managed_key(user_id) or {}
    return round(float(record.get("usage_total_usd") or 0), 4)


async def ensure_managed_openrouter_key(user_id: str) -> str:
    record = db.get_managed_key(user_id)
    if record and record.get("encrypted_openrouter_key") and not record.get("disabled"):
        key = decrypt_secret(record["encrypted_openrouter_key"])
        if key:
            return key
    if not openrouter_management.configured():
        raise RuntimeError("Managed model usage is temporarily unavailable. Your balance was not charged. You can still use your own OpenRouter key.")

    raw_allowance = _raw_allowance(user_id)
    created = await openrouter_management.create_child_key(user_id, raw_allowance)
    plaintext_key = created.get("key") or created.get("api_key") or created.get("token")
    key_hash = created.get("hash") or created.get("key_hash") or created.get("id") or (hash_secret(plaintext_key) if plaintext_key else None)
    if not plaintext_key or not key_hash:
        raise RuntimeError("OpenRouter did not return a managed child key")
    db.save_managed_key(user_id, {
        "openrouter_key_hash": key_hash,
        "encrypted_openrouter_key": encrypt_secret(plaintext_key),
        "openrouter_name": created.get("name") or f"llm-council-managed-user-{user_id}",
        "limit_total_usd": raw_allowance,
        "limit_remaining_usd": created.get("limit_remaining"),
        "usage_total_usd": created.get("usage") or 0,
        "usage_daily_usd": created.get("usage_daily"),
        "usage_weekly_usd": created.get("usage_weekly"),
        "usage_monthly_usd": created.get("usage_monthly"),
        "disabled": created.get("disabled") or False,
    })
    return plaintext_key


async def sync_managed_key_limit(user_id: str) -> None:
    record = db.get_managed_key(user_id)
    if not record or not record.get("openrouter_key_hash") or not openrouter_management.configured():
        return
    limit = round(_key_usage_to_date(user_id) + _raw_allowance(user_id), 4)
    disabled = db.ledger_balance(user_id) <= 0
    updated = await openrouter_management.update_child_key(
        record["openrouter_key_hash"],
        limit_usd=limit,
        disabled=disabled,
        name=record.get("openrouter_name"),
    )
    db.save_managed_key(user_id, {
        **record,
        "limit_total_usd": updated.get("limit") or limit,
        "limit_remaining_usd": updated.get("limit_remaining"),
        "usage_total_usd": updated.get("usage") or record.get("usage_total_usd") or 0,
        "usage_daily_usd": updated.get("usage_daily"),
        "usage_weekly_usd": updated.get("usage_weekly"),
        "usage_monthly_usd": updated.get("usage_monthly"),
        "disabled": updated.get("disabled") if updated.get("disabled") is not None else disabled,
    })


def latest_coverage() -> Dict[str, Any]:
    snapshot = db.latest_coverage_snapshot()
    if snapshot:
        return snapshot
    if not openrouter_management.configured():
        return {
            "status": "not_configured",
            "coverage_ratio": None,
            "managed_raw_liability_usd": db.managed_raw_liability(),
            "message": "OPENROUTER_MANAGEMENT_KEY is not configured.",
        }
    return {
        "status": "unknown",
        "coverage_ratio": None,
        "managed_raw_liability_usd": db.managed_raw_liability(),
    }


def coverage_allows_runs() -> bool:
    if db.get_config("managed_mode_paused", False):
        return False
    snapshot = latest_coverage()
    return snapshot.get("status") in {"healthy", "warning"} or (
        snapshot.get("managed_raw_liability_usd", 0) == 0 and openrouter_management.configured()
    )


async def refresh_coverage() -> Dict[str, Any]:
    credits = await openrouter_management.fetch_credits()
    total_credits = float(credits.get("total_credits") or credits.get("total_credits_usd") or 0)
    total_usage = float(credits.get("total_usage") or credits.get("total_usage_usd") or 0)
    available = total_credits - total_usage
    liability = db.managed_raw_liability()
    largest_raw_run = 1.75 / service_multiplier()
    buffer = max(25.0, liability * 0.25, largest_raw_run * 3)
    floor = liability + buffer
    ratio = available / liability if liability > 0 else 999.0
    if available < largest_raw_run or ratio < float(os.getenv("OPENROUTER_EMERGENCY_COVERAGE_RATIO", "1.00")):
        status = "emergency"
    elif ratio < float(os.getenv("OPENROUTER_CRITICAL_COVERAGE_RATIO", "1.10")):
        status = "critical"
    elif ratio < float(os.getenv("OPENROUTER_WARNING_COVERAGE_RATIO", "1.25")):
        status = "warning"
    else:
        status = "healthy"
    return db.save_coverage_snapshot({
        "total_credits_usd": round(total_credits, 4),
        "total_usage_usd": round(total_usage, 4),
        "available_credits_usd": round(available, 4),
        "managed_raw_liability_usd": round(liability, 4),
        "operating_buffer_usd": round(buffer, 4),
        "required_floor_usd": round(floor, 4),
        "coverage_ratio": round(ratio, 4) if ratio != 999.0 else None,
        "status": status,
    })


async def prepare_managed_run(user_id: str, run_id: str, profile: Dict[str, Any], estimate: Dict[str, Any]) -> Dict[str, Any]:
    if not managed_mode_enabled():
        raise ValueError("Managed LLM Council Balance is not enabled yet.")
    if not profile.get("enabled"):
        raise ValueError("This managed counsel profile is temporarily unavailable.")
    if not coverage_allows_runs():
        raise ValueError("Managed model usage is temporarily unavailable. Your balance was not charged. You can still use your own OpenRouter key.")

    max_charge = float(estimate["max_app_charge_usd"])
    reservation = db.create_reservation(
        user_id,
        run_id,
        max_charge,
        {
            "profile_slug": profile["slug"],
            "estimated_app_cost_low_usd": estimate.get("estimated_app_cost_low_usd"),
            "estimated_app_cost_high_usd": estimate.get("estimated_app_cost_high_usd"),
        },
    )
    try:
        key = await ensure_managed_openrouter_key(user_id)
        await sync_managed_key_limit(user_id)
    except Exception:
        db.release_reservation(reservation["reservation_id"])
        raise
    return {
        "billing_mode": "managed",
        "profile_slug": profile["slug"],
        "reservation_id": reservation["reservation_id"],
        "reserved_amount_usd": max_charge,
        "openrouter_api_key": key,
        "council_models": profile["models"],
        "chairman_model": profile["chairman_model"],
        "estimate": estimate,
    }


def release_run_reservation(run_billing: Dict[str, Any]) -> None:
    reservation_id = run_billing.get("reservation_id")
    if reservation_id:
        db.release_reservation(reservation_id)


async def finalize_managed_run(user_id: str, run_id: str, run_billing: Dict[str, Any], cost_summary: Dict[str, Any]) -> Dict[str, Any]:
    raw_cost = float(cost_summary.get("total_usd") or 0)
    multiplier = float(run_billing.get("estimate", {}).get("profile", {}).get("service_multiplier") or service_multiplier())
    actual_app_cost = min(float(run_billing.get("reserved_amount_usd") or 0), round(raw_cost * multiplier, 4))
    reservation_id = run_billing.get("reservation_id")
    if reservation_id:
        db.finalize_reservation(
            reservation_id,
            actual_app_cost,
            {
                "raw_openrouter_cost_usd": raw_cost,
                "service_multiplier": multiplier,
                "cost_summary_status": cost_summary.get("status"),
            },
        )
    remaining = db.available_balance(user_id)
    receipt = {
        "council_run_id": run_id,
        "user_id": user_id,
        "billing_mode": "managed",
        "profile_slug": run_billing.get("profile_slug"),
        "estimated_app_cost_low_usd": run_billing.get("estimate", {}).get("estimated_app_cost_low_usd"),
        "estimated_app_cost_high_usd": run_billing.get("estimate", {}).get("estimated_app_cost_high_usd"),
        "max_app_charge_usd": run_billing.get("estimate", {}).get("max_app_charge_usd"),
        "reserved_amount_usd": run_billing.get("reserved_amount_usd"),
        "actual_raw_cost_usd": round(raw_cost, 6),
        "actual_app_cost_usd": round(actual_app_cost, 4),
        "service_multiplier": multiplier,
        "remaining_balance_usd": round(remaining, 2),
        "metadata": {"cost_summary_status": cost_summary.get("status")},
    }
    db.save_run_receipt(receipt)
    await sync_managed_key_limit(user_id)
    return receipt


def admin_overview() -> Dict[str, Any]:
    balance = db.outstanding_app_credits()
    snapshot = latest_coverage()
    failed = db.failed_webhooks()
    users = db.users_by_balance()
    return {
        "managed_mode_enabled": managed_mode_enabled(),
        "managed_mode_paused": bool(db.get_config("managed_mode_paused", False)),
        "app_credits_outstanding_usd": round(balance, 2),
        "managed_raw_liability_usd": round(db.managed_raw_liability(), 2),
        "coverage": snapshot,
        "failed_webhooks_count": len(failed),
        "failed_webhooks": failed,
        "recent_payments": db.recent_payments(),
        "recent_runs": db.recent_runs(),
        "users_by_balance": users,
        "negative_balance_users": [user for user in users if float(user.get("balance") or 0) < 0],
    }


def pause_managed_mode(admin_user_id: str) -> Dict[str, Any]:
    db.set_config("managed_mode_paused", True)
    db.audit(admin_user_id, "managed_mode_pause", target_object_type="billing_config", target_object_id="managed_mode_paused", after={"paused": True})
    return admin_overview()


def resume_managed_mode(admin_user_id: str) -> Dict[str, Any]:
    db.set_config("managed_mode_paused", False)
    db.audit(admin_user_id, "managed_mode_resume", target_object_type="billing_config", target_object_id="managed_mode_paused", after={"paused": False})
    return admin_overview()
