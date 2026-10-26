# Cloudflare Worker Deployment Guide

## Prerequisites

- Node.js 24 (pinned in `.nvmrc`)
- `npm ci` in `src/backend`, which installs Wrangler locally
- A Cloudflare account with Workers enabled

## Environments

| Environment | Worker | Command | GitHub workflow |
|-------------|--------|---------|-----------------|
| Development | `spotibye-backend-development` | `npm run deploy:dev` | Deploy Backend (`deploy-backend.yml`) |
| Production | `spotibye-backend-production` | `npm run deploy:prod` | Deploy Production (`deploy-production.yml`) |

There is no default target. A bare `wrangler deploy` creates a stray top-level
`spotibye-backend` Worker. Production deploys normally go through the Deploy
Production workflow, which runs tests and the security gate first.

## Deployment Steps

1. **Log in to Cloudflare**
   ```bash
   cd src/backend
   npx wrangler login
   ```

2. **Check the configuration.** `src/backend/wrangler.toml` defines the KV,
   Queue, and Durable Object bindings for each `[env.*]` block.

3. **Run the checks**
   ```bash
   npm run test:run
   npm run typecheck
   ```

4. **Deploy**
   ```bash
   npm run deploy:dev    # or deploy:prod
   ```

5. **Verify** from the repo root:
   ```bash
   ./scripts/backend-deploy-status.sh dev   # or prod
   ```

## Secrets

Set secrets per environment:
```bash
npx wrangler secret put SPOTIFY_CLIENT_ID --env production
npx wrangler secret put SPOTIFY_CLIENT_SECRET --env production
npx wrangler secret put JWT_SECRET --env production
```

## KV Namespaces

The Worker binds `CACHE_KV` and `SESSIONS_KV`. A new account needs its own:
```bash
npx wrangler kv namespace create CACHE_KV
npx wrangler kv namespace create SESSIONS_KV
npx wrangler kv namespace create CACHE_KV --preview
npx wrangler kv namespace create SESSIONS_KV --preview
```

Then replace both `id` and `preview_id` in every `kv_namespaces` block of
`wrangler.toml`: the top level, `[env.development]`, and `[env.production]`.
Keep the preview namespaces separate from the deployed ones, so `wrangler dev`
never writes to live data. The analysis queues are
listed in `src/backend/docs/deployment-configuration.md`.

## Common Issues

- **Secrets not available:** Check `npx wrangler secret list --env <env>`. Secrets
  set without `--env` land on the stray top-level Worker.
- **`/health` reports `release_sha: unknown`:** The Worker was deployed without
  `deploy-with-metadata.sh`.
- **KV access errors:** Check the namespace bindings in `wrangler.toml`.
