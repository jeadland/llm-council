"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import os

from . import storage
from . import auth
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)
from .openrouter import fetch_available_models

app = FastAPI(title="LLM Council API")
RUN_TASKS: Dict[str, asyncio.Task] = {}
PUBLIC_API_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
}

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
    path = request.url.path
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


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
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


@app.get("/api/auth/me")
async def auth_me(request: Request):
    if not auth.is_auth_required():
        return {"authenticated": True, "auth_required": False, "email": None}

    user = auth.get_user_from_request(request)
    return {
        "authenticated": user is not None,
        "auth_required": True,
        "email": user.get("email") if user else None,
        "configured": auth.ensure_admin_user() is not None,
    }


@app.post("/api/auth/login")
async def auth_login(request: LoginRequest, response: Response):
    if not auth.is_auth_required():
        return {"authenticated": True, "auth_required": False, "email": None}

    if auth.ensure_admin_user() is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    attempts = storage.increment_login_attempts(request.email, auth.LOGIN_ATTEMPT_TTL_SECONDS)
    if attempts > auth.MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again shortly.")

    user = auth.authenticate(request.email, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    storage.clear_login_attempts(request.email)
    token = auth.create_session(user["email"])
    _set_session_cookie(response, token)
    return {"authenticated": True, "auth_required": True, "email": user["email"]}


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


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.get("/api/settings")
async def get_settings():
    settings = storage.get_settings()

    # Keep available model list aligned with this deployment's OpenRouter access.
    discovered = await fetch_available_models()
    if discovered != settings.get("available_models", []):
        settings = storage.save_settings({"available_models": discovered})

    return settings


@app.patch("/api/settings")
async def update_settings(request: UpdateSettingsRequest):
    patch = {}
    if request.council_models is not None:
        patch["council_models"] = request.council_models
    if request.chairman_model is not None:
        patch["chairman_model"] = request.chairman_model
    if request.theme_mode is not None:
        patch["theme_mode"] = request.theme_mode
    updated = storage.save_settings(patch)
    return updated


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/api/conversations/{conversation_id}/pin")
async def pin_conversation(conversation_id: str, request: PinConversationRequest):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    storage.set_conversation_pinned(conversation_id, request.pinned)
    return {"ok": True, "pinned": request.pinned}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    storage.delete_conversation(conversation_id)
    return {"ok": True}


@app.get("/api/conversations/{conversation_id}/runs/active")
async def get_active_run(conversation_id: str):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    run = storage.get_latest_active_run_for_conversation(conversation_id)
    return {"run": run}


@app.get("/api/conversations/{conversation_id}/runs/{run_id}")
async def get_run(conversation_id: str, run_id: str):
    run = storage.get_run(run_id)
    if run is None or run.get("conversation_id") != conversation_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/api/conversations/{conversation_id}/runs/{run_id}/stop")
async def stop_run(conversation_id: str, run_id: str):
    run = storage.get_run(run_id)
    if run is None or run.get("conversation_id") != conversation_id:
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
    settings = storage.get_settings()
    council_models = settings.get("council_models", [])
    chairman_model = settings.get("chairman_model")

    try:
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
        storage.update_run(
            run_id,
            {
                "stage3": {"status": "complete", "data": stage3_result},
                "status": "complete",
                "error": None,
            },
        )
        storage.upsert_assistant_message_for_run(
            conversation_id,
            run_id,
            stage3=stage3_result,
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
async def create_run(conversation_id: str, request: CreateRunRequest):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0

    storage.add_user_message(conversation_id, request.content)

    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    run_id = str(uuid.uuid4())
    run = storage.create_run(run_id, conversation_id, request.content)
    storage.upsert_assistant_message_for_run(conversation_id, run_id)

    if os.getenv("RUN_EXECUTION_MODE", "").strip().lower() == "sync":
        await _execute_run(run_id)
        completed = storage.get_run(run_id) or run
        return {"run_id": run_id, "status": completed["status"]}

    task = asyncio.create_task(_execute_run(run_id))
    RUN_TASKS[run_id] = task

    return {"run_id": run_id, "status": run["status"]}


@app.get("/api/conversations/{conversation_id}/runs/{run_id}/events")
async def run_events(conversation_id: str, run_id: str):
    run = storage.get_run(run_id)
    if run is None or run.get("conversation_id") != conversation_id:
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
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Legacy non-stream endpoint (kept for compatibility).
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    storage.add_user_message(conversation_id, request.content)

    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(request.content)

    storage.add_assistant_message(conversation_id, stage1_results, stage2_results, stage3_result)

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Backward-compatible stream endpoint now backed by durable runs.
    """
    created = await create_run(conversation_id, CreateRunRequest(content=request.content))
    run_id = created["run_id"]
    return await run_events(conversation_id, run_id)


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("BACKEND_PORT", "8001"))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
