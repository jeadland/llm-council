"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR, COUNCIL_MODELS, CHAIRMAN_MODEL, PREMIER_MODELS

RUNS_DIR = "data/runs"
SETTINGS_PATH = "data/settings.json"


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
        "pinned": False,
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
    import json  # Ensure available
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            try:
                path = os.path.join(DATA_DIR, filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "pinned": data.get("pinned", False),
                    "message_count": len(data["messages"])
                })
            except (json.JSONDecodeError, KeyError, Exception) as e:
                print(f"Skipping invalid conversation {filename}: {e}")
                continue

    # Sort pinned first, then newest first
    conversations.sort(key=lambda x: (not x.get("pinned", False), -int(datetime.fromisoformat(x["created_at"]).timestamp())))

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


def set_conversation_pinned(conversation_id: str, pinned: bool):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conversation["pinned"] = pinned
    save_conversation(conversation)


def delete_conversation(conversation_id: str):
    path = get_conversation_path(conversation_id)
    if os.path.exists(path):
        os.remove(path)


def upsert_assistant_message_for_run(
    conversation_id: str,
    run_id: str,
    stage1: Optional[List[Dict[str, Any]]] = None,
    stage2: Optional[List[Dict[str, Any]]] = None,
    stage3: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    loading: Optional[Dict[str, bool]] = None,
    error: Optional[str] = None,
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
            "error": None,
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
    if error is not None:
        target["error"] = error

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


def get_settings() -> Dict[str, Any]:
    default = {
        "available_models": PREMIER_MODELS,
        "council_models": COUNCIL_MODELS,
        "chairman_model": CHAIRMAN_MODEL,
        "theme_mode": "system",
    }
    if not os.path.exists(SETTINGS_PATH):
        return default

    with open(SETTINGS_PATH, "r") as f:
        current = json.load(f)

    settings = {**default, **current}

    # sanitize
    settings["council_models"] = [
        m for m in settings.get("council_models", []) if m in settings["available_models"]
    ]
    if not settings["council_models"]:
        settings["council_models"] = default["council_models"]

    if settings.get("chairman_model") not in settings["available_models"]:
        settings["chairman_model"] = default["chairman_model"]

    return settings


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    ensure_data_dir()
    current = get_settings()
    merged = {**current, **settings}

    available = merged.get("available_models", PREMIER_MODELS)
    council = [m for m in merged.get("council_models", []) if m in available]
    if not council:
        council = current.get("council_models", COUNCIL_MODELS)

    chairman = merged.get("chairman_model", current.get("chairman_model", CHAIRMAN_MODEL))
    if chairman not in available:
        chairman = current.get("chairman_model", CHAIRMAN_MODEL)

    theme_mode = merged.get("theme_mode", current.get("theme_mode", "system"))
    if theme_mode not in {"light", "dark", "system"}:
        theme_mode = current.get("theme_mode", "system")

    final = {
        "available_models": available,
        "council_models": council,
        "chairman_model": chairman,
        "theme_mode": theme_mode,
    }

    with open(SETTINGS_PATH, "w") as f:
        json.dump(final, f, indent=2)

    return final
