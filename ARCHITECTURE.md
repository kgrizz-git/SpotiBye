# ARCHITECTURE.md

> Top-level architectural map of SpotiBye. Start here when reasoning about where code lives, what depends on what, and why.

---

## System Overview

SpotiBye is a two-tier application:

```
[User Desktop]
  Python CustomTkinter GUI (src/frontend/)
      ↕ HTTPS REST
[Cloudflare Edge]
  Cloudflare Worker — Hono framework (src/backend/)
      ↕ HTTPS REST
[Spotify API]
  api.spotify.com
```

The frontend is a local desktop executable. It never calls Spotify directly — all Spotify API traffic is proxied through the backend. This keeps secrets server-side and allows token refresh without the user re-authenticating.

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
| `routes/auth.ts` | OAuth PKCE initiation, callback, token exchange, logout |
| `routes/spotify.ts` | Playlist listing, track fetching, audio features |
| `routes/export.ts` | Batch export jobs, resumable export assembly, format conversion |
| `routes/analysis.ts` | Playlist analysis and scoring |
| `middleware/auth.ts` | JWT verification middleware |
| `middleware/error.ts` | Global error handler |
| `services/spotify.ts` | Spotify API client — all `api.spotify.com` fetch calls live here |
| `services/spotify-auth.ts` | Token refresh, OAuth exchange |
| `services/export.ts` | Export logic: CSV/XLSX/JSON generation, cursor persistence |
| `services/analysis.ts` | Analysis scoring logic |
| `services/cache.ts` | KV-backed cache with namespaced keys |
| `services/jwt.ts` | JWT sign/verify using HMAC-SHA256 (no external library) |
| `services/reccobeats.ts` | ReccoBeats audio features API client |
| `types/auth.ts` | JWT payload shape, token TTL constants |
| `types/env.ts` | Cloudflare Worker `Env` bindings interface |
| `types/spotify.ts` | Spotify API response shapes |
| `types/api.ts` | Shared API response envelope types |
| `types/variables.ts` | Shared constants |

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

---

## Auth Flow (PKCE)

1. Frontend opens a local HTTP server on a random port to receive the OAuth callback
2. Frontend calls `GET /auth/login` on the backend with a PKCE `code_challenge`
3. Backend redirects the user's browser to Spotify's authorization endpoint
4. Spotify redirects to the backend callback URL with `code`
5. Backend exchanges `code` for `access_token` + `refresh_token` with Spotify
6. Backend issues a signed JWT to the frontend containing `user_id` and `access_token`
7. Frontend stores the JWT locally; sends it as `Authorization: Bearer <jwt>` on every request

**Why JWT instead of session cookies:** The frontend is a native desktop app, not a browser. Cookies are not natively managed. JWTs are stored locally and sent explicitly. See `services/jwt.ts` for the HMAC-SHA256 implementation (no external JWT library is used, avoiding a dependency that would be opaque to agents).

Full flow doc: [docs/authentication-flow.md](docs/authentication-flow.md)

---

## Export Flow

1. User selects playlist(s) and format (CSV / XLSX / JSON)
2. Frontend calls `POST /export/batch` — backend creates a job record in KV
3. Backend fetches tracks page-by-page, writing a cursor to KV after each page
4. If the worker is interrupted, the next invocation resumes from the last cursor
5. When all pages are fetched, backend assembles the file and marks the job complete
6. Frontend polls `GET /export/batch/:job_id` until `status === 'completed'`
7. Frontend downloads the assembled file

Cursor persistence design: [docs/design-docs/resumable-export-cursors.md](docs/design-docs/resumable-export-cursors.md)

---

## Caching Strategy

All cache keys follow the pattern: `<user_id>:<resource_type>:<identifier>`

Examples:
- `abc123:playlists:all` — full playlist list for user `abc123`
- `abc123:tracks:playlist_456` — tracks for playlist `456`

Cache is backed by Cloudflare KV. TTLs are set per resource type in `types/variables.ts`.

---

## Key External Dependencies

| Dependency | Why used | Agent notes |
|-----------|---------|-------------|
| [Hono](https://hono.dev) | Lightweight, Cloudflare-native HTTP framework | Well-documented; prefer Hono middleware patterns over custom solutions |
| Cloudflare KV | Persistent key-value store for cache + job state | Has eventual-consistency caveats; don't use for counters |
| Cloudflare Workers | Edge serverless runtime | CPU time limit 30s (unbundled); see `docs/references/cloudflare-workers-constraints.md` |
| CustomTkinter | Python GUI toolkit | Limited agent training data; keep UI layer thin |
| Spotify Web API | Music data source | See `docs/references/spotify-api-reference.md` and `docs/february-2026-spotify-migration-findings.md` |
