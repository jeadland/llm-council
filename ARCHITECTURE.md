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
| Auth | Owner email/password plus BYOK user signup | Required in hosted mode |
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
| Conversation | User-visible thread with messages, scoped by authenticated email | `data/conversations/*.json` locally; Redis keys on Vercel |
| Assistant message | Stage 1, Stage 2, Stage 3 output for a run | Embedded in conversation |
| Run | Durable progress/result snapshot for one council query | `data/runs/*.json` locally; Redis keys on Vercel |
| Cost summary | Actual tracked OpenRouter usage/cost for one completed council run | Embedded in run and assistant message when available |
| Settings | Available models, active council/chairman, custom groups, theme, scoped by user | Owner defaults in `data/settings.json`, user settings in `data/user-settings.json`; Redis keys on Vercel |
| Integration credential | Per-user OpenRouter API key status and server-side secret | `data/integrations.json` locally; Redis key on Vercel |
| Model curation state | App-core curator model and promotion history | `data/model-curation-state.json` locally; Redis key on Vercel |
| Model curation draft | Reviewable weekly curated-preset recommendation | `data/model-curation-drafts.json` locally; Redis keys on Vercel |
| Agent research approval | Codex MCP prepared prompt, approved preset, payload hash, cost cap, and linked run | `data/agent-research-approvals.json` locally; Redis keys on Vercel if enabled |
| Auth user | Email, optional name, role, and password hash | `data/auth-users.json` locally; Redis on Vercel |
| Session | HttpOnly-cookie session backing record | `data/auth-sessions/` locally; Redis with TTL on Vercel |

Persistence changes are high-risk. Do not change storage shape or key format without documenting the migration in `DECISIONS.md`.

## Request Flow

1. Frontend calls `/api/auth/me`.
2. If auth is required and no session exists, show sign-in/create-account/reset screen.
3. New users sign up with optional name, required email/password, and required OpenRouter key.
4. Authenticated user creates/selects a conversation in their own scope.
5. Sending a message creates a user-scoped run.
6. Non-owner runs require a saved account OpenRouter key and never fall back to the server owner key.
7. Stage 1 queries council models in parallel.
8. Stage 2 anonymizes Stage 1 answers and asks models to rank responses.
9. Stage 3 asks chairman to synthesize a final answer.
10. Frontend displays all stages and metadata.

Local mode uses background run tasks and polling. Vercel mode uses `RUN_EXECUTION_MODE=sync`, so the create-run request completes the full council run in one function invocation.

## Codex MCP Agent Access

Codex can call LLM Council through the local MCP server at `mcp/llm_council_server.py`. The MCP server is local-first and talks to the FastAPI backend at `http://127.0.0.1:8001`; if the backend is down, it starts only the backend with `BACKEND_HOST=127.0.0.1 BACKEND_PORT=8001 uv run python -m backend.main`. It does not start the React frontend.

Agent access uses bearer-token auth, separate from browser cookies. The raw token lives outside the repo in `~/.codex/secrets/llm-council-agent.env`; the backend reads only `LLM_COUNCIL_AGENT_TOKEN_HASH`. Agent endpoints are disabled unless that hash is configured.

The agent flow is two-step:

1. `prepare_council_research` calls `/api/agent/research/prepare`, which performs no model calls, selects an approved preset, estimates cost, and stores a payload hash.
2. `run_council_research` calls `/api/agent/research/run`, which consumes the prepared approval, verifies the cost cap and payload hash, executes the council, and returns disclosure metadata.

Preset selection is deterministic and uses only approved presets: `quick` -> `efficient-daily`, `standard` -> `premium-balanced`, and `hard`/`adversarial` -> `ultra-premium-frontier`. Unapproved weekly curation drafts are never used by the MCP path.

Hosted fallback is intentionally out of scope for v1. Production routing, hosted auth, and serverless timeout behavior must be validated separately before the MCP server can target a hosted backend.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Frontend app |
| `/api/auth/me` | Auth/session state |
| `/api/auth/signup` | Create BYOK user account, validate OpenRouter key, create session |
| `/api/auth/login` | Create session |
| `/api/auth/logout` | Delete session |
| `/api/auth/change-password` | Rotate password and invalidate old sessions |
| `/api/auth/reset-password` | Create/reset owner password with recovery code and invalidate old sessions |
| `/api/settings` | Read/update active model group, custom groups, chairman, and theme settings |
| `/api/integrations/openrouter` | Read masked OpenRouter key status and save/clear the current user's account key |
| `/api/models/status` | Safe model-provider status booleans and catalog reachability |
| `/api/models/catalog` | OpenRouter text model catalog metadata plus app-level council presets |
| `/api/model-curation/latest` | Read latest model curation draft and app-core curation state |
| `/api/model-curation/run` | Owner-triggered curation draft generation |
| `/api/model-curation/{id}/approve` | Owner approval path for curated preset updates |
| `/api/agent/research/prepare` | Bearer-token protected no-spend Codex MCP preparation endpoint |
| `/api/agent/research/run` | Bearer-token protected approved Codex MCP council run endpoint |
| `/api/agent/research/runs/{id}` | Bearer-token protected Codex MCP result lookup |
| `/api/cron/model-curation` | Vercel Cron entrypoint for weekly curation drafts |
| `/api/conversations` | List/create conversations |
| `/api/conversations/{id}` | Read/delete conversation |
| `/api/conversations/{id}/runs` | Create council run |
| `/api/conversations/{id}/runs/{run_id}` | Read run snapshot |

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Vercel/direct mode | Direct OpenRouter calls, scoped to owner account in hosted mode |
| `OPENROUTER_OWNER_EMAIL` | Optional hosted | Overrides `ADMIN_EMAIL` as the account allowed to use the server OpenRouter key |
| `MODEL_CURATION_MODEL` | Optional hosted | Initial curation model override before app-core curation state exists; default is `openrouter/auto` |
| `MODEL_CURATION_MAX_USD` | Optional hosted | Maximum estimated spend for one curation model call, default `2.00` |
| `LLM_COUNCIL_AGENT_TOKEN_HASH` | Local MCP agent | SHA-256 hash of the Codex MCP bearer token; endpoints are disabled when absent |
| `LLM_COUNCIL_AGENT_OWNER_EMAIL` | Optional local MCP agent | Account scope used for agent runs; defaults to `ADMIN_EMAIL` or local owner scope |
| `LLM_COUNCIL_AGENT_MAX_USD` | Optional local MCP agent | Maximum estimated/approved spend for one agent run, default `3.00` |
| `CRON_SECRET` | Hosted cron | Secret Vercel sends as `Authorization: Bearer ...` for weekly curation |
| `OPENCLAW_GATEWAY_TOKEN` | Optional local | Override OpenClaw gateway token |
| `OPENCLAW_CONFIG_PATH` | Optional local | Override OpenClaw config path |
| `STORAGE_BACKEND=redis` | Vercel | Force Redis storage |
| `UPSTASH_REDIS_REST_URL` or `KV_REST_API_URL` | Vercel | Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` or `KV_REST_API_TOKEN` | Vercel | Redis token |
| `RUN_EXECUTION_MODE=sync` | Vercel | Avoid serverless background tasks |
| `ADMIN_EMAIL` | Hosted auth | Single allowed owner email |
| `ADMIN_INITIAL_PASSWORD` | Hosted auth bootstrap | Used only to create first password hash |
| `ADMIN_PASSWORD_RESET_TOKEN` | Hosted password recovery | Owner-only recovery code for resetting password from login screen |
| `AUTH_REQUIRED` | Optional | Force auth on/off locally |
| `COOKIE_SECURE` | Optional local | Use `false` for local auth smoke over HTTP |

Non-owner users must save their own OpenRouter API key. The server `OPENROUTER_API_KEY` is owner-scoped and is not used for non-owner council runs.

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
| Auth | Can expose or block private app access | Smoke signup/login/logout/password change |
| Redis persistence | Can lose or cross-contaminate conversation/settings state | Verify user-scoped data survives reload/redeploy and remains isolated |
| Vercel run mode | Council runs may exceed function duration | Test with realistic model count |
| Model catalog | OpenClaw aliases and OpenRouter IDs differ | Verify settings output and direct query IDs |
| Local vs hosted branches | Easy to break one mode while fixing the other | Verify branch intent before editing |
| Public deployment | Private app with paid model calls | Protect APIs and avoid unauthenticated access |

## Known Risks

- Vercel synchronous council runs may time out for large model sets or slow providers.
- Redis schema is intentionally JSON-shaped for fast migration, not optimized analytics.
- Local browser cache/service workers on `localhost:5173` can show stale apps from other projects.
- The app currently relies on manual smoke checks rather than automated end-to-end tests.
