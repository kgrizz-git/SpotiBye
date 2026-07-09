# ARCHITECTURE.md

> Top-level architectural map of SpotiBye. Start here when reasoning about where code lives, what depends on what, and why.

---

## System Overview

SpotiBye is a two-tier application:

```
[User Desktop]
  Python Kivy/KivyMD GUI (src/frontend/)
      ↕ HTTPS REST
[Cloudflare Edge]
  Cloudflare Worker — Hono framework (src/backend/)
      ↕ HTTPS REST
[Spotify API]
  api.spotify.com
```

The frontend is a local desktop executable. It never calls Spotify directly — all Spotify API traffic is proxied through the backend. This keeps secrets server-side and allows transparent token refresh without the user re-authenticating.

---

## Backend: Domain and Layer Breakdown

### Layer Contract

```
routes/          ← HTTP entry points; validate inputs, delegate to services
    ↓
middleware/      ← Cross-cutting: auth verification, error handling
    ↓
services/        ← Business logic; all external I/O happens here
    ↓
types/           ← Shared TypeScript interfaces and enums; no logic
```

**Dependency rules (enforced by ESLint and structural test):**
- `routes/` may import from `services/`, `middleware/`, and `types/`
- `services/` may import from `types/` only — never from `routes/` or `middleware/`
- `middleware/` may import from `services/` and `types/`
- `types/` has no internal imports
- A route file must not import from another route file
- All calls to `api.spotify.com` must go through `services/spotify.ts`

### Files

| File | Responsibility |
|------|---------------|
| `routes/auth.ts` | OAuth PKCE flow: `POST /auth/spotify/login`, `GET /auth/spotify/callback`, `POST /auth/spotify/refresh`, `POST /auth/logout`, `GET /auth/me` |
| `routes/spotify.ts` | Playlists and tracks: `GET /spotify/playlists`, `GET /spotify/playlists/:id`, `GET /spotify/playlists/:id/items`, `GET /spotify/playlists/:id/tracks` (alias), `GET /spotify/tracks/:id`, `GET /spotify/tracks/:id/audio-features` |
| `routes/export/index.ts` | Composed Hono sub-app: mounts `jobsApp` at `/jobs`, `playlistsApp` at `/playlists`, `playlistApp` at `/playlist`. Sub-routers live at `routes/export/{jobs,playlists,playlist}.ts`; helpers at `routes/export/helpers/`. Single-playlist export (`POST /export/playlist/:id`), combined export (`POST /export/playlists`), chunked combined export (`POST /export/playlists/chunk`), resumable job API (`POST /export/jobs`, `POST /export/jobs/:jobId/step`, `GET /export/jobs/:jobId/status`, `GET /export/jobs/:jobId/download`), status and download endpoints for each |
| `routes/analysis.ts` | Playlist analysis job lifecycle: `POST /analysis/playlist/:id`, `GET /analysis/playlist/:id/status`, `GET /analysis/playlist/:id/results`, `DELETE /analysis/playlist/:id` |
| `middleware/auth.ts` | JWT verification; loads full session from SESSIONS_KV; transparently refreshes Spotify access token when expired |
| `middleware/error.ts` | Global error → structured `ErrorResponse` |
| `services/spotify.ts` | Spotify API client — **only** caller of `api.spotify.com` |
| `services/spotify-auth.ts` | OAuth code exchange, token refresh, user profile fetch |
| `services/export.ts` | Export logic: CSV/XLSX/JSON generation, resumable job state machine, cursor persistence, render modes (rich/lite/auto) |
| `services/analysis.ts` | Playlist analysis using Spotify track metadata — computes overview stats, artist diversity, genre distribution, insights. No external analysis API dependency. |
| `services/cache.ts` | KV wrapper with namespaced keys |
| `services/jwt.ts` | JWT sign/verify using HMAC-SHA256 (no external library) |
| `types/auth.ts` | `JWTPayload` (contains `session_id`, not access token), `AuthTokens`, `SessionData`, TTL constants |
| `types/env.ts` | Cloudflare Worker `Env` bindings — `CACHE_KV`, `SESSIONS_KV`, Spotify credentials, `JWT_SECRET` |
| `types/spotify.ts` | Spotify response shapes |
| `types/spotify-api.ts` | API response schemas, `parseSpotifyResponse()` |
| `types/api.ts` | `ErrorResponse` envelope |
| `types/variables.ts` | Hono context variable types |

---

## Frontend: Domain and Layer Breakdown

### Layer Contract

```
screens/         ← Top-level UI screens; orchestrate service calls
    ↓
services/        ← Backend API client calls, business logic
    ↓
auth/            ← OAuth token storage and refresh
caching/         ← Local response caching
config/          ← App configuration loading
    ↓
ui/              ← Reusable UI components (leaf nodes, no business logic)
utils/           ← Pure utility functions (no imports from other app layers)
```

**Dependency rules:**
- `screens/` may import from `services/`, `ui/`, `config/`, `utils/`
- `services/` may import from `auth/`, `caching/`, `config/`, `utils/`
- `ui/` must not import from `screens/` or `services/`
- `utils/` must not import from any other app layer
- `auth/` may import from `config/` and `utils/` only

### UI Component Split: `BackendPlaylistCard`

`src/frontend/ui/backend_playlist_card.py` is a thin orchestrator that preserves the public `BackendPlaylistCard` API while delegating implementation details to focused helper modules:

- `backend_playlist_card_utils.py` — pure helpers such as `_mood_label`
- `backend_playlist_card_ui.py` — card layout, checkbox wiring, graphics updates
- `backend_playlist_card_interaction.py` — touch, single-click, double-click, long-press handling
- `backend_playlist_card_analysis_popup.py` — analysis popup construction and async analysis updates
- `backend_playlist_card_tracks_popup.py` — track-list popup construction and async track loading

The runtime class uses mixin inheritance with `BoxLayout` last in the MRO so Kivy event dispatch stays intact while each concern remains under the file-length target.

---

## Auth Flow (PKCE)

1. Frontend opens a local HTTP server on a random port to receive the OAuth callback
2. Frontend calls `POST /auth/spotify/login` on the backend with a PKCE `code_challenge`
3. Backend redirects the user's browser to Spotify's authorization endpoint
4. Spotify redirects to the backend callback URL with `code`
5. Backend exchanges `code` for `access_token` + `refresh_token` with Spotify
6. Backend creates a session record in `SESSIONS_KV` (stores access/refresh tokens + expiry) and issues a signed JWT to the frontend containing `user_id`, `session_id`, and user metadata — **not** the access token directly
7. Frontend stores the JWT locally; sends it as `Authorization: Bearer <jwt>` on every request
8. `middleware/auth.ts` verifies the JWT, loads the full session from `SESSIONS_KV`, and transparently refreshes the Spotify access token if it has expired before delegating to the route handler

**Why session-backed JWT:** The JWT is long-lived (30 days) but contains only a `session_id`. The actual Spotify access token (1 hour TTL) lives in `SESSIONS_KV` and is refreshed transparently by the middleware. This avoids re-issuing JWTs on every token refresh and keeps short-lived secrets out of the JWT payload.

Full flow doc: [dev-docs/guides/authentication-flow.md](dev-docs/guides/authentication-flow.md)

---

## Export Flow

### Resumable Job API (primary path for multi-playlist exports)

1. Frontend calls `POST /export/jobs` with `playlist_ids` and format — backend creates a job record in KV and returns a `job_id`
2. Frontend calls `POST /export/jobs/:jobId/step` repeatedly, advancing a cursor through playlists (1–3 per step, respects CPU time limits)
3. Each step validates the cursor/resume token to prevent stale concurrent writes; returns `409` on conflict with the latest cursor
4. When all playlists are processed, the final step pre-builds the file bytes (XLSX rich/lite or CSV) and caches them in KV
5. Frontend polls `GET /export/jobs/:jobId/status` until `status === 'completed'`
6. Frontend downloads via `GET /export/jobs/:jobId/download?mode=rich|lite|auto`

### Single-playlist path

`POST /export/playlist/:id` — synchronous, returns completed status in one call. Pre-builds file bytes in KV for zero-CPU download.

### Combined (legacy batch) path

`POST /export/playlists` — synchronous combined export for multiple playlists. `POST /export/playlists/chunk` — incremental version that carries state across invocations via `job_id` cursor.

---

## Analysis Flow

1. Frontend calls `POST /analysis/playlist/:id`
2. Backend checks KV for an existing completed, queued, or actively-processing job; returns it if found
3. Otherwise, writes `queued` status to KV and sends a small message to `ANALYSIS_QUEUE`
4. The Worker queue consumer loads the session from `SESSIONS_KV`, refreshes the Spotify token if needed, writes `processing`, and runs `AnalysisService`
5. Analysis fetches all tracks from Spotify, computes stats (track count, duration, artist diversity, genre distribution, text insights), and adds best-effort ReccoBeats audio-feature summary data when available
6. Results are written to KV under `analysis:<playlistId>:<userId>:results`; status updates to `completed`, `retrying`, or `failed`
7. Frontend polls `GET /analysis/playlist/:id/status` then fetches `GET /analysis/playlist/:id/results`

---

## Caching Strategy

**Backend (Cloudflare KV):**

Cache keys in the backend do not follow a single format — each service uses its own scheme:

| Resource | Key pattern | TTL |
|----------|-------------|-----|
| Playlists | `playlists:v2:<userId>` | 5 min |
| Single playlist | `playlist:<playlistId>` | 10 min |
| Playlist tracks | `playlist:<playlistId>:tracks:<limit>:<offset>` | 5 min |
| Track | `track:<trackId>` | 1 hr |
| Audio features | `track:<trackId>:audio-features` | 1 hr |
| Analysis status | `analysis:<playlistId>:<userId>:status` | 1 hr |
| Analysis results | `analysis:<playlistId>:<userId>:results` | 24 hr |
| Export job | `export:job:<jobId>:<userId>` | 1 hr |
| Export file bytes | `export:job:<jobId>:<userId>:file[:<mode>]` | 1 hr |
| Batch export job | `export:batch:<jobId>:<userId>` | 1 hr |
| Batch export data | `export:batch:<jobId>:<userId>:data` | 1 hr |
| Batch export file | `export:batch:<jobId>:<userId>:file` | 1 hr |
| Single export status | `export:<playlistId>:<userId>` | 1 hr |
| Single export data | `export:<playlistId>:<userId>:data` | 1 hr |
| Single export file | `export:<playlistId>:<userId>:file` | 1 hr |

Sessions are stored separately in `SESSIONS_KV` (not `CACHE_KV`) with a 30-day TTL.

**Frontend (Python disk cache):**

`BackendCacheManager` maintains a local disk cache at `~/.spotibye/cache/` for tokens, job state, and analysis results. This layer is checked before calling the backend. Its TTLs are longer than the backend's KV TTLs, so the frontend can serve stale data even after the backend would have refreshed from Spotify.

---

## Key External Dependencies

| Dependency | Why used | Agent notes |
|-----------|---------|-------------|
| [Hono](https://hono.dev) | Lightweight, Cloudflare-native HTTP framework | Well-documented; prefer Hono middleware patterns over custom solutions |
| Cloudflare KV (`CACHE_KV`) | Cache for playlists, tracks, analysis, export data | Eventual consistency — don't use for counters or mutex state |
| Cloudflare KV (`SESSIONS_KV`) | Session storage — access/refresh tokens keyed by session_id | 30-day TTL; auth middleware reads this on every authenticated request |
| Cloudflare Workers | Edge serverless runtime | CPU time limit applies; export steps are bounded to 1–3 playlists to stay within budget |
| Kivy/KivyMD | Python GUI toolkit | Dynamic widget/event system; keep UI layer thin and boundary-validated |
| Spotify Web API | Music data source | See `dev-docs/references/spotify-api-reference.md` and `dev-docs/investigations/february-2026-spotify-migration-findings.md` |
