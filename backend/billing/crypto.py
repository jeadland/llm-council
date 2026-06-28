"""Secret encryption helpers for stored provider keys.

The hosted app must set KEY_ENCRYPTION_SECRET. Local tests and local-only
development can use a deterministic fallback so existing smoke tests keep
working without real secrets.
"""

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet


LOCAL_DEV_SECRET = "llm-council-local-dev-key-not-for-production"


def _secret_material() -> str:
    secret = os.getenv("KEY_ENCRYPTION_SECRET", "").strip()
    if secret:
        return secret
    if os.getenv("VERCEL") or os.getenv("MANAGED_MODE_ENABLED", "").lower() == "true":
        raise RuntimeError("KEY_ENCRYPTION_SECRET is required for hosted or managed billing mode")
    return LOCAL_DEV_SECRET


def _fernet() -> Fernet:
    material = _secret_material()
    try:
        # Accept an operator-supplied Fernet key directly when it is valid.
        return Fernet(material.encode("utf-8"))
    except Exception:
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value:
        raise ValueError("Cannot encrypt an empty secret")
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 12:
        return f"{value[:3]}..."
    return f"{value[:8]}...{value[-4:]}"
