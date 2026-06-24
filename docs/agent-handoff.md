# Agent Handoff

Use this file to transfer context between ChatGPT, Codex, Cursor, GitHub, and human review.

## Current State Summary

```text
The app is LLM Council, a React + FastAPI multi-model deliberation app.
The active branch is web/vercel for hosted deployment work.
main remains the local/OpenClaw/LAN branch.
The current implementation includes Vercel config, Redis-backed storage, private auth, BYOK signup, password change, and sync run mode.
The next task is Vercel preview deployment and hosted smoke verification.
```

## Active Task

Task name: Deploy and validate Vercel web branch

Goal: Push/deploy `web/vercel`, configure env vars, and verify hosted private use.

Expected behavior:

- Unauthenticated hosted visitors see sign-in/create-account options.
- New users can create an account with optional name, required email, password, and required OpenRouter API key.
- Authenticated owner and BYOK users can use the council.
- Password can be changed after launch.
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
- `frontend/src/App.jsx`
- `frontend/src/api.js`
- `frontend/src/components/LoginScreen.jsx`
- `frontend/src/components/Sidebar.jsx`
- `tests/test_byok_onboarding.py`
- `README.md`

## What Has Been Tried

- Created `web/vercel` from `main`.
- Implemented Vercel wiring.
- Implemented Redis storage with JSON fallback.
- Implemented private auth and password change.
- Implemented no-invite BYOK signup with OpenRouter tutorial and account-created confirmation.
- Implemented per-user conversation/settings/run/integration scoping and non-owner server-key fallback protection.
- Verified local auth smoke using a temporary local password.
- Verified compile, lint, and build.

## Known Constraints

- Do not commit secrets.
- Vercel hosted mode requires Upstash Redis and OpenRouter env vars.
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

- [ ] User-facing behavior: sign-in/create-account wall appears on hosted preview.
- [ ] Data or persistence behavior: conversation/settings survive reload and redeploy and remain user-scoped.
- [ ] Loading, empty, error, and permission states: unauthenticated APIs return `401`; bad login shows clear error.
- [ ] BYOK onboarding: signup validates a user OpenRouter key, shows account-created confirmation, and masks the key afterward.
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
local curl auth smoke with AUTH_REQUIRED=true and temporary password
```

Results:

```text
compileall passed
unittest passed
frontend build passed
frontend lint passed with 2 hook dependency warnings
auth smoke: unauth=401, login=200, me=200, change=200, old_login=401, new_login=200
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
User-visible behavior: private login-gated hosted app, password change, persisted conversations/settings, and successful small council query.
Relevant files: vercel.json, api/index.py, backend/auth.py, backend/storage.py, frontend/src/App.jsx, frontend/src/api.js, frontend/src/components/LoginScreen.jsx, frontend/src/components/Sidebar.jsx.
Acceptance criteria: hosted preview login wall; unauth API 401; login/logout/password change; old password rejected after change; conversation persists; small council query completes.
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
