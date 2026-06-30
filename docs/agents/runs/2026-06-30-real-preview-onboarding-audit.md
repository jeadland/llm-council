# Agent Loop Run Report

Date: 2026-06-30
Project: LLM Council
Loop: Paid Onboarding Readiness Loop
Run limit: real preview deploy plus signed-in desktop verification

## Goal

Verify the paid-site onboarding polish on the actual Vercel Preview stable alias after the owner provided an authenticated in-app browser session.

## Bounds

- Max time: one live preview verification pass.
- Max artifacts: one report and one audit note.
- Forbidden actions: no email auth, no production deploy, no Stripe checkout, no paid model run, no secret inspection, no data deletion.
- Approval gates: stop before production promotion, managed-mode enablement, checkout, or paid runs.

## Work Completed

- Deployed the current onboarding UI patch to Vercel Preview.
- Confirmed the stable preview alias points to deployment `dpl_3BpqGngAtdRQ7yERtXrksY7idU7n`.
- Verified `/llm-council/api/health` reports `managed_mode_enabled:false`.
- Verified `/llm-council/api/auth/me` reports auth configured and unauthenticated before login.
- Used the owner-provided in-app browser session to verify the signed-in onboarding UI on the stable preview alias.

## Evidence

- Stable preview URL: `https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council`.
- Exact deployment URL: `https://llm-council-qqalkzzks-josh-adlands-projects.vercel.app`.
- Vercel inspect deployment: `dpl_3BpqGngAtdRQ7yERtXrksY7idU7n`.
- Health check returned `managed_mode_enabled:false`, with billing database, Stripe, and OpenRouter management configured.
- In-app browser title: `LLM Council`.
- Signed-in email visible in the app: `qbot1106@gmail.com`.
- Desktop viewport metrics: `1280x720`, document width `1280`, body width `1280`, horizontal overflow `false`.
- Visible onboarding text included:
  - `Choose how you want to run LLM Council`
  - `START HERE`
  - `Use your OpenRouter key`
  - `PRIVATE BETA`
  - `Add LLM Council Balance`
  - `Current balance`
  - `$9.99`
  - `LLM Council Balance is not available yet.`
- Visible onboarding actions included an enabled `Add OpenRouter key` button and a disabled `Add balance` button.
- Viewport screenshot showed the setup panel fully visible on desktop with no clipped controls.

## Artifacts

- `frontend/src/components/ChatInterface.jsx`
- `frontend/src/components/Sidebar.jsx`
- `docs/preview-bootstrap.md`
- `docs/agent-handoff.md`
- `docs/agents/CONTROL_PLANE.md`
- This report.
- `docs/agents/runs/2026-06-30-real-preview-onboarding-audit-review.md`

## Approval Gates Reached

- Preview deployment was performed.
- Production was not touched.
- Managed mode remained disabled.
- Checkout and paid runs were not exercised.

## Blockers

- The in-app browser bridge did not expose mobile viewport resizing for the authenticated tab, so signed-in mobile preview verification remains open.
- Stripe test-mode balance top-up and first managed paid-run audits remain blocked pending explicit approval and test-mode readiness.

## Control Plane Updates

- Marked preview browser access done.
- Moved the preview onboarding audit to `needs-review`.
- Added a separate signed-in mobile preview walkthrough item.

## Learnings

- The provided in-app browser session is sufficient for live signed-in desktop verification behind Vercel Deployment Protection.
- Google-only auth does not block agent review when the owner can provide an authenticated browser session.
- Email login should remain parked unless beta-user evidence shows Google-only login blocks activation.

## UX Findings

| Severity | Screen | Evidence | User impact | Suggested fix |
|---|---|---|---|---|
| P1 verified | Post-login setup | Stable preview shows `START HERE` on the OpenRouter path | Users are directed to the usable onboarding path first | Keep BYOK first while managed mode is disabled |
| P1 verified | Post-login setup | Stable preview shows `PRIVATE BETA`, disabled `Add balance`, and unavailable copy for LLM Council Balance | The unavailable paid-balance path reads intentional instead of broken | Recheck when managed mode is intentionally enabled |
| P2 open | Mobile preview | Controlled local mobile evidence exists, but signed-in mobile preview was not captured | Small-screen protected preview could still hide a blemish | Run a signed-in mobile preview pass before initial marketing |

## Promotion Candidates

- None.
