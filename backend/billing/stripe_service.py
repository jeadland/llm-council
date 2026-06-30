"""Stripe Checkout and webhook helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

import httpx

from . import db
from .profiles import package_amount, package_price_env_var


STRIPE_API_BASE = "https://api.stripe.com/v1"
STRIPE_API_VERSION = "2026-02-25.clover"
TEST_TOPUP_LOOKUP_KEY = "llm_council_balance_test_1"


def _secret_key() -> str:
    return os.getenv("STRIPE_SECRET_KEY", "").strip()


def _webhook_secret() -> str:
    return os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


def _price_id(package_id: str) -> Optional[str]:
    price_env_var = package_price_env_var(package_id)
    if not price_env_var:
        return None
    return os.getenv(price_env_var, "").strip()


def _stripe_headers(secret_key: str, *, idempotency_key: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Stripe-Version": STRIPE_API_VERSION,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def _resolve_test_topup_price_id(secret_key: str) -> str:
    configured_price_id = _price_id("test_1")
    if configured_price_id:
        return configured_price_id

    reference_price_id = _price_id("standard_10")
    if not reference_price_id:
        raise RuntimeError("Stripe price id is not configured for standard_10")

    async with httpx.AsyncClient(timeout=15.0) as client:
        existing = await client.get(
            f"{STRIPE_API_BASE}/prices",
            params=[("lookup_keys[]", TEST_TOPUP_LOOKUP_KEY), ("limit", "1")],
            headers=_stripe_headers(secret_key),
        )
        existing.raise_for_status()
        existing_payload = existing.json()
        existing_prices = existing_payload.get("data") or []
        if existing_prices:
            return existing_prices[0]["id"]

        reference = await client.get(
            f"{STRIPE_API_BASE}/prices/{reference_price_id}",
            headers=_stripe_headers(secret_key),
        )
        reference.raise_for_status()
        product_id = reference.json().get("product")
        if not product_id:
            raise RuntimeError("Reference Stripe price is missing a product")

        created = await client.post(
            f"{STRIPE_API_BASE}/prices",
            data={
                "currency": "usd",
                "unit_amount": "100",
                "product": product_id,
                "nickname": "LLM Council Balance $1 test",
                "lookup_key": TEST_TOPUP_LOOKUP_KEY,
                "metadata[llm_council_package]": "test_1",
                "metadata[purpose]": "llm_council_balance",
                "metadata[test_topup]": "true",
            },
            headers=_stripe_headers(
                secret_key,
                idempotency_key="llm-council-balance-test-1-usd-v1",
            ),
        )
        created.raise_for_status()
        return created.json()["id"]


async def _resolve_price_id(package_id: str, secret_key: str) -> Optional[str]:
    if package_id == "test_1":
        return await _resolve_test_topup_price_id(secret_key)
    return _price_id(package_id)


def stripe_configured() -> bool:
    return bool(_secret_key())


async def create_checkout_session(*, user_id: str, package_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
    amount = package_amount(package_id)
    secret_key = _secret_key()
    if amount is None:
        raise ValueError("Unsupported balance package")
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    price_id = await _resolve_price_id(package_id, secret_key)
    if not price_id:
        raise RuntimeError(f"Stripe price id is not configured for {package_id}")

    data = {
        "mode": "payment",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata[user_id]": user_id,
        "metadata[credit_package]": package_id,
        "metadata[app_credit_amount_usd]": f"{amount:.2f}",
        "payment_intent_data[metadata][user_id]": user_id,
        "payment_intent_data[metadata][credit_package]": package_id,
        "payment_intent_data[metadata][app_credit_amount_usd]": f"{amount:.2f}",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{STRIPE_API_BASE}/checkout/sessions",
            data=data,
            headers=_stripe_headers(secret_key),
        )
        response.raise_for_status()
        payload = response.json()
    return {
        "checkout_session_id": payload.get("id"),
        "url": payload.get("url"),
        "package_id": package_id,
        "amount_usd": amount,
    }


def verify_webhook(payload: bytes, signature_header: str, tolerance_seconds: int = 300) -> Dict[str, Any]:
    secret = _webhook_secret()
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")

    parts = {}
    for item in (signature_header or "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts.setdefault(key, []).append(value)
    timestamps = parts.get("t") or []
    signatures = parts.get("v1") or []
    if not timestamps or not signatures:
        raise ValueError("Missing Stripe webhook signature")

    timestamp = timestamps[0]
    try:
        signed_at = int(timestamp)
    except ValueError as e:
        raise ValueError("Invalid Stripe webhook timestamp") from e
    if abs(time.time() - signed_at) > tolerance_seconds:
        raise ValueError("Stripe webhook timestamp is outside tolerance")

    signed_payload = timestamp.encode("utf-8") + b"." + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise ValueError("Invalid Stripe webhook signature")
    return json.loads(payload.decode("utf-8"))


def _usd_from_cents(value: Any) -> float:
    return round(float(value or 0) / 100.0, 4)


def _payment_intent_id(stripe_object: Dict[str, Any]) -> Optional[str]:
    payment_intent = stripe_object.get("payment_intent") or stripe_object.get("payment_intent_id")
    if isinstance(payment_intent, dict):
        return payment_intent.get("id")
    return payment_intent


def _fulfill_payment_adjustment(event_id: str, event_type: str, stripe_object: Dict[str, Any]) -> Dict[str, Any]:
    payment_intent_id = _payment_intent_id(stripe_object)
    if not payment_intent_id:
        raise ValueError("Stripe adjustment is missing payment_intent")
    payment = db.get_stripe_payment_by_intent(payment_intent_id)
    if not payment:
        raise ValueError("Stripe adjustment does not match a managed-balance payment")

    is_refund = event_type in {"refund.created", "charge.refunded"}
    entry_type = "refund" if is_refund else "dispute"
    status = "refunded" if is_refund else "disputed"
    cumulative = event_type == "charge.refunded"
    amount_usd = _usd_from_cents(stripe_object.get("amount_refunded") if cumulative else stripe_object.get("amount"))
    if amount_usd <= 0:
        raise ValueError("Stripe adjustment amount must be positive")

    existing_refunds = abs(db.ledger_adjustment_total(payment_intent_id, "refund"))
    existing_disputes = abs(db.ledger_adjustment_total(payment_intent_id, "dispute"))
    original_credit = float(payment.get("app_credit_amount_usd") or 0)
    remaining_adjustable = max(0.0, original_credit - existing_refunds - existing_disputes)
    same_type_existing = existing_refunds if entry_type == "refund" else existing_disputes
    amount_to_apply = max(0.0, amount_usd - same_type_existing) if cumulative else amount_usd
    amount_to_apply = min(amount_to_apply, remaining_adjustable)

    if amount_to_apply > 0:
        db.add_ledger_entry(
            payment["user_id"],
            entry_type,
            -round(amount_to_apply, 4),
            stripe_checkout_session_id=payment.get("checkout_session_id"),
            stripe_payment_intent_id=payment_intent_id,
            stripe_event_id=event_id,
            metadata={"event_type": event_type},
        )
    db.update_stripe_payment_status(payment["checkout_session_id"], status)
    db.mark_stripe_event(event_id, "processed")
    return {
        "status": "processed",
        "stripe_event_id": event_id,
        "adjustment_type": entry_type,
        "adjusted_usd": round(amount_to_apply, 4),
    }


def fulfill_checkout_session(event: Dict[str, Any]) -> Dict[str, Any]:
    event_id = event.get("id")
    event_type = event.get("type") or "unknown"
    if not event_id:
        raise ValueError("Stripe event is missing id")

    event_claim = db.insert_stripe_event(event_id, event_type, event)
    if event_claim == "duplicate":
        return {"status": "duplicate", "stripe_event_id": event_id}

    try:
        stripe_object = ((event.get("data") or {}).get("object") or {})
        if event_type in {"refund.created", "charge.refunded", "charge.dispute.created", "charge.dispute.funds_withdrawn"}:
            return _fulfill_payment_adjustment(event_id, event_type, stripe_object)

        if event_type != "checkout.session.completed":
            db.mark_stripe_event(event_id, "ignored")
            return {"status": "ignored", "stripe_event_id": event_id, "event_type": event_type}

        session = stripe_object
        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id")
        package_id = metadata.get("credit_package")
        amount = package_amount(package_id or "")
        if not user_id or amount is None:
            raise ValueError("Stripe checkout session is missing managed-balance metadata")
        if session.get("mode") != "payment":
            raise ValueError("Stripe checkout session is not a one-time payment")
        if session.get("currency") != "usd":
            raise ValueError("Stripe checkout currency is not supported")
        if session.get("payment_status") != "paid":
            raise ValueError("Stripe checkout session is not paid")

        checkout_session_id = session.get("id")
        payment_intent_id = session.get("payment_intent")
        if not checkout_session_id:
            raise ValueError("Stripe checkout session is missing id")
        if not payment_intent_id:
            raise ValueError("Stripe checkout session is missing payment intent")
        expected_cents = int(round(amount * 100))
        paid_cents = int(session.get("amount_total") or 0)
        if paid_cents != expected_cents:
            raise ValueError("Stripe checkout amount does not match the selected balance package")
        if db.stripe_purchase_credit_exists(checkout_session_id):
            db.mark_stripe_event(event_id, "processed")
            return {
                "status": "duplicate_payment",
                "stripe_event_id": event_id,
                "checkout_session_id": checkout_session_id,
            }
        gross_amount = paid_cents / 100.0
        db.upsert_stripe_payment(
            user_id=user_id,
            checkout_session_id=checkout_session_id,
            payment_intent_id=payment_intent_id,
            app_credit_amount_usd=amount,
            gross_amount_usd=gross_amount,
            stripe_customer_id=session.get("customer"),
            status="paid",
        )
        db.add_ledger_entry(
            user_id,
            "purchase",
            amount,
            stripe_checkout_session_id=checkout_session_id,
            stripe_payment_intent_id=payment_intent_id,
            stripe_event_id=event_id,
            metadata={"credit_package": package_id},
        )
        profile = db.get_or_create_profile(user_id)
        if profile.get("billing_mode") != "managed":
            db.set_billing_mode(user_id, "managed")
        db.mark_stripe_event(event_id, "processed")
        return {"status": "processed", "stripe_event_id": event_id, "credited_usd": amount}
    except Exception as e:
        db.mark_stripe_event(event_id, "failed", str(e))
        raise
