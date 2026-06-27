# Agent Instructions - LLM Council

## Core Working Agreement

This repo is worked on by a human product owner using AI coding agents. Optimize for correctness, clarity, small diffs, and easy review.

- Work on a feature branch, not `main`, unless the user explicitly instructs otherwise.
- Keep `main` as the local/OpenClaw/LAN branch.
- Keep `web/vercel` as the hosted Vercel branch.
- Do not mix unrelated cleanup with feature work.
- Do not commit secrets, `.env`, `data/`, local screenshots, or generated build output.
- If a task touches auth, persistence, deployment, external AI models, or data deletion, treat it as high risk and verify live/runtime behavior.

## Source Of Truth

Use these files in this order:

1. `PRODUCT_SPEC.md` for product scope and user value.
2. `ARCHITECTURE.md` for system shape, commands, risk areas, and technical constraints.
3. `DECISIONS.md` for settled choices.
4. `TASKS.md` for active and upcoming work.
5. `docs/agent-handoff.md` for current state and resume context.
6. `docs/brand/brand-guidelines.md` for visual identity and brand constraints.
7. `JOSH_SITE_DEPLOYMENT.md` before changing production routing, Vercel config,
   auth redirects, hosted storage, or deployment behavior.

If these conflict with code reality, inspect the code and update the docs as part of the work.

## Owner Collaboration

Read `OWNER_OPERATING_GUIDE.md` before non-trivial work.

- The owner is product-minded and AI-fluent, but should not be expected to debug build systems, resolve merge conflicts, inspect production data, or safely edit secrets without step-by-step instructions.
- Provide clear recommendations instead of pushing low-level architecture choices back to the owner.
- Ask for explicit approval before spending money, changing production hosting/DNS, deleting data, changing auth/permissions/privacy behavior, adding vendors/dependencies/models, or broadening scope.
- Prefer safe implementation and verification work directly when the agent can do it.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

Current split:

- Local/LAN branch: `main`
- Hosted web branch: `web/vercel`

## Architecture Notes

### Backend Structure (`backend/`)

**`config.py`**
- Contains default `COUNCIL_MODELS` and `CHAIRMAN_MODEL`.
- Uses `OPENROUTER_API_KEY` from env for direct OpenRouter mode.
- Backend runs on port `8001` locally.

**`openrouter.py`**
- `query_model()`: single async model query.
- `query_models_parallel()`: parallel queries using `asyncio.gather()`.
- Routes through OpenClaw local proxy first when available, then falls back to direct OpenRouter.
- Graceful degradation: returns `None` on model failure and continues with successful responses.

**`council.py`**
- `stage1_collect_responses()`: parallel queries to all council models.
- `stage2_collect_rankings()`: anonymizes responses as `Response A`, `Response B`, etc.; collects peer rankings; parses `FINAL RANKING:`.
- `stage3_synthesize_final()`: chairman synthesis with fallback to council models or top Stage 1 response.
- `calculate_aggregate_rankings()`: computes average rank position across peer evaluations.

**`storage.py`**
- Local default: JSON files under ignored `data/`.
- Vercel mode: Upstash Redis when `STORAGE_BACKEND=redis` or Upstash env vars exist.
- Persists conversations, runs, settings, auth users, sessions, and login attempt counters.

**`auth.py`**
- Google-only auth for hosted web use.
- Uses verified Google email identity, HttpOnly session cookies, and OAuth state validation. Legacy password routes intentionally return `403`.

**`main.py`**
- FastAPI app.
- Protects `/api/*` when auth is required, excluding auth endpoints.
- Local default run mode uses background tasks and run polling.
- Vercel mode uses `RUN_EXECUTION_MODE=sync` to execute the full council inside the request.

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: auth boot, conversations list, current conversation, active run, settings.
- Shows `LoginScreen` before loading app data when auth is required.

**`api.js`**
- API client. Uses `credentials: 'include'` for auth cookies.

**`components/ChatInterface.jsx`**
- Message input, run progress, stage display, stop button.

**`components/Stage1.jsx`**
- Tab view of individual model responses.

**`components/Stage2.jsx`**
- Raw peer evaluations, client-side de-anonymized display, extracted rankings, aggregate rankings.

**`components/Stage3.jsx`**
- Final synthesized answer and copy-to-clipboard controls.

**`components/Sidebar.jsx`**
- Conversations, settings, model picker, chairman picker, theme, Google account, and OpenRouter integration controls.

## Key Design Decisions

### Stage 2 Prompt Format

Stage 2 requires a strict final section:

```text
FINAL RANKING:
1. Response C
2. Response A
3. Response B
```

The parser falls back to extracting `Response X` patterns if a model partially misses the format.

### De-anonymization Strategy

- Models receive anonymous labels.
- Backend creates `label_to_model`.
- Frontend displays model names in bold for readability.
- The raw evaluation process remains anonymous to reduce model favoritism.

### Deployment Strategy

- `main` remains optimized for local OpenClaw/self-hosted LAN usage.
- `web/vercel` contains the hosted Vercel adaptation.
- Vercel requires Redis-backed persistence and synchronous council execution.
- The hosted app is mounted at `https://joshadland.com/llm-council` through the
  `josh-site` front-door repo. Read `JOSH_SITE_DEPLOYMENT.md` before changing
  routing or production deployment behavior.

## Commands

Install:

```bash
uv sync
npm --prefix frontend install
```

Run local app:

```bash
./start.sh
```

Manual backend/frontend:

```bash
uv run python -m backend.main
npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173
```

Verify:

```bash
uv run python -m compileall backend api
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Common Gotchas

- Run backend as `python -m backend.main` from repo root, not from `backend/`.
- Browser/service-worker cache on `localhost:5173` may show stale content from another app; use a different port or clear site data.
- Local OpenClaw mode can work without `OPENROUTER_API_KEY`; Vercel mode requires direct provider secrets.
- Vercel/serverless cannot rely on local JSON files or in-process background tasks.
- Do not expose or log `ADMIN_INITIAL_PASSWORD`, `OPENROUTER_API_KEY`, or Upstash tokens.

## Before Editing

For non-trivial work:

1. Restate the goal.
2. Identify likely files.
3. Explain the smallest viable change.
4. State what should not change.
5. List acceptance criteria.
6. Describe risks and approval gates.
7. Describe verification.
8. Then implement.

For trivial copy, style, or one-file fixes, proceed directly.

## Review Behavior

When asked to review, follow `code_review.md` and lead with findings ordered by severity.
