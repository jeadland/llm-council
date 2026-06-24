"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import os
import httpx

from . import storage
from . import auth
from .config import OPENROUTER_API_KEY
from .council import (
    build_council_cost_summary,
    collect_council_cost_calls,
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)
from .openrouter import build_cost_summary, fetch_openrouter_model_catalog, reconcile_cost_calls, resolve_model_presets
from .openrouter import use_openrouter_account_scope
from .model_curation import create_model_curation_draft

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
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/reset-password",
    "/api/cron/model-curation",
}
OPENROUTER_KEY_INFO_URL = "https://openrouter.ai/api/v1/key"

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


class PinConversationRequest(BaseModel):
    pinned: bool


class UpdateSettingsRequest(BaseModel):
    council_models: Optional[List[str]] = None
    chairman_model: Optional[str] = None
    theme_mode: Optional[str] = None
    active_model_group_id: Optional[str] = None
    custom_model_groups: Optional[List[Dict[str, Any]]] = None
    curated_model_presets: Optional[List[Dict[str, Any]]] = None
    last_approved_curation_id: Optional[str] = None


class UpdateOpenRouterIntegrationRequest(BaseModel):
    api_key: Optional[str] = None
    clear: bool = False


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
    return {"ok": True, "app": "llm-council", "storage": "redis-or-local"}


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


@app.post("/api/auth/signup")
async def auth_signup(payload: SignupRequest, response: Response):
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
async def latest_model_curation():
    return {
        "draft": storage.get_latest_model_curation_draft(),
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
    updated = storage.save_settings({
        "curated_model_presets": preset_definitions,
        "last_approved_curation_id": draft_id,
    }, owner_email)
    return {"ok": True, "settings": updated}


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
    council_models = settings.get("council_models", [])
    chairman_model = settings.get("chairman_model")
    openrouter_api_key = _owner_openrouter_api_key(owner_email)
    if not openrouter_api_key and not auth.is_owner_email(owner_email):
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

            # Stage 1
            stage1_results = await stage1_collect_responses(content, council_models=council_models)
            storage.update_run(
                run_id,
                {
                    "stage1": {"status": "complete", "data": stage1_results},
                },
            )
            storage.upsert_assistant_message_for_run(
                conversation_id,
                run_id,
                stage1=stage1_results,
                loading={"stage1": False, "stage2": True, "stage3": False},
            )

            # Stage 2
            storage.update_run(run_id, {"stage2": {"status": "running"}})
            stage2_results, label_to_model = await stage2_collect_rankings(content, stage1_results, council_models=council_models)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            stage2_metadata = {
                "label_to_model": label_to_model,
                "aggregate_rankings": aggregate_rankings,
            }
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
            stage2_metadata["cost_summary"] = cost_summary
            storage.update_run(
                run_id,
                {
                    "stage3": {"status": "complete", "data": stage3_result},
                    "cost_summary": cost_summary,
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
        storage.update_run(run_id, {"status": "canceled", "error": "Stopped by user"})
        storage.upsert_assistant_message_for_run(
            conversation_id,
            run_id,
            loading={"stage1": False, "stage2": False, "stage3": False},
        )
        raise
    except Exception as e:
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
    if not openrouter_api_key and not auth.is_owner_email(owner_email):
        raise HTTPException(status_code=403, detail="Connect your OpenRouter API key before running the council.")

    storage.add_user_message(conversation_id, request.content)

    if is_first_message:
        with use_openrouter_account_scope(owner_email, api_key=openrouter_api_key):
            title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    run_id = str(uuid.uuid4())
    run = storage.create_run(run_id, conversation_id, request.content, owner_email)
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
    if not openrouter_api_key and not auth.is_owner_email(owner_email):
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
