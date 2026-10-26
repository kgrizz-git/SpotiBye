# Monitoring and Logging Setup

This guide covers what monitoring and logging the SpotiBye Cloudflare Workers
backend actually has. The code is the source of truth.

## Overview

The backend has:
- Structured `console.*` logging, read with `wrangler tail` or the Cloudflare
  dashboard
- Hono's request logger middleware
- A `/health` endpoint with deployment metadata

The backend has no metrics pipeline, Analytics Engine binding, alerting,
external error webhook, or log-level configuration. `wrangler.toml` has no
`[observability]` block.

There are two Workers: `spotibye-backend-development` and
`spotibye-backend-production`.

## Logging

### Structured Logger
`utils/logger.ts` exports a small `logger` object:

```typescript
logger.info(message: string, context?: Record<string, unknown>);
logger.warn(message: string, context?: Record<string, unknown>);
logger.error(message: string, context?: Record<string, unknown>);
```

Each call maps to `console.info`, `console.warn`, or `console.error` with
`(message, context ?? {})`. The logger adds no timestamp, level field, or
environment field. There is no `debug` level, and there is no level filter.
Every call logs in every environment.

`services/analysis.ts`, `services/reccobeats-track-cache.ts`, and
`services/export-tracks.ts` use the logger.

### Other Log Conventions
Most other code calls `console.*` directly in one of two forms:
- `console.info('[tag] message', { ...context })`, for example
  `[playlists] cache hit` and `[export] start`
- `console.error(JSON.stringify({ event: 'EVENT_NAME', ... }))` for auth,
  queue, and error events

Event names in use include `ERROR_OCCURRED` (global error handler),
`OAUTH_INIT_FAILED`, `TOKEN_REFRESH_FAILED`, `QUEUE_INVALID_MESSAGE_BODY`,
`QUEUE_JOB_COMPLETED`, `QUEUE_JOB_FAILED`, and `QUEUE_MARK_FAILED_THREW`.
`QUEUE_JOB_COMPLETED` is logged at error level even though it is a success
event.

`console.log` is banned in non-test backend code (Golden Principle #5). Use
`console.info` or the logger instead.

### Request Logging
`index.ts` installs `logger()` from `hono/logger` on every route. It prints
one line per request and one per response, with method, path, status, and
elapsed time.

### Error Handler
`middleware/error.ts` logs every unhandled error as `ERROR_OCCURRED` with
`error`, `name`, `path`, `method`, and `timestamp`. It then returns the
standard error envelope with a `request_id`.

### Security
- Never log Spotify tokens, JWTs, or secrets.
- Truncate session IDs before logging. `TOKEN_REFRESH_FAILED` logs only the
  first 8 characters.

## Viewing Logs

Stream live logs from a deployed Worker:

```bash
cd src/backend
npx wrangler tail --env development
npx wrangler tail --env production --format json
```

`--format json` keeps the context objects parseable. Use `--status error` or
`--search <text>` to filter. Local `npm run dev` prints the same logs to the
terminal.

## Health Monitoring

`GET /health` is unauthenticated and does no dependency checks. It returns:

```json
{
  "data": {
    "status": "healthy",
    "service": "spotibye-backend",
    "environment": "production",
    "release_sha": "<git sha or unknown>",
    "release_version": "<version or unknown>",
    "deployed_at": "<ISO time or unknown>",
    "timestamp": "<ISO time>"
  }
}
```

`scripts/deploy-with-metadata.sh` injects `RELEASE_SHA`, `RELEASE_VERSION`,
and `DEPLOYED_AT` as Worker vars at deploy time. To check whether a deployed
Worker is behind the current branch, run from the repo root:

```bash
./scripts/backend-deploy-status.sh prod   # or: dev
```

## Queue Failures

The analysis queue consumer retries a failed message up to 3 times. After the
third attempt, it marks the job failed and acks the message, so these failures
never reach the dead-letter queue. Look for them in the logs instead. Only
messages whose invocation dies before acking, such as on a CPU-limit kill,
exhaust delivery retries and land in `spotibye-analysis-dlq` in production or
`spotibye-analysis-dev-dlq` in development.
