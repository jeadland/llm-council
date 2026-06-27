# Brand Guidelines

Use this file as the source of truth for brand direction before frontend, marketing, icon, logo, copy, or visual design work.

## Brand Status

Current status:

- [ ] No brand direction defined yet
- [x] Rough direction defined
- [ ] Approved brand direction
- [x] Existing logo/icon assets present
- [ ] Approved launch-ready visual system

## Brand Summary

Brand/product name: LLM Council

One-sentence positioning:

```text
A private AI deliberation room where multiple models answer, critique, rank, and synthesize a better final response.
```

Primary audience:

```text
Josh as a private owner/operator using AI models for deeper answers and decision support.
```

Desired feel:

```text
Practical, private, clear, analytical, calm, trustworthy, and tool-like.
```

Should not feel:

```text
Public marketing-first, playful for its own sake, flashy, decorative, or like a generic chatbot clone.
```

## Visual Direction

Reference products, sites, apps, or screenshots:

- Current local LLM Council UI.
- Compact productivity tools with persistent sidebars and inspectable detail panels.

Approved assets:

- `frontend/public/images/llm-council-icon.svg`
- `frontend/public/images/llm-council-logo.svg`
- `frontend/public/images/llm-council-logo-v2.svg`
- PNG/favicons under `frontend/public/`

Logo/icon status:

```text
Existing assets are acceptable for current app and Vercel launch. Do not replace or regenerate without owner approval.
```

Typography direction:

```text
Use system UI fonts. Do not introduce a webfont unless a redesign is explicitly approved.
```

Color direction:

```text
Keep the current utility palette: blue primary action, neutral light/dark surfaces, restrained borders, and orange/gold chairman accent.
```

Imagery direction:

```text
No stock imagery or decorative hero art for the app. The primary experience is the working council interface.
```

## UI Principles

- Product usability comes before decoration.
- Use the brand to make the workflow clearer, not slower.
- Preserve accessibility, contrast, responsive behavior, and touch targets.
- Prefer dense but readable operational UI over landing-page composition.
- Keep Stage 1, Stage 2, and Stage 3 transparency visible and inspectable.
- Do not introduce new logo, icon, color, or type assets without owner approval.

## Brand Approval Gates

Ask for owner approval before:

- Creating or replacing logo marks.
- Adding app icons, favicons, or launch assets.
- Changing the primary palette or typography system.
- Making a broad visual redesign.
- Publishing public marketing pages.
- Exporting final brand assets.

## Frontend Agent Instructions

Before frontend, marketing, visual design, styling, icon, or brand-asset work:

1. Read this file.
2. Inspect existing brand implementation points in the repo.
3. State the smallest visual change needed.
4. Identify what should not change.
5. Verify the result with a screenshot, preview, or browser check when possible.

If brand direction is missing for a future task, create TODOs here and use conservative, product-appropriate defaults instead of inventing a full identity.
