# Product Spec

## Product Name

LLM Council

## Product Summary

LLM Council lets the owner ask one question to a panel of AI models, inspect their independent answers, see anonymized peer rankings, and read a final synthesized answer from a designated chairman model.

## Target Users

| User type | Description | Primary needs |
| --- | --- | --- |
| Primary user | Josh Adland, private owner/operator | Better answers through model disagreement, transparent ranking, and reusable conversations |
| Admin/owner | Same as primary user | Private Google sign-in, model selection, safe deployment |
| BYOK beta users | Invited or trusted users with their own OpenRouter account | Sign in with Google, connect their own API key, and keep private conversations/settings |
| Managed-balance beta users | Invited or trusted users who do not want to manage OpenRouter | Add LLM Council Balance, choose curated counsel profiles, see estimated/max cost, and receive a post-run receipt |

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
2. Log in with Google.
3. Use the app.

Success criteria:

- Unauthenticated users cannot access app APIs.
- Email/password signup, login, reset, and password change endpoints are disabled.
- Conversations/settings persist through reload and deploy.

### Google BYOK Onboarding

User goal: sign in with Google and use the council with the user's own OpenRouter key.

Steps:

1. Open the hosted app.
2. Choose Continue with Google.
3. Add an OpenRouter API key through API & Integrations.
4. Run the council after the key is saved.

Success criteria:

- Google provides the verified email identity.
- OpenRouter key is required before non-owner council runs.
- Key validation uses a non-generative OpenRouter key endpoint when saving the key.
- Non-owner users cannot use Josh's/server OpenRouter key.
- Conversations, settings, runs, and integration status are private to the authenticated user.

### Managed LLM Council Balance

User goal: use the hosted app without pasting an OpenRouter key.

Steps:

1. Sign in with Google.
2. Select managed billing in Settings.
3. Add $1 test, $5, $10, or $20 of LLM Council Balance through Stripe Checkout.
4. Choose a curated counsel profile.
5. Review estimated cost, maximum charge, and current balance before running.
6. Receive a post-run receipt with actual charge and remaining balance.

Success criteria:

- Managed balance is called LLM Council Balance, not OpenRouter credits.
- Stripe webhook fulfillment is idempotent and is the source of truth for credited balance.
- One OpenRouter child key is provisioned per managed user and used only server-side.
- Managed runs reserve the maximum charge before execution and release unused balance.
- BYOK remains available when managed mode is paused or underfunded.

## Functional Requirements

| Area | Requirement | Priority | Notes |
| --- | --- | --- | --- |
| Council run | Execute Stage 1, Stage 2, Stage 3 | High | Parallel where possible |
| Transparency | Show raw answers, raw rankings, parsed rankings, aggregate rankings | High | Core trust feature |
| Settings | Configure council and chairman | High | Persisted |
| Conversation storage | Store conversation history locally and hosted | High | JSON local, Redis hosted |
| Private auth | Restrict hosted access to authenticated Google users | High | Owner plus BYOK users |
| Google-only login | Hosted login uses only the Google button | High | Password signup/login/reset/change routes return 403 |
| BYOK integration | Users save their own OpenRouter key after Google sign-in | High | Non-owner runs require an account key |
| Managed balance beta | Invited users can buy LLM Council Balance and spend it on curated council profiles | High | Private beta only; disabled by default until Stripe/Postgres/OpenRouter env is configured |
| Branch split | Keep local/OpenClaw branch separate from Vercel branch | High | `main` vs `web/vercel` |

## Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| Performance | Run model calls in parallel where platform allows |
| Accessibility | Use semantic forms/buttons and readable focus states |
| Responsiveness | App should remain usable on desktop and mobile browser widths |
| Data persistence | Avoid data loss across reload/deploy |
| Privacy | Do not expose conversations or paid model access publicly |
| Security | Use verified Google identity, server-side sessions, and HttpOnly cookies |
| Cost control | Keep model count configurable, use managed profile caps, reserve before managed runs, and avoid accidental public usage |

## Non-Goals

- Password login, email confirmation, email reset links, subscriptions, public billing launch, and role-management UI.
- Public marketing site.
- Subscriptions or public self-serve paid launch.
- Full analytics/reporting over model performance.
- Replacing OpenClaw local install flow on `main`.

## Product Constraints

- Tech stack: React/Vite frontend, FastAPI backend.
- Deployment target: local LAN and Vercel.
- Authentication: Google-only hosted sign-in plus BYOK OpenRouter integration.
- Data storage: local JSON for dev, Upstash Redis for hosted conversations/settings/runs, and Postgres for managed billing.
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
