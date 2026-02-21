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

- Durable run tracking (survives navigation/reload)
- Progressive stage rendering (inspect stages as they arrive)
- Conversation pin + delete
- Theme modes: **Light / Dark / System**
- Settings panel with:
  - **Your Available Models** (from local OpenClaw model config)
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

### 3) Configure API key

Create `.env` in repo root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

### 4) Run app

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

## Settings behavior on other OpenClaw installs

The model picker is sourced from that machine’s OpenClaw model config (not a global OpenRouter catalog), so each deployment reflects local configured models.

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
- **Model API:** OpenRouter
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
