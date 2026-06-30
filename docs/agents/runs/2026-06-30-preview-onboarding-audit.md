# Agent Loop Run Report

Date: 2026-06-30
Project: LLM Council
Loop: Paid Onboarding Readiness Loop
Run limit: 90 minutes, one report, no product source edits

## Goal

Run the first bounded onboarding-readiness audit against the stable paid-version preview with managed mode expected to be disabled.

## Bounds

- Max time: 90 minutes.
- Max artifacts: one run report plus temporary screenshots outside the repo.
- Forbidden actions: no product source edits, no production deploy, no auth/billing/provider/Vercel/Stripe/OpenRouter config changes, no managed-mode enablement, no checkout, no paid model runs, no external account changes.
- Approval gates: stop before auth changes, billing changes, managed paid flows, production routing, or any action that could spend money.

## Work Completed

- Installed the project-local Agent Team scaffold before this run.
- Read the project bootstrap docs, preview bootstrap, loop spec, control plane, runbook, and guardrails.
- Ran safe Vercel preview API checks.
- Attempted desktop and mobile browser access to the stable preview URL.
- Inspected the current source for likely onboarding polish issues that need browser confirmation.
- Stopped before authenticated app/billing testing because the preview did not match the approved run assumptions.

## Evidence

- URL: `https://llm-council-jeadland-josh-adlands-projects.vercel.app/llm-council`
- Branch: local worktree on `codex/managed-balance-test`
- Vercel inspect: stable alias currently resolves to preview deployment `dpl_HXd81xEngfF3KscSATmiv6Ycnt8a`, created June 28, 2026 at 22:58:51 CDT, status Ready.
- Auth state: unauthenticated for API checks and browser screenshot attempt.
- Managed mode expectation from docs: `docs/preview-bootstrap.md` says managed mode remains disabled and expected health includes `managed_mode_enabled:false`.
- Actual health check: `npx --yes vercel@latest curl /llm-council/api/health --deployment https://llm-council-jeadland-josh-adlands-projects.vercel.app` returned `managed_mode_enabled:true`, with billing database, Stripe, and OpenRouter management reported configured.
- Auth check: `npx --yes vercel@latest curl /llm-council/api/auth/me --deployment https://llm-council-jeadland-josh-adlands-projects.vercel.app` returned `authenticated:false`, `auth_required:true`, `configured:true`.
- Billing status unauthenticated check: `/llm-council/api/billing/status` returned HTTP 401 `Not authenticated`, which is expected for unauthenticated API access.
- Browser desktop viewport `1440x1000`: navigating to the stable preview redirected to Vercel Deployment Protection login, not the LLM Council login screen. Temporary screenshot: `/tmp/llm-council-onboarding-audit-2026-06-30/desktop-login.png`.
- Browser mobile viewport `390x844`: navigating to the stable preview redirected to Vercel Deployment Protection login, not the LLM Council login screen. Temporary screenshot: `/tmp/llm-council-onboarding-audit-2026-06-30/mobile-login.png`.
- Browser layout metrics on Vercel login did not show horizontal overflow, but that is not evidence about the LLM Council app UI.

## Artifacts

- Created this run report.
- Updated `docs/agents/CONTROL_PLANE.md`.
- Temporary screenshots were saved outside the repo under `/tmp/llm-council-onboarding-audit-2026-06-30/`.

## Approval Gates Reached

- Managed billing gate: actual preview health reported `managed_mode_enabled:true`, while this run was authorized only for managed-mode-disabled onboarding audit.
- Browser access gate: Deployment Protection blocked direct browser access to the app UI, so authenticated onboarding screens could not be audited without owner/session intervention or config changes.

## Blockers

- The preview environment appears to have drifted from the documented disabled-managed-mode state. Do not run balance, checkout, or managed paid-run onboarding checks until the owner confirms whether this is intentional.
- The stable preview is protected by Vercel login in a fresh browser context. A real UI audit needs either an existing authenticated browser session, an owner-completed Vercel/Google login in the test browser, or a deliberately approved preview-access setup.

## Control Plane Updates

- Move `Preview onboarding audit with managed mode disabled` to `blocked`.
- Add a human-input item to confirm desired preview state: disabled managed mode versus intentionally enabled test mode.
- Keep Stripe and first managed paid-run audits in `needs-human-input`.

## Learnings

- The safe API path is useful before browser work: it caught managed-mode drift before any paid-flow interaction.
- Vercel Deployment Protection can block browser UX evidence even when `vercel curl` can validate API status.
- The current docs and live preview disagree on both deployment id and managed-mode status; future runs should refresh `docs/preview-bootstrap.md` after the owner decides the intended state.

## UX Findings

| Severity | Screen | Evidence | User impact | Suggested fix |
|---|---|---|---|---|
| P0 blocker | Preview environment | Health returns `managed_mode_enabled:true` while the approved run and docs expect false | The first onboarding audit cannot safely assume disabled balance behavior; paid-flow UI may be live enough to mis-test or mislead | Owner should confirm intended preview state, then either disable managed mode for this audit or explicitly approve test-mode billing audit |
| P0 blocker | Browser access | Fresh desktop/mobile browser reaches Vercel login, not LLM Council | No first-user UI evidence can be collected from a fresh browser session | Owner should provide/complete preview access for the browser session or approve an access mechanism; do not add email auth for this |
| P2 needs browser confirmation | Post-login setup choice | Source labels LLM Council Balance as Option 1 and shows `Available now` in the balance card while the button may be disabled | If managed balance is unavailable, users may interpret the disabled primary option as a broken product | In disabled mode, make BYOK primary or label balance as private beta/unavailable instead of `Available now` |
| P3 polish | Managed estimate modal | Source uses a literal `x` close button while the Add Balance modal uses `Close` | Small inconsistency in launch polish | Use the same close affordance pattern across billing modals |
| P3 polish | Login screen | Source login copy is only `Sign in to continue.` | Fine for private access, but thin for first marketing traffic | Consider one short value/subtitle line once browser review confirms the screen composition |

## Promotion Candidates

- None yet.
