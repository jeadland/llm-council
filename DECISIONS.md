# Decisions

Use this file to record important product, architecture, design, and implementation decisions.

## Decision Log

## 2026-06-24 - Hosted auth is Google-only

Decision:

- Hosted login uses only the Google button.
- Email/password signup, login, reset, and password-change routes return `403`.
- The configured owner email can use Google login only when `ALLOW_OWNER_GOOGLE_OAUTH=true` is set.
- Google-created non-owner users must save their own OpenRouter API key before running council requests.

Rationale:

- Google gives the simplest hosted sign-in surface and removes password bootstrap/recovery complexity.
- Email remains the storage and access scope, so Google can prove identity without migrating conversations, settings, sessions, or OpenRouter keys.
- BYOK protects Josh's owner/server OpenRouter key from becoming shared model access.

Status:

- Active

## 2026-06-24 - Password auth was removed from hosted login

Decision:

- Previous owner password bootstrap, reset, and BYOK email/password signup paths are superseded by Google-only hosted login.
- Password hashes may remain in existing user records for historical compatibility, but hosted routes do not accept password auth.
- OpenRouter key setup moved from signup to API & Integrations after Google sign-in.

Rationale:

- A single auth path reduces hosted support and recovery risk.
- OpenRouter key storage remains server-side and per-user.

Status:

- Active

## 2026-06-24 - BYOK uses post-Google OpenRouter key setup

Decision:

- Hosted account creation comes from Google sign-in.
- Every non-owner account must save a valid OpenRouter API key through API & Integrations before running the council.
- Saving an OpenRouter key validates it with the non-generative OpenRouter key endpoint.
- Non-owner users never fall back to the server `OPENROUTER_API_KEY`; if their account key is missing, council runs are blocked.

Context:

- The desired onboarding path is low-friction: Google sign-in first, then key setup only when model access is needed.
- The app does not yet handle email delivery, email confirmation, managed credits, or billing.

Rationale:

- BYOK keeps model spend attached to the user's own OpenRouter account and avoids Josh-funded access.
- Requiring a key before a run is the practical gate while managed credits are intentionally deferred.

Implications:

- User conversations, settings, runs, and OpenRouter integration status must be scoped by authenticated email.
- Public deployments should still be treated as sensitive because anyone with the URL can create an account if they bring a valid key.

Status:

- Active

## 2026-06-27 - Codex MCP agent access is local-first and approval-gated

Decision:

- Codex can call LLM Council through a local MCP server backed by bearer-token protected `/api/agent/research/*` endpoints.
- MCP preparation is no-spend and creates a durable approval record with a payload hash, preset, model list, and estimated cost.
- The paid run endpoint consumes the prepared approval, verifies the cost cap and payload hash, and returns required disclosure fields.
- If the local backend is down, MCP starts only the FastAPI backend on `127.0.0.1:8001`; it does not start the React frontend.
- Hosted fallback is not part of v1.

Context:

- The owner wants LLM Council available to Codex for difficult research questions, but only with explicit approval and transparent cost reporting.
- The app already has approved presets, owner-scoped provider access, and run-level cost-summary plumbing.

Rationale:

- A local-first MCP path avoids production routing, hosted auth, and serverless timeout risk while still making the tool generally available to Codex on this Mac.
- Splitting prepare from run lets Codex show the selected preset and estimate before any paid model calls.
- Requiring the tool result to include disclosure metadata makes transparency enforceable rather than relying on convention.

Alternatives considered:

- Directly importing council code from MCP, which would bypass the app's auth boundary.
- Hosted fallback, deferred until production auth and timeout behavior are proven.
- Manual-only backend startup, rejected because Codex should be able to use the tool without frontend startup steps.

Implications:

- `LLM_COUNCIL_AGENT_TOKEN_HASH` must be configured before agent endpoints work.
- The raw MCP token must stay outside tracked files, under `~/.codex/secrets/`.
- Weekly curation drafts remain review-gated and do not affect Codex runs until approved.

Owner approval:

- Approved in chat on 2026-06-27.

Status:

- Active

## 2026-06-24 - OpenRouter onboarding uses a hybrid path before managed credits

Decision:

- Near-term hosted onboarding is Google sign-in plus BYOK for non-owner users: each user signs in with Google, then saves their own OpenRouter key.
- The owner can still use the server environment key or save an account OpenRouter key through API & Integrations.
- Future OpenRouter OAuth support can reduce paste-key friction before LLM Council offers Josh-managed paid credits.
- Josh-managed credits, if built, should provision one OpenRouter API key per LLM Council user through OpenRouter Management API, set hard per-user spend limits, and keep a local cost ledger tied to each run.
- Stripe-backed credit wallets and markup are a later business feature, not part of the first hosted/private launch.

Context:

- OpenRouter supports manual API keys, OAuth PKCE user key connection, Management API key provisioning, per-key spend limits, shared/organization credit pools, and usage/credit APIs.
- The product explicitly keeps billing, managed credits, and subscriptions out of the MVP.
- The server `OPENROUTER_API_KEY` is owner-scoped and must not become a shared credential for future users by accident.

Rationale:

- Parent-friendly onboarding eventually needs a simple "create account, buy credits, ask questions" flow, but implementing billing before private hosted launch would broaden auth, privacy, cost, and support risk.
- User-owned OpenRouter keys are the safest intermediate step because each user's provider spend stays outside Josh's account.
- Managed credits become viable after multi-user identity, per-run attribution, hard spend caps, and payment/refund rules exist.

Implications:

- Do not add shared-user access to the owner/server OpenRouter key.
- Multi-user account work must user-scope conversations, settings, sessions, OpenRouter credentials, and run cost records before any managed-credit beta.
- Managed credits require explicit owner approval before implementation because they affect billing, entitlements, payments, and privacy-sensitive account behavior.

References:

- OpenRouter authentication: https://openrouter.ai/docs/api/reference/authentication
- OpenRouter OAuth PKCE: https://openrouter.ai/docs/guides/overview/auth/oauth
- OpenRouter Management API keys: https://openrouter.ai/docs/guides/overview/auth/management-api-keys
- OpenRouter per-user spend limits: https://openrouter.zendesk.com/hc/en-us/articles/51680687417499-Can-I-create-one-API-key-per-user-with-its-own-spending-limit-Management-API-keys

Owner approval:

- Requested by owner in chat on 2026-06-24.

Status:

- Active

## 2026-06-24 - Per-answer costs use stored OpenRouter generation IDs

Decision:

- Future council runs store per-call OpenRouter usage/generation metadata and aggregate it into a `cost_summary` on the run and assistant message.
- The app does not infer exact answer costs from OpenRouter activity time windows.
- Older runs without stored call metadata show cost unavailable.

Context:

- OpenRouter returns usage in completion responses and supports post-hoc generation stats by generation ID.
- Multiple runs or other apps can share the same API key, so time-window matching is not reliable enough for exact per-answer attribution.

Status:

- Active

## 2026-06-24 - Server OpenRouter key is owner-scoped

Decision:

- Hosted direct OpenRouter calls may use the server `OPENROUTER_API_KEY` only under the configured owner account scope.
- The owner may also save an account-scoped OpenRouter key through API & Integrations; the UI only receives masked status, and model calls receive the key server-side.
- Future multi-user support should require each non-owner user to upload or configure their own provider key before running paid model calls.

Context:

- The app now supports BYOK users, so the hosted server key must not become a shared multi-user credential by accident.

Rationale:

- This preserves the private-owner launch path while avoiding a future permission footgun.

Alternatives considered:

- Share the server key with all authenticated users.
- Build the full upload-key flow immediately.

Implications:

- `ADMIN_EMAIL` is the default key owner; `OPENROUTER_OWNER_EMAIL` can override the env-key owner.
- Legacy or future run paths must carry owner/user scope before direct OpenRouter fallback.

Owner approval:

- Requested by owner in chat on 2026-06-24.

Status:

- Active

## 2026-06-24 - Weekly model curation creates reviewable drafts

Decision:

- Weekly model curation generates a draft for owner review instead of automatically replacing curated presets.
- Approving a draft is a separate owner action.
- The curation process may automatically promote the next curation model for future drafts, starting from `openrouter/auto`.

Context:

- Model availability, pricing, and rankings change over time, but changing defaults can affect cost and answer quality.

Rationale:

- Review-first curation keeps recommendations fresh without silently changing the app's behavior or spend profile.

Alternatives considered:

- Fully automatic curated preset updates.
- Manual-only curation refresh.

Implications:

- Vercel Cron requires `CRON_SECRET`.
- `MODEL_CURATION_MODEL` is only an initial override before app-core curation state exists; `MODEL_CURATION_MAX_USD` caps curation calls when fixed pricing is available.
- Curator promotion does not apply curated preset changes; preset changes remain approval-gated.

Owner approval:

- Approved in chat on 2026-06-24.

Status:

- Active

## 2026-06-24 - Keep local and hosted branches separate

Decision:

- `main` remains the local/OpenClaw/LAN branch.
- `web/vercel` is the hosted web branch.

Context:

- The app needs to keep working locally through OpenClaw while gaining a private hosted Vercel deployment.

Rationale:

- Branch separation avoids breaking the local install while Vercel-specific auth, Redis, and serverless run behavior mature.

Alternatives considered:

- Put Vercel changes directly on `main`.

Implications:

- Vercel production branch should be configured as `web/vercel`.
- Agents must check branch before editing deployment-sensitive code.

Owner approval:

- Approved in chat on 2026-06-24.

Status:

- Active

## 2026-06-24 - Use Upstash Redis for hosted persistence

Decision:

- Hosted Vercel mode uses Upstash Redis for conversations, runs, settings, auth user, sessions, and login attempts.

Context:

- Vercel functions cannot rely on durable local JSON files.

Rationale:

- Redis preserves the current JSON-shaped persistence model with less schema work than Postgres and better fit than Blob for sessions/password updates.

Alternatives considered:

- Supabase Postgres.
- Vercel Blob.
- Local JSON on serverless.

Implications:

- Redis env vars are required for hosted mode.
- Future analytics or relational querying may need a later Postgres migration.

Owner approval:

- Approved in chat on 2026-06-24.

Status:

- Active

## 2026-06-24 - First hosted launch uses synchronous council runs

Decision:

- Vercel mode uses `RUN_EXECUTION_MODE=sync`.

Context:

- Current local background tasks are not reliable across stateless serverless invocations.

Rationale:

- Synchronous execution is the simplest reliable first launch.

Alternatives considered:

- Durable job queue and worker.
- Keep local-style background task.

Implications:

- Hosted runs may time out if model calls are slow or model count is too high.
- Queue/progressive updates remain a later enhancement.

Owner approval:

- Approved in chat on 2026-06-24.

Status:

- Active

## 2026-06-24 - Single-owner password auth for hosted app

Decision:

- Hosted app began with owner email/password auth with password change capability.
- This is superseded by Google-only hosted login.

Context:

- The app will call paid/private model providers and must not be publicly usable.

Rationale:

- Single-owner auth was enough for the first hosted launch and avoided early permission complexity.

Alternatives considered:

- No auth.
- OAuth provider.
- Multi-user account system.

Implications:

- Auth, sessions, and password changes are high-risk and require smoke testing before production.
- Bootstrap password must live only in env vars and should be changed after launch.

Owner approval:

- Approved in chat on 2026-06-24.

Status:

- Superseded by Google-only hosted login.

## 2026-06-24 - Hosted password reset uses owner recovery code

Decision:

- Hosted password reset uses `ADMIN_PASSWORD_RESET_TOKEN` as an owner recovery code.
- The login screen exposes a reset form that accepts the owner email, recovery code, and new password.
- A valid recovery code can create the first owner password if `ADMIN_INITIAL_PASSWORD` was not configured.

Context:

- Password change requires an active session, which does not help if the owner is locked out.
- Adding email delivery would introduce another vendor and more secrets before first launch.

Rationale:

- A server-side recovery code is the smallest recovery path for a single-owner private app.
- Resetting the password invalidates existing sessions, matching password-change behavior.
- Recovery also fixes a missing bootstrap password without manually editing Redis.

Alternatives considered:

- Email-based reset links.
- Manual Redis edit.
- Reusing `ADMIN_INITIAL_PASSWORD` after bootstrap.

Implications:

- Hosted deployments should set `ADMIN_PASSWORD_RESET_TOKEN` to a long random value.
- Anyone with the recovery code and owner email can rotate the password, so it must be handled like a secret.

Owner approval:

- Requested by owner in chat on 2026-06-24.

Status:

- Superseded by Google-only hosted login.
