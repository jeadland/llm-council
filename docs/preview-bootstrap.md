# Preview Bootstrap

Use this when resuming paid-version testing on the managed-balance branch.

## Current Test Site

- Branch: `codex/managed-balance-test`
- Vercel project: `josh-adlands-projects/llm-council`
- Stable preview URL: `https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council`
- Latest verified preview deployment: `https://llm-council-3ycrk5wdc-josh-adlands-projects.vercel.app`
- Vercel inspect URL: `https://vercel.com/josh-adlands-projects/llm-council/3PoZfomLi1JJUv8Nu8GX8xvajw48`
- Production URL, not changed by this test: `https://joshadland.com/llm-council`

Use the stable preview URL for owner feedback. Do not send the one-off deployment URL as the primary test URL unless you have a reason to pin an exact build.

## What Was Configured

The Vercel Preview environment was configured for the paid-version test site with:

- Google OAuth env: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `OAUTH_STATE_SECRET`
- Auth env: `AUTH_REQUIRED=true`, `ADMIN_EMAIL=josh.adland@gmail.com`, `ALLOW_OWNER_GOOGLE_OAUTH=true`
- Redis/env runtime: `STORAGE_BACKEND=redis`, `RUN_EXECUTION_MODE=sync`, `KV_REST_API_URL`, `KV_REST_API_TOKEN`, `KV_REST_API_READ_ONLY_TOKEN`, `KV_URL`, `REDIS_URL`
- Billing test env names are present in Preview, but managed mode remains disabled.
- `STRIPE_PRICE_ID_1` was not present in the read-only env-name check on 2026-06-30. Current code can still test the $1 package by creating/reusing the Stripe lookup-key Price `llm_council_balance_test_1` from the existing `$10` package product.

Do not print or commit env values. Some sensitive Vercel Production values list by name but pull as empty values; Development had the Google OAuth values that were copied to Preview.

## Google OAuth

Google Cloud project: `josh-openclaw-493002`

OAuth client used by the preview:

- Name: `LLM Council Google OAuth Active`
- Client ID prefix: `1038064032233-ehp6pmsid2e1h96e21pam7828hclq14d`

Authorized redirect URI added for the stable preview:

```text
https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council/api/auth/oauth/google/callback
```

The OAuth flow must start and callback on the same host because the state check uses an HttpOnly cookie. For preview testing, use the stable alias above rather than a one-off `llm-council-<hash>-josh-adlands-projects.vercel.app` URL.

## Verification Already Completed

- Preview deploy with the onboarding and Stripe-readiness fixes completed as Vercel deployment `dpl_7PYGmgNpr7775116mC9fPj8N6tNG`.
- Stable alias points to that deployment.
- `/llm-council/api/auth/me` returns `configured:true`, `authenticated:false` before login.
- `/llm-council/api/health` returns OK with `managed_mode_enabled:false`.
- `/llm-council/api/auth/oauth/google/start` redirects to Google with the stable preview callback.
- Google OAuth callback was accepted after adding the preview redirect URI.
- In-app browser loaded the app signed in as owner `josh.adland@gmail.com`.
- On 2026-06-30, `MANAGED_MODE_ENABLED` was restored to `false` in the Preview environment. The stable alias was then updated to `dpl_3BpqGngAtdRQ7yERtXrksY7idU7n`, which includes the onboarding UI polish.
- In-app browser verification on the stable alias showed a signed-in test account, BYOK as the `START HERE` path, `LLM Council Balance` as `PRIVATE BETA`, and the disabled `Add balance` button with `LLM Council Balance is not available yet.`
- On 2026-06-30, managed mode was temporarily enabled on Preview deployment `dpl_GX7PbQ2HkqC1UbWjBVK1abCKiQqh` for a Stripe sandbox checkout test. The app created a Stripe Checkout Session, the owner completed the sandbox payment, Vercel logs showed `POST /llm-council/api/stripe/webhook` returning `200`, and the visible app balance increased by $10.
- After that successful test, `MANAGED_MODE_ENABLED` was restored to `false` and the stable alias was redeployed as `dpl_7PYGmgNpr7775116mC9fPj8N6tNG`.
- On 2026-06-30, a later read-only health check still reported `managed_mode_enabled:false`, `billing_database_configured:true`, `stripe_configured:true`, and `openrouter_management_configured:true`. Vercel env names included `STRIPE_PRICE_ID_5`, `STRIPE_PRICE_ID_10`, and `STRIPE_PRICE_ID_20`, but not `STRIPE_PRICE_ID_1`.
- On 2026-06-30, an approved $1 checkout smoke temporarily enabled managed mode on Preview deployment `dpl_GCjj4Vft7NgG2vUhhbYAWdFx6MS6`. The owner completed Stripe Checkout and reported the visible app balance increased by $1. The post-checkout OpenRouter-key modal was traced to the app requesting the `integrations` settings section after `?billing=success`; this was fixed to return to the Balance card. Managed mode was restored to false and the stable alias now points to safe deployment `dpl_F1id6Au3m8JqRcCRHv5QvuQrD2EE`.
- On 2026-06-30, an owner-approved real managed paid-run smoke temporarily enabled managed mode on Preview deployment `dpl_GXV2s65ZfYHaQdiiinSQ4gxRN8FB`. The signed-in Preview account `qbot1106@gmail.com` ran a `Balanced Council` prompt with max charge `$0.90`. The UI showed `ACTUAL ANSWER COST $0.05`, `9 calls`, `8,491 tokens`, and managed receipt `Actual cost $0.07 - Remaining balance $20.93`. Vercel logs showed `POST /llm-council/api/council/estimate`, `POST /llm-council/api/conversations/.../runs`, `GET /llm-council/api/conversations/.../runs/...`, and `GET /llm-council/api/billing/status` returning `200`. Managed mode was restored to false and the stable alias now points to safe deployment `dpl_FpCmRL6h2utgEFceG1jcp6nAY6uM`; `/llm-council/api/health` reports `managed_mode_enabled:false`.
- On 2026-06-30, the managed-run cost display mismatch was fixed on Preview deployment `dpl_7L1Xa53oQpVRLkLpqGmJHp6i2MDa`. The same smoke run now shows `ACTUAL ANSWER COST $0.07`, `LLM Council Balance - 9 calls - 8,491 tokens`, and receipt `Actual cost $0.07 - Remaining balance $20.93`; the old raw top-line `$0.05` is no longer visible. The stable alias points to `dpl_7L1Xa53oQpVRLkLpqGmJHp6i2MDa`; `/llm-council/api/health` reports `managed_mode_enabled:false`.
- On 2026-06-30, browser comment cleanup was deployed to Preview `dpl_3PoZfomLi1JJUv8Nu8GX8xvajw48`. The selected-provider stack now renders inline provider marks instead of initials, the standalone managed receipt block was removed, and the Stage 3 cost metadata now includes remaining balance. The stable alias points to this deployment; `/llm-council/api/health` reports `managed_mode_enabled:false`.

## Safe Verification Commands

Use `vercel curl` for protected previews. Plain `curl` may stop at Vercel Deployment Protection.

```bash
npx --yes vercel@latest inspect https://llm-council-jeadland-josh-adlands-projects.vercel.app
npx --yes vercel@latest curl /llm-council/api/auth/me --deployment https://llm-council-jeadland-josh-adlands-projects.vercel.app
npx --yes vercel@latest curl /llm-council/api/health --deployment https://llm-council-jeadland-josh-adlands-projects.vercel.app
npx --yes vercel@latest curl /llm-council/api/auth/oauth/google/start --deployment https://llm-council-jeadland-josh-adlands-projects.vercel.app -- --include --max-redirs 0
```

Expected `auth/me` before login includes:

```json
{"authenticated":false,"auth_required":true,"email":null,"name":null,"role":null,"configured":true}
```

Expected health includes:

```json
{"ok":true,"app":"llm-council","managed_mode_enabled":false}
```

## Guardrails

- Do not promote this branch to production without explicit owner approval.
- Do not change `joshadland.com` routing from this branch.
- Do not enable `MANAGED_MODE_ENABLED=true` again without explicit owner approval for the target environment, spend cap, and restore plan.
- Do not replace production Google OAuth redirect URIs when adding preview callbacks.
- Keep `main` as the local/OpenClaw branch and `web/vercel` as the hosted production branch.
