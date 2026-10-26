# SpotiBye API Documentation

This directory contains documentation for the SpotiBye Cloudflare Workers backend. The code is the source of truth; when a page and the code disagree, fix the page.

## Files Overview

| File | Contents |
|------|----------|
| [`api-examples.md`](api-examples.md) | Request/response examples for the auth, Spotify data, analysis, and export endpoints |
| [`authentication-flow.md`](authentication-flow.md) | Spotify OAuth + PKCE flow, JWT and session storage, automatic Spotify token refresh, and auth error responses |
| [`deployment-configuration.md`](deployment-configuration.md) | The `development` and `production` Workers, secrets, KV/queue/Durable Object bindings, deploy checks, and rollback |
| [`environment-variables.md`](environment-variables.md) | Worker variables and secrets, where each is configured, and how they are validated |
| [`kv-namespace-structure.md`](kv-namespace-structure.md) | KV keys the backend reads and writes, their TTLs, and cache invalidation |
| [`monitoring-logging.md`](monitoring-logging.md) | Structured logging, viewing logs, the `/health` endpoint, and queue failure handling |
| [`troubleshooting-guide.md`](troubleshooting-guide.md) | Diagnosis steps, common issues, and an error code reference |
| [`openapi.yaml`](openapi.yaml) | OpenAPI 3.0.3 specification of the API |
| [`swagger-ui.html`](swagger-ui.html) | Static Swagger UI page that renders `./openapi.yaml` |

## Viewing the OpenAPI Spec

The Worker does not serve these files. There is no hosted `/docs` route. To browse the spec in Swagger UI, serve this directory locally and open the page:

```bash
cd src/backend/docs
python3 -m http.server 8000
# open http://localhost:8000/swagger-ui.html
```

Swagger UI loads its assets from unpkg, so the page needs network access.

## API Overview

### Base URLs
- **Production**: `https://spotibye-backend-production.<your-subdomain>.workers.dev`
- **Development**: `https://spotibye-backend-development.<your-subdomain>.workers.dev`
- **Local**: `http://localhost:8787` (`npm run dev`)

### Authentication
The API uses an app-issued JWT. See [`authentication-flow.md`](authentication-flow.md) for details.

1. **Initiate OAuth**: `POST /auth/spotify/login`
2. **Handle Callback**: `GET /auth/spotify/callback`
3. **Use Token**: Include the JWT in the Authorization header: `Bearer <token>`

### Main Endpoints

Route handlers live in `src/backend/routes/`. Every route except `/health`, `/auth/spotify/login`, and `/auth/spotify/callback` requires a JWT.

#### System
- `GET /health` - Health check with release metadata

#### Authentication
- `POST /auth/spotify/login` - Initiate Spotify OAuth
- `GET /auth/spotify/callback` - Handle OAuth callback and issue a JWT
- `POST /auth/spotify/refresh` - Reissue the JWT for the current session
- `POST /auth/logout` - Delete the current session
- `GET /auth/me` - Get the current user from the JWT

#### Spotify Data
- `GET /spotify/playlists` - Get user playlists
- `GET /spotify/playlists/{id}` - Get playlist details
- `GET /spotify/playlists/{id}/items` - Get playlist items (`limit`, `offset`)
- `GET /spotify/playlists/{id}/tracks` - Backward-compatible alias for playlist items
- `GET /spotify/tracks/{id}` - Get track details

#### Analysis
- `POST /analysis/playlist/{id}` - Start playlist analysis
- `GET /analysis/playlist/{id}/status` - Get analysis status
- `GET /analysis/playlist/{id}/results` - Get analysis results
- `DELETE /analysis/playlist/{id}` - Delete stored analysis

#### Export
- `POST /export/playlist/{id}` - Generate a single-playlist export
- `GET /export/playlist/{id}/status` - Get export status
- `GET /export/playlist/{id}/download` - Download export
- `DELETE /export/playlist/{id}` - Clear stored exports for the playlist
- `POST /export/playlists`, `POST /export/playlists/chunk` - Batch export
- `GET /export/playlists/{jobId}/status`, `GET /export/playlists/{jobId}/download` - Batch export status and download
- `POST /export/jobs`, `POST /export/jobs/{jobId}/step` - Stepped export job
- `GET /export/jobs/{jobId}/status`, `GET /export/jobs/{jobId}/download` - Export job status and download

## Error Handling

Errors use a common envelope:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message"
  }
}
```

Errors raised through the global error handler (for example, auth failures) also include `timestamp`, `request_id`, and `details: { path, method }`. Some route-level errors include `details` with extra context.

Common HTTP statuses:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid token, or `AUTH_REQUIRED`)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error

The backend has no rate limiting of its own. `services/spotify.ts` absorbs Spotify 429s: it waits for `Retry-After` and retries, then throws `Max retries exceeded` without a status. Routes then return `500`, so the `429` / `SPOTIFY_RATE_LIMITED` responses in `openapi.yaml` are not reachable today.

## Response Formats
- JSON for API responses, wrapped in `{ "data": ... }`
- CSV, JSON, or XLSX files for export downloads

## Development

### Updating Documentation
1. Edit `openapi.yaml` with your changes
2. Check the result in Swagger UI (see above)
3. Update any related examples in `api-examples.md`

### Validation
Use an OpenAPI validator to check the spec:
```bash
npx @redocly/cli lint src/backend/docs/openapi.yaml
```
