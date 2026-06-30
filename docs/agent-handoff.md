# Agent Handoff

Use this file to transfer context between ChatGPT, Codex, Cursor, GitHub, and human review.

## Current State Summary

```text
The app is LLM Council, a React + FastAPI multi-model deliberation app.
The active branch for this task is codex/managed-balance-test, branched from web/vercel.
main remains the local/OpenClaw/LAN branch.
The current implementation includes Vercel config, Redis-backed storage, Google-only private auth, BYOK OpenRouter key setup after login, sync run mode, and managed-balance beta code.
The managed-balance test site is deployed on a stable Vercel preview alias. Read `docs/preview-bootstrap.md` before re-debugging preview auth, URLs, or Vercel/Google setup.
The hosted/infrastructure smoke path has now passed on Preview: Postgres billing storage, Stripe sandbox checkout/webhook, a real managed OpenRouter run, managed receipt, balance decrement, and safe restore with MANAGED_MODE_ENABLED=false.
The managed run result UI now shows the LLM Council Balance charge as the user-facing actual answer cost; raw OpenRouter cost remains backend/internal detail.
The branch supports a temporary `$1` top-up package. If `STRIPE_PRICE_ID_1` is absent, the server can create/reuse a Stripe test Price with lookup key `llm_council_balance_test_1` from the existing `$10` package product.
```

## Active Task

Task name: Validate managed balance private beta

Goal: Validate Stripe-backed LLM Council Balance on the managed-balance feature branch while keeping managed runs disabled except for explicit, bounded Preview tests.

Expected behavior:

- Unauthenticated hosted visitors see only the Google sign-in button.
- New users create/sign into an account with Google, then add their own OpenRouter key through API & Integrations before running council requests.
- Authenticated owner and BYOK users can use the council.
- Managed beta users can add LLM Council Balance, choose curated profiles, see pre-run max-charge estimates, and receive receipts once enabled.
- A temporary `$1` test package is available when `STRIPE_PRICE_ID_1` is configured.
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
- Deployed the paid-version branch to a stable Vercel Preview alias and fixed Preview Google OAuth by adding Preview env plus the Google Cloud redirect URI. Details are in `docs/preview-bootstrap.md`.
- Completed one real managed paid-run smoke on Preview under a $1 owner-approved cap. The run charged `$0.07` app balance, showed a receipt with `$20.93` remaining, and the stable alias was restored to `MANAGED_MODE_ENABLED=false`.
- Fixed the managed-run cost display mismatch so Stage 3 `Actual answer cost` uses the managed receipt amount, matching the LLM Council Balance receipt.

## Known Constraints

- Do not commit secrets.
- Vercel hosted mode requires Upstash Redis and OpenRouter env vars.
- Managed billing hosted mode requires Supabase/Postgres `DATABASE_URL`, Stripe test keys/webhook secret/price IDs, `OPENROUTER_MANAGEMENT_KEY`, and `KEY_ENCRYPTION_SECRET`.
- The temporary $1 test top-up additionally requires `STRIPE_PRICE_ID_1`.
- `MANAGED_MODE_ENABLED` defaults off and should remain off except during explicit, bounded Preview tests or a separately approved production rollout.
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
Stable test URL: https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council
Vercel deployment dpl_7PYGmgNpr7775116mC9fPj8N6tNG is Ready.
/llm-council/api/auth/me returns configured:true before login.
/llm-council/api/health returns ok with managed_mode_enabled:false.
Google OAuth sign-in works on the stable preview alias after adding the callback in Google Cloud.
In-app browser loaded the app signed in as owner josh.adland@gmail.com.
On 2026-06-30, the Preview `MANAGED_MODE_ENABLED` flag was reset to false. The stable alias now serves the onboarding UI polish deployment, with BYOK featured first and disabled LLM Council Balance marked as private beta.
In-app browser verification on the stable alias loaded a signed-in test account (`qbot1106@gmail.com`) and showed no horizontal overflow at a 1280px desktop viewport.
On 2026-06-30, Stripe-readiness fixes were deployed to Preview. Managed mode was temporarily enabled on `dpl_GX7PbQ2HkqC1UbWjBVK1abCKiQqh`; signed-in Preview created a Stripe Checkout Session for the recommended $10 top-up, the owner completed the sandbox payment, Vercel logged `POST /llm-council/api/stripe/webhook` with status `200`, and the visible app balance increased by $10. `MANAGED_MODE_ENABLED` was restored to false and the stable alias now points to safe redeploy `dpl_7PYGmgNpr7775116mC9fPj8N6tNG`.
On 2026-06-30, local code was updated to support a temporary `$1` top-up (`test_1`) and a more prominent Settings balance card above OpenRouter. Verification passed locally. A later approved Preview checkout smoke temporarily enabled managed mode on deployment `dpl_GCjj4Vft7NgG2vUhhbYAWdFx6MS6`; the owner completed Stripe Checkout and reported the visible balance increased by $1. Preview managed mode was restored to false and the stable alias now points to safe deployment `dpl_F1id6Au3m8JqRcCRHv5QvuQrD2EE`.
On 2026-06-30, an owner-approved real managed paid-run smoke temporarily enabled Preview managed mode on `dpl_GXV2s65ZfYHaQdiiinSQ4gxRN8FB`. The signed-in Preview account `qbot1106@gmail.com` ran a `Balanced Council` prompt with max charge `$0.90`; the UI showed `ACTUAL ANSWER COST $0.05`, `9 calls`, `8,491 tokens`, and managed receipt `Actual cost $0.07 · Remaining balance $20.93`. Vercel logs showed estimate, run, run snapshot, and billing status requests returning `200`. Preview managed mode was restored to false and the stable alias now points to safe deployment `dpl_FpCmRL6h2utgEFceG1jcp6nAY6uM`.
On 2026-06-30, the managed-run cost display mismatch was fixed and deployed to Preview `dpl_7L1Xa53oQpVRLkLpqGmJHp6i2MDa`. The same smoke run now shows `ACTUAL ANSWER COST $0.07`, `LLM Council Balance · 9 calls · 8,491 tokens`, and receipt `Actual cost $0.07 · Remaining balance $20.93`. The old raw top-line `$0.05` is no longer visible. Stable Preview health reports `managed_mode_enabled:false`.
On 2026-06-30, browser comment cleanup was deployed to Preview `dpl_3PoZfomLi1JJUv8Nu8GX8xvajw48`. The selected-provider stack now uses inline provider marks instead of initials, the duplicate managed receipt block below the answer was removed, and the Stage 3 cost metadata now includes `Remaining balance $20.93`. Stable Preview health still reports `managed_mode_enabled:false`.
```

## Resume Protocol

If this work resumes after chat reset, context loss, or usage-limit interruption:

1. Read `AGENTS.md`, `OWNER_OPERATING_GUIDE.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TASKS.md`, and this file.
2. Read `docs/preview-bootstrap.md` before touching Vercel Preview, Google OAuth, or the paid-version test URL.
3. For UI or brand work, also read `docs/brand/brand-guidelines.md`.
4. Confirm current branch with `git status --short --branch`.
5. Continue from the first unchecked acceptance criterion or verification item.
6. Do not broaden scope without updating `TASKS.md` and getting owner approval if an approval gate applies.

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
