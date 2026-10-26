# KV Namespace Structure Documentation

This document describes the KV keys the SpotiBye Cloudflare Workers backend
actually reads and writes. The code is the source of truth. When this page and
the code disagree, fix this page.

## Overview

The backend binds two KV namespaces (see `wrangler.toml`):
- `CACHE_KV` - Spotify response cache, OAuth state, analysis results, export
  state and file bytes, and the global per-track ReccoBeats cache
- `SESSIONS_KV` - Spotify sessions and the token-refresh negative cache

Both bindings point at the same namespace IDs in `development` and
`production`.

Live playlist-analysis status is intentionally not stored in KV. The
`ANALYSIS_STATUS` Durable Object stores the current queued/processing/retrying/
completed/failed record for a user playlist so progress polling can read the
latest update consistently. Completed analysis results remain in `CACHE_KV`.

Most `CACHE_KV` access goes through `CacheService` (`services/cache.ts`).
`set()` JSON-encodes the value, and `setBuffer()` stores raw `ArrayBuffer`
file bytes. A TTL is applied only when one is passed. `routes/auth.ts`
and `middleware/auth.ts` call the KV bindings directly.

## Key Naming Conventions

The project rule is `<user_id>:<resource_type>:<identifier>`. Current keys do
not follow it. Most keys lead with the resource type and embed the user ID
later. A few keys carry no user ID at all. The tables below list the keys as
built in code.

### CACHE_KV Keys

| Key | Value | TTL | Written by |
|-----|-------|-----|------------|
| `oauth_state:{state}` | `{ redirect_uri, code_verifier }` (legacy: bare redirect URI string) | 600 s | `routes/auth.ts` login. Deleted on callback. |
| `playlists:v2:{userId}` | `SpotifyPlaylist[]` (all pages) | 300 s | `routes/spotify.ts` |
| `user:{userId}:playlist:{playlistId}` | Spotify playlist | 600 s | `routes/spotify.ts` |
| `user:{userId}:playlist:{playlistId}:tracks:{limit}:{offset}` | Spotify tracks page | 300 s | `routes/spotify.ts` |
| `track:{trackId}` | Spotify track | 3600 s | `routes/spotify.ts` (not user-scoped) |
| `analysis:{playlistId}:{userId}:results` | `AnalysisResult` | `ANALYSIS_RESULTS_TTL_SECONDS` var, else 86400 s | `services/analysis-job.ts` |
| `analysis:{playlistId}:{userId}:fandata:{jobId}` | `FanoutTracksSnapshot` | 3600 s (`FANOUT_STATE_TTL_SECONDS`) | fan-out seed |
| `analysis:{playlistId}:{userId}:chunks:{jobId}:{chunkId}` | `AnalysisChunkPartial` | 3600 s | fan-out chunk |
| `export:{playlistId}:{userId}:{format}:{plain\|enriched}` | single-export status record | 3600 s | `routes/export/playlist.ts` |
| `...:{format}:{plain\|enriched}:data` | `ExportData` | 3600 s | same |
| `...:{format}:{plain\|enriched}:file` | file bytes | 3600 s | same |
| `export:{playlistId}:{userId}:latest` | `{ format, includeEnrichment }` | 3600 s | same |
| `export:job:{jobId}:{userId}` | export job state | 3600 s | `routes/export/jobs.ts` |
| `export:job:{jobId}:{userId}:data` | `ExportData[]` | 3600 s | same |
| `export:job:{jobId}:{userId}:assembly` | assembly state | 3600 s | same |
| `export:job:{jobId}:{userId}:file` | file bytes (canonical slot) | 3600 s | same |
| `export:job:{jobId}:{userId}:file:{rich\|lite\|csv}` | XLSX variant or prebuilt CSV bytes | 3600 s | same |
| `export:batch:{jobId}:{userId}` | batch status | 3600 s | `routes/export/playlists.ts` |
| `export:batch:{jobId}:{userId}:data` | `ExportData[]` | 3600 s | same |
| `export:batch:{jobId}:{userId}:file` | file bytes | 3600 s | same |
| `global:reccobeats:audio-features:{spotifyTrackId}` | ReccoBeats audio-features row | 15552000 s (6 months) | `services/reccobeats-track-cache.ts` |
| `global:reccobeats:track-metadata:{spotifyTrackId}` | ReccoBeats track-metadata row | 6 months | same |
| `global:reccobeats:absent:audio-features:{spotifyTrackId}` | `{ absent: true, cached_at }` | 604800 s (7 days) | same |
| `global:reccobeats:absent:track-metadata:{spotifyTrackId}` | `{ absent: true, cached_at }` | 7 days | same |

All export key builders live in `routes/export/helpers/cache-keys.ts`. The
unsuffixed `export:{playlistId}:{userId}` key and its `:data`/`:file` forms are
legacy single-export slots. The status and download routes still read them as
a fallback.

The `global:reccobeats:*` keys are shared across users on purpose. This is a
documented exception to the namespacing rule. See
[`dev-docs/reccobeats-api-contract.md`](../../../dev-docs/reccobeats-api-contract.md)
for join keys and absent-sentinel semantics.

Two legacy keys are only deleted, never written:
`analysis:{playlistId}:{userId}:status` and
`analysis:playlist:{playlistId}:raw-enrichment`.

### SESSIONS_KV Keys

| Key | Value | TTL | Written by |
|-----|-------|-----|------------|
| `{sessionId}` (bare UUID) | `SessionData`: `{ user_id, access_token, refresh_token, expires_at }` | 30 days (`SPOTIFY_SESSION_TTL_SECONDS`) | `routes/auth.ts` callback. Rewritten on token refresh by `middleware/auth.ts` and `services/analysis-job.ts`. |
| `REFRESH_FAILED:{sessionId}` | `'1'` | 60 s | `middleware/auth.ts` after a failed refresh |

`expires_at` is the Spotify access-token expiry in epoch milliseconds. The KV
TTL bounds the session itself. Logout deletes both keys. An
`AuthRequiredException` during refresh or analysis deletes the session.

## Durable Object and Queue

`ANALYSIS_STATUS` (`AnalysisStatusObject`) gets one object per
`analysis:{userId}:{playlistId}` name. Its storage holds:
- `status` - the current `AnalysisStatusRecord`
- `fanout:{jobId}` - the fan-out countdown state. A 24-hour alarm sweeps
  orphaned countdowns.

`ANALYSIS_QUEUE` carries analysis seed and chunk messages. It does not touch
KV directly. The consumer in `index.ts` calls `AnalysisJobService`, which
writes the analysis keys above.

## Cache Invalidation

- `DELETE /export/playlist/:id` calls `clearPrefixPaginated('export:{playlistId}:{userId}')`.
  It clears all single-export variants. In-flight `export:job:*` and
  `export:batch:*` keys are not cleared.
- A successful force-enrichment analysis clears the same single-export prefix.
- A force-enrichment fan-out seed deletes the positive and absent
  `global:reccobeats:*` keys for the playlist's tracks.
- `DELETE /analysis/playlist/:id` deletes the results key, the legacy
  raw-enrichment key, and the Durable Object status.
- `GET /analysis/playlist/:id/results` deletes a result whose
  `schema_version` is older than `ANALYSIS_SCHEMA_VERSION`.

Use `clearPrefixPaginated()` for prefix deletes. `clear()` only reads one
`list()` page of up to 1000 keys.

## Best Practices

- Add new key builders next to existing ones instead of inlining strings.
- Always pass a TTL. `CacheService.set()` stores the value with no expiry
  when the TTL is omitted.
- Never cache Spotify tokens in `CACHE_KV`. Tokens belong in `SESSIONS_KV`
  only.
