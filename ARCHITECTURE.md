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
| Auth | Google-only hosted sign-in plus BYOK OpenRouter integration | Required in hosted mode |
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
| Auth user | Email, optional name, role, disabled legacy password hash when present, and OAuth account metadata | `data/auth-users.json` locally; Redis on Vercel |
| Session | HttpOnly-cookie session backing record | `data/auth-sessions/` locally; Redis with TTL on Vercel |

Persistence changes are high-risk. Do not change storage shape or key format without documenting the migration in `DECISIONS.md`.

## Request Flow

1. Frontend calls `/api/auth/me`.
2. If auth is required and no session exists, show the Google-only sign-in screen.
3. Users sign in with Google; non-owner users add an OpenRouter key later through API & Integrations.
4. Authenticated user creates/selects a conversation in their own scope.
5. Sending a message creates a user-scoped run.
6. Non-owner runs require a saved account OpenRouter key and never fall back to the server owner key.
7. Stage 1 queries council models in parallel.
8. Stage 2 anonymizes Stage 1 answers, asks every configured council model to rank responses, retries missing reviewers, and persists progress as rankings arrive.
9. Stage 3 asks chairman to synthesize a final answer only after every expected Stage 2 reviewer returns a usable ranking.
10. Frontend displays all stages and metadata.

Local mode uses background run tasks and polling. Vercel mode uses `RUN_EXECUTION_MODE=sync`, so the create-run request completes the full council run in one function invocation.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Frontend app |
| `/api/auth/me` | Auth/session state |
| `/api/auth/signup` | Disabled; returns 403 because hosted auth is Google-only |
| `/api/auth/login` | Disabled; returns 403 because hosted auth is Google-only |
| `/api/auth/oauth/google/start` | Redirect unauthenticated users to Google OAuth |
| `/api/auth/oauth/google/callback` | Exchange Google OAuth code, verify email, link/create non-owner account, create session |
| `/api/auth/logout` | Delete session |
| `/api/auth/change-password` | Disabled; returns 403 because hosted auth is Google-only |
| `/api/auth/reset-password` | Disabled; returns 403 because hosted auth is Google-only |
| `/api/settings` | Read/update active model group, custom groups, chairman, and theme settings |
| `/api/integrations/openrouter` | Read masked OpenRouter key status and save/clear the current user's account key |
| `/api/models/status` | Safe model-provider status booleans and catalog reachability |
| `/api/models/catalog` | OpenRouter text model catalog metadata plus app-level council presets |
| `/api/model-curation/latest` | Read latest model curation draft and app-core curation state |
| `/api/model-curation/run` | Owner-triggered curation draft generation |
| `/api/model-curation/{id}/approve` | Owner approval path for curated preset updates |
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
| `GOOGLE_OAUTH_CLIENT_ID` | Hosted Google login | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Hosted Google login | Google OAuth client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | Hosted Google login | Callback URL, usually `https://joshadland.com/llm-council/api/auth/oauth/google/callback` |
| `OAUTH_STATE_SECRET` | Hosted Google login | HMAC secret for OAuth state validation |
| `ALLOW_OWNER_GOOGLE_OAUTH` | Optional hosted | Defaults off; set true only when intentionally allowing the configured owner email to use Google login |
| `MODEL_CURATION_MODEL` | Optional hosted | Initial curation model override before app-core curation state exists; default is `openrouter/auto` |
| `MODEL_CURATION_MAX_USD` | Optional hosted | Maximum estimated spend for one curation model call, default `2.00` |
| `CRON_SECRET` | Hosted cron | Secret Vercel sends as `Authorization: Bearer ...` for weekly curation |
| `OPENCLAW_GATEWAY_TOKEN` | Optional local | Override OpenClaw gateway token |
| `OPENCLAW_CONFIG_PATH` | Optional local | Override OpenClaw config path |
| `STORAGE_BACKEND=redis` | Vercel | Force Redis storage |
| `UPSTASH_REDIS_REST_URL` or `KV_REST_API_URL` | Vercel | Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` or `KV_REST_API_TOKEN` | Vercel | Redis token |
| `RUN_EXECUTION_MODE=sync` | Vercel | Avoid serverless background tasks |
| `ADMIN_EMAIL` | Hosted auth | Single allowed owner email |
| `ADMIN_INITIAL_PASSWORD` | Legacy password bootstrap | Ignored by hosted Google-only login routes |
| `ADMIN_PASSWORD_RESET_TOKEN` | Legacy password recovery | Ignored by hosted Google-only login routes |
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
- Required Vercel env vars: OpenRouter, Upstash Redis, Google OAuth, sync run mode.
- Validate preview before production.

## High-Risk Areas

| Area | Why risky | Required caution |
| --- | --- | --- |
| Auth | Can expose or block private app access | Smoke Google login/logout, disabled password routes, and user-scoped data |
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
