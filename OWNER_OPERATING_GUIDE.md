# Owner Operating Guide

This project is owned by a non-developer product owner who is AI-fluent, pragmatic, and actively improving technical judgment. Agents should harness that product judgment without assuming the owner can safely perform developer-only tasks unaided.

## Collaboration Model

- Treat the owner as the product decision-maker.
- Do not assume the owner can resolve merge conflicts, interpret stack traces, edit environment files, inspect databases, debug build systems, or choose between architectural options without a clear recommendation.
- Provide exact commands and plain-English implications when asking the owner to do anything technical.
- Prefer safe defaults and explain tradeoffs briefly.
- If a task can be executed safely by the agent, do the work instead of turning it into homework for the owner.
- Keep durable context in repo files rather than relying on chat history.

## Capability Assumptions

The owner can usually:

- Describe the intended product behavior.
- Judge whether a workflow feels right.
- Review screenshots, previews, and live app behavior.
- Approve scope, copy, visual direction, and business rules.
- Paste a prepared prompt into Cursor or another agent.
- Run clearly specified commands when necessary.

The owner should not be expected to independently:

- Diagnose production, auth, database, or deployment failures.
- Design data migrations or rollback plans.
- Interpret low-level compiler, bundler, or CI errors.
- Decide between libraries, vendors, or architecture patterns without guidance.
- Manually edit secrets, DNS, billing, or app-store configuration without step-by-step instructions.

## Source Of Truth Ladder

Use these files in this order when deciding what to build:

1. `PRODUCT_SPEC.md` - what the product is and who it serves.
2. `ARCHITECTURE.md` - how the system works.
3. `DECISIONS.md` - settled product, technical, and design decisions.
4. `TASKS.md` - current and upcoming work.
5. `docs/agent-handoff.md` - current state, active task, and resume instructions.
6. `docs/brand/brand-guidelines.md` - visual identity and brand constraints.

If these conflict, stop and explain the conflict before editing.

## Approval Gates

Ask for explicit owner approval before:

- Spending money or enabling paid services.
- Buying, changing, or transferring domains.
- Changing DNS, production hosting, app-store listings, or public launch settings.
- Deleting user data, production data, accounts, teams, projects, or files.
- Changing auth, billing, entitlements, permissions, or privacy-sensitive behavior.
- Running irreversible database migrations.
- Adding new dependencies, vendors, AI models, or external services.
- Broadening product scope beyond the active task.

Do not ask the owner to decide low-level implementation details unless there is a real product, cost, security, privacy, or maintenance tradeoff.

## LLM Council Specific Gates

For this project, also treat these as approval-gated:

- Changing which branch Vercel deploys from.
- Changing hosted auth behavior, bootstrap password handling, or session behavior.
- Adding/removing model providers or default paid model sets.
- Moving hosted persistence away from Upstash Redis.
- Publishing a public URL, custom domain, or marketing page.
- Running a broad live model smoke that could create meaningful provider cost.

## Task Framing Standard

For meaningful work, define the task like this before editing:

```md
Goal:
User-visible behavior:
Relevant files:
Acceptance criteria:
Out of scope:
Risks:
Verification plan:
Owner approval needed:
```

## Acceptance Criteria Standard

Every meaningful task should answer:

- What should the user be able to do?
- What should happen to data and persistence?
- What are the loading, empty, error, and permission states?
- What should happen on mobile and desktop?
- What must not change?
- What commands, previews, or live checks prove completion?

## Scope Governor

Classify new ideas before acting:

```text
MVP requirement
Later enhancement
Nice-to-have polish
Dangerous distraction
```

Park non-current ideas in `TASKS.md` under `Parking Lot` instead of folding them into active implementation.

## Verification Bias

Do not call work complete based only on code edits or compile success when live behavior matters.

Prefer real evidence:

- Browser preview or deployed URL
- Mobile/responsive screenshot
- Simulator/device run
- Database query
- API response
- CI run
- Manual smoke test

If a check cannot be run, say why and identify the residual risk.

## Handoff Standard

When handing work to Cursor or another agent, provide:

- Pasteable starter prompt
- Phase checklist
- Exact files likely involved
- Tests and manual checks to run
- Stop conditions
- Resume instructions after chat reset, context loss, or usage-limit interruption

## Final Report Standard

End completed work with:

```md
Changed:
- ...
Verified:
- ...
Risks:
- ...
Owner action needed:
- ...
Suggested next step:
- ...
```
