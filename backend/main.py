"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import os
import hmac
import httpx
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode

from . import storage
from . import auth
from . import agent_auth
from .config import OPENROUTER_API_KEY, ENHANCER_MODEL
from .council import (
    build_council_cost_summary,
    collect_council_cost_calls,
    run_full_council,
    generate_conversation_title,
    improve_user_prompt,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    format_stage2_incomplete_error,
)
from .openrouter import build_cost_summary, fetch_openrouter_model_catalog, reconcile_cost_calls, resolve_model_presets
from .openrouter import use_openrouter_account_scope
from .billing import service as billing_service
from .billing import stripe_service
from .model_curation import (
    create_model_curation_draft,
    is_draft_pending_review,
    mark_model_curation_draft_approved,
)

SUBPATH_PREFIX = "/llm-council"


class SubpathPrefixMiddleware:
    """Let the API work both at the domain root and under /llm-council."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in {"http", "websocket"}:
            path = scope.get("path", "")
            if path == SUBPATH_PREFIX:
                scope["root_path"] = f"{scope.get('root_path', '')}{SUBPATH_PREFIX}"
                scope["path"] = "/"
            elif path.startswith(f"{SUBPATH_PREFIX}/"):
                scope["root_path"] = f"{scope.get('root_path', '')}{SUBPATH_PREFIX}"
                scope["path"] = path[len(SUBPATH_PREFIX):] or "/"
        await self.app(scope, receive, send)


def _normalize_request_path(path: str) -> str:
    if path == SUBPATH_PREFIX:
        return "/"
    if path.startswith(f"{SUBPATH_PREFIX}/"):
        return path[len(SUBPATH_PREFIX):] or "/"
    return path


app = FastAPI(title="LLM Council API")
app.add_middleware(SubpathPrefixMiddleware)
RUN_TASKS: Dict[str, asyncio.Task] = {}
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/auth/oauth/google/start",
    "/api/auth/oauth/google/callback",
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/reset-password",
    "/api/cron/model-curation",
    "/api/stripe/webhook",
}
OPENROUTER_KEY_INFO_URL = "https://openrouter.ai/api/v1/key"
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_OAUTH_PROVIDER = "google"
GOOGLE_OAUTH_STATE_COOKIE = "llm_council_google_oauth_state"
GOOGLE_ONLY_AUTH_DETAIL = "Email/password login is disabled. Use Google sign-in."

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.0\.1\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_auth_for_api(request: Request, call_next):
    """Protect app APIs while keeping auth bootstrap endpoints public."""
    path = _normalize_request_path(request.url.path)
    if path.startswith("/api/agent/"):
        return await call_next(request)
    if path.startswith("/api/") and path not in PUBLIC_API_PATHS and auth.is_auth_required():
        if auth.get_user_from_request(request) is None:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    content: str


class CreateRunRequest(BaseModel):
    content: str
    billing_mode: Optional[str] = None
    profile_slug: Optional[str] = None


class AgentResearchPrepareRequest(BaseModel):
    question: str
    evidence: Optional[str] = None
    research_depth: str = "hard"
    max_cost_usd: Optional[float] = None


class AgentResearchRunRequest(BaseModel):
    approval_id: str
    approved_cost_cap_usd: float


class PinConversationRequest(BaseModel):
    pinned: bool


class UpdateSettingsRequest(BaseModel):
    council_models: Optional[List[str]] = None
    chairman_model: Optional[str] = None
    enhancer_model: Optional[str] = None
    theme_mode: Optional[str] = None
    active_model_group_id: Optional[str] = None
    custom_model_groups: Optional[List[Dict[str, Any]]] = None
    curated_model_presets: Optional[List[Dict[str, Any]]] = None
    last_approved_curation_id: Optional[str] = None


class ImprovePromptRequest(BaseModel):
    content: str


class UpdateOpenRouterIntegrationRequest(BaseModel):
    api_key: Optional[str] = None
    clear: bool = False


class UpdateBillingModeRequest(BaseModel):
    billing_mode: str


class CreateCheckoutRequest(BaseModel):
    package_id: str


class CouncilEstimateRequest(BaseModel):
    content: str
    profile_slug: Optional[str] = "balanced"


class SignupRequest(BaseModel):
    name: Optional[str] = None
    email: str
    password: str
    openrouter_api_key: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    email: str
    reset_token: str
    new_password: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""

    id: str
    created_at: str
    title: str
    pinned: bool = False
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""

    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "app": "llm-council",
        "storage": "redis-or-local",
        "managed_mode_enabled": os.getenv("MANAGED_MODE_ENABLED", "false").strip().lower() == "true",
        "billing_database_configured": bool(os.getenv("BILLING_DATABASE_URL") or os.getenv("DATABASE_URL")),
        "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
        "openrouter_management_configured": bool(os.getenv("OPENROUTER_MANAGEMENT_KEY")),
    }


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=auth.SESSION_TTL_SECONDS,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response):
    response.delete_cookie(
        auth.SESSION_COOKIE,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _set_oauth_state_cookie(response: Response, state: str):
    response.set_cookie(
        GOOGLE_OAUTH_STATE_COOKIE,
        auth.hash_token(state),
        max_age=auth.OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_oauth_state_cookie(response: Response):
    response.delete_cookie(
        GOOGLE_OAUTH_STATE_COOKIE,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _google_oauth_config() -> Dict[str, str]:
    config = {
        "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip(),
    }
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise HTTPException(status_code=503, detail=f"Google sign-in is missing configuration: {', '.join(missing)}")
    if not os.getenv("OAUTH_STATE_SECRET", "").strip():
        raise HTTPException(status_code=503, detail="Google sign-in is missing OAuth state configuration")
    return config


def _auth_error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(f"{SUBPATH_PREFIX}?{urlencode({'auth_error': message})}", status_code=303)


async def _exchange_google_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    config = _google_oauth_config()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Google sign-in could not be completed")
    return response.json()


async def _fetch_google_profile(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Google profile could not be verified")
    return response.json()


def _owner_email_for_request(request: Request) -> Optional[str]:
    user = auth.get_user_from_request(request)
    return user.get("email") if user else auth.admin_email()


def _require_owner_email(request: Request) -> Optional[str]:
    if not auth.is_auth_required():
        return auth.admin_email()
    user = auth.get_user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = user.get("email")
    if user.get("role") != "owner" and not auth.is_owner_email(email):
        raise HTTPException(status_code=403, detail="Owner access required")
    return email


def _owner_openrouter_api_key(owner_email: Optional[str]) -> Optional[str]:
    return storage.get_openrouter_api_key(owner_email)


RESEARCH_DEPTH_PRESETS = {
    "quick": "efficient-daily",
    "standard": "premium-balanced",
    "hard": "ultra-premium-frontier",
    "adversarial": "ultra-premium-frontier",
}
AGENT_APPROVAL_TTL_MINUTES = 60


def _canonical_payload_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_agent_question(question: str, evidence: Optional[str]) -> str:
    question = question.strip()
    if not evidence or not evidence.strip():
        return question
    return (
        "Use the evidence packet below when answering. Distinguish evidence-backed "
        "claims from inference, and call out uncertainty.\n\n"
        f"Question:\n{question}\n\nEvidence packet:\n{evidence.strip()}"
    )


def _estimate_usd_from_preset(preset: Dict[str, Any]) -> Optional[float]:
    normal = (preset.get("estimated_costs") or {}).get("scenarios", {}).get("normal") or {}
    if normal.get("available") and normal.get("high") is not None:
        return float(normal["high"])
    return None


def _cost_warning(cost_summary: Optional[Dict[str, Any]]) -> Optional[str]:
    if not cost_summary:
        return "Actual provider usage was unavailable; estimate shown instead."
    if cost_summary.get("status") in {"unavailable", "partial"}:
        return "Actual provider usage was incomplete; estimate and available usage are shown."
    return None


def _final_answer_from_run(run: Dict[str, Any]) -> Optional[str]:
    stage3 = ((run.get("stage3") or {}).get("data") or {})
    return stage3.get("response")


def _disclosure_text(result: Dict[str, Any]) -> str:
    actual = result.get("actual_cost_usd")
    actual_text = f"${actual:.4f}" if isinstance(actual, (int, float)) else "Unavailable"
    estimated = result.get("estimated_cost_usd")
    estimated_text = f"${estimated:.4f}" if isinstance(estimated, (int, float)) else "Unavailable"
    return (
        "I used LLM Council via MCP for this answer. "
        f"Preset: {result.get('preset_id')}; "
        f"models: {', '.join(result.get('council_models') or [])}; "
        f"chairman: {result.get('chairman_model')}; "
        f"approval id: {result.get('approval_id')}; "
        f"run id: {result.get('run_id')}; "
        f"estimated cost: {estimated_text}; actual cost: {actual_text}."
    )


def _agent_run_result(run: Dict[str, Any], approval: Dict[str, Any]) -> Dict[str, Any]:
    cost_summary = run.get("cost_summary")
    actual_cost = cost_summary.get("total_usd") if isinstance(cost_summary, dict) else None
    result = {
        "used_llm_council_mcp": True,
        "approval_id": approval["approval_id"],
        "run_id": run["run_id"],
        "status": run.get("status"),
        "preset_id": approval["preset_id"],
        "council_models": approval["council_models"],
        "chairman_model": approval["chairman_model"],
        "estimated_cost_usd": approval.get("estimated_cost_usd"),
        "actual_cost_usd": actual_cost,
        "cost_warning": _cost_warning(cost_summary),
        "cost_summary": cost_summary,
        "final_answer": _final_answer_from_run(run),
        "error": run.get("error"),
    }
    result["required_disclosure_text"] = _disclosure_text(result)
    return result


async def _resolve_agent_preset(
    research_depth: str,
    owner_email: Optional[str],
) -> Dict[str, Any]:
    depth = (research_depth or "hard").strip().lower()
    preset_id = RESEARCH_DEPTH_PRESETS.get(depth)
    if not preset_id:
        raise HTTPException(status_code=400, detail="Unsupported research depth")

    try:
        catalog = await fetch_openrouter_model_catalog()
    except Exception as e:
        raise HTTPException(status_code=503, detail="OpenRouter model catalog is temporarily unavailable") from e

    settings = storage.get_settings(owner_email)
    preset_definitions = settings.get("curated_model_presets") or None
    presets = resolve_model_presets(catalog, preset_definitions=preset_definitions)
    preset = next((item for item in presets if item.get("id") == preset_id), None)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Approved preset {preset_id} is not available")
    if not preset.get("models") or not preset.get("chairman_model"):
        raise HTTPException(status_code=400, detail=f"Approved preset {preset_id} has no routable models")
    if preset.get("missing"):
        raise HTTPException(status_code=400, detail=f"Approved preset {preset_id} is missing model slots")
    return preset


def _openrouter_integration_status(owner_email: Optional[str]) -> Dict[str, Any]:
    account_status = storage.get_openrouter_api_key_status(owner_email)
    env_configured = bool(OPENROUTER_API_KEY) and (not owner_email or auth.is_owner_email(owner_email))
    if account_status.get("configured"):
        return {
            "configured": True,
            "source": "account",
            "masked_key": account_status.get("masked_key"),
            "updated_at": account_status.get("updated_at"),
            "env_configured": env_configured,
        }
    return {
        "configured": env_configured,
        "source": "environment" if env_configured else "none",
        "masked_key": None,
        "updated_at": None,
        "env_configured": env_configured,
    }


async def _managed_profiles_for_request(owner_email: Optional[str]) -> List[Dict[str, Any]]:
    try:
        catalog = await fetch_openrouter_model_catalog()
    except Exception:
        catalog = []
    settings = storage.get_settings(owner_email)
    return billing_service.get_profiles(catalog, settings.get("curated_model_presets") or None)


def _billing_status_for_request(owner_email: Optional[str]) -> Dict[str, Any]:
    openrouter_status = _openrouter_integration_status(owner_email)
    return billing_service.billing_status(
        owner_email or auth.admin_email(),
        byok_configured=bool(openrouter_status.get("configured")),
    )


def _public_app_base_url(request: Request) -> str:
    configured = (os.getenv("PUBLIC_APP_URL") or os.getenv("APP_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    root_path = (request.scope.get("root_path") or "").rstrip("/")
    return f"{request.url.scheme}://{request.url.netloc}{root_path}"


def _auth_payload(user: Optional[Dict[str, Any]], authenticated: bool = True) -> Dict[str, Any]:
    if not user:
        return {
            "authenticated": False,
            "auth_required": True,
            "email": None,
            "name": None,
            "role": None,
            "configured": auth.ensure_admin_user() is not None,
        }
    return {
        "authenticated": authenticated,
        "auth_required": True,
        "email": user.get("email"),
        "name": user.get("name"),
        "role": user.get("role") or ("owner" if auth.is_owner_email(user.get("email")) else "user"),
        "configured": True,
        "onboarding_completed": bool(user.get("onboarding_completed_at")),
        "auth_methods": user.get("auth_methods") or (["password"] if user.get("password_hash") else []),
        "password_auth_enabled": bool(user.get("password_hash")),
    }


async def _validate_openrouter_api_key(api_key: str) -> Dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Enter an OpenRouter API key")
    if len(key) < 20:
        raise HTTPException(status_code=400, detail="OpenRouter API key looks too short")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                OPENROUTER_KEY_INFO_URL,
                headers={"Authorization": f"Bearer {key}"},
            )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Could not validate OpenRouter key right now") from e

    if response.status_code == 401:
        raise HTTPException(status_code=400, detail="OpenRouter API key was rejected")
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="Could not validate OpenRouter key right now")

    return response.json().get("data") or {}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    if not auth.is_auth_required():
        return {"authenticated": True, "auth_required": False, "email": None}

    user = auth.get_user_from_request(request)
    return _auth_payload(user, authenticated=user is not None)


@app.get("/api/auth/oauth/google/start")
async def auth_google_start():
    if not auth.is_auth_required():
        raise HTTPException(status_code=400, detail="Google sign-in is available only when auth is enabled")

    config = _google_oauth_config()
    try:
        state = auth.create_oauth_state(GOOGLE_OAUTH_PROVIDER)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    authorization_params = {
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    }
    authorization_url = f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(authorization_params)}"
    response = RedirectResponse(authorization_url, status_code=303)
    _set_oauth_state_cookie(response, state)
    return response


@app.get("/api/auth/oauth/google/callback")
async def auth_google_callback(request: Request, response: Response, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    redirect = _auth_error_redirect("Google sign-in could not be completed")
    try:
        if error:
            return _auth_error_redirect("Google sign-in was canceled")
        if not code or not state:
            return _auth_error_redirect("Google sign-in returned an incomplete response")
        expected_state_hash = request.cookies.get(GOOGLE_OAUTH_STATE_COOKIE)
        if not expected_state_hash or not hmac.compare_digest(expected_state_hash, auth.hash_token(state)):
            return _auth_error_redirect("Google sign-in state could not be verified")
        if not auth.verify_oauth_state(state, GOOGLE_OAUTH_PROVIDER):
            return _auth_error_redirect("Google sign-in state expired")

        config = _google_oauth_config()
        token = await _exchange_google_code(code, config["redirect_uri"])
        access_token = token.get("access_token")
        if not access_token:
            return _auth_error_redirect("Google sign-in did not return an access token")

        profile = await _fetch_google_profile(access_token)
        email = auth.normalize_email(str(profile.get("email") or ""))
        subject = str(profile.get("sub") or "")
        name = profile.get("name")
        email_verified = profile.get("email_verified")
        if isinstance(email_verified, str):
            email_verified = email_verified.lower() == "true"
        if not email or not subject or not email_verified:
            return _auth_error_redirect("Google account email could not be verified")
        if auth.is_owner_email(email) and not auth.owner_oauth_enabled():
            return _auth_error_redirect("Owner Google sign-in is not enabled")

        user = auth.upsert_oauth_user(GOOGLE_OAUTH_PROVIDER, email, subject, str(name) if name else None)
        session_token = auth.create_session(user["email"])
        redirect = RedirectResponse(SUBPATH_PREFIX, status_code=303)
        _set_session_cookie(redirect, session_token)
        _clear_oauth_state_cookie(redirect)
        return redirect
    except HTTPException as e:
        return _auth_error_redirect(str(e.detail))
    except Exception:
        return redirect


@app.post("/api/auth/signup")
async def auth_signup(payload: SignupRequest, response: Response):
    raise HTTPException(status_code=403, detail=GOOGLE_ONLY_AUTH_DETAIL)
    if not auth.is_auth_required():
        raise HTTPException(status_code=400, detail="Signup is available only when auth is enabled")
    if len(payload.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")

    normalized_email = auth.normalize_email(payload.email)
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if storage.get_auth_user(normalized_email):
        raise HTTPException(status_code=409, detail="An account already exists for that email")

    api_key = payload.openrouter_api_key.strip()
    await _validate_openrouter_api_key(api_key)
    try:
        role = "owner" if auth.is_owner_email(normalized_email) else "user"
        user = auth.create_user(normalized_email, payload.password, payload.name, role=role)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    storage.save_openrouter_api_key(user["email"], api_key)
    token = auth.create_session(user["email"])
    _set_session_cookie(response, token)
    result = _auth_payload(user)
    result["openrouter"] = _openrouter_integration_status(user["email"])
    return result


@app.post("/api/auth/login")
async def auth_login(request: LoginRequest, response: Response):
    raise HTTPException(status_code=403, detail=GOOGLE_ONLY_AUTH_DETAIL)
    if not auth.is_auth_required():
        return {"authenticated": True, "auth_required": False, "email": None}

    auth.ensure_admin_user()

    attempts = storage.increment_login_attempts(request.email, auth.LOGIN_ATTEMPT_TTL_SECONDS)
    if attempts > auth.MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again shortly.")

    user = auth.authenticate(request.email, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    storage.clear_login_attempts(request.email)
    token = auth.create_session(user["email"])
    _set_session_cookie(response, token)
    return _auth_payload(user)


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get(auth.SESSION_COOKIE)
    user = auth.get_user_for_token(token)
    if token:
        auth_hash = auth.hash_token(token)
        storage.delete_session(auth_hash, user.get("email") if user else None)
    _clear_session_cookie(response)
    return {"ok": True}


@app.post("/api/auth/change-password")
async def auth_change_password(request: Request, payload: ChangePasswordRequest, response: Response):
    raise HTTPException(status_code=403, detail=GOOGLE_ONLY_AUTH_DETAIL)
    user = auth.get_user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if len(payload.new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must be at least 12 characters")

    changed = auth.change_password(user["email"], payload.current_password, payload.new_password)
    if not changed:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    token = auth.create_session(user["email"])
    _set_session_cookie(response, token)
    return {"ok": True}


@app.post("/api/auth/reset-password")
async def auth_reset_password(payload: ResetPasswordRequest, response: Response):
    raise HTTPException(status_code=403, detail=GOOGLE_ONLY_AUTH_DETAIL)
    if not auth.is_auth_required():
        return {"authenticated": True, "auth_required": False, "email": None}
    if not os.getenv("ADMIN_PASSWORD_RESET_TOKEN"):
        raise HTTPException(status_code=503, detail="Password reset is not configured")
    if len(payload.new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must be at least 12 characters")

    attempts = storage.increment_login_attempts(
        f"reset:{payload.email}",
        auth.PASSWORD_RESET_TTL_SECONDS,
    )
    if attempts > auth.MAX_PASSWORD_RESET_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many reset attempts. Try again shortly.")

    changed = auth.reset_password(payload.email, payload.reset_token, payload.new_password)
    if not changed:
        raise HTTPException(status_code=401, detail="Invalid reset code")

    storage.clear_login_attempts(f"reset:{payload.email}")
    token = auth.create_session(payload.email)
    _set_session_cookie(response, token)
    user = storage.get_auth_user(auth.normalize_email(payload.email))
    return _auth_payload(user)


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(request: Request):
    """List all conversations (metadata only)."""
    return storage.list_conversations(_owner_email_for_request(request))


@app.get("/api/settings")
async def get_settings(request: Request):
    return storage.get_settings(_owner_email_for_request(request))


@app.patch("/api/settings")
async def update_settings(request: Request, payload: UpdateSettingsRequest):
    patch = {}
    if payload.council_models is not None:
        if not [model for model in payload.council_models if model and model.strip()]:
            raise HTTPException(status_code=400, detail="Select at least one council model")
        patch["council_models"] = payload.council_models
    if payload.chairman_model is not None:
        if not payload.chairman_model.strip():
            raise HTTPException(status_code=400, detail="Select a chairman model")
        patch["chairman_model"] = payload.chairman_model
    if payload.enhancer_model is not None:
        if not payload.enhancer_model.strip():
            raise HTTPException(status_code=400, detail="Select an enhancer model")
        patch["enhancer_model"] = payload.enhancer_model
    if payload.theme_mode is not None:
        patch["theme_mode"] = payload.theme_mode
    if payload.active_model_group_id is not None:
        patch["active_model_group_id"] = payload.active_model_group_id
    if payload.custom_model_groups is not None:
        patch["custom_model_groups"] = payload.custom_model_groups
    if payload.curated_model_presets is not None:
        patch["curated_model_presets"] = payload.curated_model_presets
    if payload.last_approved_curation_id is not None:
        patch["last_approved_curation_id"] = payload.last_approved_curation_id
    updated = storage.save_settings(patch, _owner_email_for_request(request))
    return updated


@app.post("/api/prompt/improve")
async def improve_prompt(request: Request, payload: ImprovePromptRequest):
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Enter a question before improving it.")

    owner_email = _owner_email_for_request(request)
    openrouter_api_key = _owner_openrouter_api_key(owner_email)
    if not openrouter_api_key and auth.is_auth_required() and not auth.is_owner_email(owner_email):
        raise HTTPException(status_code=403, detail="Connect your OpenRouter API key before improving questions.")

    settings = storage.get_settings(owner_email)
    enhancer_model = settings.get("enhancer_model") or ENHANCER_MODEL

    with use_openrouter_account_scope(owner_email, api_key=openrouter_api_key):
        improved = await improve_user_prompt(content, enhancer_model)

    return {"improved": improved, "original": content, "model": enhancer_model}


def _filter_catalog(
    catalog: List[Dict[str, Any]],
    q: Optional[str],
    provider: Optional[str],
    sort: str,
    max_price: Optional[float],
    min_context: Optional[int],
) -> List[Dict[str, Any]]:
    filtered = catalog

    if q:
        needle = q.strip().lower()
        filtered = [
            model for model in filtered
            if needle in model["id"].lower()
            or needle in model["name"].lower()
            or needle in model["provider"].lower()
            or needle in model.get("description", "").lower()
            or any(needle in tag.lower() for tag in model.get("recommendation_tags", []))
        ]

    if provider:
        provider_needle = provider.strip().lower()
        filtered = [
            model for model in filtered
            if model["provider"].lower() == provider_needle
            or model["id"].split("/", 1)[0].lower() == provider_needle
        ]

    if max_price is not None:
        filtered = [
            model for model in filtered
            if (
                model["pricing"]["prompt_per_million"] is not None
                and model["pricing"]["completion_per_million"] is not None
                and model["pricing"]["prompt_per_million"] <= max_price
                and model["pricing"]["completion_per_million"] <= max_price
            )
        ]

    if min_context is not None:
        filtered = [
            model for model in filtered
            if isinstance(model.get("context_length"), int)
            and model["context_length"] >= min_context
        ]

    if sort == "price":
        filtered = sorted(
            filtered,
            key=lambda model: (
                model["pricing"]["prompt_per_million"] is None,
                (model["pricing"]["prompt_per_million"] or 0) + (model["pricing"]["completion_per_million"] or 0),
                model["name"],
            ),
        )
    elif sort == "context":
        filtered = sorted(filtered, key=lambda model: model.get("context_length") or 0, reverse=True)
    elif sort == "provider":
        filtered = sorted(filtered, key=lambda model: (model["provider"], model["name"]))
    else:
        filtered = sorted(
            filtered,
            key=lambda model: (
                "Recommended" not in model.get("recommendation_tags", []),
                model["provider"],
                model["name"],
            ),
        )

    return filtered


@app.get("/api/integrations/openrouter")
async def get_openrouter_integration(request: Request):
    owner_email = _owner_email_for_request(request)
    return _openrouter_integration_status(owner_email)


@app.put("/api/integrations/openrouter")
async def update_openrouter_integration(request: Request, payload: UpdateOpenRouterIntegrationRequest):
    owner_email = _owner_email_for_request(request)
    if payload.clear:
        storage.delete_openrouter_api_key(owner_email)
        return _openrouter_integration_status(owner_email)

    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Enter an OpenRouter API key")
    await _validate_openrouter_api_key(api_key)

    storage.save_openrouter_api_key(owner_email, api_key)
    return _openrouter_integration_status(owner_email)


@app.get("/api/billing/status")
async def get_billing_status(request: Request):
    owner_email = _owner_email_for_request(request)
    return _billing_status_for_request(owner_email)


@app.post("/api/billing/mode")
async def update_billing_mode(request: Request, payload: UpdateBillingModeRequest):
    owner_email = _owner_email_for_request(request)
    mode = payload.billing_mode.strip().lower()
    try:
        billing_service.set_mode(owner_email or auth.admin_email(), mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _billing_status_for_request(owner_email)


@app.get("/api/billing/ledger")
async def get_billing_ledger(request: Request):
    owner_email = _owner_email_for_request(request)
    return billing_service.ledger(owner_email or auth.admin_email())


@app.post("/api/billing/checkout")
async def create_billing_checkout(request: Request, payload: CreateCheckoutRequest):
    owner_email = _owner_email_for_request(request)
    user_id = owner_email or auth.admin_email()
    package_id = payload.package_id.strip()
    base_url = _public_app_base_url(request)
    if not billing_service.billing_status(user_id, byok_configured=False).get("managed_mode_enabled"):
        raise HTTPException(status_code=403, detail="Managed LLM Council Balance is not enabled yet.")
    try:
        session = await stripe_service.create_checkout_session(
            user_id=user_id,
            package_id=package_id,
            success_url=f"{base_url}?billing=success",
            cancel_url=f"{base_url}?billing=cancelled",
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/council/profiles")
async def get_council_profiles(request: Request):
    owner_email = _owner_email_for_request(request)
    profiles = await _managed_profiles_for_request(owner_email)
    return {"profiles": profiles}


@app.post("/api/council/estimate")
async def estimate_council_profile(request: Request, payload: CouncilEstimateRequest):
    owner_email = _owner_email_for_request(request)
    profiles = await _managed_profiles_for_request(owner_email)
    try:
        estimate = billing_service.estimate_for_profile(profiles, payload.profile_slug, payload.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    status = _billing_status_for_request(owner_email)
    return {
        **estimate,
        "profile": estimate["profile"],
        "billing_status": status,
        "can_run": status.get("available_balance_usd", 0) >= estimate["max_app_charge_usd"],
    }


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.verify_webhook(payload, signature)
        result = stripe_service.fulfill_checkout_session(event)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/admin/finance/overview")
async def admin_finance_overview(request: Request):
    _require_owner_email(request)
    return billing_service.admin_overview()


@app.get("/api/admin/openrouter/coverage")
async def admin_openrouter_coverage(request: Request, refresh: bool = Query(default=False)):
    _require_owner_email(request)
    if refresh:
        try:
            return await billing_service.refresh_coverage()
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
    return billing_service.latest_coverage()


@app.post("/api/admin/managed-mode/pause")
async def admin_pause_managed_mode(request: Request):
    owner_email = _require_owner_email(request)
    return billing_service.pause_managed_mode(owner_email or auth.admin_email())


@app.post("/api/admin/managed-mode/resume")
async def admin_resume_managed_mode(request: Request):
    owner_email = _require_owner_email(request)
    return billing_service.resume_managed_mode(owner_email or auth.admin_email())


@app.get("/api/models/status")
async def model_status(request: Request):
    owner_email = _owner_email_for_request(request)
    openrouter_status = _openrouter_integration_status(owner_email)
    try:
        catalog = await fetch_openrouter_model_catalog()
        return {
            "openrouter_key_configured": openrouter_status["configured"],
            "openrouter_key_source": openrouter_status["source"],
            "catalog_reachable": True,
            "catalog_model_count": len(catalog),
        }
    except Exception:
        return {
            "openrouter_key_configured": openrouter_status["configured"],
            "openrouter_key_source": openrouter_status["source"],
            "catalog_reachable": False,
            "catalog_model_count": 0,
        }


@app.get("/api/models/catalog")
async def model_catalog(
    request: Request,
    q: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    sort: str = Query(default="recommended", pattern="^(recommended|price|context|provider)$"),
    max_price: Optional[float] = Query(default=None, ge=0),
    min_context: Optional[int] = Query(default=None, ge=0),
):
    try:
        catalog = await fetch_openrouter_model_catalog()
    except Exception as e:
        raise HTTPException(status_code=503, detail="OpenRouter model catalog is temporarily unavailable") from e

    filtered = _filter_catalog(catalog, q, provider, sort, max_price, min_context)
    providers = sorted({model["provider"] for model in catalog if model.get("provider")})
    settings = storage.get_settings(_owner_email_for_request(request))
    preset_definitions = settings.get("curated_model_presets") or None
    return {
        "models": filtered,
        "presets": resolve_model_presets(catalog, preset_definitions=preset_definitions),
        "providers": providers,
        "total_count": len(catalog),
        "filtered_count": len(filtered),
    }


@app.get("/api/model-curation/latest")
async def latest_model_curation(request: Request):
    owner_email = _owner_email_for_request(request)
    draft = storage.get_latest_model_curation_draft()
    settings = storage.get_settings(owner_email)
    return {
        "draft": draft,
        "pending_review": is_draft_pending_review(draft, settings),
        "last_approved_curation_id": settings.get("last_approved_curation_id"),
        "curation_state": storage.get_model_curation_state(),
    }


@app.post("/api/model-curation/run")
async def run_model_curation(request: Request):
    owner_email = _require_owner_email(request)
    draft = await create_model_curation_draft(trigger="manual", owner_email=owner_email)
    return {"draft": draft, "curation_state": storage.get_model_curation_state()}


@app.post("/api/model-curation/{draft_id}/approve")
async def approve_model_curation(draft_id: str, request: Request):
    owner_email = _require_owner_email(request)
    draft = storage.get_model_curation_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Model curation draft not found")
    preset_definitions = draft.get("proposed_preset_definitions") or draft.get("preset_definitions") or []
    settings_patch = {
        "curated_model_presets": preset_definitions,
        "last_approved_curation_id": draft_id,
    }
    enhancer_validation = draft.get("enhancer_model_validation") or {}
    recommended_enhancer = draft.get("recommended_enhancer_model")
    if recommended_enhancer and enhancer_validation.get("ok"):
        settings_patch["enhancer_model"] = enhancer_validation.get("normalized_model") or recommended_enhancer
    updated = storage.save_settings(settings_patch, owner_email)
    approved_draft = mark_model_curation_draft_approved(draft, owner_email)
    return {
        "ok": True,
        "settings": updated,
        "draft": approved_draft,
        "pending_review": False,
    }


@app.post("/api/agent/research/prepare")
async def prepare_agent_research(payload: AgentResearchPrepareRequest, request: Request):
    owner_email = agent_auth.require_agent(request)
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    preset = await _resolve_agent_preset(payload.research_depth, owner_email)
    estimated_cost = _estimate_usd_from_preset(preset)
    if estimated_cost is None:
        raise HTTPException(status_code=400, detail="Estimated cost is unavailable for the selected preset")

    agent_max = agent_auth.max_cost_usd()
    requested_max = payload.max_cost_usd if payload.max_cost_usd is not None else agent_max
    cost_cap = min(float(requested_max), agent_max)
    if estimated_cost > cost_cap:
        raise HTTPException(
            status_code=400,
            detail=f"Estimated cost ${estimated_cost:.4f} exceeds allowed cap ${cost_cap:.4f}",
        )

    approval_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=AGENT_APPROVAL_TTL_MINUTES)
    question_payload = _format_agent_question(question, payload.evidence)
    prepared_payload = {
        "question": question,
        "evidence": payload.evidence or "",
        "question_payload": question_payload,
        "research_depth": (payload.research_depth or "hard").strip().lower(),
        "preset_id": preset["id"],
        "council_models": preset["models"],
        "chairman_model": preset["chairman_model"],
        "estimated_cost_usd": estimated_cost,
        "max_cost_usd": cost_cap,
    }
    payload_hash = _canonical_payload_hash(prepared_payload)
    approval = {
        "approval_id": approval_id,
        "owner_email": owner_email,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat(),
        "payload_hash": payload_hash,
        "status": "prepared",
        **prepared_payload,
    }
    storage.save_agent_research_approval(approval)

    return {
        "approval_id": approval_id,
        "expires_at": approval["expires_at"],
        "payload_hash": payload_hash,
        "recommended_preset": preset["id"],
        "preset_id": preset["id"],
        "preset_name": preset.get("name"),
        "chairman_model": preset["chairman_model"],
        "council_models": preset["models"],
        "research_depth": approval["research_depth"],
        "estimated_cost_usd": estimated_cost,
        "approved_cost_cap_usd": cost_cap,
        "cost_source": "OpenRouter catalog estimate, normal-question high scenario",
        "reason": preset.get("best_for") or preset.get("summary"),
        "alternatives": sorted({item for item in RESEARCH_DEPTH_PRESETS.values() if item != preset["id"]}),
    }


@app.post("/api/agent/research/run")
async def run_agent_research(payload: AgentResearchRunRequest, request: Request):
    owner_email = agent_auth.require_agent(request)
    approval = storage.get_agent_research_approval(payload.approval_id)
    if approval is None or approval.get("owner_email") != owner_email:
        raise HTTPException(status_code=404, detail="Agent research approval not found")
    if approval.get("status") == "used":
        raise HTTPException(status_code=409, detail="Agent research approval has already been used")

    try:
        expires_at = datetime.fromisoformat(approval.get("expires_at"))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Agent research approval is invalid") from e
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=410, detail="Agent research approval has expired")

    prepared_payload = {
        "question": approval["question"],
        "evidence": approval.get("evidence") or "",
        "question_payload": approval["question_payload"],
        "research_depth": approval["research_depth"],
        "preset_id": approval["preset_id"],
        "council_models": approval["council_models"],
        "chairman_model": approval["chairman_model"],
        "estimated_cost_usd": approval["estimated_cost_usd"],
        "max_cost_usd": approval["max_cost_usd"],
    }
    if _canonical_payload_hash(prepared_payload) != approval.get("payload_hash"):
        raise HTTPException(status_code=400, detail="Agent research approval payload hash mismatch")

    approved_cap = float(payload.approved_cost_cap_usd)
    estimated_cost = float(approval["estimated_cost_usd"])
    if approved_cap > agent_auth.max_cost_usd():
        raise HTTPException(status_code=400, detail="Approved cap exceeds configured agent maximum")
    if estimated_cost > approved_cap:
        raise HTTPException(status_code=400, detail="Estimated cost exceeds approved cap")

    conversation_id = str(uuid.uuid4())
    storage.create_conversation(conversation_id, owner_email)
    storage.update_conversation_title(conversation_id, f"Codex Research {approval['preset_id']}")
    storage.add_user_message(conversation_id, approval["question_payload"])

    run_id = str(uuid.uuid4())
    run = storage.create_run(run_id, conversation_id, approval["question_payload"], owner_email)
    storage.update_run(run_id, {
        "agent_research": {
            "approval_id": approval["approval_id"],
            "payload_hash": approval["payload_hash"],
            "preset_id": approval["preset_id"],
            "research_depth": approval["research_depth"],
            "council_models": approval["council_models"],
            "chairman_model": approval["chairman_model"],
            "estimated_cost_usd": approval["estimated_cost_usd"],
        }
    })
    storage.upsert_assistant_message_for_run(conversation_id, run_id)
    storage.update_agent_research_approval(approval["approval_id"], {
        "status": "used",
        "run_id": run_id,
        "conversation_id": conversation_id,
        "used_at": datetime.utcnow().isoformat(),
    })
    approval = storage.get_agent_research_approval(approval["approval_id"]) or approval

    await _execute_run(run_id)
    completed = storage.get_run(run_id) or run
    return _agent_run_result(completed, approval)


@app.get("/api/agent/research/runs/{run_id}")
async def get_agent_research_run(run_id: str, request: Request):
    owner_email = agent_auth.require_agent(request)
    run = storage.get_run(run_id)
    if run is None or run.get("owner_email") != storage._owner_scope(owner_email):
        raise HTTPException(status_code=404, detail="Agent research run not found")
    agent_research = run.get("agent_research") or {}
    approval_id = agent_research.get("approval_id")
    approval = storage.get_agent_research_approval(approval_id) if approval_id else None
    if approval is None:
        raise HTTPException(status_code=404, detail="Agent research approval not found")
    return _agent_run_result(run, approval)


@app.get("/api/cron/model-curation")
async def cron_model_curation(request: Request):
    configured_secret = os.getenv("CRON_SECRET")
    if not configured_secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured")
    authorization = request.headers.get("authorization") or ""
    supplied = authorization.removeprefix("Bearer ").strip() or request.query_params.get("secret")
    if supplied != configured_secret:
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    draft = await create_model_curation_draft(trigger="cron", owner_email=auth.admin_email())
    return {"draft_id": draft["id"], "status": draft["status"]}


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: Request, payload: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, _owner_email_for_request(request))
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, request: Request):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id, _owner_email_for_request(request))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/api/conversations/{conversation_id}/pin")
async def pin_conversation(conversation_id: str, payload: PinConversationRequest, request: Request):
    conversation = storage.get_conversation(conversation_id, _owner_email_for_request(request))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    storage.set_conversation_pinned(conversation_id, payload.pinned)
    return {"ok": True, "pinned": payload.pinned}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    conversation = storage.get_conversation(conversation_id, _owner_email_for_request(request))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    storage.delete_conversation(conversation_id)
    return {"ok": True}


@app.get("/api/conversations/{conversation_id}/runs/active")
async def get_active_run(conversation_id: str, request: Request):
    owner_email = _owner_email_for_request(request)
    conversation = storage.get_conversation(conversation_id, owner_email)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    run = storage.get_latest_active_run_for_conversation(conversation_id, owner_email)
    return {"run": run}


@app.get("/api/conversations/{conversation_id}/runs/{run_id}")
async def get_run(conversation_id: str, run_id: str, request: Request):
    owner_email = _owner_email_for_request(request)
    run = storage.get_run(run_id)
    if run is None or run.get("conversation_id") != conversation_id or not storage._belongs_to_scope(run, owner_email):
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/api/conversations/{conversation_id}/runs/{run_id}/stop")
async def stop_run(conversation_id: str, run_id: str, request: Request):
    owner_email = _owner_email_for_request(request)
    run = storage.get_run(run_id)
    if run is None or run.get("conversation_id") != conversation_id or not storage._belongs_to_scope(run, owner_email):
        raise HTTPException(status_code=404, detail="Run not found")

    if run.get("status") in {"complete", "failed", "canceled"}:
        return {"ok": True, "status": run.get("status")}

    task = RUN_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()

    storage.update_run(run_id, {"status": "canceled", "error": "Stopped by user"})
    storage.upsert_assistant_message_for_run(
        conversation_id,
        run_id,
        loading={"stage1": False, "stage2": False, "stage3": False},
    )
    return {"ok": True, "status": "canceled"}


async def _execute_run(run_id: str):
    run = storage.get_run(run_id)
    if run is None:
        return

    conversation_id = run["conversation_id"]
    content = run["content"]
    owner_email = run.get("owner_email") or auth.admin_email()
    settings = storage.get_settings(owner_email)
    agent_research = run.get("agent_research") or {}
    run_billing = run.get("billing") or {}
    billing_mode = run_billing.get("billing_mode") or "byok"
    council_models = (
        agent_research.get("council_models")
        or run_billing.get("council_models")
        or settings.get("council_models", [])
    )
    chairman_model = agent_research.get("chairman_model") or run_billing.get("chairman_model") or settings.get("chairman_model")
    openrouter_api_key = _owner_openrouter_api_key(owner_email)
    if billing_mode == "managed":
        openrouter_api_key = await billing_service.ensure_managed_openrouter_key(owner_email)
    if not openrouter_api_key and auth.is_auth_required() and not auth.is_owner_email(owner_email):
        raise RuntimeError("Connect your OpenRouter API key before running the council.")

    try:
        with use_openrouter_account_scope(owner_email, api_key=openrouter_api_key):
            storage.update_run(
                run_id,
                {"status": "running", "stage1": {"status": "running"}, "stage2": {"status": "pending"}, "stage3": {"status": "pending"}},
            )
            storage.upsert_assistant_message_for_run(
                conversation_id,
                run_id,
                loading={"stage1": True, "stage2": False, "stage3": False},
            )

            # Stage 1 — stream each model's result as it lands for a live per-model race.
            stage1_execution_metadata = {}

            async def persist_stage1_progress(partial_results, partial_execution_metadata):
                nonlocal stage1_execution_metadata
                stage1_execution_metadata = partial_execution_metadata
                storage.update_run(
                    run_id,
                    {
                        "stage1": {
                            "status": "running",
                            "data": partial_results,
                            "metadata": {"stage1_execution": partial_execution_metadata},
                        }
                    },
                )
                storage.upsert_assistant_message_for_run(
                    conversation_id,
                    run_id,
                    stage1=partial_results,
                    metadata={"stage1_execution": partial_execution_metadata},
                    loading={"stage1": True, "stage2": False, "stage3": False},
                )

            stage1_results = await stage1_collect_responses(
                content,
                council_models=council_models,
                progress_callback=persist_stage1_progress,
            )
            storage.update_run(
                run_id,
                {
                    "stage1": {
                        "status": "complete",
                        "data": stage1_results,
                        "metadata": {"stage1_execution": stage1_execution_metadata},
                    },
                },
            )
            storage.upsert_assistant_message_for_run(
                conversation_id,
                run_id,
                stage1=stage1_results,
                metadata={"stage1_execution": stage1_execution_metadata},
                loading={"stage1": False, "stage2": True, "stage3": False},
            )

            # Stage 2
            storage.update_run(run_id, {"stage2": {"status": "running"}})

            async def persist_stage2_progress(partial_results, partial_label_to_model, partial_execution_metadata):
                partial_aggregate = calculate_aggregate_rankings(partial_results, partial_label_to_model)
                partial_metadata = {
                    "label_to_model": partial_label_to_model,
                    "aggregate_rankings": partial_aggregate,
                    "stage2_execution": partial_execution_metadata,
                    "stage1_execution": stage1_execution_metadata,
                }
                storage.update_run(
                    run_id,
                    {
                        "stage2": {
                            "status": "running",
                            "data": partial_results,
                            "metadata": partial_metadata,
                        }
                    },
                )
                storage.upsert_assistant_message_for_run(
                    conversation_id,
                    run_id,
                    stage2=partial_results,
                    metadata=partial_metadata,
                    loading={"stage1": False, "stage2": True, "stage3": False},
                )

            stage2_results, label_to_model, stage2_execution_metadata = await stage2_collect_rankings(
                content,
                stage1_results,
                council_models=council_models,
                progress_callback=persist_stage2_progress,
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            stage2_metadata = {
                "label_to_model": label_to_model,
                "aggregate_rankings": aggregate_rankings,
                "stage2_execution": stage2_execution_metadata,
                "stage1_execution": stage1_execution_metadata,
            }

            valid_stage2_count = int(stage2_execution_metadata.get("completed_rankings_count") or 0)
            minimum_valid_stage2 = int(stage2_execution_metadata.get("minimum_valid_rankings_to_synthesize") or 2)
            if valid_stage2_count < minimum_valid_stage2:
                error_message = format_stage2_incomplete_error(stage2_execution_metadata)
                storage.update_run(
                    run_id,
                    {
                        "stage2": {
                            "status": "failed",
                            "data": stage2_results,
                            "metadata": stage2_metadata,
                        },
                    },
                )
                storage.upsert_assistant_message_for_run(
                    conversation_id,
                    run_id,
                    stage2=stage2_results,
                    metadata=stage2_metadata,
                    loading={"stage1": False, "stage2": False, "stage3": False},
                    error=error_message,
                )
                raise RuntimeError(error_message)
            if stage2_execution_metadata.get("is_partial"):
                stage2_metadata["stage2_warning"] = format_stage2_incomplete_error(stage2_execution_metadata)

            storage.update_run(
                run_id,
                {
                    "stage2": {
                        "status": "complete",
                        "data": stage2_results,
                        "metadata": stage2_metadata,
                    }
                },
            )
            storage.upsert_assistant_message_for_run(
                conversation_id,
                run_id,
                stage2=stage2_results,
                metadata=stage2_metadata,
                loading={"stage1": False, "stage2": False, "stage3": True},
            )

            # Stage 3
            storage.update_run(run_id, {"stage3": {"status": "running"}})
            stage3_result = await stage3_synthesize_final(content, stage1_results, stage2_results, chairman_model=chairman_model, council_models=council_models)
            cost_calls = collect_council_cost_calls(
                stage1_results,
                stage2_results,
                stage3_result,
                council_models,
            )
            cost_calls = await reconcile_cost_calls(cost_calls, openrouter_api_key or OPENROUTER_API_KEY)
            cost_summary = build_cost_summary(cost_calls)
            billing_receipt = None
            if billing_mode == "managed":
                billing_receipt = await billing_service.finalize_managed_run(
                    owner_email,
                    run_id,
                    run_billing,
                    cost_summary,
                )
                stage2_metadata["billing_receipt"] = billing_receipt
            stage2_metadata["cost_summary"] = cost_summary
            storage.update_run(
                run_id,
                {
                    "stage3": {"status": "complete", "data": stage3_result},
                    "cost_summary": cost_summary,
                    "billing_receipt": billing_receipt,
                    "status": "complete",
                    "error": None,
                },
            )
            storage.upsert_assistant_message_for_run(
                conversation_id,
                run_id,
                stage3=stage3_result,
                metadata=stage2_metadata,
                cost_summary=cost_summary,
                loading={"stage1": False, "stage2": False, "stage3": False},
            )

    except asyncio.CancelledError:
        if billing_mode == "managed":
            billing_service.release_run_reservation(run_billing)
        storage.update_run(run_id, {"status": "canceled", "error": "Stopped by user"})
        storage.upsert_assistant_message_for_run(
            conversation_id,
            run_id,
            loading={"stage1": False, "stage2": False, "stage3": False},
        )
        raise
    except Exception as e:
        if billing_mode == "managed":
            billing_service.release_run_reservation(run_billing)
        import traceback
        traceback.print_exc()
        storage.update_run(
            run_id,
            {
                "status": "failed",
                "error": str(e),
                "stage1": {"status": storage.get_run(run_id).get("stage1", {}).get("status", "pending")},
                "stage2": {"status": storage.get_run(run_id).get("stage2", {}).get("status", "pending")},
                "stage3": {"status": storage.get_run(run_id).get("stage3", {}).get("status", "pending")},
            },
        )
        storage.upsert_assistant_message_for_run(
            conversation_id,
            run_id,
            loading={"stage1": False, "stage2": False, "stage3": False},
            error=str(e),
        )
    finally:
        RUN_TASKS.pop(run_id, None)


@app.post("/api/conversations/{conversation_id}/runs")
async def create_run(conversation_id: str, request: CreateRunRequest, http_request: Request):
    owner_email = _owner_email_for_request(http_request)
    conversation = storage.get_conversation(conversation_id, owner_email)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    openrouter_api_key = _owner_openrouter_api_key(owner_email)
    billing_status = _billing_status_for_request(owner_email)
    billing_mode = (request.billing_mode or billing_status.get("billing_mode") or "byok").strip().lower()
    if billing_mode not in {"byok", "managed"}:
        raise HTTPException(status_code=400, detail="Unsupported billing mode")
    run_id = str(uuid.uuid4())
    run_billing: Dict[str, Any] = {"billing_mode": billing_mode}

    if billing_mode == "managed":
        profiles = await _managed_profiles_for_request(owner_email)
        try:
            estimate = billing_service.estimate_for_profile(profiles, request.profile_slug or "balanced", request.content)
            run_billing = await billing_service.prepare_managed_run(
                owner_email or auth.admin_email(),
                run_id,
                estimate["profile"],
                estimate,
            )
        except ValueError as e:
            raise HTTPException(status_code=402, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
    elif not openrouter_api_key and auth.is_auth_required() and not auth.is_owner_email(owner_email):
        raise HTTPException(status_code=403, detail="Connect your OpenRouter API key before running the council.")

    storage.add_user_message(conversation_id, request.content)

    if is_first_message:
        if billing_mode == "managed":
            title = request.content.strip().splitlines()[0][:64] or "Managed Council"
        else:
            with use_openrouter_account_scope(owner_email, api_key=openrouter_api_key):
                title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    run = storage.create_run(run_id, conversation_id, request.content, owner_email)
    if billing_mode == "managed":
        storage.update_run(
            run_id,
            {
                "billing": {
                    key: value
                    for key, value in run_billing.items()
                    if key != "openrouter_api_key"
                }
            },
        )
        run = storage.get_run(run_id) or run
    storage.upsert_assistant_message_for_run(conversation_id, run_id)

    if os.getenv("RUN_EXECUTION_MODE", "").strip().lower() == "sync":
        await _execute_run(run_id)
        completed = storage.get_run(run_id) or run
        return {"run_id": run_id, "status": completed["status"]}

    task = asyncio.create_task(_execute_run(run_id))
    RUN_TASKS[run_id] = task

    return {"run_id": run_id, "status": run["status"]}


@app.get("/api/conversations/{conversation_id}/runs/{run_id}/events")
async def run_events(conversation_id: str, run_id: str, request: Request):
    owner_email = _owner_email_for_request(request)
    run = storage.get_run(run_id)
    if run is None or run.get("conversation_id") != conversation_id or not storage._belongs_to_scope(run, owner_email):
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_snapshot = None
        while True:
            current = storage.get_run(run_id)
            if current is None:
                break

            payload = json.dumps(current)
            if payload != last_snapshot:
                last_snapshot = payload
                yield f"data: {payload}\n\n"

            if current.get("status") in {"complete", "failed", "canceled"}:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest, http_request: Request):
    """
    Legacy non-stream endpoint (kept for compatibility).
    """
    owner_email = _owner_email_for_request(http_request)
    conversation = storage.get_conversation(conversation_id, owner_email)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    openrouter_api_key = _owner_openrouter_api_key(owner_email)
    if not openrouter_api_key and auth.is_auth_required() and not auth.is_owner_email(owner_email):
        raise HTTPException(status_code=403, detail="Connect your OpenRouter API key before running the council.")
    storage.add_user_message(conversation_id, request.content)

    with use_openrouter_account_scope(owner_email, api_key=openrouter_api_key):
        if is_first_message:
            title = await generate_conversation_title(request.content)
            storage.update_conversation_title(conversation_id, title)

        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(request.content)

    cost_summary = build_council_cost_summary(
        stage1_results,
        stage2_results,
        stage3_result,
        storage.get_settings(owner_email).get("council_models", []),
    )
    metadata = metadata or {}
    metadata = {**metadata, "cost_summary": metadata.get("cost_summary") or cost_summary}
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        metadata=metadata,
        cost_summary=metadata.get("cost_summary"),
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest, http_request: Request):
    """
    Backward-compatible stream endpoint now backed by durable runs.
    """
    created = await create_run(conversation_id, CreateRunRequest(content=request.content), http_request)
    run_id = created["run_id"]
    return await run_events(conversation_id, run_id, http_request)


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("BACKEND_PORT", "8001"))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
