# Agent Team Runbook

Project: LLM Council

## Before A Run

1. Read project bootstrap docs and `docs/agents/LOOP_SPEC.md`.
2. Confirm the target task is `agent-ready`.
3. Confirm forbidden actions and approval gates.
4. Set a time limit and max artifact count.
5. Read `docs/preview-bootstrap.md` before preview, Vercel, or Google OAuth checks.
6. Confirm the current branch with `git status --short --branch`.

## During A Run

1. Work on one bounded task.
2. Keep evidence as you go.
3. Stop when evidence is missing, a gate is reached, or the run limit is hit.
4. Do not expand scope without updating the control plane.
5. Prefer runtime/browser evidence for user-visible onboarding claims.
6. Keep managed billing disabled unless the run explicitly has owner approval to test it.

## After A Run

1. Save a report under `docs/agents/runs/`.
2. Update `docs/agents/CONTROL_PLANE.md`.
3. Mark approval gates and blockers.
4. Record `[PROMOTE]` candidates only when the learning is reusable beyond this project.

## Recommended Prompt

```text
Use $agent-loop-runner for this project. Run Paid Onboarding Readiness Loop for 90 minutes max. Use docs/agents/LOOP_SPEC.md and stop before any forbidden action.
```

## Preferred First Run

```text
Run the Preview onboarding audit with managed mode disabled. Produce one report under docs/agents/runs/. Do not edit product source, change auth/billing settings, spend money, deploy, or modify external systems.
```
