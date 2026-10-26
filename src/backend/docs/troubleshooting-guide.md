# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the SpotiBye Cloudflare Workers backend.

## Quick Diagnosis

### Health Check
Set the backend URL once per shell. Your value is in `.desktop.env.local`.

```bash
export SPOTIBYE_PRODUCTION_BACKEND_URL=https://spotibye-backend-production.<your-subdomain>.workers.dev

curl "${SPOTIBYE_PRODUCTION_BACKEND_URL:?set SPOTIBYE_PRODUCTION_BACKEND_URL first}/health"
```

Use `SPOTIBYE_DEV_BACKEND_URL` the same way for the development Worker.

The `:?` guard stops the command when the variable is unset, instead of
requesting a bare `/health`.

Expected response:
```json
{
  "data": {
    "status": "healthy",
    "service": "spotibye-backend",
    "environment": "production",
    "release_sha": "<git sha>",
    "release_version": "<package.json version>",
    "deployed_at": "2026-01-01T00:00:00Z",
    "timestamp": "2026-01-01T00:05:00.000Z"
  }
}
```

The release fields read `unknown` when the Worker was deployed without
`scripts/deploy-with-metadata.sh`. To compare the live `release_sha` with your
checkout, run `./scripts/backend-deploy-status.sh prod` (or `dev`) from the repo root.

### Log Monitoring
```bash
cd src/backend

# View real-time logs
npx wrangler tail --env production   # or --env development

# Pretty output, errors only
npx wrangler tail --env production --format pretty --status error
```

Always pass `--env`. Without it, Wrangler targets a top-level `spotibye-backend`
Worker that is not deployed.

## Error Response Shape

Errors use this envelope:

```json
{ "error": { "code": "SESSION_NOT_FOUND", "message": "Session not found" } }
```

Errors from the global handler and export routes also include `request_id`.
The global handler adds `timestamp` and `details.path` / `details.method`.
Unhandled errors return `500` with code `INTERNAL_ERROR` and message
`Internal Server Error`. The real cause appears only in the `ERROR_OCCURRED` log line.

## Common Issues

### Every Request Returns 500

**Symptoms**: All routes, including `/health`, return `500 INTERNAL_ERROR`
**Cause**: `ENVIRONMENT`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, or
`JWT_SECRET` is missing or empty, or `ALLOWED_REDIRECT_URIS` is missing
entirely. `middleware/env.ts` checks them on the first request in each isolate.
An empty `ALLOWED_REDIRECT_URIS` is accepted. It only makes login reject every
`redirect_uri` with `DISALLOWED_REDIRECT_URI`.

**Diagnostics**: Look for `Invalid Worker environment bindings: <NAME>: ...` in
`npx wrangler tail --env <environment>`, then check
`npx wrangler secret list --env <environment>`.

**Solution**: For a secret, run `npx wrangler secret put <NAME> --env <environment>`.
For `ENVIRONMENT` or `ALLOWED_REDIRECT_URIS`, set it in that environment's
`vars` in `wrangler.toml`. See
[environment-variables.md](environment-variables.md).

### Authentication Problems

#### 401 Unauthorized Errors
**Symptoms**: API calls return 401 with code `UNAUTHORIZED` or `AUTH_REQUIRED`
**Causes** (message from `middleware/auth.ts`):
- `Missing or invalid authorization header`: The `Authorization: Bearer <jwt>` header is absent.
- `Invalid token`: The JWT signature is bad or the JWT has expired. It also appears after `JWT_SECRET` rotation.
- `Session expired or invalid`: The session is gone from `SESSIONS_KV` (30-day TTL, or deleted on logout).
- `Token expired`: The Spotify token expired and could not be refreshed.
- `AUTH_REQUIRED`: Spotify rejected the refresh token. The session is deleted, and the user must log in again.

**Solution**: Log in again. App JWTs and sessions both last 30 days.
`POST /auth/spotify/refresh` reissues the app JWT while the session still exists.

#### OAuth Login and Callback Failures
**Symptoms**: Login fails before or after Spotify authorization
**Causes**:
- `400 MISSING_REDIRECT_URI`: The `POST /auth/spotify/login` body has no valid `redirect_uri`.
- `400 DISALLOWED_REDIRECT_URI`: The `redirect_uri` is not in `ALLOWED_REDIRECT_URIS` for that environment. Matching is exact.
- `400 INVALID_CALLBACK`: The callback has no `code` or `state`, or the state has expired. OAuth state lives in `CACHE_KV` for 10 minutes and is single-use.
- `400 OAUTH_ERROR`: Spotify returned an `error` parameter, such as `access_denied`.
- `500 OAUTH_CALLBACK_FAILED` / `OAUTH_BAD_REQUEST`: The token exchange or profile fetch failed. Check `details.reason`. A mismatch between the redirect URI and the Spotify Developer Dashboard, or bad client credentials, shows up here.

### Spotify API Issues

#### Rate Limit Errors
**Symptoms**: `500` with a `*_FETCH_FAILED` or `EXPORT_*` code and a `Max retries exceeded` log line
**Behavior**: The backend has no rate limiter of its own. `services/spotify.ts` absorbs Spotify 429s: it waits for `Retry-After` and retries, then throws `Max retries exceeded` without a status. The
routes therefore return `500`, not `429`. Their `SPOTIFY_RATE_LIMITED` and
`EXPORT_*` 429 branches are unreachable today. Network errors back off
exponentially (1s, 2s). Other 4xx and 5xx responses are not retried.

**Solution**: Wait and retry. Cached responses reduce repeat calls. Playlists and
playlist tracks are cached for 5 minutes, playlist details for 10 minutes, and
tracks for 1 hour.

#### Spotify Token Errors
**Symptoms**: `401 SPOTIFY_TOKEN_EXPIRED` ("Spotify access token expired. Please log in again.")
**Cause**: Spotify rejected the access token after the auth middleware passed.
**Solution**: Log in again. If it recurs for all users, verify the Spotify client credentials.

### Export Issues

#### Export Failures
**Symptoms**: Export start, step, or chunk requests fail
**Causes**:
- `400 INVALID_PLAYLISTS`: The request body failed validation.
- `401` with an `EXPORT_*` code: Spotify returned 401. `details.upstream_status` shows it. Persistent Spotify rate limiting surfaces as a `500`, not a `429`.
- `503` with `details.cpu_limited: true`: The Worker hit its CPU time limit. Use the stepped jobs API (`POST /export/jobs`, then `POST /export/jobs/:jobId/step`) for large exports.
- `409 EXPORT_JOB_CONFLICT`: A step request carried a stale cursor or resume token. Re-read `/export/jobs/:jobId/status` and resume from there.
- `500 EXPORT_FAILED`, `EXPORT_START_FAILED`, `EXPORT_BATCH_FAILED`, `EXPORT_JOB_STEP_FAILED`: Unexpected failure. Check `wrangler tail --env <env>`.

#### Download Failures
**Symptoms**: 404 or 409 on a download route
**Causes**:
- `404 EXPORT_NOT_FOUND`, `EXPORT_JOB_NOT_FOUND`, or `EXPORT_DATA_NOT_FOUND`: The ID is wrong, or the export expired. Export status, data, and files are kept in `CACHE_KV` for 1 hour.
- `409 EXPORT_NOT_READY`: The job is not `completed` yet. Poll the status route first.
- `503 EXPORT_DOWNLOAD_FAILED` / `EXPORT_JOB_DOWNLOAD_FAILED`: Rendering the file failed.

**Solution**: Re-run the export if it expired.

### Analysis Issues

- `404 ANALYSIS_NOT_FOUND` / `ANALYSIS_RESULTS_NOT_FOUND`: No job or cached result exists for that playlist. Results expire after `ANALYSIS_RESULTS_TTL_SECONDS` (default 24 hours).
- A job stuck in a non-terminal status usually means the queue consumer failed. Look for `QUEUE_JOB_FAILED` or `QUEUE_MARK_FAILED_THREW` in `wrangler tail --env <env>`. On the third attempt the consumer marks the job failed and acks the message, so these failures do not reach the dead-letter queue. Non-retryable errors are acked on the first attempt. Only messages whose invocation dies before acking, such as on a CPU-limit kill, exhaust delivery retries and land in `spotibye-analysis-dlq` or `spotibye-analysis-dev-dlq`.

### KV Namespace Issues

**Symptoms**: Routes that read or write KV fail with 500
**Causes**:
- Wrong namespace ID in the `[env.*]` block of `wrangler.toml`
- Namespace deleted or created in another account

**Diagnostics**:
```bash
cd src/backend

# List namespaces in the account
npx wrangler kv namespace list

# Read a key from the deployed namespace (Wrangler defaults to local storage without --remote)
npx wrangler kv key get --binding CACHE_KV --env production --remote "<key>"
```

## Debugging Tools

### Local Development
```bash
cd src/backend

# Start local development server (reads .dev.vars)
npm run dev

# Use the development environment's bindings
npx wrangler dev --env development
```

### Remote Debugging
```bash
# Filter by text, method, or Worker version
npx wrangler tail --env production --search "OAUTH_CALLBACK_FAILED"
npx wrangler tail --env production --method POST
npx wrangler tail --env production --version-id <version-id>
```

Backend logs are structured JSON lines with an `event` field, such as
`ERROR_OCCURRED`, `TOKEN_REFRESH_FAILED`, and `SESSION_DELETED`. Search for the event name.

## Error Codes Reference

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request (validation error, bad OAuth callback)
- `401` - Unauthorized (missing or invalid JWT, expired session, Spotify 401)
- `404` - Not Found (unknown route, session, export, or analysis)
- `409` - Conflict (export not ready, stale export cursor)
- `500` - Internal Server Error (unexpected error, missing bindings)
- `503` - Service Unavailable (Worker CPU limit, export download failure)

### Common Error Codes
- `INTERNAL_ERROR`, `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `AUTH_REQUIRED` - Global handler and auth middleware
- `MISSING_REDIRECT_URI`, `DISALLOWED_REDIRECT_URI`, `INVALID_CALLBACK`, `OAUTH_ERROR`, `OAUTH_INIT_FAILED`, `OAUTH_CALLBACK_FAILED`, `OAUTH_BAD_REQUEST`, `OAUTH_TOKEN_EXPIRED`, `SESSION_NOT_FOUND`, `TOKEN_REFRESH_FAILED`, `LOGOUT_FAILED`, `USER_INFO_FAILED` - `routes/auth.ts`
- `SPOTIFY_TOKEN_EXPIRED`, `SPOTIFY_RATE_LIMITED`, `PLAYLISTS_FETCH_FAILED`, `PLAYLIST_FETCH_FAILED`, `PLAYLIST_TRACKS_FETCH_FAILED`, `TRACK_FETCH_FAILED` - `routes/spotify.ts`
- `ANALYSIS_*` - `routes/analysis.ts`
- `EXPORT_*`, `INVALID_PLAYLISTS` - `routes/export/`

## Recovery Procedures

### Emergency Rollback
```bash
cd src/backend

# List recent deployments
npx wrangler deployments list --env production

# Roll back to a specific version
npx wrangler rollback --env production <version-id>

# Roll back to the previous version
npx wrangler rollback --env production
```

After a rollback, `/health` reports the older `release_sha`.

### Data Recovery
KV data here is cache and session state with TTLs. There is no backup to restore.
To inspect keys:

```bash
npx wrangler kv key list --binding CACHE_KV --env production --remote --prefix "<prefix>"
```

### Service Recovery
```bash
# Check service health
curl -f "${SPOTIBYE_PRODUCTION_BACKEND_URL:?set SPOTIBYE_PRODUCTION_BACKEND_URL first}/health" || echo "Service down"

# Redeploy the current checkout (from src/backend)
npm run deploy:prod

# Clear a problematic cache entry
npx wrangler kv key delete --binding CACHE_KV --env production --remote "<key>"
```

## Prevention Strategies

### Monitoring Setup
- Watch `wrangler tail --env production` error rates after each deploy
- Track KV operation failures
- Watch Spotify API quota usage

### Regular Maintenance
- Rotate secrets quarterly
- Review logs for anomalies
- Update dependencies monthly

### Testing Practices
- Run `npm run test:run` and `npm run lint` before deployment
- Test with large playlists
- Verify error handling paths

## Contact Support

When reporting issues, include:
- Environment (development/production)
- Error code, message, and `request_id`
- Request/response logs
- Steps to reproduce
- Client and app version

Report code and deployment problems in GitHub Issues.
