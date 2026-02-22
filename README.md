# LLM Council

![llmcouncil](header.jpg)

LLM Council lets you ask one question to multiple models, have them critique/rank each other, and then synthesize a final chairman answer.

## How it works

1. **Stage 1 — First opinions**: each selected council model answers independently.
2. **Stage 2 — Peer review**: each model ranks anonymized responses.
3. **Stage 3 — Chairman synthesis**: one designated chairman model produces a final answer.

---

## What this fork adds

This fork is optimized for OpenClaw/self-hosting and includes:

- **OpenClaw local proxy** — routes through the local OpenClaw gateway; no API key needed
- Durable run tracking (survives navigation/reload)
- Progressive stage rendering (inspect stages as they arrive)
- Conversation pin + delete
- Theme modes: **Light / Dark / System**
- Settings panel with:
  - **Your Available Models** (live catalog from OpenClaw gateway)
  - Council model picker
  - Chairman designation
- Local data safety defaults (`data/` and `.env` are gitignored)

---

## OpenClaw-friendly quick install

### 1) Clone

```bash
git clone https://github.com/jeadland/llm-council.git
cd llm-council
```

### 2) Install dependencies

Backend:
```bash
uv sync
```

Frontend:
```bash
cd frontend
npm install
cd ..
```

### 3) Run app (no API key needed on OpenClaw installs)

Backend:
```bash
uv run python -m backend.main
```

Frontend (dev):
```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5174
```

Frontend (preview/prod-like):
```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

> **How it works locally:** The backend automatically detects the running OpenClaw gateway
> at `http://127.0.0.1:18789` and uses it as an OpenAI-compatible proxy. The gateway
> handles authentication and routes to any configured provider (OpenRouter, Bedrock, Ollama, etc.).
> No `.env` file or API key is required when the OpenClaw gateway is running.

---

## Optional: OpenRouter direct API (non-OpenClaw installs)

If you're running without an OpenClaw gateway, create `.env` in the repo root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

The backend falls back to direct OpenRouter API calls when the local gateway is not available.

---

## Model routing

```
query_model("openrouter/anthropic/claude-sonnet-4.6", ...)
    │
    ├─ 1. OpenClaw gateway (http://127.0.0.1:18789/v1/chat/completions)
    │       ✓ No API key needed
    │       ✓ Supports all configured providers
    │       ✓ Full model catalog via models.list RPC
    │
    └─ 2. OpenRouter direct (https://openrouter.ai/api/v1/chat/completions)
            Fallback when gateway unavailable
            Requires OPENROUTER_API_KEY
```

---

## Optional: expose through Caddy on `:5173`

Example Caddyfile:

```caddy
:5173 {
  encode zstd gzip

  handle /api/* {
    reverse_proxy 127.0.0.1:8001
  }

  handle {
    reverse_proxy 127.0.0.1:4173
  }
}
```

Then reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

---

## Settings behavior

The model picker is sourced from the live OpenClaw gateway catalog (`models.list` RPC) when
available. Falls back to statically configured models in `openclaw.json`, then a curated
premier models list. Each deployment automatically reflects the models available to that
OpenClaw instance.

---

## Data + privacy

Local runtime data is stored under:

- `data/conversations/`
- `data/runs/`
- `data/settings.json`

These are ignored by git (`data/` in `.gitignore`), so conversation history is not pushed by default.

---

## Tech stack

- **Backend:** FastAPI (Python 3.10+), async httpx
- **Frontend:** React + Vite
- **Model API:** OpenClaw local proxy (primary) + OpenRouter direct (fallback)
- **Package mgmt:** uv + npm

---

## Dev notes

- If Safari caches stale CSS, hard refresh after UI theme/style changes.
- If ports clash, check listeners:

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN
lsof -nP -iTCP:4173 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
```
