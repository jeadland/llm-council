# One Dollar Payment Readiness Run

Date: 2026-06-30
Loop: Paid Onboarding Readiness Loop
Status: needs-review

## Goal

Prepare the managed-balance payment path for a small $1 test top-up while improving the Settings balance surface and preserving BYOK/OpenRouter access.

## Bounds

- Code and local verification only.
- Read-only Vercel health/env-name checks were allowed.
- No production deploy, DNS change, live Stripe charge, Stripe account mutation, Vercel env mutation, managed-mode enablement, or paid managed model run.
- The owner approved the actual $1 Preview checkout smoke.
- Production deployment remained out of scope.

## Work Completed

- Added `test_1` as a first-class $1 LLM Council Balance package behind `STRIPE_PRICE_ID_1`.
- Centralized top-up package definitions so checkout amount validation, Stripe Price lookup, and billing status metadata share the same package source.
- Added package `configured` and `status_label` metadata to `/api/billing/status`.
- Updated the Add Balance modal so unconfigured packages are visible but disabled with a `Needs price` label.
- Moved LLM Council Balance into a prominent Settings card above OpenRouter model access.
- Kept Add Balance disabled unless managed mode is enabled, Stripe is configured, billing status is healthy, and at least one package has a configured Stripe Price.
- Updated product/deployment docs to include the temporary `$1` test top-up and `STRIPE_PRICE_ID_1`.
- Added server-side on-demand `$1` Stripe Price resolution: if `STRIPE_PRICE_ID_1` is absent, checkout searches for `llm_council_balance_test_1` and otherwise creates a `$1` Price from the existing `$10` package product.
- Fixed the post-checkout return path so `?billing=success` opens the Balance card instead of the OpenRouter key dialog.
- Temporarily enabled Preview managed mode for the approved checkout smoke, then restored Preview managed mode to `false` and redeployed the safe alias.

## Evidence

- `uv run python -m unittest discover tests -p 'test_billing.py'` passed after the on-demand resolver: 21 tests.
- `uv run python -m unittest discover tests` passed: 65 tests.
- `uv run python -m compileall backend api` passed.
- `npm --prefix frontend run lint` passed with the existing two `frontend/src/App.jsx` hook dependency warnings.
- `npm --prefix frontend run build` passed.
- `git diff --check` passed.
- No-spend OpenRouter catalog smoke passed through the app code path: fetched 338 models, and `ultra-premium-frontier`, `premium-balanced`, `efficient-daily`, and `open-source-open-weights` resolved as ready.
- Read-only Preview health check against `https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council/api/health` returned `managed_mode_enabled:false`, `billing_database_configured:true`, `stripe_configured:true`, and `openrouter_management_configured:true`.
- Read-only Vercel env-name inventory showed `STRIPE_PRICE_ID_5`, `STRIPE_PRICE_ID_10`, and `STRIPE_PRICE_ID_20` are present in Preview/Production, but `STRIPE_PRICE_ID_1` is not present.
- Approved checkout smoke: Preview deployment `dpl_GCjj4Vft7NgG2vUhhbYAWdFx6MS6` temporarily ran with `managed_mode_enabled:true`; the owner completed the Stripe Checkout and reported the visible app balance increased by $1.
- Vercel CLI historical logs did not return checkout/webhook lines during the polling window; the visible balance increase is still app-level proof that the signed webhook fulfillment credited the ledger.
- Safe restore: Preview env was set back to `MANAGED_MODE_ENABLED=false`; stable alias now points to `dpl_F1id6Au3m8JqRcCRHv5QvuQrD2EE`; `/llm-council/api/health` returns `managed_mode_enabled:false`.

## Artifacts Changed

- `backend/billing/profiles.py`
- `backend/billing/stripe_service.py`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/Sidebar.css`
- `tests/test_billing.py`
- `PRODUCT_SPEC.md`
- `ARCHITECTURE.md`
- `TASKS.md`
- `JOSH_SITE_DEPLOYMENT.md`

## Approval Gates Reached

- Stripe Price creation for the $1 package.
- Adding `STRIPE_PRICE_ID_1` to Vercel Preview and Production.
- Enabling `MANAGED_MODE_ENABLED=true` in Preview or Production.
- Running an actual Stripe checkout, even for $1.
- Running a managed paid council prompt that spends provider credits.
- Production deployment or Josh-site routing changes.

## Blockers And Open Questions

- Decide whether to keep the on-demand `$1` Price resolver or replace it with an explicit `STRIPE_PRICE_ID_1` before production launch.
- Decide whether `$1` should exist only in Preview/test mode or also temporarily in Production for launch smoke.
- The first managed paid-run readiness audit still needs explicit owner approval for spend/cost cap.

## Reusable Learnings

- Keep test top-up packages visible but disabled when their Stripe Price is missing; hiding them makes launch readiness harder to diagnose.
- The billing status endpoint is the right UI contract for package readiness because it already reflects managed mode, Stripe setup, balance, and BYOK state.
