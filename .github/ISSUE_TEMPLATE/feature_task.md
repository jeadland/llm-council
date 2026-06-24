---
name: Feature task
about: A bounded implementation task suitable for Cursor/Codex workflow
title: "[Feature] "
labels: feature
assignees: ""
---

## Goal

Describe the goal in one paragraph.

```text
TODO
```

## User-Visible Behavior

What should the user see or be able to do?

```text
TODO
```

## Relevant Files

Known or likely files:

- TODO

## Scope Classification

- [ ] MVP requirement
- [ ] Later enhancement
- [ ] Nice-to-have polish
- [ ] Dangerous distraction to avoid or park

## Acceptance Criteria

Done means:

- [ ] User-facing behavior: TODO
- [ ] Data or persistence behavior: TODO
- [ ] Loading, empty, error, and permission states: TODO
- [ ] Mobile/responsive behavior: TODO
- [ ] What must not change: TODO
- [ ] Verification evidence: TODO

## Approval Gates

Owner approval is required before:

- [ ] Spending money or enabling paid services
- [ ] Changing DNS, production hosting, app-store listings, or public launch settings
- [ ] Deleting user or production data
- [ ] Changing auth, billing, entitlements, permissions, or privacy-sensitive behavior
- [ ] Running irreversible database migrations
- [ ] Adding new dependencies, vendors, AI models, or external services
- [ ] Broadening product scope beyond this task
- [ ] None of the above apply

## Out Of Scope

This task should not change:

- TODO

## Design Notes

Visual or interaction notes:

```text
TODO
```

Brand guidance:

```text
Read docs/brand/brand-guidelines.md before frontend, marketing, visual design, styling, icon, or brand-asset work.
```

## Technical Notes

Architecture, state, persistence, or integration notes:

```text
TODO
```

## Verification Plan

- [ ] Lint
- [ ] Tests
- [ ] Build
- [ ] Manual check
- [ ] Vercel preview, if applicable

## Cursor Prompt

```text
Read AGENTS.md, OWNER_OPERATING_GUIDE.md, PRODUCT_SPEC.md, ARCHITECTURE.md, DECISIONS.md, TASKS.md, and relevant Cursor rules. For UI or brand work, also read docs/brand/brand-guidelines.md.
Implement this feature task only.
Goal:
TODO
User-visible behavior:
TODO
Acceptance criteria:
TODO
Out of scope:
TODO
Approval gates:
TODO
Verification:
TODO
Keep the diff small. Do not introduce new dependencies. Do not change persistence, routing, deployment config, or data model unless explicitly required.
```

## Codex Review Prompt

```text
Read AGENTS.md and code_review.md.
Review this branch as a senior engineer. Prioritize correctness, edge cases, state bugs, data loss risk, test gaps, and scope control.
Return:
1. Summary
2. Must fix
3. Should fix
4. Optional
5. Verification gaps
6. Suggested next action
```
