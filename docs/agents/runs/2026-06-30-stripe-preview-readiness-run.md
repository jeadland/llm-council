# Stripe Preview Readiness Run

Date: 2026-06-30
Loop: Paid Onboarding Readiness Loop
Status: needs-review

## Goal

Move the Stripe managed-balance flow closer to release readiness by fixing app-side checkout/webhook risks, validating the Preview top-up path in Stripe sandbox mode, and restoring the stable Preview alias to the safer disabled managed-mode state afterward.

## Bounds

- Preview/test mode only.
- No production deploy, DNS change, live Stripe charge, data deletion, or production routing change.
- Managed mode could be temporarily enabled on Preview for the checkout test, then had to be restored to `false`.
- A managed paid model run was not executed because it would consume provider credits and needs a separate explicit spend approval.

## Work Completed

- Added webhook retry handling so failed or pending Stripe events can be retried instead of being permanently blocked by the first event insert.
- Added purchase deduplication by checkout session and payment intent, not only by Stripe event id.
- Tightened checkout fulfillment validation to require a paid USD payment Checkout Session.
- Added frontend handling for billing status load errors and missing checkout redirect URLs.
- Added an explicit `Use balance for runs` managed-mode control when balance is available.
- Moved the Add Balance modal into a document-body portal to avoid transformed-sidebar clipping.
- Added focused billing tests for webhook retry, duplicate checkout prevention, and unpaid Checkout rejection.

## Verification

- `uv run python -m unittest discover tests -p 'test_billing.py'` passed: 18 tests.
- `npm --prefix frontend run lint` passed with existing hook dependency warnings in `frontend/src/App.jsx`.
- `npm --prefix frontend run build` passed.
- `uv run python -m compileall backend api` passed.
- Managed-mode Preview deployment: `dpl_GX7PbQ2HkqC1UbWjBVK1abCKiQqh`.
- Health during test reported `managed_mode_enabled:true`, `billing_database_configured:true`, `stripe_configured:true`, and `openrouter_management_configured:true`.
- Signed-in Preview showed LLM Council Balance, available balance, enabled Add Balance, and a $10 recommended top-up modal.
- Vercel logs showed `POST /llm-council/api/billing/checkout` returned `200` and included a Stripe API `checkout/sessions` `200`.
- Owner completed the Stripe sandbox payment in the browser.
- Vercel logs showed `POST /llm-council/api/stripe/webhook` returned `200`.
- Owner reported the visible app balance increased by $10.
- Safe redeploy after test: `dpl_7PYGmgNpr7775116mC9fPj8N6tNG`.
- Stable alias health after restore reported `managed_mode_enabled:false`.

## Findings

| Item | Status | Evidence |
|---|---|---|
| Failed webhook retry can strand a paid purchase | fixed | `test_failed_checkout_webhook_can_be_retried` covers retry behavior. |
| New Stripe event id for the same checkout can double-credit | fixed | `test_same_checkout_session_under_new_event_id_does_not_double_credit` covers checkout-session dedupe. |
| Checkout fulfillment accepted incomplete payment state | fixed | `test_checkout_webhook_requires_paid_payment_session` covers unpaid rejection. |
| Billing status load failures were visually hidden | fixed | Sidebar now receives and displays `billingStatusError`; Add Balance is disabled when status is unknown. |
| User with balance lacked an explicit managed-mode switch | fixed | Sidebar now exposes a `Use balance for runs` action when balance is available but mode is BYOK. |
| Add Balance modal could clip inside transformed sidebar | fixed | Modal renders through `createPortal(document.body)`. |
| First managed paid run | not run | Requires explicit approval for provider-credit spend/cost cap. |

## Current State

The stable Preview alias is back in managed-mode-disabled state:

```text
https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council
dpl_7PYGmgNpr7775116mC9fPj8N6tNG
/llm-council/api/health -> managed_mode_enabled:false
```

The Stripe top-up path has now been proven in sandbox mode from app checkout creation through webhook fulfillment and visible balance update.

## Next Gate

Run the first managed paid-run readiness audit only after explicit owner approval for a small provider-credit spend. That audit should verify estimate, reservation, run completion, receipt, balance decrement, and remaining balance display.
