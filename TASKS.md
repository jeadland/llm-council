# Tasks

Use this file as the lightweight source of truth for current and upcoming work. Each task should be small enough for one agent session.

## Now

### Task: Deploy and validate Vercel web branch

Status: Not started

Goal:

Push `web/vercel`, configure Vercel/Upstash/OpenRouter environment variables, deploy a preview, and verify private auth plus a small council query before production.

User-visible behavior:

- Hosted app shows login before any conversation data.
- Josh can log in, change password, and use the council.
- Conversations/settings persist through reload.

Relevant files:

- `vercel.json`
- `api/index.py`
- `backend/auth.py`
- `backend/storage.py`
- `frontend/src/components/LoginScreen.jsx`
- `frontend/src/components/Sidebar.jsx`

Acceptance criteria:

- [ ] User-facing behavior: login wall appears on hosted preview.
- [ ] Data or persistence behavior: conversation/settings survive reload and redeploy.
- [ ] Loading, empty, error, and permission states: unauthenticated API returns `401`; failed login shows clear error.
- [ ] Mobile/responsive behavior: login and main app usable on phone width.
- [ ] What must not change: `main` remains local/OpenClaw branch.

Out of scope:

- Multi-user accounts.
- Queue-based progressive hosted runs.
- Public marketing site.

Approval gates:

- [x] Production, DNS, app-store, or public launch settings
- [x] Auth, billing, entitlements, permissions, or privacy-sensitive behavior
- [x] New dependencies, vendors, AI models, or external services

Verification:

- [ ] `uv run python -m compileall backend api`
- [ ] `npm --prefix frontend run lint`
- [ ] `npm --prefix frontend run build`
- [ ] Vercel preview smoke
- [ ] Hosted auth smoke
- [ ] Hosted small council query

Notes:

- Do not commit or print real secrets.
- Set Vercel production branch to `web/vercel`, not `main`.

## Next

- Add automated backend tests for auth hash/session behavior.
- Add a documented Vercel deploy checklist with exact env var setup steps.
- Decide whether hosted runs need queue/progress architecture if sync runs time out.

## Later

- Conversation export to Markdown/PDF.
- Model performance analytics over time.
- Custom ranking criteria per question.
- Durable queue/worker for hosted progressive run updates.

## Parking Lot

- Multi-user auth and sharing.
- Public landing/marketing page.
- Billing or subscription access.

## Completed

- 2026-06-24: Added Vercel web branch implementation with Redis storage, private auth, password change, and sync run mode. Commit: `4892cb6`.
- 2026-06-24: Added project-bootstrap workflow docs and Cursor/GitHub templates.
