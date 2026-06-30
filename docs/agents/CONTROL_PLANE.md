# Agent Control Plane

Project: LLM Council
Project id: llm-council

## Status Model

- `backlog`: Useful idea, not ready for an agent.
- `agent-ready`: Bounded, clear, and safe to run.
- `in-progress`: Currently being worked.
- `needs-human-input`: Missing decision, account access, data, or approval.
- `needs-review`: Artifact is ready for human review.
- `done`: Completed and verified.
- `blocked`: Cannot progress without external change.

## Backlog

| Item | Loop | Status | Owner | Evidence Needed | Notes |
|---|---|---|---|---|---|
| Preview onboarding audit with managed mode disabled | Paid Onboarding Readiness Loop | needs-review | Agent | Desktop and mobile evidence for login, post-login setup, disabled balance state, BYOK setup, empty/error states, and safe API status checks | Real desktop preview evidence is complete; controlled mobile evidence is complete; signed-in mobile preview remains a follow-up because the in-app browser bridge did not expose viewport resizing. Reports: `docs/agents/runs/2026-06-30-real-preview-onboarding-audit.md`, `docs/agents/runs/2026-06-30-disabled-onboarding-local-ui-audit.md`. |
| Confirm intended preview state for onboarding audit | Paid Onboarding Readiness Loop | done | Agent | Stable preview `/llm-council/api/health` returns `managed_mode_enabled:false` | Preview env flag was reset to false and the stable alias was deployed as `dpl_7PYGmgNpr7775116mC9fPj8N6tNG`. |
| Disabled-mode local UI polish audit | Paid Onboarding Readiness Loop | done | Agent | Controlled desktop/mobile browser screenshots and DOM metrics for no-key, no-managed-balance onboarding | Report: `docs/agents/runs/2026-06-30-disabled-onboarding-local-ui-audit.md`; audit: `docs/agents/runs/2026-06-30-disabled-onboarding-local-ui-audit-review.md`. |
| Provide browser access for preview UI audit | Paid Onboarding Readiness Loop | done | Human | Owner-completed Vercel/Google login in the test browser, existing authenticated app session, or approved preview access approach | Owner provided the stable preview in the in-app browser with an authenticated session. Do not add email auth solely to support agent testing. |
| Signed-in mobile preview walkthrough | Paid Onboarding Readiness Loop | agent-ready | Agent | Mobile viewport screenshot and DOM metrics against the stable preview with an authenticated session | Requires a browser path that can resize/emulate mobile while preserving auth, or a fresh authenticated mobile session. |
| Stripe app-side release blocker fix | Paid Onboarding Readiness Loop | needs-review | Agent | Tests/build pass; Preview deploy contains webhook retry/dedup guards, strict checkout validation, visible billing-status errors, and managed-balance mode control | Report: `docs/agents/runs/2026-06-30-stripe-preview-readiness-run.md`. |
| $1 top-up and balance settings readiness | Paid Onboarding Readiness Loop | needs-review | Agent | Tests/build pass; billing status exposes `$1` package metadata; Settings shows balance above OpenRouter; approved Stripe Checkout smoke increased visible balance by $1; managed mode restored to false | Report: `docs/agents/runs/2026-06-30-one-dollar-payment-readiness-run.md`. |
| Stripe test-mode balance top-up audit | Paid Onboarding Readiness Loop | done | Agent | Completed Stripe sandbox payment, webhook delivery to `/llm-council/api/stripe/webhook`, updated balance, ledger/status proof | Owner completed sandbox Checkout. Vercel logged checkout `200` and webhook `200`; visible app balance increased by $10. Managed mode is back off. Report: `docs/agents/runs/2026-06-30-stripe-preview-readiness-run.md`. |
| First managed paid-run readiness audit | Paid Onboarding Readiness Loop | done | Agent | Real managed run under an owner-approved $1 cap, with estimate, reservation, run completion, receipt, balance decrement, and safe restore evidence | Preview deployment `dpl_GXV2s65ZfYHaQdiiinSQ4gxRN8FB` ran one managed prompt. UI showed max charge `$0.90`, actual app cost `$0.07`, and remaining balance `$20.93`. Stable alias was restored to safe deployment `dpl_FpCmRL6h2utgEFceG1jcp6nAY6uM` with `managed_mode_enabled:false`. Report: `docs/agents/runs/2026-06-30-first-managed-paid-run-readiness.md`. |
| Managed cost display alignment | Paid Onboarding Readiness Loop | done | Agent | Final-answer actual cost and managed receipt show the same LLM Council Balance charge on stable Preview | Preview deployment `dpl_7L1Xa53oQpVRLkLpqGmJHp6i2MDa` shows `ACTUAL ANSWER COST $0.07` and receipt `Actual cost $0.07 - Remaining balance $20.93`; `/llm-council/api/health` reports `managed_mode_enabled:false`. Report: `docs/agents/runs/2026-06-30-managed-cost-display-alignment.md`. |
| Email login exploration | Paid Onboarding Readiness Loop | backlog | Human | Evidence from beta users that Google-only login blocks activation | Keep parked; do not add email auth just to help agents test. |

## Active Run

- Loop:
- Started:
- Bound:
- Approval gates:

## Needs Human Input

- Provide or approve a browser path for a signed-in mobile preview walkthrough.

## Needs Review

- Review `docs/agents/runs/2026-06-30-preview-onboarding-audit.md`.
- Review `docs/agents/runs/2026-06-30-preview-onboarding-audit-review.md`.
- Review `docs/agents/runs/2026-06-30-disabled-onboarding-local-ui-audit.md`.
- Review `docs/agents/runs/2026-06-30-disabled-onboarding-local-ui-audit-review.md`.
- Review `docs/agents/runs/2026-06-30-real-preview-onboarding-audit.md`.
- Review `docs/agents/runs/2026-06-30-real-preview-onboarding-audit-review.md`.
- Review `docs/agents/runs/2026-06-30-stripe-preview-readiness-run.md`.
- Review `docs/agents/runs/2026-06-30-one-dollar-payment-readiness-run.md`.
- Review `docs/agents/runs/2026-06-30-first-managed-paid-run-readiness.md`.
- Review `docs/agents/runs/2026-06-30-managed-cost-display-alignment.md`.

## Done

- Disabled-mode local UI polish audit.
- Real desktop preview onboarding audit.
- Stripe test-mode balance top-up audit.
- First managed paid-run readiness audit.
- Managed cost display alignment.

## Promotion Candidates

Use `[PROMOTE]` for reusable improvements that may belong in the Agent Team hub.
