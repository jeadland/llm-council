"""Private auth for hosted LLM Council."""

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Request

from . import storage

SESSION_COOKIE = "llm_council_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
PASSWORD_ITERATIONS = 390_000
LOGIN_ATTEMPT_TTL_SECONDS = 60 * 10
MAX_LOGIN_ATTEMPTS = 8
PASSWORD_RESET_TTL_SECONDS = 60 * 10
MAX_PASSWORD_RESET_ATTEMPTS = 8
OAUTH_STATE_TTL_SECONDS = 60 * 10


def normalize_email(email: str) -> str:
    return (email or "").lower().strip()


def normalize_name(name: Optional[str]) -> Optional[str]:
    cleaned = (name or "").strip()
    return cleaned or None


def is_auth_required() -> bool:
    configured = os.getenv("AUTH_REQUIRED")
    if configured is not None:
        return configured.strip().lower() not in {"0", "false", "no", "off"}
    return bool(os.getenv("VERCEL") or os.getenv("ADMIN_EMAIL"))


def admin_email() -> Optional[str]:
    email = os.getenv("ADMIN_EMAIL")
    return normalize_email(email) if email else None


def is_owner_email(email: Optional[str]) -> bool:
    expected = admin_email()
    return bool(expected and normalize_email(email or "") == expected)


def owner_oauth_enabled() -> bool:
    configured = os.getenv("ALLOW_OWNER_GOOGLE_OAUTH")
    return configured is not None and configured.strip().lower() in {"1", "true", "yes", "on"}


def cookie_secure() -> bool:
    configured = os.getenv("COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() not in {"0", "false", "no", "off"}
    return bool(os.getenv("VERCEL"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _oauth_state_secret() -> Optional[str]:
    secret = os.getenv("OAUTH_STATE_SECRET")
    return secret.strip() if secret else None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + ("=" * (-len(value) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def create_oauth_state(provider: str) -> str:
    secret = _oauth_state_secret()
    if not secret:
        raise RuntimeError("OAuth state secret is not configured")

    payload = {
        "provider": provider,
        "nonce": secrets.token_urlsafe(18),
        "created_at": datetime.utcnow().isoformat(),
    }
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def verify_oauth_state(state: str, provider: str) -> bool:
    secret = _oauth_state_secret()
    if not secret or not state:
        return False
    try:
        payload_part, signature_part = state.split(".", 1)
        expected = hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected, actual):
            return False
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
        if payload.get("provider") != provider:
            return False
        created_at = datetime.fromisoformat(payload["created_at"])
        if created_at < datetime.utcnow() - timedelta(seconds=OAUTH_STATE_TTL_SECONDS):
            return False
        return True
    except Exception:
        return False


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join([
        "pbkdf2_sha256",
        str(PASSWORD_ITERATIONS),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ])


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def ensure_admin_user() -> Optional[Dict[str, Any]]:
    email = admin_email()
    if not is_auth_required() or not email:
        return None

    existing = storage.get_auth_user(email)
    if existing:
        return existing

    initial_password = os.getenv("ADMIN_INITIAL_PASSWORD")
    if not initial_password:
        return None

    user = {
        "email": email,
        "name": None,
        "role": "owner",
        "password_hash": hash_password(initial_password),
        "auth_methods": ["password"],
        "created_at": datetime.utcnow().isoformat(),
        "password_changed_at": None,
        "onboarding_completed_at": datetime.utcnow().isoformat(),
    }
    storage.save_auth_user(email, user)
    return user


def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    ensure_admin_user()
    normalized_email = normalize_email(email)
    user = storage.get_auth_user(normalized_email)
    if not user:
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    return user


def create_user(email: str, password: str, name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise ValueError("Email is required")
    if storage.get_auth_user(normalized_email):
        raise ValueError("An account already exists for that email")

    now = datetime.utcnow().isoformat()
    user = {
        "email": normalized_email,
        "name": normalize_name(name),
        "role": "owner" if role == "owner" else "user",
        "password_hash": hash_password(password),
        "auth_methods": ["password"],
        "created_at": now,
        "password_changed_at": None,
        "onboarding_completed_at": now,
    }
    storage.save_auth_user(normalized_email, user)
    return user


def upsert_oauth_user(provider: str, email: str, subject: str, name: Optional[str] = None) -> Dict[str, Any]:
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise ValueError("Email is required")
    if not subject:
        raise ValueError("OAuth subject is required")
    if is_owner_email(normalized_email) and not owner_oauth_enabled():
        raise PermissionError("Owner Google sign-in is not enabled")

    now = datetime.utcnow().isoformat()
    user = storage.get_auth_user(normalized_email)
    if user is None:
        user = {
            "email": normalized_email,
            "name": normalize_name(name),
            "role": "user",
            "created_at": now,
            "password_changed_at": None,
            "onboarding_completed_at": now,
        }
    else:
        user.setdefault("email", normalized_email)
        user.setdefault("role", "owner" if is_owner_email(normalized_email) else "user")
        user.setdefault("created_at", now)
        user.setdefault("onboarding_completed_at", now)
        if not user.get("name") and normalize_name(name):
            user["name"] = normalize_name(name)

    auth_methods = set(user.get("auth_methods") or [])
    if user.get("password_hash"):
        auth_methods.add("password")
    auth_methods.add(provider)
    user["auth_methods"] = sorted(auth_methods)

    oauth_accounts = user.get("oauth_accounts") or {}
    existing_account = oauth_accounts.get(provider) or {}
    oauth_accounts[provider] = {
        **existing_account,
        "subject": subject,
        "email": normalized_email,
        "name": normalize_name(name),
        "linked_at": existing_account.get("linked_at") or now,
        "last_login_at": now,
    }
    user["oauth_accounts"] = oauth_accounts
    user["last_login_at"] = now
    storage.save_auth_user(normalized_email, user)
    return user


def create_session(email: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    expires_at = datetime.utcnow() + timedelta(seconds=SESSION_TTL_SECONDS)
    storage.save_session(
        token_hash,
        {
            "email": normalize_email(email),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
        },
        ttl_seconds=SESSION_TTL_SECONDS,
    )
    return token


def get_user_for_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    token_hash = hash_token(token)
    session = storage.get_session(token_hash)
    if not session:
        return None
    try:
        if datetime.fromisoformat(session["expires_at"]) < datetime.utcnow():
            storage.delete_session(token_hash, session.get("email"))
            return None
    except Exception:
        storage.delete_session(token_hash, session.get("email"))
        return None

    user = storage.get_auth_user(session["email"])
    return user


def get_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    return get_user_for_token(request.cookies.get(SESSION_COOKIE))


def change_password(email: str, current_password: str, new_password: str) -> bool:
    normalized_email = normalize_email(email)
    user = storage.get_auth_user(normalized_email)
    if not user or not verify_password(current_password, user.get("password_hash", "")):
        return False
    user["password_hash"] = hash_password(new_password)
    user["password_changed_at"] = datetime.utcnow().isoformat()
    storage.save_auth_user(normalized_email, user)
    storage.delete_sessions_for_email(normalized_email)
    return True


def reset_password(email: str, reset_token: str, new_password: str) -> bool:
    expected_email = admin_email()
    configured_token = os.getenv("ADMIN_PASSWORD_RESET_TOKEN")
    if not expected_email or not configured_token:
        return False
    if email.lower().strip() != expected_email:
        return False
    if not hmac.compare_digest(reset_token, configured_token):
        return False

    user = storage.get_auth_user(expected_email) or {
        "email": expected_email,
        "name": None,
        "role": "owner",
        "auth_methods": ["password"],
        "created_at": datetime.utcnow().isoformat(),
        "password_changed_at": None,
        "onboarding_completed_at": datetime.utcnow().isoformat(),
    }

    user.setdefault("role", "owner")
    auth_methods = set(user.get("auth_methods") or [])
    auth_methods.add("password")
    user["auth_methods"] = sorted(auth_methods)
    user["password_hash"] = hash_password(new_password)
    user["password_changed_at"] = datetime.utcnow().isoformat()
    user["password_reset_at"] = datetime.utcnow().isoformat()
    storage.save_auth_user(expected_email, user)
    storage.delete_sessions_for_email(expected_email)
    return True
