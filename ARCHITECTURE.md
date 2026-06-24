# Architecture

## Overview

LLM Council is a React + FastAPI app that asks multiple LLMs the same user question, has them anonymously rank each other, and synthesizes a final answer through a chairman model. The repo supports two deployment shapes: local/OpenClaw LAN mode from `main`, and hosted Vercel web mode from `web/vercel`.

## Tech Stack

| Layer | Technology | Notes |
| --- | --- | --- |
| Frontend | React 19 + Vite | App shell, conversation UI, stage views, settings, auth screen |
| Styling | Plain CSS | Component CSS files plus global variables in `index.css` |
| Backend | FastAPI | Local uvicorn or Vercel Python Function |
| Model API | OpenClaw local proxy + OpenRouter direct | OpenClaw first locally; OpenRouter direct for Vercel |
| Persistence | JSON files locally; Upstash Redis on Vercel | Selected by env |
| Auth | Single-owner email/password | Required in hosted mode |
| Package managers | `uv` and `npm` | Python backend, JS frontend |
| Deployment | Local LAN, Vercel | `main` for local/OpenClaw, `web/vercel` for hosted |

## Main Directories

```text
backend/               FastAPI app, council orchestration, storage, auth, model API clients
api/index.py           Vercel Python Function entrypoint
frontend/src/          React app
frontend/public/       Icons and static image assets
skills/install-llm-council/  OpenClaw installer skill bundle
docs/                  Agent handoff and brand guidance
.cursor/rules/         Cursor workflow rules
.github/               PR and issue templates
```

## Core Data

| Entity | Purpose | Persistence |
| --- | --- | --- |
| Conversation | User-visible thread with messages | `data/conversations/*.json` locally; Redis keys on Vercel |
| Assistant message | Stage 1, Stage 2, Stage 3 output for a run | Embedded in conversation |
| Run | Durable progress/result snapshot for one council query | `data/runs/*.json` locally; Redis keys on Vercel |
| Settings | Available models, council selection, chairman, theme | `data/settings.json` locally; Redis key on Vercel |
| Auth user | Owner email and password hash | `data/auth-users.json` locally; Redis on Vercel |
| Session | HttpOnly-cookie session backing record | `data/auth-sessions/` locally; Redis with TTL on Vercel |

Persistence changes are high-risk. Do not change storage shape or key format without documenting the migration in `DECISIONS.md`.

## Request Flow

1. Frontend calls `/api/auth/me`.
2. If auth is required and no session exists, show `LoginScreen`.
3. Authenticated user creates/selects a conversation.
4. Sending a message creates a run.
5. Stage 1 queries council models in parallel.
6. Stage 2 anonymizes Stage 1 answers and asks models to rank responses.
7. Stage 3 asks chairman to synthesize a final answer.
8. Frontend displays all stages and metadata.

Local mode uses background run tasks and polling. Vercel mode uses `RUN_EXECUTION_MODE=sync`, so the create-run request completes the full council run in one function invocation.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Frontend app |
| `/api/auth/me` | Auth/session state |
| `/api/auth/login` | Create session |
| `/api/auth/logout` | Delete session |
| `/api/auth/change-password` | Rotate owner password and invalidate old sessions |
| `/api/auth/reset-password` | Create/reset owner password with recovery code and invalidate old sessions |
| `/api/settings` | Read/update model and theme settings |
| `/api/conversations` | List/create conversations |
| `/api/conversations/{id}` | Read/delete conversation |
| `/api/conversations/{id}/runs` | Create council run |
| `/api/conversations/{id}/runs/{run_id}` | Read run snapshot |

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Vercel/direct mode | Direct OpenRouter calls |
| `OPENCLAW_GATEWAY_TOKEN` | Optional local | Override OpenClaw gateway token |
| `OPENCLAW_CONFIG_PATH` | Optional local | Override OpenClaw config path |
| `STORAGE_BACKEND=redis` | Vercel | Force Redis storage |
| `UPSTASH_REDIS_REST_URL` | Vercel | Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | Vercel | Redis token |
| `RUN_EXECUTION_MODE=sync` | Vercel | Avoid serverless background tasks |
| `ADMIN_EMAIL` | Hosted auth | Single allowed owner email |
| `ADMIN_INITIAL_PASSWORD` | Hosted auth bootstrap | Used only to create first password hash |
| `ADMIN_PASSWORD_RESET_TOKEN` | Hosted password recovery | Owner-only recovery code for resetting password from login screen |
| `AUTH_REQUIRED` | Optional | Force auth on/off locally |
| `COOKIE_SECURE` | Optional local | Use `false` for local auth smoke over HTTP |

Never print secrets in chat, logs, screenshots, or docs.

## Commands

```bash
uv sync
npm --prefix frontend install
./start.sh
uv run python -m backend.main
npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173
uv run python -m compileall backend api
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Deployment

Local:

- `main`
- `./start.sh`
- OpenClaw gateway preferred when available.

Hosted:

- `web/vercel`
- Vercel project production branch should be `web/vercel`.
- Required Vercel env vars: OpenRouter, Upstash Redis, admin email/password bootstrap, sync run mode.
- Validate preview before production.

## High-Risk Areas

| Area | Why risky | Required caution |
| --- | --- | --- |
| Auth | Can expose or block private app access | Smoke login/logout/password change |
| Redis persistence | Can lose conversation/settings state | Verify data survives reload/redeploy |
| Vercel run mode | Council runs may exceed function duration | Test with realistic model count |
| Model catalog | OpenClaw aliases and OpenRouter IDs differ | Verify settings output and direct query IDs |
| Local vs hosted branches | Easy to break one mode while fixing the other | Verify branch intent before editing |
| Public deployment | Private app with paid model calls | Protect APIs and avoid unauthenticated access |

## Known Risks

- Vercel synchronous council runs may time out for large model sets or slow providers.
- Redis schema is intentionally JSON-shaped for fast migration, not optimized analytics.
- Local browser cache/service workers on `localhost:5173` can show stale apps from other projects.
- The app currently relies on manual smoke checks rather than automated end-to-end tests.
