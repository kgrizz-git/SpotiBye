# Spotify Web API February 2026 Migration Findings (Development Mode)

https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide

## NOTE: POSSIBLE PAUSE OR REVERSAL IN SOME OF THESE CHANGES
Only external_id. Possible developer tier coming. See this thread: https://community.spotify.com/t5/Spotify-for-Developers/February-2026-Spotify-for-Developers-update-thread/td-p/7330564/page/11

Biggest problem is no tier between 5 users and >250k monthly listeners.


### Other Options
Perhaps can use client credentials to get public playlists without users being authenticated? Although that may have changed since 2025 https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow

Apple API seems robust.

## Scope
This summary is based on a targeted scan of active code paths under `src/backend` and `src/frontend` against the February 2026 Spotify Web API Development Mode migration guide.

Because this app is in Development Mode, migration updates are required.

## High-Risk Required Updates

### 1) Playlist endpoint rename not applied
Spotify renamed playlist track endpoints from `/playlists/{id}/tracks` to `/playlists/{id}/items`.

Current usage:
- `src/backend/services/spotify.ts:28`
- `src/backend/routes/spotify.ts:67`
- `src/backend/routes/spotify.ts:68`
- `src/frontend/services/backend_client.py:176`
- `src/frontend/tests/mock_backend.py:27`

Impact:
- Playlist track fetches may fail or return incompatible payloads in Development Mode.

Required action:
- Update endpoint calls and route naming conventions from `tracks` to `items` where they represent Spotify playlist item APIs.

### 2) Playlist response shape assumptions are outdated
Migration guide indicates playlist payload fields changed from `tracks` to `items`, and nested payload examples use `item` instead of `track`.

Current assumptions:
- `tracksData.items[*].track` in `src/backend/services/analysis.ts:25`
- `tracksData.items[*].track` in `src/backend/services/export.ts:56`
- Playlist total from `playlist.tracks.total` in `src/backend/services/export.ts:131`
- Type definitions still model old shape in `src/backend/types/spotify.ts`

Impact:
- Runtime null/undefined errors or empty results when processing playlist contents.

Required action:
- Add normalization for old/new payload shapes and update types accordingly.

### 3) Removed `popularity` field is used directly
The migration removes `popularity` for Track responses in Development Mode.

Current usage:
- `src/backend/services/analysis.ts:44`
- `src/backend/services/export.ts:11`
- `src/backend/services/export.ts:104`
- `src/backend/services/export.ts:183`
- `src/backend/types/spotify.ts:39`

Impact:
- Undefined values and potential downstream scoring/export issues.

Required action:
- Make `popularity` optional and handle missing values safely (fallback/null/default).

### 4) Auth/profile code assumes `/me.email` exists
Migration removes `email` from `GET /me` for Development Mode.

Current assumptions:
- JWT generation stores `email` from Spotify profile: `src/backend/routes/auth.ts:69`
- JWT payload requires `email: string`: `src/backend/types/auth.ts:10`
- Middleware user context requires `email: string`: `src/backend/types/variables.ts:4`
- OAuth scopes include `user-read-email`: `src/backend/services/spotify-auth.ts:17`

Impact:
- Inconsistent session/user payloads and type mismatches when `email` is absent.

Required action:
- Treat email as optional in payload/types/context and avoid hard dependency on it.

## Medium-Risk / Follow-Up Updates

### 5) Docs and test doubles still use old track endpoint naming
Examples and mock/test paths still use `/tracks` semantics.

Examples:
- `src/backend/docs/openapi.yaml:266`
- `src/backend/docs/README.md:77`
- `src/backend/README.md:54`
- `src/frontend/tests/mock_backend.py` endpoint matching and responses

Impact:
- Confusion for maintainers and possible test drift after code migration.

Required action:
- Update docs/mocks to align with migrated endpoint names and payload shape.

## Findings Not Currently Blocking
- Removed batch endpoints like `GET /tracks?ids=...` are not currently used in active code paths.
- Removed browse/user-data endpoints (`/browse/*`, `/users/{id}`) are not used in active runtime paths.
- Search limit reduction (max 10) does not appear in active queried paths.

## Recommended Migration Order
1. Update Spotify service endpoint to `/playlists/{id}/items`.
2. Add payload normalization layer for playlist items (`track` vs `item`, `tracks` vs `items`).
3. Make `popularity` optional-safe in types, analysis, and export.
4. Make `email` optional-safe in auth/JWT/context types.
5. Update docs, OpenAPI, and test mocks.

## Bottom Line
Yes, code updates are needed for this repository because the app is in Spotify Development Mode and currently relies on multiple pre-migration endpoint/field assumptions.

## Patch Plan
1. Update Spotify playlist item fetches to use `GET /playlists/{id}/items` at the Spotify API layer while keeping backend route compatibility for existing frontend calls.
2. Add a normalization helper in the backend Spotify service to normalize playlist item payloads (`track` vs `item`) and expose stable fields (`items`, `total`) to downstream services.
3. Update analysis/export services to consume normalized playlist items and make `popularity` optional-safe with numeric fallback (`0`) where required for CSV/export output.
4. Update shared TypeScript types to reflect Development Mode response reality:
	- `SpotifyUser.email` optional
	- `SpotifyUser.country` optional
	- `SpotifyTrack.popularity` optional
	- `SpotifyPlaylist` supports `tracks` or `items`
5. Make auth/JWT middleware type contracts email-optional so `/me` responses without `email` do not break token/session processing.
6. Update frontend client and mock backend to add `/items` support while preserving `/tracks` compatibility to avoid immediate UI regressions.
7. Run backend typecheck/tests where available and fix any strict-mode compile issues introduced by these changes.

## Status Update (2026-03-06)
- Patch plan implementation completed for backend/frontend code compatibility with Development Mode.
- Backend docs were aligned to migrated naming:
	- `src/backend/docs/openapi.yaml` now documents `GET /spotify/playlists/{id}/items`.
	- `src/backend/docs/README.md` and `src/backend/README.md` now list `/items` as primary and `/tracks` as backward-compatible alias.
