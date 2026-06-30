# Agent Team Guardrails

Project: LLM Council

## Authority

Project-local bootstrap docs and current user instructions outrank this file. This file narrows loop execution; it does not grant authority to override project rules.

## Approval Required

- Sending emails, DMs, texts, or outreach.
- Public posts, publishing, or SEO page deployment.
- Production deploys.
- Paid services, ads, or purchases.
- Credential, billing, auth, or data-retention changes.
- Destructive data or infrastructure changes.
- Changing Google OAuth, Vercel, Stripe, OpenRouter, Redis, Postgres, or production routing configuration.
- Enabling managed paid runs or changing `MANAGED_MODE_ENABLED`.
- Adding email login, password login, magic links, or another auth provider.
- Running broad live model tests that create meaningful OpenRouter/provider cost.

## Evidence Standards

- External facts need source URLs.
- Runtime claims need tests, logs, screenshots, or direct checks.
- Marketing claims need product support or source-backed customer language.
- Missing evidence must be labeled as missing, not inferred as true.
- UI blemishes must name the screen, viewport, observed issue, severity, and suggested fix.
- Billing evidence must clearly separate disabled-preview behavior from test-mode or production behavior.

## Waste And Drift Checks

- Stop if the loop has become broad research without a defined artifact.
- Stop if outputs are generic and not tied to project evidence.
- Stop if the agent is creating work that cannot be reviewed.
- Stop if review bandwidth is the bottleneck.
- Stop if the work turns into a public launch, auth redesign, billing architecture project, or marketing campaign instead of onboarding readiness.
