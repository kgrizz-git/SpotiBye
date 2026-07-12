# Plan: Per-Track ReccoBeats Cache, Auto Enrichment & Refresh Controls

**Date:** 2026-07-12
**Status:** Active
**Contract:** [`dev-docs/reccobeats-api-contract.md`](../../reccobeats-api-contract.md)
**Backlog:** `dev-docs/backlog/TO_DO.md` → enrichment refresh, export ReccoBeats migration, optional client-side fetch (Phase B5)

## Problem

1. **Incomplete analysis appears stuck** — local 24h analysis cache, raw-enrichment partial reuse (claim E), and ≥50% silent coverage bypass auto-retry; no user-facing refresh.
2. **Export shows N/A for enrichment** — export uses Spotify `/audio-features` with `include_audio_features: false`; analysis uses ReccoBeats and never feeds export.
3. **Wrong cache granularity** — playlist-scoped `raw-enrichment` blob conflates mutable membership with stable per-track features.

## Empirical ReccoBeats verification (2026-07-12)

Live requests to `https://api.reccobeats.com/v1` (no auth). Resolves assessment **Blocker 1** for implementation. Full field notes live in the contract doc.

### Join key & omission (locked)

| Rule | Detail |
|------|--------|
| Spotify join | Parse track-level `href` (`https://open.spotify.com/track/{id}`) — never ReccoBeats UUID `id` |
| Omission | Missing IDs are **dropped** from `content` (not null); all-miss → HTTP 200 + `"content": []` |
| Miss set | `requested − { parseSpotifyId(row.href) }` |
| No `time_signature` | Export column stays permanent `N/A` or dropped |
| Negative-cache probe | `4cOdK2wGLETKBW3PvgPWoT` alone → audio-features **and** `/track` both return `[]` (**verified 2026-07-12**) |

### Type drift to fix in B0

- `ReccoBeatsTrackMetadata` / `isReccoBeatsTrackMetadata` do not require track-level `href` today; live API returns it.
- Batch fetch helpers concatenate `content` without mapping via `href`.

---

## Approach

Two parallel tracks:

| Track | Goal | Blocks |
|-------|------|--------|
| **A — Hotfix** | Fix silent incomplete analysis + retry UX **now** | Nothing |
| **B — Cache tiering** | Global per-track backend cache, offline-aware auto miss-fetch, export, buttons | B0 type/parser fixes |

Keep each PR ~one logical change, ≤400 lines where possible. **Track B PR split (required):** B0+B1 (backend cache + schema), B2 (composition/offline), B3 (frontend UX + force wire-through), B4 (export migration). Do not land B0–B4 as one PR.

### Two invalidation modes (do not conflate)

| Mode | Detectable offline? | Trigger | Action |
|------|---------------------|---------|--------|
| **Enrichment completeness** | **Yes** | endpoint-specific resolved counts (unique hits + absents) vs playlist **unique** track-ID count — **not** `audio_features.track_count` / row totals alone | If all required endpoints cover the unique set → return analysis cache offline; if less / coverage `< 1.0` → backend miss-resolution for **unresolved IDs only** |
| **Composition change** | **No** (needs current Spotify state) | `snapshot_id` or track-ID set differs from cached | Network fetch (details or tracks); **delta** re-enrich **new IDs only** |

**Why not `audio_features.track_count`:** that field is `features.length` (successful ReccoBeats hits only). Permanent misses (omitted from ReccoBeats `content`) would keep `track_count < playlist size` forever and cause endless “incomplete” retries. Completeness = every **unique** playlist track ID has been **resolved** to either a positive enrichment row or a verified absent sentinel (duplicate rows in a playlist do not change the unique set).

**Coverage `< 1.0` still matters:** it should trigger a targeted miss-fill for only unresolved track IDs when those IDs are known. It must **not** trigger a full playlist reanalysis loop, must stop retrying an ID once that ID is recorded as an endpoint-specific absent sentinel, and must not keep retrying the same unresolved set over and over within one frontend app session.

Offline return is safe **only** for completeness. Composition checks always need a lightweight network call when online.

### Cache model (target)

| Layer | TTL | Scope |
|-------|-----|-------|
| Playlist tracks (`tracks_{id}.json`) | **24 h** | Per playlist, local |
| Per-track audio-features | **6 mo** | Global backend KV |
| Per-track track-metadata | **6 mo** | Global backend KV |
| Per-track negative sentinel (per endpoint) | **7 d** | Global backend KV |
| Analysis aggregates | Invalidate on incomplete enrichment or composition change | Local + user KV results |

**Global KV key convention (GP#4 exception):** per-track enrichment is shared across users — same rationale as today’s playlist `raw-enrichment` blob. Use an explicit `global:` prefix so agents do not “fix” keys into `<user_id>:…` form:

```text
global:reccobeats:audio-features:{spotifyTrackId}
global:reccobeats:track-metadata:{spotifyTrackId}
global:reccobeats:absent:audio-features:{spotifyTrackId}
global:reccobeats:absent:track-metadata:{spotifyTrackId}
```

Absent sentinels are **per endpoint** so an empty `/audio-features` response cannot poison `/track` lookups (and vice versa).

Document this exception in `dev-docs/guides/golden-principles.md` when B1 lands.

---

## Track A — Hotfix PR (ship first)

- [x] **A1.** Add `cacheService.delete` for `analysis:playlist:{id}:raw-enrichment` on `DELETE /analysis/playlist/:id` (stopgap for claim E). Today that handler only clears status + results — this is a **new** deletion, not extending an existing one. Becomes a harmless no-op after B1.3 removes the blob.
- [x] **A2.** Soften coverage UX and fix completeness semantics (do **not** use `coverageRatio < 1.0` as a red-banner / auto-retry gate):
  - Keep backend `reccobeats:coverage` **error** threshold meaningful (e.g. current `< 0.5` floor, or hard fetch failures only).
  - **Hotfix only:** do **not** depend on endpoint-specific resolved counts (those fields land in B1.2b + schema bump). Approximate incompleteness with existing signals: hard `reccobeats:*` errors and/or meaningful coverage floor — **never** `audio_features.track_count === playlist.track_count` (false incomplete forever when ReccoBeats omits tracks).
  - Decide and encode helper semantics explicitly: rename the frontend helper to `has_retriable_reccobeats_errors()` if it drives auto-retry. `reccobeats:coverage` may be retry-worthy only when the retry path can target known unresolved IDs. If Track A cannot compute missing IDs without B1/B2 fields, keep coverage as informational/manual-retry only until targeted miss-fill lands.
  - Add/plan a per-session auto-retry ledger keyed by `playlist_id`, composition fingerprint (`snapshot_id` or track-ID hash), endpoint, and sorted unresolved IDs. Automatic miss-fill may run **once** for that key in a frontend app session; manual **Retry enrichment** / **Refresh track info** bypasses this guard.
  - Full completeness gate (endpoint-specific resolved counts vs **unique** playlist track IDs) ships with B1/B2 after schema bump.
  - Partial coverage (e.g. 70–99% hits before absents are known) should schedule targeted missing-track fetch once B1/B2 can identify unresolved IDs; after absents are recorded, the same hit ratio may be complete and should be informational via B3.1 `N/M` status line.
  - **Known limitation (CHANGELOG):** permanent ReccoBeats omissions that are not hard errors may stay silent until B1/B2 ship endpoint-specific resolved counts / targeted missing-track retry — call this out in A6.
- [x] **A3.** Consolidate `_has_reccobeats_errors` into **`src/frontend/services/enrichment_errors.py`** (canonical; under `services/`, not `adapter_mixins/`). Prefer the explicit name `has_retriable_reccobeats_errors` if the helper is used for retry decisions. Import from both consumers, e.g. `from ...services.enrichment_errors import has_retriable_reccobeats_errors` in `adapter_mixins/analysis.py` and `from .enrichment_errors import has_retriable_reccobeats_errors` in `reccobeats_backend.py`; delete the two duplicate local defs.
- [x] **A4.** Add **Retry enrichment** button on analysis popup → `force_reanalyze_playlist()` with progress bar.
- [x] **A5.** Tests: raw-enrichment cleared on delete; retry button calls force reanalyze; consolidated helper used in both paths; coverage warnings do **not** cause full-playlist auto-retry when missing IDs are unknown. Do **not** add resolved/absent-sentinel completeness tests in Track A; those fields do not exist until B1/B2.
- [x] **A6.** `CHANGELOG.md` (Unreleased): incomplete-analysis retry UX fixes + known limitation that full omission/completeness status arrives with per-track cache follow-up.

---

## Track B — Per-track cache & enrichment (exec plan)

### Phase B0 — Types, parser, contract (prerequisite)

- [x] **B0.1.** Add optional `href?: string` to `ReccoBeatsTrackMetadata`; optional `ean`, `upc`, `availableCountries` as optional boundary fields.
- [x] **B0.2.** Make `href` **optional** in **both** row-level validators (`isReccoBeatsAudioFeature` and `isReccoBeatsTrackMetadata`). Today `ReccoBeatsAudioFeature.href` is required — that defeats per-row batch resilience if any AF row omits it. At cache-write / map time: skip + log rows with missing/unparseable `href`; treat as fetch miss for that request; **do not** write negative sentinel for href-parse failures. Never treat ReccoBeats UUID `id` as a Spotify track ID.
- [x] **B0.3.** Add `parseSpotifyTrackIdFromHref()` in `src/backend/utils/reccobeats-helpers.ts` (unit tests: `https://open.spotify.com/track/{id}`, query/hash strip; also accept `spotify:track:{id}` defensively). Mirror behavior of `extract_spotify_id_from_href` in `scripts/test_reccobeats_coverage.py` (cross-reference in a comment; do not share runtime with the script).
- [x] **B0.4.** Refactor batch fetch helpers to return `Map<spotifyTrackId, row>` using href parser:
  - **Do not** reject the whole batch via `content.every(...)` if one row is malformed.
  - Iterate `content`, accept rows that pass row-level guards + parseable `href`, skip/log the rest.
- [x] **B0.5.** Update `dev-docs/reccobeats-api-contract.md` — **done 2026-07-12**. Before coding B0, **re-probe** `4cOdK2wGLETKBW3PvgPWoT` on both `/audio-features` and `/track` (expect `content: []`) — negative-cache model depends on this still holding.
- [x] **B0.6.** Backend tests: batch with known + missing ID → correct miss set; href parsing; one malformed / href-less AF or metadata row does not fail the batch.

### Phase B1 — Global per-track backend cache service

- [x] **B1.1.** Add constants: `RECCOBEATS_TRACK_ENRICHMENT_TTL_SECONDS = 15_552_000` (6 mo), `RECCOBEATS_NEGATIVE_CACHE_TTL_SECONDS = 604_800` (7 d). Note: `popularity` **is** consumed (analysis `popularity_min`/`max` UI) and shares the 6 mo metadata TTL as an intentional freshness tradeoff; **Refresh track info** is the escape hatch.
- [x] **B1.1b.** Update `dev-docs/guides/golden-principles.md` §4: allow `global:<resource_type>:<identifier>` for non-user-specific derived data (ReccoBeats per-track enrichment).
- [x] **B1.2.** Create `src/backend/services/reccobeats-track-cache.ts`:
  - Preserve existing **batch size ≤ 30** and concurrency bounds (do not unbounded-fetch).
  - `resolveAudioFeatures(trackIds, { force? })` and `resolveTrackMetadata(trackIds, { force? })`:
    - **Fetch misses internally**; return a **merged complete** `Map<spotifyTrackId, row>` (hits + newly fetched).
    - Also return informational counters and sets `{ fetchedCount, negativeSkipped, unparseableCount, resolvedCount, resolvedIds, absentIds, unresolvedIds }` — callers must not re-fetch `misses` themselves. `resolvedIds` means positive hit **or** verified absent for that endpoint.
  - KV keys (see cache model): positive keys + **per-endpoint** absent keys.
  - **Two-stage lookup:** for each ID, read positive key first; only read `absent:…` on positive miss (avoids 2× KV gets on warm hits).
  - **Chunked KV ops (known keys):** bound concurrent KV get/put/delete (e.g. ≤ 25 parallel). Force-refresh deletes **known** keys by track ID — do **not** use `CacheService.clear(prefix)` for this path (`clear()` today lists once with no cursor and can miss keys past 1000).
  - On successful HTTP 200: for each content row, `spotifyId = parseSpotifyTrackIdFromHref(row.href)`; if parseable, write the positive KV key under that Spotify ID; if not, skip + log (do **not** key by ReccoBeats UUID `id`). Write **endpoint-specific absent** only for requested IDs still missing after that map (not for parse failures).
  - **Write resilience:** each endpoint resolver writes its own successful positive/absent cache entries independently. Do not let a track-metadata write/fetch failure discard already-successful audio-feature cache writes.
  - **In-flight dedup:** module-level `Map<string, Promise>` keyed by `` `${endpoint}:${force ? 'force:' : ''}${hash(sortedIds)}` ``; remove entry on settle. Use a Worker-compatible stable hash/key (global `crypto.subtle` or deterministic join for ≤30 IDs), not Node-only `crypto` APIs. Force and non-force do **not** share a key. **Limitation:** coalesce is **per Worker isolate only** — concurrent requests on different isolates can still duplicate ReccoBeats HTTP (blast radius bounded by batch ≤30); do not rely on this Map to cap global QPS under a thundering herd.
  - **`force: true`**: delete that endpoint’s positive **and** absent keys for every requested ID **before** refetching (chunked deletes of known keys).
- [x] **B1.2a.** Add `clearPrefixPaginated(prefix)` (on `CacheService` or track-cache helpers) using `kv.list({ prefix, cursor })` until `list_complete`. Keep existing `clear()` for small prefixes if desired, but **document** that large prefixes (especially `global:reccobeats:`) must use the paginated helper. Optional ops script: `scripts/flush-reccobeats-cache.ts`.
- [x] **B1.2b.** Schema + aggregation for completeness fields:
  - Add endpoint-specific completeness counts to `AnalysisResult` / `PlaylistInsights` / `reccobeats_metadata` as appropriate:
    - `unique_track_count`: unique Spotify track IDs in the playlist.
    - `audio_features_resolved_count`: unique IDs that are ReccoBeats audio-feature hits **or** endpoint-specific absents.
    - `track_metadata_resolved_count`: unique IDs that are ReccoBeats `/track` hits **or** endpoint-specific absents.
    - Optional display shortcut `enrichment_resolved_track_count = min(audio_features_resolved_count, track_metadata_resolved_count)`.
  - Offline completeness is true only when all analysis-required endpoints are resolved for all unique IDs (normally both audio-features and track-metadata) and there is no hard `reccobeats:*` error. Do not compare endpoint hit counts to duplicate-inflated playlist row totals.
  - Derive endpoint-specific `unresolvedIds` as `unique playlist IDs - resolvedIds`; this is the only set eligible for automatic coverage miss-fill when coverage `< 1.0`.
  - Update `generatePlaylistInsights` (or equivalent) to populate these fields from the **unique** ID set and the `resolve*` endpoint counters/sets (duplicates in a playlist do not inflate either side of the completeness comparison).
  - Bump `ANALYSIS_SCHEMA_VERSION` (backend `constants.ts`) and `EXPECTED_ANALYSIS_SCHEMA_VERSION` (frontend `analysis.py`) in lockstep (e.g. `"1.0"` → `"1.1"`). Ship backend + frontend together when possible; existing mismatch logic clears stale `"1.0"` caches — document one-time re-fetch in CHANGELOG.
  - Update OpenAPI / openapi-schema tests and any result-shape assertions.
- [x] **B1.3.** Wire `AnalysisService.fetchReccoBeatsEnrichment` to track-cache service; **remove** playlist `raw-enrichment` blob read/write (A1 delete of that key becomes a harmless no-op). Accept `force_enrichment` from the job path (see B3.5). Analysis/export callers should resolve audio features first or tolerate metadata failure independently; metadata failure must not block successful audio-feature analysis/export data.
- [x] **B1.4.** `DELETE /analysis/playlist/:id` clears user status/results and optional playlist manifest/raw-enrichment stopgap only — **not** global per-track keys.
- [x] **B1.5.** Tests: cache hit skips HTTP and skips absent get; cross-user reuse; per-endpoint absent; force clears correct keys; concurrent force coalesces; chunked KV; batch size respected; one bad content row does not fail batch; schema bump invalidates old results.

### Phase B2 — Playlist composition & offline-aware frontend

- [x] **B2.1.** `snapshot_id` end-to-end (today backend `SpotifyPlaylist` **omits** it; frontend only reads raw `playlist_data.get("snapshot_id")`):
  - Add `snapshot_id?: string` to `SpotifyPlaylist`, `SpotifyPlaylistsResponse.items[]`, `SpotifyPlaylistResponse`, and OpenAPI/examples for list/details responses.
  - Verify `/spotify/playlists` (and details if used) actually returns it — Spotify simplified playlist objects include it; if our route or parser strips unknown fields, add explicit passthrough.
  - Prefer list `snapshot_id` when present; details/tracks fetch remains the composition-change path when online.
- [x] **B2.1b.** Make playlist track refresh/fingerprint code operate on **all** playlist items, not the first route page:
  - Backend route `/spotify/playlists/:id/items` is paginated and currently defaults/maxes to 50 via `PaginationQuerySchema`; `BackendClient.get_playlist_tracks()` calls it once and discards `rawCount`/`total`.
  - Add a paginated frontend helper (or update `BackendClient.get_playlist_tracks`) that loops `limit`/`offset` until `rawCount < limit` or `offset >= total`, preserving only track items for existing callers.
  - Keep a page-level helper if the tracks popup needs lazy display later, but composition fingerprinting and local cache completeness must use the full unique ID set.
- [x] **B2.1c.** Add real force-refresh passthrough for playlist details/items:
  - Extend backend query schemas/routes (`/spotify/playlists/:id`, `/spotify/playlists/:id/items`, and `/tracks` alias if kept) with `force_refresh=true` to skip backend `CACHE_KV` reads and overwrite the cached value after fetching Spotify.
  - Extend `BackendClient.get_playlist_details(..., force_refresh=False)` / `get_playlist_tracks(..., force_refresh=False)` and `TracksMixin` to pass the flag through; today `force_refresh=True` bypasses only the local disk cache.
  - Tests must prove refresh buttons bypass both local `tracks_{id}.json` and backend playlist-items KV cache.
- [x] **B2.2.** Extend track-cache storage to keep composition fingerprint (`snapshot_id` and/or sorted track-ID hash) + default TTL **86400** (bump from 7200).
  - Preserve `get_cached_tracks()` returning `List[Dict[str, Any]]` for existing callers, or update all callers/tests in the same PR. Prefer adding `get_cached_tracks_entry()` / `cache_tracks(..., metadata=...)` so old callers still receive a list while B2 gates can read `{ tracks, snapshot_id, track_id_hash, unique_track_count, cached_at }`.
  - **UX tradeoff (intentional):** playlist membership can be stale for up to 24h vs today’s 2h. Rely on discoverable **Refresh playlist tracks** (B3.2 / B3.4) for sooner updates — do not silently revert to 2h.
- [x] **B2.3.** Split analysis-cache gates:
  - **Offline completeness:** valid when endpoint-specific resolved counts (hits + absents) cover the playlist’s **unique** track-ID count (and schema ok) — **not** when `audio_features.track_count` equals playlist row count, and **not** comparing unique resolved count to duplicate-inflated row totals. No network required.
  - **Targeted coverage retry:** when schema is current but one or more required endpoint counts are `< unique_track_count`, call backend miss-resolution for only the endpoint-specific `unresolvedIds`. Before calling, check the per-session auto-retry ledger; if the same playlist composition + endpoint + unresolved-ID set was already attempted in this frontend app session, return the cached result with informational status instead of retrying again. Do not delete/recompute successful aggregate data unless new rows arrive; merge new hits/absents, recompute affected aggregate fields, and persist the updated analysis result.
  - **Composition check (when online):** if current `snapshot_id` / track-ID set differs from fingerprint → invalidate analysis; load current tracks; delta-enrich **new** IDs only. If Spotify check times out, fall back to cached tracks + completeness gate.
- [x] **B2.4.** `analyze_playlist`: if offline-complete → return local cache; if incomplete / coverage `< 1.0` → backend miss-resolution for unresolved IDs only; if composition changed → delta path above.
- [ ] **B2.5.** Optional backend manifest: `analysis:playlist:{id}:manifest` @ 24h with `{ track_ids, snapshot_id }` (`track_ids` unique). Not required for B2.3/B2.4 — if missing when online, fall back to a normal tracks/details fetch (safe, possibly slower). **Skipped for B2 PR** — tracked in [`dev-docs/backlog/TO_DO.md`](../../backlog/TO_DO.md); online tracks/details fallback is implemented.
- [x] **B2.6.** Tests: complete cache → no backend call; incomplete / coverage `< 1.0` → miss fetch for unresolved IDs only; same unresolved set is not auto-retried twice in one frontend session; verified absents are not retried; composition change or a different unresolved set can retry; manual force refresh bypasses the session guard; offline path never requires Spotify; playlist with duplicate track IDs still counts as complete when unique set is resolved.

### Phase B3 — Auto miss-fetch on open + refresh buttons

- [x] **B3.1.** Analysis popup: informational status line *"Enrichment: N/M tracks"* + last refreshed times. If `N < M` and unresolved IDs remain, show neutral/progress copy while the targeted missing-track fetch runs; if all unresolved IDs are verified absent, show complete-with-omissions status rather than a red banner.
- [x] **B3.2.** **Refresh playlist tracks** → `get_playlist_tracks(force_refresh=True)` with backend force passthrough from B2.1c; then auto-enrich **new** IDs only. Place the button where users can find it (analysis + tracks popups) so the 24h tracks TTL does not feel like a silent regression.
- [x] **B3.3.** **Refresh track info** → `POST` analysis with `force_enrichment=true` (clears positive + per-endpoint absent keys for playlist track IDs, then refetch — see B1.2).
  - **Export cache invalidation (after enrichment succeeds, not before):** clear the single-export prefix `export:${playlistId}:${userId}`; it catches base, `:data`, and `:file` keys (`cache-keys.ts`). Prefer post-success clear so a mid-flight export is not emptied into an empty/unenriched race (accept user-initiated race only if they export *during* the job).
  - **In-flight job/batch keys** (`export:job:{jobId}:{userId}:*`, `export:batch:{jobId}:{userId}:*`) and resumable render variants (`:file:rich|lite|csv`) are **not** cleared by that prefix. Decision: **accept staleness for in-flight jobs** (user must recreate / restart the job after refresh). Document in route comments; do not invent a user-wide `export:job:*` wipe unless product asks.
- [x] **B3.4.** Tracks popup: **Refresh playlist tracks** button only. On force track refresh, invalidate the same **single-export** prefix after tracks are refreshed (composition may have changed). Same job/batch caveat as B3.3.
- [x] **B3.5.** Wire `force_enrichment` end-to-end:
  - Analysis POST accepts query/body `force_enrichment?: boolean` and the route comment/openapi schema must stop saying the body is ignored for this field.
  - If `force_enrichment=true`, bypass the current completed/queued short-circuit: delete user results/status, enqueue a new job, and let any older in-flight queue message become stale via job-id mismatch. Otherwise keep existing idempotent status behavior.
  - Extend `AnalysisQueueMessage`, `AnalysisQueueMessagePayloadSchema`, and `AnalysisQueueMessageSchema` with `force_enrichment?: boolean`; Zod currently strips unknown fields, so the schema change is required.
  - Route enqueues the flag; `AnalysisJobService.process` passes it into `AnalysisService.analyzePlaylist` / `fetchReccoBeatsEnrichment` → track-cache `resolve*(…, { force })`.
  - Extend `BackendClient.analyze_playlist(..., force_enrichment=False)` and `ReccoBeatsBackendService.force_reanalyze_playlist()` so the frontend can send the flag instead of relying only on DELETE + POST.
  - Tests: queued message includes flag; queue schema preserves it; force POST bypasses cached completed status; force path reaches resolve with `force: true`; non-force still returns existing queued/processing/completed status.
- [x] **B3.6.** Frontend tests: buttons call correct adapter methods; coverage `< 1.0` with unresolved IDs triggers backend miss-fill only for those IDs; the same unresolved set does not retrigger automatically in the same app session; verified absents do not retrigger; force path clears absents and bypasses the session auto-retry ledger; single-export cache cleared **after** successful force enrichment / track refresh.

### Phase B4 — Export uses per-track cache

- [x] **B4.1.** `loadAudioFeaturesMap` (`src/backend/services/export-tracks.ts`) / export path reads global per-track cache via `resolveAudioFeatures` (same miss-fill as analysis — **do not** require the user to have analyzed first). Define a minimal adapter (do **not** force ReccoBeats into `SpotifyAudioFeatures`):
  - Thread `CacheService`/KV access into export code before calling `resolveAudioFeatures`: `ExportService` currently only stores `accessToken`, and `runCollectStep` / `generatePlaylistExportSlice` / `buildExportTracks` currently pass only `SpotifyService`. Update those signatures/routes in one PR so single exports and resumable jobs use the same cache-backed path.
  - Type e.g. `ReccoBeatsExportFeatures` = ReccoBeats audio-feature numeric fields used by export (`tempo`, `key`, `danceability`, `energy`, `valence`, `acousticness`, `instrumentalness`, `liveness`, `speechiness`, `loudness`, …) — **no** `time_signature`.
  - `toExportFeatures(row: ReccoBeatsAudioFeature): ReccoBeatsExportFeatures` mapping function; wire export columns through it.
  - **Empty-cache case:** when enrichment is requested and IDs miss the global cache, export **miss-fills** via ReccoBeats (progress/status as appropriate); only leave columns as `N/A` for verified absents or hard fetch failures — never silently all-`N/A` solely because analysis was never opened.
- [x] **B4.2.** Update `mapTrackForExport` in `export-tracks.ts` (today reads `audioFeatures?.time_signature` from Spotify shape): map adapter fields → `ExportTrack`; **`Time Signature`** → permanent literal `N/A`; add an explicit test asserting that.
- [x] **B4.3.** After B4.1: flip enrichment on in **all** frontend export call sites in `src/frontend/services/backend_client.py` that currently hardcode `include_audio_features: False`:
  - `generate_export`
  - `generate_batch_export`
  - `generate_batch_export_chunk`
  - `create_export_job`
  - Document semantic change in route/helper comments: flag means **“include ReccoBeats/per-track enrichment”**, not Spotify `/audio-features`. Renaming to `include_enrichment` is optional (can be a follow-up).
  - Required before flipping the frontend default: update `buildSingleExportKey` / related single-export keys (or explicitly invalidate legacy `export:${playlistId}:${userId}` first) so enriched vs unenriched and format variants do not collide. Today the single-export cache key ignores `include_audio_features` and `format`, so a previous unenriched export can be returned before B3 refresh invalidation ever runs.
- [x] **B4.4.** Export tests: numeric enrichment values (not all `N/A`); export without prior analysis still miss-fills; shared track across playlists hits cache; Time Signature always `N/A`; post-force-enrichment export is not a stale cached file.
- [x] **B4.5.** `CHANGELOG.md`: export includes ReccoBeats enrichment columns; note one-time analysis re-fetch if schema bump already landed in B1.
- [x] **B4.6.** Remove dead Spotify audio-features path once unused: `SpotifyService.getMultipleAudioFeatures`, `GET /spotify/tracks/:id/audio-features` (or equivalent proxy), and frontend `get_multiple_track_audio_features` / `_safe` stubs that raise `NotImplementedError`. Update/remove related tests. **Order:** B4.1 must land before B4.6 — today `loadAudioFeaturesMap` still hard-depends on the Spotify path. If any legacy stub remains, update/remove stale `docs/exec-plans/...` references; canonical historical plans live under `dev-docs/exec-plans/completed/`.

### Phase B5 — Deferred: optional client-side ReccoBeats fetch

- [ ] **B5.1.** Feature flag + UI toggle; privacy notice; upload to backend per-track cache.
- [ ] **B5.2.** **Security (required if built):** auth-gated + rate-limited upload; strict schema validation against ReccoBeats shapes; **reject client-set negative sentinels** (poisoning risk on shared global cache).
- [ ] **B5.3.** Only after B1–B4 stable.

---

## Peer-review decisions incorporated (2026-07-12)

| Item | Decision |
|------|----------|
| G1 snapshot_id / offline | Split completeness (offline) vs composition (network + delta). Add `snapshot_id` to types; Spotify list objects **do** include it — verify passthrough rather than assuming “details only.” |
| G2 A2 `< 1.0` | Coverage `<1.0` should trigger targeted miss-fill for endpoint-specific unresolved IDs once known; it must not be a red-banner/full-reanalysis gate. Track A uses existing signals until B1/B2 fields exist. |
| G3 require `href` | Rejected; optional href; skip/log; no negative cache on parse fail. |
| G4 force | Must clear positive **and** `absent` keys. |
| G5 resolve\* | Fetch internally; return merged Map + counters. |
| R1/R2 export | Adapter type; flag semantics; remove dead Spotify path. |
| R3 B5 write-back | No client negatives; validate + rate-limit. |
| R6 batch size | Cap ≤ 30 in track-cache service. |
| R7 `/track` empty | Confirmed for `4cOdK2w…`. |
| GP#4 / global keys | Use `global:reccobeats:…:{spotifyTrackId}`; document GP#4 exception (B1.1b). |
| Tracks TTL 24h | Keep (product choice); document staleness + discoverable refresh button — do not revert to 2h. |
| Manifest required? | No — optional with online tracks/details fallback. |
| Force/miss dedup | In-flight coalesce in B1.2. |
| Export call sites | Enumerate all four `backend_client.py` hardcodes in B4.3. |
| KV partial writes | Endpoint writes are independent; metadata failure must not discard successful audio-feature cache writes. |
| Completeness ≠ hit count | Use endpoint-specific resolved counts (hits + absents), never `audio_features.track_count === playlist size`. |
| Coverage retry scope | Retry only `unresolvedIds`; positive hits and verified absents are not re-fetched unless the user explicitly uses force refresh. |
| Session retry guard | Automatic coverage miss-fill runs at most once per playlist composition + endpoint + unresolved-ID set per frontend app session; manual refresh bypasses it. |
| Batch `content.every` | Per-row filter; one bad row must not fail the batch. |
| Absent sentinel | Per-endpoint keys (`absent:audio-features` / `absent:track-metadata`). |
| KV force scale | Two-stage lookup + chunked KV ops (≤ ~25 concurrent). |
| Stale export after refresh | Invalidate single-export prefix **after** enrichment succeeds; accept in-flight job/batch staleness; single-export keys must also distinguish enriched/unenriched and format before frontend defaults flip. |
| AnalysisResult counts | Add `unique_track_count`, `audio_features_resolved_count`, `track_metadata_resolved_count`, optional display shortcut `enrichment_resolved_track_count`; bump schema `1.0`→`1.1` (backend + frontend) in B1.2b — not assumed present for Track A. |
| force_enrichment queue | Field on `AnalysisQueueMessage` **and** queue Zod schemas; force POST bypasses completed/queued short-circuit and wires route → job → resolve (B3.5). |
| snapshot_id types | Backend `SpotifyPlaylist` currently omits it — B2.1 must add + verify route passthrough. |
| Frontend track pagination | `BackendClient.get_playlist_tracks()` currently fetches one route page; B2 fingerprint/completeness code must fetch all pages or use an equivalent full-track helper. |
| Force playlist refresh | Existing `force_refresh=True` bypasses only local disk cache; B2/B3 add backend query passthrough to skip Worker KV for details/items. |
| Local tracks cache shape | Preserve list return for existing callers or add a metadata-aware getter before storing fingerprints. |
| CacheService.clear pagination | Force path uses known-key deletes; paginated list only for emergency `global:reccobeats:` flush / fixing `clear()` (B1.2a). |
| In-flight dedup design | `Map` key `${endpoint}:${force?}:${hash(sortedIds)}`; remove on settle (B1.2). |
| A3 canonical module | `src/frontend/services/enrichment_errors.py`, with retry-specific helper naming and coverage semantics tied to targeted unresolved-ID fetch. |
| B4 adapter | Explicit `ReccoBeatsExportFeatures` + mapper (B4.1). |
| Dead Spotify AF removal | Checkbox B4.6. |
| Track B PR split | B0+B1, B2, B3, B4 separate PRs. |
| Export race | Clear export cache after successful force enrichment, not at request start. |
| Export empty cache | Export miss-fills per-track cache (same resolve path); do not require prior analysis. |
| href optional both validators | `ReccoBeatsAudioFeature.href` and metadata `href` both optional at validate; map requires parseable href. |
| Completeness uniqueness | Compare unique resolved IDs to unique playlist track IDs (duplicates OK). |
| Dedup isolate limit | Module Map is per-isolate only; note in B1.2. |
| clearPrefixPaginated | Add helper in B1.2a; do not reuse single-shot `clear()` for `global:reccobeats:`. |
| mapTrackForExport | Explicit B4.2 edit point in `export-tracks.ts`. |
| Track A omission silence | CHANGELOG known limitation until B1/B2 completeness UX and targeted missing-track retry. |
| Export KV access | `ExportService`/collect helpers currently have only `accessToken`/`SpotifyService`; B4 must thread `CacheService` to `buildExportTracks` for per-track miss-fill. |

---

## Verification commands (repeatable)

```bash
# Single track
curl -sS "https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B" | python3 -m json.tool
curl -sS "https://api.reccobeats.com/v1/track?ids=01K4zKU104LyJ8gMb7227B" | python3 -m json.tool

# Omission: known + missing; empty alone
curl -sS "https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B&ids=4cOdK2wGLETKBW3PvgPWoT" | python3 -m json.tool
curl -sS "https://api.reccobeats.com/v1/track?ids=4cOdK2wGLETKBW3PvgPWoT" | python3 -m json.tool

# Coverage script (playlist-scale)
.venv/bin/python scripts/test_reccobeats_coverage.py --track-id 01K4zKU104LyJ8gMb7227B
```

---

## Success criteria

- [ ] Opening analysis on an incomplete playlist auto-fetches missing ReccoBeats data for unresolved IDs only (with progress); **complete** cached analysis still works **offline** (complete = all **unique** track IDs resolved to hit or absent, not “all have features”).
- [ ] Playlists with permanent ReccoBeats omissions do **not** loop auto-retry once absents are recorded.
- [ ] Playlists with duplicate track rows still count as complete when the unique ID set is resolved.
- [ ] Composition change (when online) delta-enriches new track IDs without full refetch of warm cache.
- [ ] Same track enriched once is reused across playlists and users without duplicate ReccoBeats HTTP.
- [ ] Permanent misses stop re-fetching for 7 days (per-endpoint negative cache); force refresh clears absents.
- [ ] Export enrichment columns populated from per-track cache when enabled (including first export without prior analysis via miss-fill); Time Signature stays `N/A`; post-refresh export is not stale.
- [ ] User can force refresh playlist tracks or track info before 24h / 6mo TTLs.
- [ ] Hotfix PR merged independently before Phase B1 (without the false `track_count === total` completeness trap; without depending on B1 schema fields).
- [ ] Coverage `<1.0` triggers targeted missing-track retry while unresolved IDs remain, but not repeatedly for the same unresolved set within one app session; it becomes informational once misses are verified absent; no red-banner or full-reanalysis loop.
- [ ] Track B lands as separate PRs (B0+B1, B2, B3, B4).

---

## When complete

- [ ] Move this plan to `dev-docs/exec-plans/completed/`
- [ ] Index in `dev-docs/exec-plans/completed/README.md`
- [ ] Trim related backlog items in `dev-docs/backlog/TO_DO.md`
