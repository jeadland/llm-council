"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

from . import storage
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.0\.1\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    content: str


class CreateRunRequest(BaseModel):
    content: str


class PinConversationRequest(BaseModel):
    pinned: bool


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


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


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


async def _execute_run(run_id: str):
    run = storage.get_run(run_id)
    if run is None:
        return

    conversation_id = run["conversation_id"]
    content = run["content"]

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
        stage1_results = await stage1_collect_responses(content)
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
        stage2_results, label_to_model = await stage2_collect_rankings(content, stage1_results)
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
        stage3_result = await stage3_synthesize_final(content, stage1_results, stage2_results)
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

    except Exception as e:
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
        )


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

    asyncio.create_task(_execute_run(run_id))

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

            if current.get("status") in {"complete", "failed"}:
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
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
