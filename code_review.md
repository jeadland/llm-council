# Code Review Instructions

Review the branch as a senior engineer. Prioritize correctness over style.

The goal is not to show how much can be improved. The goal is to determine whether the change is safe, focused, maintainable, and aligned with the requested task.

## Review Buckets

### Must Fix

Use this bucket for issues that should block merge:

- Bugs
- Data loss risks
- Broken user flows
- Security or privacy issues
- Missing owner approval for gated changes
- Build failures
- Test failures
- Incorrect assumptions
- Regressions
- Unintended architecture changes
- Changes that conflict with the task

### Should Fix

Use this bucket for issues that should usually be addressed before or soon after merge:

- Edge cases
- Maintainability problems
- Confusing state management
- Missing tests
- Fragile implementation choices
- Poor error handling
- Accessibility problems
- Brand or visual direction drift
- Performance issues likely to matter
- Unclear user-facing behavior

### Optional

Use this bucket for non-blocking improvements:

- Naming
- Minor cleanup
- Small cosmetic refactors
- Documentation polish
- Future simplifications

## Constraints

- Do not request broad rewrites unless the current approach is unsafe or structurally wrong.
- Do not nitpick formatting if the formatter or linter handles it.
- Do not ask for new dependencies unless clearly justified.
- Do not expand product scope during review.
- Do not review unrelated existing code unless the change makes it worse.
- Prefer precise comments with file paths and line/function references.
- Explain each issue in terms of user impact, correctness, maintainability, or risk.
- Check whether approval gates were triggered and documented.
- For UI or marketing work, check alignment with `docs/brand/brand-guidelines.md`.

## For Each Issue

Include:

- What is wrong
- Why it matters
- The minimal fix
- Whether it blocks merge

## Checklist

- Does the change solve the requested problem and stay in scope?
- Did it modify unrelated files?
- Did it preserve existing behavior?
- Are state transitions correct?
- Are edge cases and errors handled?
- Is user data preserved?
- Does the change fit the current architecture?
- Did it change persistence, routing, auth, deployment, or data model without explicit need?
- Did it trigger owner approval gates for data, production, auth, billing, entitlements, vendors, AI models, or paid services?
- Is the UI clear, accessible, and usable on expected screen sizes?
- Does UI or brand work follow `docs/brand/brand-guidelines.md`?
- Were relevant tests added or updated?
- Do lint, build, and test commands pass?
- Is there live/runtime evidence when compile-only verification is insufficient?

## Final Review Format

```md
# Code Review
## Summary
Brief judgment on whether the change is safe to merge.

## Must fix
- ...

## Should fix
- ...

## Optional
- ...

## Verification gaps
- ...

## Suggested next action
One concrete next step.
```

If there are no issues in a bucket, write `None identified.`
