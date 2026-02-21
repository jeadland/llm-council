"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

RUNS_DIR = "data/runs"


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def ensure_runs_dir():
    """Ensure the runs directory exists."""
    Path(RUNS_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": []
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                # Return metadata only
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data["messages"])
                })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def upsert_assistant_message_for_run(
    conversation_id: str,
    run_id: str,
    stage1: Optional[List[Dict[str, Any]]] = None,
    stage2: Optional[List[Dict[str, Any]]] = None,
    stage3: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    loading: Optional[Dict[str, bool]] = None,
):
    """Create/update a durable assistant message linked to a run id."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    target = None
    for msg in reversed(conversation["messages"]):
        if msg.get("role") == "assistant" and msg.get("run_id") == run_id:
            target = msg
            break

    if target is None:
        target = {
            "role": "assistant",
            "run_id": run_id,
            "stage1": None,
            "stage2": None,
            "stage3": None,
            "metadata": None,
            "loading": {
                "stage1": False,
                "stage2": False,
                "stage3": False,
            },
        }
        conversation["messages"].append(target)

    if stage1 is not None:
        target["stage1"] = stage1
    if stage2 is not None:
        target["stage2"] = stage2
    if stage3 is not None:
        target["stage3"] = stage3
    if metadata is not None:
        target["metadata"] = metadata
    if loading is not None:
        target["loading"] = {**target.get("loading", {}), **loading}

    save_conversation(conversation)


def get_run_path(run_id: str) -> str:
    return os.path.join(RUNS_DIR, f"{run_id}.json")


def create_run(run_id: str, conversation_id: str, content: str) -> Dict[str, Any]:
    ensure_runs_dir()
    run = {
        "run_id": run_id,
        "conversation_id": conversation_id,
        "content": content,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "error": None,
        "stage1": {"status": "pending", "data": None},
        "stage2": {"status": "pending", "data": None, "metadata": None},
        "stage3": {"status": "pending", "data": None},
    }
    with open(get_run_path(run_id), "w") as f:
        json.dump(run, f, indent=2)
    return run


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    path = get_run_path(run_id)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_run(run: Dict[str, Any]):
    ensure_runs_dir()
    run["updated_at"] = datetime.utcnow().isoformat()
    with open(get_run_path(run["run_id"]), "w") as f:
        json.dump(run, f, indent=2)


def update_run(run_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    run = get_run(run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    for key, value in patch.items():
        if key in {"stage1", "stage2", "stage3"} and isinstance(value, dict):
            run[key] = {**run.get(key, {}), **value}
        else:
            run[key] = value

    save_run(run)
    return run


def get_latest_active_run_for_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    ensure_runs_dir()
    latest = None
    for filename in os.listdir(RUNS_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(RUNS_DIR, filename)
        with open(path, "r") as f:
            run = json.load(f)
        if run.get("conversation_id") != conversation_id:
            continue
        if run.get("status") in {"queued", "running"}:
            if latest is None or run.get("created_at", "") > latest.get("created_at", ""):
                latest = run
    return latest
