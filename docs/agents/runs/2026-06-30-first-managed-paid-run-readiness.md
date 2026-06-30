# First Managed Paid-Run Readiness

Date: 2026-06-30
Project: LLM Council
Loop: Paid Onboarding Readiness Loop
Status: done

## Goal

Run one real managed-balance council prompt on the paid-version Preview site to verify the end-to-end paid plumbing before any production deployment.

## Bounds

- Max spend: $1.00 approved by the owner in chat.
- Target: Vercel Preview only.
- Max artifacts: one run report plus control-plane/bootstrap updates.
- Forbidden actions: no production deploy, DNS change, Josh-site routing change, data deletion, Stripe live-mode payment, broad model smoke, or managed mode left enabled.
- Approval gates reached: temporary Preview `MANAGED_MODE_ENABLED=true`, one managed OpenRouter council run, then restore Preview `MANAGED_MODE_ENABLED=false`.

## Work Completed

- Verified the stable Preview alias initially pointed to safe deployment `dpl_F1id6Au3m8JqRcCRHv5QvuQrD2EE` with `managed_mode_enabled:false`.
- Temporarily changed Vercel Preview `MANAGED_MODE_ENABLED` to `true`.
- Deployed Preview deployment `dpl_GXV2s65ZfYHaQdiiinSQ4gxRN8FB`.
- Verified `/llm-council/api/health` returned `managed_mode_enabled:true` with billing database, Stripe, and OpenRouter management configured.
- Used the authenticated Preview session for `qbot1106@gmail.com`.
- Confirmed Settings showed `$20.99 available`, Add Balance ready, and Balance will be used for runs.
- Sent a small managed-balance smoke prompt.
- Confirmed the pre-run modal showed `Balanced Council`, estimated `$0.21-$0.40`, maximum charge `$0.90`, and balance `$20.99`.
- Ran the council under the approved $1 cap.
- Verified the final answer, actual answer cost, token/call count, app receipt, and remaining balance in the UI.
- Restored Vercel Preview `MANAGED_MODE_ENABLED` to `false`.
- Deployed safe Preview deployment `dpl_FpCmRL6h2utgEFceG1jcp6nAY6uM`.
- Verified the stable alias now points to `dpl_FpCmRL6h2utgEFceG1jcp6nAY6uM` and `/llm-council/api/health` returns `managed_mode_enabled:false`.

## Evidence

- URL: `https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council`
- Branch: `codex/managed-balance-test`
- Auth state: signed in as `qbot1106@gmail.com`.
- Pre-run estimate: `$0.21-$0.40`.
- Maximum charge: `$0.90`.
- UI final answer evidence: `Council Verdict`, `ACTUAL ANSWER COST $0.05`, `9 calls - 8,491 tokens`.
- Managed receipt evidence: `Actual cost $0.07 - Remaining balance $20.93`.
- Final answer text included: `The managed-balance smoke test confirms that the paid council plumbing ran successfully.`
- Vercel logs showed:
  - `POST /llm-council/api/council/estimate` returned `200`.
  - `POST /llm-council/api/conversations/cb3b68dd-d764-47fd-8aa6-e31bd4ae69dd/runs` returned `200`.
  - `GET /llm-council/api/conversations/cb3b68dd-d764-47fd-8aa6-e31bd4ae69dd/runs/dfd7329b-9e26-4e93-a4f1-22e8ce28b364` returned `200`.
  - `GET /llm-council/api/billing/status` returned `200` after the run.
- Safe restore evidence:
  - Stable alias inspect: `dpl_FpCmRL6h2utgEFceG1jcp6nAY6uM`, Ready.
  - `/llm-council/api/health` returned `managed_mode_enabled:false`.
  - Settings after restore showed `$20.93 available`, private-beta disabled copy, and the run receipt remained visible.

## Artifacts Changed

- `docs/agents/runs/2026-06-30-first-managed-paid-run-readiness.md`
- `docs/agents/CONTROL_PLANE.md`
- `docs/agent-handoff.md`
- `docs/preview-bootstrap.md`
- `TASKS.md`
- `JOSH_SITE_DEPLOYMENT.md`

## Approval Gates Reached

- Owner approved real spend, ideally $1.
- Actual app charge was `$0.07`, below the approved cap.
- Preview managed mode was enabled only for the test and restored to `false`.

## Blockers And Open Questions

- Production deployment remains gated.
- Decide whether the `$1` package should remain as Preview-only/test-only before production.
- Decide whether to replace on-demand `$1` Stripe Price creation with an explicit `STRIPE_PRICE_ID_1` before launch.
- A signed-in mobile Preview walkthrough remains separate follow-up work.

## Control Plane Updates

- Marked `First managed paid-run readiness audit` as `done`.
- Removed the managed-run approval blocker from `Needs Human Input`.
- Added this report to `Needs Review`.

## Learnings

- A real managed run verifies more than the Stripe checkout smoke: estimate, reservation, managed key availability/sync, OpenRouter model calls, final ledger charge, receipt persistence, and safe disabled-mode restore.
- The Preview health endpoint is the fastest safe check for confirming the env flip before and after the run.

## UX Findings

| Severity | Screen | Evidence | User impact | Suggested fix |
|---|---|---|---|---|
| Low | Conversation list | A previous conversation titled `Reply with OK only.` remained in the sidebar during the run. | Test accounts can accumulate confusing old smoke threads. | Consider a cleanup pass for Preview test accounts before polished demos. |

## Promotion Candidates

- None yet.
