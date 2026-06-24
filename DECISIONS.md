# Decisions

Use this file to record important product, architecture, design, and implementation decisions.

## Decision Log

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

- Hosted app uses owner email/password auth with password change capability.

Context:

- The app will call paid/private model providers and must not be publicly usable.

Rationale:

- Single-owner auth is enough for first hosted launch and avoids multi-user permission complexity.

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

- Active

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
