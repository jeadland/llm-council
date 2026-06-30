# Managed Cost Display Alignment

Date: 2026-06-30
Project: LLM Council
Loop: Paid Onboarding Readiness Loop
Status: done

## Goal

Fix the managed-run result UI so the user-facing actual answer cost matches the LLM Council Balance charge rather than the raw OpenRouter provider cost.

## Bounds

- Code and Preview verification only.
- No new managed run, Stripe payment, production deploy, DNS change, routing change, credential change, or `MANAGED_MODE_ENABLED` change.
- Preserve backend ledger semantics: raw provider cost remains stored internally; user-facing managed cost should use `billing_receipt.actual_app_cost_usd`.

## Work Completed

- Updated `Stage3` to accept a managed billing receipt alongside the OpenRouter cost summary.
- When a managed receipt exists, the Stage 3 top-line `Actual answer cost` now uses `actual_app_cost_usd`.
- The cost metadata line labels managed runs as `LLM Council Balance`.
- The expanded cost breakdown scales priced call and stage costs to the app-billed total so it does not contradict the receipt.
- Non-managed and older runs continue to use the raw tracked `cost_summary` behavior or the existing unavailable state.
- Passed the managed receipt from `ChatInterface` into `Stage3`.
- Deployed the fix to Preview deployment `dpl_7L1Xa53oQpVRLkLpqGmJHp6i2MDa`.

## Evidence

- Branch: `codex/managed-balance-test`.
- Stable Preview alias: `https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council`.
- Stable alias inspect points to `dpl_7L1Xa53oQpVRLkLpqGmJHp6i2MDa`, Ready.
- `/llm-council/api/health` returned `managed_mode_enabled:false`.
- In-app browser, authenticated as `qbot1106@gmail.com`, opened the prior managed smoke run.
- Main result now shows:
  - `ACTUAL ANSWER COST`
  - `$0.07`
  - `LLM Council Balance - 9 calls - 8,491 tokens`
- Receipt still shows `Actual cost $0.07 - Remaining balance $20.93`.
- Browser check confirmed the old raw top-line `ACTUAL ANSWER COST $0.05` is no longer present.
- Expanded breakdown stayed under the app-billed total and did not reintroduce `$0.05` as the top-line actual cost.

## Verification

- `npm --prefix frontend run lint` passed with the existing two `frontend/src/App.jsx` hook dependency warnings.
- `npm --prefix frontend run build` passed.
- `git diff --check` passed.
- Vercel Preview deploy passed.
- Stable Preview health check passed with managed mode disabled.
- Browser verification against the stable Preview alias passed.

## Artifacts Changed

- `frontend/src/components/Stage3.jsx`
- `frontend/src/components/ChatInterface.jsx`
- `docs/agents/runs/2026-06-30-managed-cost-display-alignment.md`
- `docs/agents/CONTROL_PLANE.md`
- `docs/agent-handoff.md`
- `docs/preview-bootstrap.md`
- `TASKS.md`
- `JOSH_SITE_DEPLOYMENT.md`

## Approval Gates Reached

- Preview deploy only. No production deploy.
- No new paid run or external paid action.
- No Vercel env, Stripe, OpenRouter, Redis, Postgres, Google OAuth, auth, or production routing change.

## Blockers And Open Questions

- Production deployment remains gated.
- Decide later whether managed users should see any provider-cost language in admin-only finance views; this fix only changes the end-user answer UI.

## Control Plane Updates

- Added and completed `Managed cost display alignment`.

## Learnings

- For managed runs, `cost_summary.total_usd` is provider/raw cost and should not be the primary user-facing amount.
- `billing_receipt.actual_app_cost_usd` is the canonical user-facing completed-run charge.

## UX Findings

| Severity | Screen | Evidence | User impact | Suggested fix |
|---|---|---|---|---|
| High | Final answer cost card | Before the fix, top-line `Actual answer cost` showed `$0.05` while the receipt showed `$0.07`. | Users could infer the service fee as an inconsistency instead of seeing one app charge. | Fixed by using managed receipt cost as the user-facing cost. |

## Promotion Candidates

- None yet.
