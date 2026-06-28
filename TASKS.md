# Tasks

Use this file as the lightweight source of truth for current and upcoming work. Each task should be small enough for one agent session.

## Now

### Task: Make LLM Council callable by Codex via MCP

Status: Implemented on `codex/llm-council-mcp`; verification in progress

Goal:

Expose LLM Council as a local Codex MCP tool for hard research questions with bearer-token auth, prepared-run approval, deterministic preset selection, backend auto-start, and required cost/transparency metadata.

Acceptance criteria:

- [x] Agent endpoints require bearer-token auth and are disabled without token hash configuration.
- [x] `prepare` performs no model call, selects only approved presets, stores a payload hash, and returns cost estimate.
- [x] `run` consumes a prepared approval, verifies cost cap/hash/expiry, executes synchronously, and returns disclosure fields.
- [x] MCP server auto-starts the local FastAPI backend only.
- [x] User-level Codex config exposes the MCP tools.
- [ ] Manual Codex smoke verifies paid-run approval prompt, run, and disclosure.

Verification:

- [x] `uv run python -m unittest tests.test_agent_research tests.test_mcp_server tests.test_settings_presets tests.test_cost_tracking`
- [x] `uv run python -m compileall backend api mcp`
- [x] `uv run python -m unittest discover tests`
- [x] `npm --prefix frontend run lint`
- [x] `npm --prefix frontend run build`
- [x] `codex mcp list`
- [x] No-spend MCP prepare smoke

### Task: Deploy and validate Vercel web branch

Status: Not started

Goal:

Push `web/vercel`, configure Vercel/Upstash/OpenRouter environment variables, deploy a preview, and verify private auth plus a small council query before production.

User-visible behavior:

- Hosted app shows login before any conversation data.
- Josh can log in with Google and use the council.
- Conversations/settings persist through reload.

Relevant files:

- `vercel.json`
- `api/index.py`
- `backend/auth.py`
- `backend/storage.py`
- `frontend/src/components/LoginScreen.jsx`
- `frontend/src/components/Sidebar.jsx`

Acceptance criteria:

- [ ] User-facing behavior: login wall appears on hosted preview.
- [ ] Data or persistence behavior: conversation/settings survive reload and redeploy.
- [ ] Loading, empty, error, and permission states: unauthenticated API returns `401`; Google auth errors show clear error.
- [ ] Password routes: signup, login, reset, and change-password return `403` with the Google-only message.
- [ ] Mobile/responsive behavior: login and main app usable on phone width.
- [ ] What must not change: `main` remains local/OpenClaw branch.

Out of scope:

- Multi-user accounts.
- Queue-based progressive hosted runs.
- Public marketing site.

Approval gates:

- [x] Production, DNS, app-store, or public launch settings
- [x] Auth, billing, entitlements, permissions, or privacy-sensitive behavior
- [x] New dependencies, vendors, AI models, or external services

Verification:

- [ ] `uv run python -m compileall backend api`
- [ ] `npm --prefix frontend run lint`
- [ ] `npm --prefix frontend run build`
- [ ] Vercel preview smoke
- [ ] Hosted auth smoke
- [ ] Hosted small council query

Notes:

- Do not commit or print real secrets.
- Set Vercel production branch to `web/vercel`, not `main`.
- Do not rely on `ADMIN_PASSWORD_RESET_TOKEN`; hosted password recovery is superseded by Google-only login.

## Next

- Configure Google OAuth env vars in Vercel and register callback URLs in Google Cloud.
- Smoke Google OAuth with a disposable non-owner account: login, OpenRouter missing-key block, key save, run unblocked.
- Validate the redesigned top model bar and curated/custom picker on hosted preview.
- Validate weekly model curation cron on hosted preview: draft creation, app-core curator promotion, Redis state persistence, and review-gated preset approval.
- Validate OpenRouter key save on hosted preview with a disposable account key.
- Add durable council-run resume/queueing so incomplete Stage 2 reviewers can continue after process restarts, browser disconnects, or Vercel function timeouts.
- Add automated backend tests for auth hash/session behavior.
- Add a documented Vercel deploy checklist with exact env var setup steps.
- Decide whether hosted runs need queue/progress architecture if sync runs time out.

## Later

- Email confirmation and recovery:
  - User-facing behavior: users confirm email and recover account access without owner intervention if a non-Google auth path is reintroduced.
  - Data or persistence behavior: confirmation and reset tokens are single-use and server-side only.
  - What must not change: BYOK remains required for non-owner model access.
- OpenRouter OAuth connect:
  - User-facing behavior: less technical users may connect an OpenRouter account through OAuth PKCE instead of pasting a key.
  - Data or persistence behavior: full keys stay server-side only; the browser receives only masked status and source.
  - What must not change: no app-managed billing or Josh-funded model access in this phase.
- Managed credits beta:
  - User-facing behavior: users can buy credits, spend them on council runs, and see remaining balance plus per-run cost.
  - Data or persistence behavior: each managed user has an OpenRouter Management API-provisioned key with a hard spend limit, a local balance ledger, and run-level cost entries tied to `user_id`, OpenRouter key hash, and billing account ID.
  - Loading, empty, error, and permission states: users are blocked before a run when balance is insufficient or their managed key limit is exhausted.
  - What must not change: no managed-credit access without explicit owner approval, payment setup, admin visibility, and spend caps.
  - Verification evidence: Stripe payment test, OpenRouter key provisioning test, balance decrement test, spend-limit block test, and admin reconciliation check against OpenRouter usage.
- Conversation export to Markdown/PDF.
- Model performance analytics over time.
- Custom ranking criteria per question.
- Durable queue/worker for hosted progressive run updates.

## Parking Lot

- Multi-user auth and sharing.
- Public landing/marketing page.
- Billing or subscription access.
- Parent-friendly managed-credit onboarding for non-technical users.

## Completed

- 2026-06-24: Switched hosted auth to Google-only while preserving BYOK model-access gating.
- 2026-06-24: Added top-level model bar, richer curated/custom model picker, owner-scoped OpenRouter key handling, cost estimates, and reviewable weekly curation draft endpoints.
- 2026-06-24: Added no-invite BYOK foundation with per-user data scoping, key masking, and non-owner server-key fallback protection.
- 2026-06-24: Added Vercel web branch implementation with Redis storage, private auth, and sync run mode. Commit: `4892cb6`.
- 2026-06-24: Added project-bootstrap workflow docs and Cursor/GitHub templates.
