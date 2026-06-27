"""Bearer-token auth for local Codex agent access."""

import hashlib
import hmac
import os
from typing import Optional

from fastapi import HTTPException, Request

from . import auth


def configured_token_hash() -> Optional[str]:
    token_hash = os.getenv("LLM_COUNCIL_AGENT_TOKEN_HASH", "").strip()
    return token_hash or None


def is_configured() -> bool:
    return configured_token_hash() is not None


def hash_agent_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def max_cost_usd() -> float:
    raw = os.getenv("LLM_COUNCIL_AGENT_MAX_USD", "3.00").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 3.0
    return max(0.0, value)


def owner_email() -> Optional[str]:
    return os.getenv("LLM_COUNCIL_AGENT_OWNER_EMAIL") or auth.admin_email()


def require_agent(request: Request) -> str:
    expected_hash = configured_token_hash()
    if not expected_hash:
        raise HTTPException(status_code=503, detail="LLM Council agent access is not configured")

    authorization = request.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Missing agent bearer token")

    supplied_hash = hash_agent_token(token.strip())
    if not hmac.compare_digest(supplied_hash, expected_hash):
        raise HTTPException(status_code=401, detail="Invalid agent bearer token")

    return owner_email() or "local-owner"
