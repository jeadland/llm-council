"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key (optional when using OpenClaw local proxy)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenClaw local proxy URL — set OPENCLAW_PROXY_URL to override
# When the local OpenClaw gateway is running, no API key is needed.
OPENCLAW_PROXY_URL = os.getenv("OPENCLAW_PROXY_URL", "http://127.0.0.1:18789")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "anthropic/claude-opus-4.6",
    "openai/gpt-5.2",
    "google/gemini-2.5-pro",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "anthropic/claude-opus-4.6"

# Curated premier models list (update over time)
PREMIER_MODELS = [
    "anthropic/claude-opus-4.6",
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.2",
    "google/gemini-2.5-pro",
    "x-ai/grok-4",
]

# OpenRouter API endpoint (override via env for local proxy mode)
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")

# Data directory for conversation storage (relative to backend/)
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'conversations'))
