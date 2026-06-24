# Decisions

Use this file to record important product, architecture, design, and implementation decisions.

## Decision Log

## 2026-06-24 - BYOK signup launches without invite codes or email confirmation

Decision:

- Hosted signup is open to anyone with the app URL, but every non-owner account must provide a valid OpenRouter API key during account creation.
- There is no invite code and no email confirmation in this version.
- Signup validates OpenRouter keys with the non-generative OpenRouter key endpoint before creating the account.
- Non-owner users never fall back to the server `OPENROUTER_API_KEY`; if their account key is missing, council runs are blocked.

Context:

- The desired onboarding path is low-friction: name optional, email required, OpenRouter key required, and an on-screen account-created confirmation.
- The app does not yet handle email delivery, email confirmation, managed credits, or billing.

Rationale:

- BYOK keeps model spend attached to the user's own OpenRouter account and avoids Josh-funded access.
- Requiring a key at signup is the practical gate while email confirmation is intentionally deferred.
- Removing invite codes avoids a confusing manual distribution step.

Implications:

- User conversations, settings, runs, and OpenRouter integration status must be scoped by authenticated email.
- Account recovery remains owner-only via recovery code until email-based recovery is added.
- Public deployments should still be treated as sensitive because anyone with the URL can create an account if they bring a valid key.

Status:

- Active

## 2026-06-24 - OpenRouter onboarding uses a hybrid path before managed credits

Decision:

- Near-term hosted onboarding is BYOK for non-owner users: each user can create an account by pasting their own OpenRouter key.
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
- This is superseded for general access by BYOK user signup, while owner bootstrap and recovery-code reset remain owner-only.

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

- Superseded for general access by BYOK signup; owner bootstrap behavior remains active.

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

- Active
