# Paid Onboarding Readiness Loop

Project: LLM Council
Project id: llm-council
Created: 2026-06-30

## Goal

Make the paid-version onboarding path feel smooth, professional, and ready for first marketing exposure while preserving the current Google-only auth model and keeping managed billing in private-beta/test mode.

## Loop Type

Primary type: activation.

Secondary type: engineering-quality.

This loop is for first-session readiness, not acquisition volume. It verifies that a user can understand the product, sign in, choose between LLM Council Balance and BYOK, avoid dead ends, and reach a first successful or clearly blocked council run with no visible UI blemishes.

## Roles

- Manager: triages onboarding-readiness items and chooses only agent-ready work from `docs/agents/CONTROL_PLANE.md`.
- Onboarding UX reviewer: walks the preview as a first-time paid beta user and records only concrete friction, unclear copy, visible UI defects, and missing states.
- Browser QA verifier: captures desktop/mobile evidence, checks overflow, focus, disabled states, modal behavior, checkout return states, and first-run visibility.
- Billing/auth risk reviewer: verifies no path enables managed spend, shared owner-key usage, production routing, or auth behavior changes without explicit owner approval.
- Implementation agent: after review approval, makes small UI/copy fixes only and runs verification.
- Auditor: reviews drift, waste, and reusable learnings after meaningful runs.

## Allowed Inputs

- Project bootstrap docs.
- Project source files and local docs.
- `docs/preview-bootstrap.md` for the stable paid-version preview URL and safe Vercel preview checks.
- Browser screenshots, DOM observations, API responses, local test output, and owner-provided feedback.
- Public sources only when directly needed to verify vendor-facing copy or checkout/auth behavior.

## Allowed Actions

- Inspect files and docs.
- Inspect the stable Vercel preview in browser or through safe `vercel curl` commands.
- Draft local artifacts under `docs/agents/`.
- Run local tests or checks.
- Record sourced research.
- Update local control-plane and run-report files.
- Recommend tightly scoped implementation tasks for owner review.

## Forbidden Actions

- Sending email or messages.
- Public posting.
- Paid ads or purchases.
- Production deploys.
- Destructive data changes.
- Scraping at scale.
- Credential changes.
- Changing hosted auth behavior, adding email login, or changing Google OAuth settings.
- Enabling `MANAGED_MODE_ENABLED=true`.
- Running Stripe live-mode payments or changing Stripe/OpenRouter/Vercel account settings.
- Changing production routing for `https://joshadland.com/llm-council`.
- Running broad live model smokes that create meaningful provider cost.

## Evidence Requirements

- Cite source URLs for external claims.
- Include command names and outcomes for local checks.
- Include screenshots or browser evidence for UI/runtime claims when relevant.
- Mark inference clearly.
- For preview checks, record the exact URL, viewport, authenticated/unauthenticated state, and whether managed mode was enabled.
- For billing checks, distinguish disabled-preview behavior, Stripe test-mode behavior, and production behavior.
- For UX findings, include the screen, expected user interpretation, actual observed behavior, severity, and suggested fix.

## Stop Conditions

- One primary artifact is ready for review.
- The time limit is reached.
- A forbidden action or approval gate is reached.
- Evidence is insufficient to continue responsibly.
- Google sign-in cannot be completed in the available browser session and no authenticated session is available.
- Preview protection, missing env, or account access blocks runtime evidence.

## Human Approval Gates

- Before public sends, posts, deploys, payments, destructive changes, or major product decisions.
- Before auth, billing, entitlement, provider, Vercel, Google OAuth, Stripe, OpenRouter, Redis/Postgres, or production routing changes.
- Before any implementation work that changes product behavior rather than documenting findings.

## First Runs

1. Preview onboarding audit with managed mode disabled: Google login wall, post-login setup choice, disabled balance state, BYOK path, empty/error states, and mobile layout.
2. Test billing path after explicit approval and test-mode setup: enabled Add Balance button, Stripe test checkout, return URL, balance update, ledger/status proof.
3. First paid-run readiness after explicit approval: select curated profile, review maximum charge, run a small prompt, verify receipt, remaining balance, and failure/cancel recovery.
