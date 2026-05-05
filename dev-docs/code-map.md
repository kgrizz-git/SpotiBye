# Code Map

> Definitive file map generated from actual imports starting at `run_frontend_backend.py`.
> Use this to orient quickly in the codebase without reading every file.
> Last updated: 2026-05.

---

## Entrypoint

```
run_frontend_backend.py
  └─ src.frontend.app.SpotifyExporterApp   (re-exported from backend_app.py)
```

There is a second, legacy entrypoint — `python -m spotify_playlist_exporter_v2` — that runs the original standalone desktop app without the Cloudflare backend. It is still functional but not the primary path.

---

## Top-Level Module Map

```mermaid
graph TD
    ENTRY["run_frontend_backend.py"]

    subgraph FE ["src/frontend/ — backend-integrated layer"]
        APP["app/backend_app.py\nBackendSpotifyExporterApp"]
        AUTH_FE["auth/backend_auth.py\nBackendAuthenticator"]
        LOGIN_FE["auth/backend_login_screen.py\nBackend login UI"]
        CLIENT["services/backend_client.py\nBackendClient (HTTP)"]
        RB_FE["services/reccobeats_backend.py\nReccoBeats via backend"]
        CACHE_FE["caching/backend_cache.py\nBackendCacheManager"]
        CFG["config/backend_config.py\nURLs · flags · timeouts"]
        ADAPTER["screens/backend_main_screen_adapter.py\nWraps original MainScreen"]
        CACHE_EXP_ADAPTER["screens/cache_explorer_adapter.py"]
        SEL["ui/backend_selector_popup.py\nBackend URL picker"]
        CACHE_UI["ui/backend_cache_explorer.py"]
        NET["utils/network_utils.py\nretry · error helpers"]
    end

    subgraph V2 ["src/spotify_playlist_exporter_v2/ — original app (wrapped)"]
        V2_APP["app.py\nSpotifyExporterApp (original)"]
        V2_CFG["config.py"]
        V2_LOG["logging_config.py"]
        V2_STATE["state.py"]
        V2_LOGIN["auth/login_screen.py"]
        V2_HTTP["auth/http_handler.py"]
        V2_MAIN["screens/main_screen.py\noriginal MainScreen"]
        V2_RB["services/reccobeats.py\nReccoBeats direct HTTP"]
        V2_PCACHE["caching/persistent_cache.py"]
        V2_TCACHE["caching/track_cache.py"]
        V2_ACACHE["caching/analysis.py"]
        V2_CARD["ui/playlist_card.py"]
        V2_CEXP["ui/cache_explorer.py"]
        V2_IMG["ui/cached_async_image.py"]
        V2_HOVER["ui/hover_manager.py"]
        V2_LAYOUT["ui/layouts.py"]
        V2_TRACKS["ui/tracks_window.py"]
        V2_PLAT["utils/platform_utils.py"]
    end

    ENTRY --> APP
    APP --> AUTH_FE & CLIENT & CACHE_FE & CFG & ADAPTER & SEL & V2_LOG & V2_PLAT
    AUTH_FE --> CLIENT & CFG
    LOGIN_FE --> AUTH_FE & CLIENT & NET
    CLIENT --> CFG
    RB_FE --> CLIENT & NET
    CACHE_FE --> CFG & CLIENT
    ADAPTER --> CLIENT & RB_FE & NET & V2_LOG & V2_MAIN
    CACHE_EXP_ADAPTER --> CACHE_UI & CFG & V2_CEXP & V2_LOG
    SEL --> CFG & CLIENT
    CACHE_UI --> V2_CEXP & V2_LOG

    V2_APP --> V2_CFG & V2_LOG & V2_STATE & V2_LOGIN & V2_MAIN & V2_PLAT
    V2_LOGIN --> V2_CFG & V2_LOG & V2_STATE & V2_HTTP
    V2_HTTP --> V2_LOG & V2_STATE
    V2_MAIN --> V2_CFG & V2_LOGIN & V2_LOG & V2_RB & V2_STATE & V2_PCACHE & V2_TCACHE & V2_ACACHE & V2_CARD & V2_CEXP
    V2_RB --> V2_CFG & V2_LOG
    V2_PCACHE --> V2_CFG & V2_LOG
    V2_TCACHE --> V2_LOG & V2_PCACHE
    V2_ACACHE --> V2_LOG & V2_STATE & V2_PCACHE
    V2_CARD --> V2_ACACHE & V2_PCACHE & V2_TCACHE & V2_LOG
    V2_CEXP --> V2_PCACHE & V2_TCACHE & V2_LOG
    V2_IMG --> V2_PCACHE & V2_LOG
    V2_TRACKS --> V2_LOG & V2_LOGIN
```

---

## HTTP Boundary: Frontend → Backend

The Python frontend never calls Spotify directly. All external API traffic goes through `BackendClient`.

```mermaid
sequenceDiagram
    participant UI as Python UI (Kivy)
    participant BC as BackendClient
    participant W as Cloudflare Worker (index.ts)
    participant MW as middleware/auth.ts
    participant SVC as services/*
    participant KV as Cloudflare KV
    participant SP as api.spotify.com

    UI->>BC: get_playlists() / analyze_playlist() / export_playlists()
    BC->>W: HTTP + Authorization: Bearer <JWT>
    W->>MW: verify JWT
    MW->>SVC: delegate to route handler
    SVC->>KV: read/write cache or job state
    SVC->>SP: fetch (only via services/spotify.ts)
    SP-->>SVC: response
    SVC-->>W: result
    W-->>BC: JSON response
    BC-->>UI: parsed data
```

---

## Backend Layer Breakdown

```mermaid
graph TD
    IDX["index.ts\nHono app · CORS · /health"]

    subgraph Routes
        R_AUTH["routes/auth.ts\nPOST /auth/spotify/login\nGET  /auth/spotify/callback"]
        R_SP["routes/spotify.ts\nGET /spotify/playlists"]
        R_AN["routes/analysis.ts\nPOST /analysis/playlist/:id\nGET  /analysis/playlist/:id/status\nGET  /analysis/playlist/:id/results\nDELETE /analysis/playlist/:id"]
        R_EX["routes/export.ts\nPOST /export/playlists\nGET  /export/job/:id"]
    end

    subgraph Middleware
        MW_AUTH["middleware/auth.ts\nJWT verify · token refresh"]
        MW_ERR["middleware/error.ts\nglobal error handler"]
    end

    subgraph Services
        SV_SP["services/spotify.ts\n⚡ ONLY caller of api.spotify.com"]
        SV_SPAUTH["services/spotify-auth.ts\nOAuth exchange · token refresh"]
        SV_JWT["services/jwt.ts\nHMAC-SHA256 sign/verify"]
        SV_CACHE["services/cache.ts\nKV wrapper"]
        SV_AN["services/analysis.ts\nfetch tracks → call ReccoBeats"]
        SV_EX["services/export.ts\nCSV/XLSX/JSON assembly · cursors"]
    end

    subgraph Types
        T_AUTH["types/auth.ts"]
        T_SP["types/spotify.ts"]
        T_SPAPI["types/spotify-api.ts"]
        T_ENV["types/env.ts"]
        T_VARS["types/variables.ts"]
        T_API["types/api.ts"]
    end

    IDX --> R_AUTH & R_SP & R_AN & R_EX & MW_ERR
    R_AUTH --> SV_SPAUTH & SV_JWT & SV_CACHE
    R_SP --> MW_AUTH & SV_SP & SV_CACHE
    R_AN --> MW_AUTH & SV_AN & SV_CACHE
    R_EX --> MW_AUTH & SV_EX & SV_CACHE
    MW_AUTH --> SV_JWT & SV_SPAUTH
    SV_AN --> SV_SP
    SV_EX --> SV_SP
    SV_SPAUTH --> T_AUTH & T_SP
    SV_SP --> T_SP & T_SPAPI
    SV_JWT --> T_AUTH
```

---

## File Index

### src/frontend/ — backend-integrated layer

| File | Class / Role |
|------|-------------|
| [app/backend_app.py](../src/frontend/app/backend_app.py) | `BackendSpotifyExporterApp` — Kivy MDApp; boot sequence, screen management |
| [app/__init__.py](../src/frontend/app/__init__.py) | re-exports `SpotifyExporterApp` |
| [auth/backend_auth.py](../src/frontend/auth/backend_auth.py) | `BackendAuthenticator` — OAuth callback server, token exchange |
| [auth/backend_login_screen.py](../src/frontend/auth/backend_login_screen.py) | `BackendLoginScreen` — Kivy login UI |
| [services/backend_client.py](../src/frontend/services/backend_client.py) | `BackendClient`, `BackendAPIError` — all HTTP to Cloudflare Worker |
| [services/reccobeats_backend.py](../src/frontend/services/reccobeats_backend.py) | `ReccoBeatsBackendService` — analysis requests via backend |
| [caching/backend_cache.py](../src/frontend/caching/backend_cache.py) | `BackendCacheManager` — disk cache for tokens, jobs, analysis |
| [config/backend_config.py](../src/frontend/config/backend_config.py) | URLs, feature flags, timeouts, `OAUTH_CALLBACK_PORT` |
| [screens/backend_main_screen_adapter.py](../src/frontend/screens/backend_main_screen_adapter.py) | `BackendMainScreenAdapter` — bridges original `MainScreen` to backend services |
| [screens/cache_explorer_adapter.py](../src/frontend/screens/cache_explorer_adapter.py) | Bridges `CacheExplorer` widget to backend-aware version |
| [ui/backend_selector_popup.py](../src/frontend/ui/backend_selector_popup.py) | `BackendSelectorPopup` — startup URL picker |
| [ui/backend_cache_explorer.py](../src/frontend/ui/backend_cache_explorer.py) | `BackendCacheExplorer` — enhanced cache browser |
| [utils/network_utils.py](../src/frontend/utils/network_utils.py) | Network monitoring, retry decorators, `BackendAPIError` helpers |

### src/spotify_playlist_exporter_v2/ — original app (wrapped)

| File | Class / Role |
|------|-------------|
| [app.py](../src/spotify_playlist_exporter_v2/app.py) | `SpotifyExporterApp` — original Kivy MDApp (standalone mode) |
| [__main__.py](../src/spotify_playlist_exporter_v2/__main__.py) | CLI entry (`python -m spotify_playlist_exporter_v2`) |
| [config.py](../src/spotify_playlist_exporter_v2/config.py) | OAuth creds, local cache paths, timeouts |
| [logging_config.py](../src/spotify_playlist_exporter_v2/logging_config.py) | Logger setup — used by both standalone and backend paths |
| [state.py](../src/spotify_playlist_exporter_v2/state.py) | Global export job state |
| [auth/login_screen.py](../src/spotify_playlist_exporter_v2/auth/login_screen.py) | `LoginScreen` — Kivy login UI for standalone OAuth |
| [auth/http_handler.py](../src/spotify_playlist_exporter_v2/auth/http_handler.py) | Local HTTP server that handles Spotify OAuth callback |
| [screens/main_screen.py](../src/spotify_playlist_exporter_v2/screens/main_screen.py) | `MainScreen` — playlist grid, export trigger, original UI |
| [services/reccobeats.py](../src/spotify_playlist_exporter_v2/services/reccobeats.py) | `ReccoBeatsAPI` — direct HTTP to ReccoBeats (standalone path only) |
| [caching/persistent_cache.py](../src/spotify_playlist_exporter_v2/caching/persistent_cache.py) | `PersistentCache` — JSON disk cache (`~/.spotibye/cache/`) |
| [caching/track_cache.py](../src/spotify_playlist_exporter_v2/caching/track_cache.py) | Track-level cache helpers |
| [caching/analysis.py](../src/spotify_playlist_exporter_v2/caching/analysis.py) | Analysis task state + cache coordination |
| [ui/playlist_card.py](../src/spotify_playlist_exporter_v2/ui/playlist_card.py) | `PlaylistCard` — card widget; direct ReccoBeats entry point in standalone mode |
| [ui/cache_explorer.py](../src/spotify_playlist_exporter_v2/ui/cache_explorer.py) | `CacheExplorer` — disk cache browser popup |
| [ui/cached_async_image.py](../src/spotify_playlist_exporter_v2/ui/cached_async_image.py) | `CachedAsyncImage` — image loading with disk cache |
| [ui/hover_manager.py](../src/spotify_playlist_exporter_v2/ui/hover_manager.py) | Hover effect state manager |
| [ui/layouts.py](../src/spotify_playlist_exporter_v2/ui/layouts.py) | Responsive grid layout |
| [ui/tracks_window.py](../src/spotify_playlist_exporter_v2/ui/tracks_window.py) | Track list window |
| [utils/platform_utils.py](../src/spotify_playlist_exporter_v2/utils/platform_utils.py) | Platform-specific diagnostics, window setup |

### src/backend/ — Cloudflare Worker (TypeScript)

| File | Class / Role |
|------|-------------|
| [index.ts](../src/backend/index.ts) | Hono app entry — mounts routes, CORS, `/health` |
| [middleware/auth.ts](../src/backend/middleware/auth.ts) | JWT verification, Spotify token refresh on every authenticated request |
| [middleware/error.ts](../src/backend/middleware/error.ts) | Global error → structured `ErrorResponse` |
| [routes/auth.ts](../src/backend/routes/auth.ts) | `POST /auth/spotify/login`, `GET /auth/spotify/callback` |
| [routes/spotify.ts](../src/backend/routes/spotify.ts) | `GET /spotify/playlists` (KV-cached) |
| [routes/analysis.ts](../src/backend/routes/analysis.ts) | Analysis job lifecycle — see known gap below |
| [routes/export.ts](../src/backend/routes/export.ts) | Two-phase resumable export |
| [services/spotify.ts](../src/backend/services/spotify.ts) | **Only** caller of `api.spotify.com` — playlists, tracks, audio features |
| [services/spotify-auth.ts](../src/backend/services/spotify-auth.ts) | OAuth code exchange, token refresh |
| [services/jwt.ts](../src/backend/services/jwt.ts) | HMAC-SHA256 JWT sign/verify (no external library) |
| [services/cache.ts](../src/backend/services/cache.ts) | KV wrapper with namespaced keys |
| [services/analysis.ts](../src/backend/services/analysis.ts) | Fetches tracks + audio features, POSTs to ReccoBeats — results NOT persisted (known gap) |
| [services/export.ts](../src/backend/services/export.ts) | CSV/XLSX/JSON generation, cursor persistence in KV |
| [services/reccobeats.ts](../src/backend/services/reccobeats.ts) | ⚠ Test stub only — throws in non-test environments, never imported by router |
| [types/auth.ts](../src/backend/types/auth.ts) | `JWTPayload`, `AuthTokens`, TTL constants |
| [types/spotify.ts](../src/backend/types/spotify.ts) | Spotify response shapes |
| [types/spotify-api.ts](../src/backend/types/spotify-api.ts) | API response schemas, `parseSpotifyResponse()` |
| [types/env.ts](../src/backend/types/env.ts) | Cloudflare `Env` — KV bindings, secrets |
| [types/variables.ts](../src/backend/types/variables.ts) | Hono context variable types |
| [types/api.ts](../src/backend/types/api.ts) | `ErrorResponse` envelope |

---

## Known Dead / Stub Code

| File | Status | Note |
|------|--------|------|
| [services/reccobeats.ts](../src/backend/services/reccobeats.ts) | Test stub | Returns fake features in test env, throws otherwise. Never imported by any route. See [backend-analysis-routes.md](backend-analysis-routes.md) |

---

## ReccoBeats: Two Separate Paths

ReccoBeats analysis works differently depending on mode:

| Mode | Entry point | Implementation |
|------|-------------|---------------|
| Standalone (no backend) | `ui/playlist_card.py` → `services/reccobeats.py` | Direct HTTP to ReccoBeats |
| Backend-connected | `screens/backend_main_screen_adapter.py` → `services/reccobeats_backend.py` → `BackendClient` | Proxied through Cloudflare Worker → `services/analysis.ts` → ReccoBeats |

The backend proxy path has a known gap: `AnalysisService.analyzePlaylist()` returns results that the route handler never writes to KV, so `GET /analysis/playlist/:id/results` always returns 404. See [backend-analysis-routes.md](backend-analysis-routes.md) for the fix.

---

## Caching: Two Independent Layers

When in backend mode, caching happens at two levels that can drift:

| Layer | Location | TTL (playlists) | What it stores |
|-------|----------|-----------------|----------------|
| Python disk cache | `~/.spotibye/cache/` JSON | 1 hour | Playlists, tracks, analysis |
| Cloudflare KV | Worker-side per-user keys | 5 minutes | Playlists, tracks, audio features |

The Python layer checks first, so a 1-hour stale playlist list can be served even after the Worker would have refreshed from Spotify. See [backend-analysis-routes.md](backend-analysis-routes.md#2-backend-path-has-two-separate-cache-layers-that-can-go-stale-independently) for fix options.
