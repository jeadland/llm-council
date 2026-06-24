# Product Spec

## Product Name

LLM Council

## Product Summary

LLM Council lets the owner ask one question to a panel of AI models, inspect their independent answers, see anonymized peer rankings, and read a final synthesized answer from a designated chairman model.

## Target Users

| User type | Description | Primary needs |
| --- | --- | --- |
| Primary user | Josh Adland, private owner/operator | Better answers through model disagreement, transparent ranking, and reusable conversations |
| Admin/owner | Same as primary user | Private access, model selection, password rotation, safe deployment |
| Future secondary users | Not currently in scope | Could require multi-user auth and permissions later |

## Core Problem

Single-model answers can miss context, hallucinate, or overfit to one reasoning style. The product helps by collecting independent model responses, having models evaluate anonymized peers, and synthesizing a final answer that preserves useful disagreement and consensus.

## Core Workflows

### Ask The Council

User goal: get a high-quality answer with visible model disagreement.

Steps:

1. Start or select a conversation.
2. Ask a question.
3. Wait for council stages.
4. Inspect Stage 1 answers, Stage 2 rankings, aggregate rankings, and Stage 3 verdict.

Success criteria:

- The final answer is visible.
- Raw model outputs remain inspectable.
- Ranking interpretation is transparent.
- Failed individual models do not fail the whole run unless all models fail.

### Configure Models

User goal: choose council members and chairman.

Steps:

1. Open Settings.
2. Select active council models.
3. Select chairman model.
4. Save settings.

Success criteria:

- Model choices persist.
- Chairman is visible in the sidebar and final answer.
- Local/OpenClaw and hosted/OpenRouter model IDs remain compatible.

### Hosted Private Access

User goal: use the Vercel-hosted app privately.

Steps:

1. Visit hosted app.
2. Log in with owner email/password.
3. Use the app.
4. Change password from Account settings after launch.

Success criteria:

- Unauthenticated users cannot access app APIs.
- Password change invalidates old password and sessions.
- Conversations/settings persist through reload and deploy.

## Functional Requirements

| Area | Requirement | Priority | Notes |
| --- | --- | --- | --- |
| Council run | Execute Stage 1, Stage 2, Stage 3 | High | Parallel where possible |
| Transparency | Show raw answers, raw rankings, parsed rankings, aggregate rankings | High | Core trust feature |
| Settings | Configure council and chairman | High | Persisted |
| Conversation storage | Store conversation history locally and hosted | High | JSON local, Redis hosted |
| Private auth | Restrict hosted access to owner | High | Single-user for now |
| Password change | Owner can rotate launch password | High | Required before public URL use |
| Branch split | Keep local/OpenClaw branch separate from Vercel branch | High | `main` vs `web/vercel` |

## Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| Performance | Run model calls in parallel where platform allows |
| Accessibility | Use semantic forms/buttons and readable focus states |
| Responsiveness | App should remain usable on desktop and mobile browser widths |
| Data persistence | Avoid data loss across reload/deploy |
| Privacy | Do not expose conversations or paid model access publicly |
| Security | Store password hashes, not plaintext passwords; use HttpOnly cookies |
| Cost control | Keep model count configurable and avoid accidental public usage |

## Non-Goals

- Multi-user accounts and role management.
- Public marketing site.
- Billing or subscriptions.
- Full analytics/reporting over model performance.
- Replacing OpenClaw local install flow on `main`.

## Product Constraints

- Tech stack: React/Vite frontend, FastAPI backend.
- Deployment target: local LAN and Vercel.
- Authentication: single-owner email/password for hosted web.
- Data storage: local JSON for dev, Upstash Redis for hosted.
- Approval gates: auth, persistence, paid services, model/vendor changes, and production deployment require explicit owner approval.

## Design Direction

LLM Council should feel practical, private, and inspectable. This is an operational tool, not a marketing site. Preserve the current light/dark utility interface, compact sidebar, stage cards, and blue primary action style unless the owner requests visual redesign.

Brand details live in `docs/brand/brand-guidelines.md`.

## Acceptance Criteria Pattern

For each feature, write acceptance criteria like this:

```md
## Acceptance Criteria
- User-facing behavior:
- Data or persistence behavior:
- Loading, empty, error, and permission states:
- Mobile/responsive behavior:
- What must not change:
- Verification evidence:
```

## Open Questions

| Question | Owner | Status |
| --- | --- | --- |
| Should hosted production use a custom domain or Vercel default URL first? | Josh | Open |
| What is the acceptable maximum wait time for a hosted council run? | Josh | Open |
| Should conversation export be Markdown/PDF later? | Josh | Later |

## Future Ideas

- Streaming/progressive Vercel runs through a durable queue.
- Export conversations.
- Model performance analytics.
- Custom ranking criteria.
- Multi-user private access if the tool is shared.
