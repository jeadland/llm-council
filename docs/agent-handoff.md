# Agent Handoff

Use this file to transfer context between ChatGPT, Codex, Cursor, GitHub, and human review.

## Current State Summary

```text
The app is LLM Council, a React + FastAPI multi-model deliberation app.
The active branch for this task is codex/managed-balance-beta, branched from web/vercel.
main remains the local/OpenClaw/LAN branch.
The current implementation includes Vercel config, Redis-backed storage, Google-only private auth, BYOK OpenRouter key setup after login, sync run mode, and managed-balance beta code.
The next task is hosted/infrastructure verification: Supabase/Postgres migration, Stripe test-mode checkout/webhook, OpenRouter child-key provisioning, and Vercel preview smoke with MANAGED_MODE_ENABLED=false.
```

## Active Task

Task name: Validate managed balance private beta

Goal: Validate Stripe-backed LLM Council Balance on the managed-balance feature branch without enabling live managed runs.

Expected behavior:

- Unauthenticated hosted visitors see only the Google sign-in button.
- New users create/sign into an account with Google, then add their own OpenRouter key through API & Integrations before running council requests.
- Authenticated owner and BYOK users can use the council.
- Managed beta users can add LLM Council Balance, choose curated profiles, see pre-run max-charge estimates, and receive receipts once enabled.
- BYOK remains usable when managed mode is paused, underfunded, or disabled.
- Password signup, login, reset, and change-password routes are intentionally disabled.
- Data persists through reload/redeploy and remains scoped by authenticated user.

Scope classification:

- [x] MVP requirement
- [ ] Later enhancement
- [ ] Nice-to-have polish
- [ ] Dangerous distraction to avoid or park

## Relevant Files

- `vercel.json`
- `api/index.py`
- `backend/auth.py`
- `backend/main.py`
- `backend/storage.py`
- `backend/billing/`
- `migrations/20260627_managed_billing.sql`
- `frontend/src/App.jsx`
- `frontend/src/api.js`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/ChatInterface.jsx`
- `tests/test_billing.py`
- `tests/test_byok_onboarding.py`
- `README.md`

## What Has Been Tried

- Created `web/vercel` from `main`.
- Implemented Vercel wiring.
- Implemented Redis storage with JSON fallback.
- Implemented private Google-only auth.
- Implemented BYOK OpenRouter setup after login through API & Integrations.
- Implemented Google OAuth start/callback routes with signed state, verified Google email, email-keyed account linking, owner Google login disabled by default unless explicitly enabled, and OAuth-only account UI handling.
- Implemented per-user conversation/settings/run/integration scoping and non-owner server-key fallback protection.
- Verified password auth routes are disabled in tests.
- Verified compile, lint, and build.
- Added managed-balance billing storage, Stripe webhook idempotency, encrypted BYOK storage, OpenRouter management-key child-key scaffolding, managed run reservations/finalization, frontend billing UI, and owner finance summary.

## Known Constraints

- Do not commit secrets.
- Vercel hosted mode requires Upstash Redis and OpenRouter env vars.
- Managed billing hosted mode requires Supabase/Postgres `DATABASE_URL`, Stripe test keys/webhook secret/price IDs, `OPENROUTER_MANAGEMENT_KEY`, and `KEY_ENCRYPTION_SECRET`.
- `MANAGED_MODE_ENABLED` defaults off and should remain off until infrastructure smoke tests pass.
- Synchronous hosted runs may hit function duration limits.
- `main` should not be accidentally converted to hosted-only behavior.

## Approval Gates

Owner approval is needed before:

- [x] Spending money or enabling paid services
- [x] Production, DNS, app-store, or public launch changes
- [x] Data deletion or irreversible migration
- [x] Auth, billing, entitlement, permission, or privacy-sensitive changes
- [x] New dependencies, vendors, AI models, or external services
- [x] Scope expansion beyond this task
- [ ] No approval gates currently apply

## Acceptance Criteria

- [ ] User-facing behavior: Google-only login wall appears on hosted preview.
- [ ] Data or persistence behavior: conversation/settings survive reload and redeploy and remain user-scoped.
- [ ] Loading, empty, error, and permission states: unauthenticated APIs return `401`; Google auth errors show clear error.
- [ ] Password routes: signup, login, reset, and change-password return `403`.
- [ ] BYOK onboarding: Google user is blocked before saving an OpenRouter key, then sees a masked key after saving.
- [ ] Google OAuth onboarding: disposable Google user can sign in, is blocked before saving an OpenRouter key, then can run after saving a key.
- [ ] Mobile/responsive behavior: login and main app are usable at phone width.
- [ ] What must not change: local OpenClaw flow on `main`.
- [ ] Verification evidence: Vercel preview URL, auth smoke results, and one small council query.

## Verification So Far

Commands run:

```text
uv run python -m compileall backend api
uv run python -m unittest discover tests
npm --prefix frontend run lint
npm --prefix frontend run build
local API auth smoke for unauthenticated access, disabled password routes, and Google-created user behavior
```

Results:

```text
compileall passed
unittest passed
frontend build passed
frontend lint passed with 2 hook dependency warnings
auth smoke: unauth=401, password auth routes disabled, Google-created users are scoped and key-gated
```

Live/runtime evidence:

```text
Local browser screenshot was captured before auth work; hosted Vercel smoke still pending.
```

## Resume Protocol

If this work resumes after chat reset, context loss, or usage-limit interruption:

1. Read `AGENTS.md`, `OWNER_OPERATING_GUIDE.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TASKS.md`, and this file.
2. For UI or brand work, also read `docs/brand/brand-guidelines.md`.
3. Confirm current branch with `git status --short --branch`.
4. Continue from the first unchecked acceptance criterion or verification item.
5. Do not broaden scope without updating `TASKS.md` and getting owner approval if an approval gate applies.

## Open Questions

- Which Vercel project/team should own the deployment?
- Should production use a custom domain or the default Vercel URL first?
- What maximum hosted council wait time is acceptable before queue/progressive architecture is needed?

## Prompt For Cursor Implementation

```text
Read AGENTS.md, OWNER_OPERATING_GUIDE.md, PRODUCT_SPEC.md, ARCHITECTURE.md, DECISIONS.md, TASKS.md, docs/agent-handoff.md, and the relevant Cursor rules.
Implement the following task only:
Goal: Deploy and validate the web/vercel hosted branch for LLM Council.
User-visible behavior: private Google-login-gated hosted app, persisted conversations/settings, OpenRouter key gating, and successful small council query.
Relevant files: vercel.json, api/index.py, backend/auth.py, backend/storage.py, frontend/src/App.jsx, frontend/src/api.js, frontend/src/components/LoginScreen.jsx, frontend/src/components/Sidebar.jsx.
Acceptance criteria: hosted preview Google-only login wall; unauth API 401; Google login/logout; password routes return 403; conversation persists; small council query completes.
Out of scope: multi-user auth, queue-based runs, marketing site, broad visual redesign.
Approval gates: production branch/domain, paid service setup, secrets, auth behavior.
Verification: compileall, lint, build, Vercel preview smoke, browser screenshot.
Keep the diff small. Do not print secrets.
```

## Prompt For Codex Code Review

```text
Read AGENTS.md, OWNER_OPERATING_GUIDE.md, ARCHITECTURE.md, DECISIONS.md, TASKS.md, docs/agent-handoff.md, and code_review.md.
Review the current web/vercel branch as a senior engineer. Prioritize hosted auth correctness, Redis persistence risks, serverless runtime risks, branch separation, test gaps, and secret exposure.
Return findings in this format:
Summary:
Must fix:
Should fix:
Optional:
Verification gaps:
Suggested next action:
```
