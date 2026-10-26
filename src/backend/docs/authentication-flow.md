# Authentication Flow Guide for Client Developers

This guide describes how a client authenticates against the SpotiBye backend. Authentication uses Spotify OAuth 2.0 (Authorization Code + PKCE), mediated by the backend, and an app-issued JWT for session management.

The reference client is the Python desktop app: `src/frontend/auth/backend_auth.py` (login orchestration and local callback server) and `src/frontend/services/backend_client.py` (HTTP calls). Route handlers live in `src/backend/routes/auth.ts`; the JWT check and Spotify token refresh live in `src/backend/middleware/auth.ts`.

## Overview

The authentication flow consists of three main steps:
1. **Initiate OAuth** - Ask the backend for a Spotify authorize URL and open it in a browser
2. **Handle Callback** - Capture `code` and `state` on the client's redirect URI and forward them to the backend, which returns a JWT
3. **Maintain Session** - Send the JWT as a Bearer token on authenticated requests

Spotify access and refresh tokens never leave the backend. The client only holds the app JWT.

### PKCE (Authorization Code + PKCE)

The flow is backend-mediated and uses PKCE (RFC 7636) in addition to the
confidential client secret. PKCE is handled entirely server-side, so the
client does not need to generate or send any verifier/challenge:

- On `POST /auth/spotify/login`, the backend generates a `code_verifier`,
  derives the S256 `code_challenge`, appends `code_challenge` and
  `code_challenge_method=S256` to the Spotify authorize URL, and persists the
  verifier alongside the `redirect_uri` under the one-time `oauth_state:<state>`
  key (`CACHE_KV`, 10-minute TTL).
- On the callback, the backend reads the verifier back from KV and includes it
  as `code_verifier` in the token exchange (still authenticated with the client
  secret via Basic auth).

## Prerequisites

- The redirect URI the client will use must be listed in `ALLOWED_REDIRECT_URIS` for the target environment (see `src/backend/wrangler.toml`) **and** registered in the Spotify Developer Dashboard for the app.
- The backend environment must have `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `JWT_SECRET` set.

Base URLs used below:
- Local: `http://localhost:8787` (`npm run dev`)
- Deployed: `https://spotibye-backend-<environment>.<your-subdomain>.workers.dev`, where `<environment>` is `development` or `production`

## Step 1: Initiate OAuth Flow

### API Endpoint
```
POST /auth/spotify/login
```

### Request Format
```bash
curl -X POST https://spotibye-backend-production.<your-subdomain>.workers.dev/auth/spotify/login \
  -H 'Content-Type: application/json' \
  -d '{"redirect_uri": "http://127.0.0.1:8080/callback"}'
```

### Parameters
- `redirect_uri` (required): Where Spotify will redirect the browser after authorization. Must exactly match an entry in `ALLOWED_REDIRECT_URIS`.

The client does not send `state`. The backend generates it (`crypto.randomUUID()`) and returns it.

### Response
```json
{
  "data": {
    "auth_url": "https://accounts.spotify.com/authorize?response_type=code&client_id=...&scope=user-read-private+user-read-email+playlist-read-private+playlist-read-collaborative&redirect_uri=...&state=...&code_challenge_method=S256&code_challenge=...",
    "state": "3f2c1a9e-..."
  }
}
```

Requested scopes: `user-read-private`, `user-read-email`, `playlist-read-private`, `playlist-read-collaborative`.

### Errors
| Status | `error.code` | Cause |
|--------|--------------|-------|
| 400 | `MISSING_REDIRECT_URI` | `redirect_uri` missing or empty |
| 400 | `DISALLOWED_REDIRECT_URI` | `redirect_uri` not in the allowlist (an empty allowlist rejects everything) |
| 500 | `OAUTH_INIT_FAILED` | Unexpected failure (for example, missing Spotify credentials) |

### Desktop Client Behaviour
`BackendAuth.login()` builds `redirect_uri` as `http://127.0.0.1:<OAUTH_CALLBACK_PORT>/callback` (port `8080` by default, overridable with `SPOTIBYE_OAUTH_PORT`), starts a local HTTP server on that address, and opens `auth_url` with `webbrowser.open`.

## Step 2: Handle OAuth Callback

Spotify redirects the browser to the client's `redirect_uri` with `code` and `state` (or `error`) as query parameters. The client then forwards them to the backend.

### API Endpoint
```
GET /auth/spotify/callback?code=<code>&state=<state>
```

### Request Format
```python
# src/frontend/services/backend_client.py
response = self._make_request(
    "GET", f"/auth/spotify/callback?code={code}&state={state}"
)
token = response.get("token")
```

### Backend Processing
1. Rejects the request if `error` is present, or if `code` or `state` is missing.
2. Looks up `oauth_state:<state>` in `CACHE_KV`. A missing or expired entry is rejected. This lookup is the CSRF check; the client does not need to verify `state` itself.
3. Exchanges the code with Spotify using the stored `redirect_uri` and `code_verifier`.
4. Deletes `oauth_state:<state>` (one-time use) after a successful exchange.
5. Fetches the Spotify profile (`GET /v1/me`).
6. Writes a session to `SESSIONS_KV` and signs a JWT (see [Session Storage](#session-storage)).

### Response Format
```json
{
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "spotify-user-id",
      "display_name": "Test User",
      "email": "test@example.com"
    },
    "expires_in": 2592000,
    "spotify_access_expires_in": 3600
  }
}
```

- `token` is the app JWT. No Spotify token is returned.
- `user` is the Spotify profile object as returned by Spotify.
- `expires_in` is the JWT and session lifetime in seconds (30 days).
- `spotify_access_expires_in` is the Spotify access token lifetime. It is informational; the backend refreshes the Spotify token itself.

### Errors
| Status | `error.code` | Cause |
|--------|--------------|-------|
| 400 | `OAUTH_ERROR` | Spotify returned `error` (for example, `access_denied`); `message` holds the Spotify value |
| 400 | `INVALID_CALLBACK` | Missing `code`/`state`, or unknown/expired state |
| 500 | `OAUTH_CALLBACK_FAILED` | Token exchange or profile fetch failed |
| 500 | `OAUTH_BAD_REQUEST` | Spotify returned a 4xx during the exchange |
| 500 | `OAUTH_TOKEN_EXPIRED` | Upstream error message contained "Token expired" |

The 500 responses include `error.details.reason` with the underlying error message.

## Step 3: Session Management

### Session Storage
| Store | Key | Value | TTL |
|-------|-----|-------|-----|
| `CACHE_KV` | `oauth_state:<state>` | `{ redirect_uri, code_verifier }` | 600 s |
| `SESSIONS_KV` | `<session_id>` (random UUID) | `{ user_id, access_token, refresh_token, expires_at }` (Spotify tokens; `expires_at` in ms) | 30 days |
| `SESSIONS_KV` | `REFRESH_FAILED:<session_id>` | `"1"` (negative cache after a revoked refresh token) | 60 s |

### JWT
- Signed HS256 with `JWT_SECRET` (`src/backend/services/jwt.ts`).
- Claims: `sub` (Spotify user id), `email`, `name` (display name), `session_id`, `iat`, `exp`.
- Lifetime: 30 days (`APP_JWT_TTL_SECONDS`, same as the session TTL).
- Verification checks the signature and `exp`. There is no clock-skew tolerance and no revocation list; deleting the session in KV is what invalidates a token.

### Client Token Storage
The desktop client persists the JWT through `cache_manager.save_auth_token(...)` for auto-login. On startup it discards a cached JWT whose `exp` has passed, then calls `GET /auth/me` to confirm the session is still valid.

### Spotify Token Refresh (automatic)
Clients never refresh Spotify tokens. On each authenticated request, `authMiddleware`:
1. Loads the session for the JWT's `session_id`. A missing or invalid session returns 401.
2. If the Spotify access token has expired, checks `REFRESH_FAILED:<session_id>`. If present, it returns 401 `AUTH_REQUIRED` without calling Spotify.
3. Otherwise refreshes with Spotify. Concurrent refreshes for the same session within one isolate share a single request. The updated session is written back with a fresh 30-day TTL.
4. If Spotify answers `invalid_grant`, it writes the `REFRESH_FAILED` marker, deletes the session, and returns 401 `AUTH_REQUIRED`. Other refresh failures return 401 `UNAUTHORIZED` ("Token expired").

### Reissuing the JWT
```
POST /auth/spotify/refresh
Authorization: Bearer <jwt>
```

This endpoint takes no body. It requires a still-valid JWT and issues a new JWT for the same session. It does not accept a Spotify refresh token. An expired JWT cannot be refreshed; the user must log in again.

```json
{
  "data": {
    "access_token": "<new app JWT>",
    "expires_in": 2592000,
    "token_type": "Bearer",
    "spotify_access_expires_in": 3412
  }
}
```

Note that the new JWT is returned as `access_token` here, while the callback returns it as `token`. The desktop client accepts either.

### Other Auth Endpoints
- `GET /auth/me` returns `{ "data": { "id", "email", "name", "session_id" } }` from the JWT claims.
- `POST /auth/logout` deletes the session and its `REFRESH_FAILED` marker, then returns `{ "data": { "message": "Logged out successfully" } }`. Any JWT for that session stops working.

## Step 4: Authenticated API Requests

Send the JWT on every request to `/auth/me`, `/auth/logout`, `/auth/spotify/refresh`, `/spotify/*`, `/analysis/*`, and `/export/*`:

```
Authorization: Bearer <jwt>
```

### Auth Error Responses
Auth failures in the middleware go through the global error handler:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Session expired or invalid",
    "timestamp": "2026-01-01T00:00:00.000Z",
    "request_id": "...",
    "details": { "path": "/spotify/playlists", "method": "GET" }
  }
}
```

| Status | `error.code` | `message` |
|--------|--------------|-----------|
| 401 | `UNAUTHORIZED` | `Missing or invalid authorization header` |
| 401 | `UNAUTHORIZED` | `Invalid token` (bad signature, malformed, or expired JWT) |
| 401 | `UNAUTHORIZED` | `Session expired or invalid` (no session in KV) |
| 401 | `UNAUTHORIZED` | `Token expired` (Spotify refresh failed for a non-revocation reason) |
| 401 | `AUTH_REQUIRED` | `Refresh token expired or revoked` |

On any of these, the client should clear its stored JWT and start a new login. The desktop client detects `AUTH_REQUIRED` with `BackendClient.is_auth_required_error()`.

## Security Notes

### State
- The backend generates `state` and stores it server-side. It is single-use and expires after 10 minutes.
- A callback whose `state` is not in KV is rejected, which covers CSRF and replay.

### Redirect URIs
`ALLOWED_REDIRECT_URIS` is a comma-separated exact-match allowlist. It fails closed when empty. Current values in `wrangler.toml`:

| Environment | Values |
|-------------|--------|
| Top-level (local `wrangler dev`) and `development` | `http://localhost:3000`, `http://localhost:3000/callback`, `http://localhost:8080`, `http://127.0.0.1:8080/callback` |
| `production` | `https://app.spotibye.com` |

The same URI must also be registered in the Spotify Developer Dashboard. If you change `SPOTIBYE_OAUTH_PORT`, add the matching `http://127.0.0.1:<port>/callback` to both.

### Token Handling
- Spotify tokens stay in `SESSIONS_KV`. Only the app JWT reaches the client.
- Treat the JWT as a 30-day bearer credential. Call `POST /auth/logout` to revoke it server-side.

## Common Issues and Solutions

### `DISALLOWED_REDIRECT_URI`
**Problem**: Login initiation returns 400
**Solution**: Add the exact `redirect_uri` (scheme, host, port, and path) to `ALLOWED_REDIRECT_URIS` for the environment

### `INVALID_CALLBACK` with "Missing or expired OAuth state"
**Problem**: The callback was forwarded more than 10 minutes after login started, was already used, or hit a different environment than the login request
**Solution**: Restart the login flow against the same backend

### Spotify `INVALID_CLIENT: Invalid redirect URI`
**Problem**: Spotify rejects the authorize URL
**Solution**: Register the redirect URI in the Spotify Developer Dashboard

### Repeated `AUTH_REQUIRED`
**Problem**: The Spotify refresh token was revoked (for example, the user removed app access)
**Solution**: Clear the stored JWT and log in again
