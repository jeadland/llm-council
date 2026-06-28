# Josh Site Deployment

This app is mounted inside Josh's personal site. Treat
`https://joshadland.com/llm-council` as the production URL that matters.

## Ownership

- App repo: `/Users/joshadland/Codex Projects/llm-council`
- App Vercel project: `llm-council`
- Public route: `https://joshadland.com/llm-council`
- Front-door site repo: `/Users/joshadland/Projects/josh-site`
- Front-door route config: `/Users/joshadland/Projects/josh-site/vercel.json`

The app owns its UI, API, auth, Redis/Vercel KV persistence, model settings,
OpenRouter integration, cron jobs, and app deployment. `josh-site` owns the
public domain and proxies `/llm-council/*` to this app's Vercel deployment.

## Before changing routing or deployment

- Keep the hosted web work on the `web/vercel` branch unless the user explicitly
  says otherwise.
- Preserve `VITE_BASE_PATH=/llm-council/` in the Vercel build command.
- Preserve the `/llm-council` rewrites for API, assets, images, favicons, and
  the SPA fallback in `vercel.json`.
- Keep backend API compatibility with both `/api/*` and `/llm-council/api/*`.
- Do not deploy this app as the root of `joshadland.com`.
- Do not change DNS, aliases, auth behavior, storage backend, provider keys, or
  Vercel project links without explicit approval.

## Deploy flow

From this repo on `web/vercel`:

```bash
uv run python -m compileall backend api
npm --prefix frontend run lint
VITE_BASE_PATH=/llm-council/ npm --prefix frontend run build
npx --yes vercel@latest deploy --prod --yes
```

If the change only affects this app, deploy this app's Vercel project. If the
change requires a new public mount, rewrite, homepage card, sitemap entry, or
route ownership change, also update and deploy `/Users/joshadland/Projects/josh-site`.

## Verify production

After deploy, verify the public Josh-site routes, not only the Vercel preview
URL:

```bash
curl -I https://joshadland.com/llm-council
curl -I https://joshadland.com/llm-council/api/health
```

Also check that the live HTML loads assets under `/llm-council/assets/` or
`/llm-council/images/` and that those assets return non-404 responses.

## Data and secret notes

Hosted production uses Redis/Vercel KV-style persistence and direct provider
credentials. Never commit `.env`, Redis tokens, OpenRouter keys, admin reset
tokens, local `data/`, screenshots, or generated build output.

Google OAuth is the hosted login method. Configure these Vercel
env vars before using it in production:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `OAUTH_STATE_SECRET`

The production Google redirect URI should be
`https://joshadland.com/llm-council/api/auth/oauth/google/callback`; the direct
Vercel app callback can also be registered for preview validation. Owner Google
sign-in stays disabled unless `ALLOW_OWNER_GOOGLE_OAUTH=true` is intentionally
set; production enables it so Josh's configured owner email can also use the
Google button. Password signup, login, reset, and change-password routes are
intentionally disabled in hosted auth.
