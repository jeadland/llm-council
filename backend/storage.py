"""Storage for conversations, runs, settings, and auth state.

Local development defaults to JSON files. Vercel uses Upstash Redis when
configured with STORAGE_BACKEND=redis or Upstash environment variables.
"""

import json
import os
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR, COUNCIL_MODELS, CHAIRMAN_MODEL, PREMIER_MODELS

RUNS_DIR = "data/runs"
SETTINGS_PATH = "data/settings.json"
AUTH_USERS_PATH = "data/auth-users.json"
AUTH_SESSIONS_DIR = "data/auth-sessions"
REDIS_PREFIX = os.getenv("REDIS_KEY_PREFIX", "llm-council")


def _using_redis() -> bool:
    backend = os.getenv("STORAGE_BACKEND", "").strip().lower()
    if backend == "redis":
        return True
    if backend in {"json", "file", "local"}:
        return False
    return bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))


def _redis_env() -> tuple[str, str]:
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        raise RuntimeError("Redis storage requires UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN")
    return url.rstrip("/"), token


def _redis_command(*command):
    url, token = _redis_env()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=list(command),
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as e:
        raise RuntimeError(f"Redis command failed: {command[0]}") from e

    if "error" in payload and payload["error"]:
        raise RuntimeError(f"Redis command failed: {payload['error']}")
    return payload.get("result")


def _key(*parts: str) -> str:
    return ":".join([REDIS_PREFIX, *parts])


def _json_get(key: str) -> Optional[Dict[str, Any]]:
    raw = _redis_command("GET", key)
    if raw is None:
        return None
    return json.loads(raw)


def _json_set(key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None):
    payload = json.dumps(value)
    if ttl_seconds:
        _redis_command("SET", key, payload, "EX", ttl_seconds)
    else:
        _redis_command("SET", key, payload)


def _strip_openrouter_prefix(model: str) -> str:
    return model[len("openrouter/"):] if model.startswith("openrouter/") else model


def _canonicalize_model(model: Optional[str], available: List[str]) -> Optional[str]:
    if not model:
        return None
    if model in available:
        return model
    normalized = _strip_openrouter_prefix(model)
    for candidate in available:
        if _strip_openrouter_prefix(candidate) == normalized:
            return candidate
    return None


def _sanitize_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    available = settings.get("available_models") or PREMIER_MODELS
    council = [
        canonical
        for model in settings.get("council_models", [])
        if (canonical := _canonicalize_model(model, available))
    ]
    if not council:
        council = [
            canonical
            for model in COUNCIL_MODELS
            if (canonical := _canonicalize_model(model, available))
        ] or COUNCIL_MODELS

    chairman = _canonicalize_model(settings.get("chairman_model"), available)
    if chairman is None:
        chairman = _canonicalize_model(CHAIRMAN_MODEL, available) or CHAIRMAN_MODEL

    theme_mode = settings.get("theme_mode", "system")
    if theme_mode not in {"light", "dark", "system"}:
        theme_mode = "system"

    return {
        "available_models": available,
        "council_models": council,
        "chairman_model": chairman,
        "theme_mode": theme_mode,
    }


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def ensure_runs_dir():
    """Ensure the runs directory exists."""
    Path(RUNS_DIR).mkdir(parents=True, exist_ok=True)


def ensure_auth_sessions_dir():
    """Ensure the auth sessions directory exists."""
    Path(AUTH_SESSIONS_DIR).mkdir(parents=True, exist_ok=True)


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
    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "pinned": False,
        "messages": []
    }

    if _using_redis():
        _json_set(_key("conversation", conversation_id), conversation)
        _redis_command("SADD", _key("conversation_ids"), conversation_id)
        return conversation

    ensure_data_dir()

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
    if _using_redis():
        return _json_get(_key("conversation", conversation_id))

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
    if _using_redis():
        _json_set(_key("conversation", conversation["id"]), conversation)
        _redis_command("SADD", _key("conversation_ids"), conversation["id"])
        return

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
    if _using_redis():
        ids = _redis_command("SMEMBERS", _key("conversation_ids")) or []
        conversations = []
        for conversation_id in ids:
            data = get_conversation(conversation_id)
            if not data:
                continue
            conversations.append({
                "id": data.get("id", conversation_id),
                "created_at": data.get("created_at", "1970-01-01T00:00:00Z"),
                "title": data.get("title", "New Conversation"),
                "pinned": data.get("pinned", False),
                "message_count": len(data.get("messages", []))
            })
        conversations.sort(key=_conversation_sort_key)
        return conversations

    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else []:
        if filename.endswith('.json'):
            try:
                path = os.path.join(DATA_DIR, filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                conversations.append({
                    "id": data.get("id", filename[:-5]),
                    "created_at": data.get("created_at", "1970-01-01T00:00:00Z"),
                    "title": data.get("title", "New Conversation"),
                    "pinned": data.get("pinned", False),
                    "message_count": len(data.get("messages", []))
                })
            except Exception as e:
                print(f"Skipping {filename}: {e}")
                continue

    # Sort pinned first, then newest first (safe parse)
    conversations.sort(key=_conversation_sort_key)

    return conversations


def _conversation_sort_key(conv: Dict[str, Any]):
    try:
        return not conv.get("pinned", False), -int(datetime.fromisoformat(conv["created_at"]).timestamp())
    except Exception:
        return True, 0  # unpinned, old


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
    if _using_redis():
        _redis_command("DEL", _key("conversation", conversation_id))
        _redis_command("SREM", _key("conversation_ids"), conversation_id)
        return

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
    if _using_redis():
        _json_set(_key("run", run_id), run)
        _redis_command("SADD", _key("run_ids"), run_id)
        return run

    ensure_runs_dir()
    with open(get_run_path(run_id), "w") as f:
        json.dump(run, f, indent=2)
    return run


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    if _using_redis():
        return _json_get(_key("run", run_id))

    path = get_run_path(run_id)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_run(run: Dict[str, Any]):
    if _using_redis():
        run["updated_at"] = datetime.utcnow().isoformat()
        _json_set(_key("run", run["run_id"]), run)
        _redis_command("SADD", _key("run_ids"), run["run_id"])
        return

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
    if _using_redis():
        latest = None
        for run_id in _redis_command("SMEMBERS", _key("run_ids")) or []:
            run = get_run(run_id)
            if not run or run.get("conversation_id") != conversation_id:
                continue
            if run.get("status") in {"queued", "running"}:
                if latest is None or run.get("created_at", "") > latest.get("created_at", ""):
                    latest = run
        return latest

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
    if _using_redis():
        current = _json_get(_key("settings")) or {}
        return _sanitize_settings({**default, **current})

    if not os.path.exists(SETTINGS_PATH):
        return _sanitize_settings(default)

    with open(SETTINGS_PATH, "r") as f:
        current = json.load(f)

    return _sanitize_settings({**default, **current})


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    current = get_settings()
    final = _sanitize_settings({**current, **settings})

    if _using_redis():
        _json_set(_key("settings"), final)
        return final

    ensure_data_dir()

    with open(SETTINGS_PATH, "w") as f:
        json.dump(final, f, indent=2)

    return final


def get_auth_user(email: str) -> Optional[Dict[str, Any]]:
    if not _using_redis():
        if not os.path.exists(AUTH_USERS_PATH):
            return None
        with open(AUTH_USERS_PATH, "r") as f:
            users = json.load(f)
        return users.get(email.lower())

    return _json_get(_key("auth", "user", email.lower()))


def save_auth_user(email: str, user: Dict[str, Any]):
    if not _using_redis():
        ensure_data_dir()
        users = {}
        if os.path.exists(AUTH_USERS_PATH):
            with open(AUTH_USERS_PATH, "r") as f:
                users = json.load(f)
        users[email.lower()] = user
        with open(AUTH_USERS_PATH, "w") as f:
            json.dump(users, f, indent=2)
        return

    _json_set(_key("auth", "user", email.lower()), user)


def save_session(token_hash: str, session: Dict[str, Any], ttl_seconds: int):
    if not _using_redis():
        ensure_auth_sessions_dir()
        with open(os.path.join(AUTH_SESSIONS_DIR, f"{token_hash}.json"), "w") as f:
            json.dump(session, f, indent=2)
        return

    _json_set(_key("auth", "session", token_hash), session, ttl_seconds=ttl_seconds)
    _redis_command("SADD", _key("auth", "sessions", session["email"].lower()), token_hash)


def get_session(token_hash: str) -> Optional[Dict[str, Any]]:
    if not _using_redis():
        path = os.path.join(AUTH_SESSIONS_DIR, f"{token_hash}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)

    return _json_get(_key("auth", "session", token_hash))


def delete_session(token_hash: str, email: Optional[str] = None):
    if not _using_redis():
        path = os.path.join(AUTH_SESSIONS_DIR, f"{token_hash}.json")
        if os.path.exists(path):
            os.remove(path)
        return

    _redis_command("DEL", _key("auth", "session", token_hash))
    if email:
        _redis_command("SREM", _key("auth", "sessions", email.lower()), token_hash)


def delete_sessions_for_email(email: str):
    if not _using_redis():
        ensure_auth_sessions_dir()
        for filename in os.listdir(AUTH_SESSIONS_DIR):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(AUTH_SESSIONS_DIR, filename)
            try:
                with open(path, "r") as f:
                    session = json.load(f)
                if session.get("email", "").lower() == email.lower():
                    os.remove(path)
            except Exception:
                continue
        return

    sessions_key = _key("auth", "sessions", email.lower())
    token_hashes = _redis_command("SMEMBERS", sessions_key) or []
    for token_hash in token_hashes:
        _redis_command("DEL", _key("auth", "session", token_hash))
    _redis_command("DEL", sessions_key)


def increment_login_attempts(email: str, ttl_seconds: int) -> int:
    if not _using_redis():
        return 1

    attempts_key = _key("auth", "attempts", email.lower())
    attempts = int(_redis_command("INCR", attempts_key) or 0)
    if attempts == 1:
        _redis_command("EXPIRE", attempts_key, ttl_seconds)
    return attempts


def clear_login_attempts(email: str):
    if not _using_redis():
        return

    _redis_command("DEL", _key("auth", "attempts", email.lower()))
