# Deployment Configuration

This guide covers deployment configuration for the SpotiBye Cloudflare Workers backend.
`src/backend/wrangler.toml` is the source of truth for names and bindings.

## Environments

The backend has two environments. There is no staging environment.

| Environment | Worker | Deploy command | GitHub workflow |
|-------------|--------|----------------|-----------------|
| Development | `spotibye-backend-development` | `npm run deploy:dev` | Deploy Backend (`deploy-backend.yml`), on push to `main` or manual dispatch |
| Production | `spotibye-backend-production` | `npm run deploy:prod` | Deploy Production (`deploy-production.yml`), manual dispatch; also Deploy Backend on a `v*` tag push |

Wrangler derives each Worker name from the top-level `name` (`spotibye-backend`)
plus the `--env` suffix. A bare `wrangler deploy` targets neither environment.
It creates a stray top-level `spotibye-backend` Worker, so `npm run deploy`
refuses to run.

The deploy scripts call `scripts/deploy-with-metadata.sh`. It injects
`RELEASE_SHA`, `RELEASE_VERSION`, and `DEPLOYED_AT`, which `/health` reports.
A raw `wrangler deploy --env <env>` skips that metadata, so prefer the npm scripts.

## Secrets

Set secrets per environment. Without `--env`, they attach to the stray
top-level Worker instead.

```bash
cd src/backend
npx wrangler secret put SPOTIFY_CLIENT_ID --env production
npx wrangler secret put SPOTIFY_CLIENT_SECRET --env production
npx wrangler secret put JWT_SECRET --env production
```

Repeat with `--env development` for the development Worker.

### Local Development

Create `src/backend/.dev.vars`:

```bash
ENVIRONMENT=development
SPOTIFY_CLIENT_ID=your-dev-client-id
SPOTIFY_CLIENT_SECRET=your-dev-client-secret
JWT_SECRET=your-dev-jwt-secret
```

Run `npm run dev` to start the Worker locally.

## Checking a Deployment

From the repo root, compare the live Worker with your checkout:

```bash
./scripts/backend-deploy-status.sh prod   # or: dev
```

The script reads `SPOTIBYE_PRODUCTION_BACKEND_URL` and `SPOTIBYE_DEV_BACKEND_URL`
from the environment or `.desktop.env.local`, then reads `release_sha` from `/health`.

## KV Namespaces

`CACHE_KV` and `SESSIONS_KV` are declared at the top level and in each
`[env.*]` block of `wrangler.toml`. A new account needs its own namespaces:

```bash
npx wrangler kv namespace create CACHE_KV
npx wrangler kv namespace create SESSIONS_KV
npx wrangler kv namespace create CACHE_KV --preview
npx wrangler kv namespace create SESSIONS_KV --preview
```

Then replace both `id` and `preview_id` in every `kv_namespaces` block of
`wrangler.toml`: the top level, `[env.development]`, and `[env.production]`.
Keep the preview namespaces separate from the deployed ones, so `wrangler dev`
never writes to live data.

## Analysis Queue

Playlist analysis uses Cloudflare Queues in both environments so large playlists can retry outside the initial HTTP request. The Worker module exports both `fetch` and `queue`; no separate Worker entry point is required.

Required queues:

```bash
cd src/backend
npx wrangler queues create spotibye-analysis-dev
npx wrangler queues create spotibye-analysis-dev-dlq
npx wrangler queues create spotibye-analysis
npx wrangler queues create spotibye-analysis-dlq
```

The producer and consumer binding name is `ANALYSIS_QUEUE`. Queue messages contain `job_id`, `playlist_id`, `user_id`, `session_id`, `enqueued_at`, and `attempt`; they never contain Spotify access tokens. The consumer loads the session from `SESSIONS_KV` and refreshes the Spotify token when needed.

## Analysis Status Durable Object

Playlist analysis live status uses the `ANALYSIS_STATUS` Durable Object binding.
The object is named deterministically as `analysis:{userId}:{playlistId}` and
stores only the current status/progress record. Completed analysis results and
raw ReccoBeats enrichment caches remain in `CACHE_KV`.

`wrangler.toml` must include the binding and SQLite-backed class migration:

```toml
[[durable_objects.bindings]]
name = "ANALYSIS_STATUS"
class_name = "AnalysisStatusObject"

[[migrations]]
tag = "v1-analysis-status"
new_sqlite_classes = ["AnalysisStatusObject"]
```

## Troubleshooting

1. **KV namespace not found:** Check the namespace IDs in `wrangler.toml`.
2. **Secret not set:** Run `npx wrangler secret list --env <development|production>`.
3. **`/health` reports `release_sha: unknown`:** The Worker was deployed without
   `deploy-with-metadata.sh`, or you are hitting the wrong Worker.

```bash
npx wrangler deployments list --env production
npx wrangler tail --env production
```

## Rollback

```bash
npx wrangler deployments list --env production
npx wrangler rollback --env production <version-id>
```

A rollback restores older code, so `/health` reports the older `release_sha`.
