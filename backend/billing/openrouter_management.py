"""OpenRouter Management API helpers for managed-balance users."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


OPENROUTER_MANAGEMENT_BASE_URL = os.getenv("OPENROUTER_MANAGEMENT_BASE_URL", "https://openrouter.ai/api/v1")


def management_key() -> str:
    return os.getenv("OPENROUTER_MANAGEMENT_KEY", "").strip()


def configured() -> bool:
    return bool(management_key())


def _headers() -> Dict[str, str]:
    key = management_key()
    if not key:
        raise RuntimeError("OPENROUTER_MANAGEMENT_KEY is not configured")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _unwrap_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        return {**data, **{key: value for key, value in payload.items() if key != "data"}}
    return payload


async def create_child_key(user_id: str, raw_allowance_usd: float) -> Dict[str, Any]:
    payload = {
        "name": f"llm-council-managed-user-{user_id}",
        "limit": round(max(0.0, raw_allowance_usd), 4),
        "limit_reset": None,
        "include_byok_in_limit": False,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{OPENROUTER_MANAGEMENT_BASE_URL}/keys",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return _unwrap_data(response.json())


async def update_child_key(key_hash: str, *, limit_usd: float, disabled: bool = False, name: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "disabled": disabled,
        "limit": round(max(0.0, limit_usd), 4),
        "limit_reset": None,
        "include_byok_in_limit": False,
    }
    if name:
        payload["name"] = name
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.patch(
            f"{OPENROUTER_MANAGEMENT_BASE_URL}/keys/{key_hash}",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return _unwrap_data(response.json())


async def disable_child_key(key_hash: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.patch(
            f"{OPENROUTER_MANAGEMENT_BASE_URL}/keys/{key_hash}",
            headers=_headers(),
            json={"disabled": True},
        )
        response.raise_for_status()
        return _unwrap_data(response.json())


async def fetch_credits() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{OPENROUTER_MANAGEMENT_BASE_URL}/credits",
            headers=_headers(),
        )
        response.raise_for_status()
        return _unwrap_data(response.json())
