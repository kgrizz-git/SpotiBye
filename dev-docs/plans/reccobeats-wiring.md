# Backend Playlist Analysis / ReccoBeats Wiring Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore backend-mode playlist analysis so the Kivy popup receives useful duration, artist, and genre data, while preserving the path to ReccoBeats integration from the old monolithic app.

**Architecture:** The existing Cloudflare Worker analysis path is reliable using Spotify playlist metadata and best-effort artist metadata. ReccoBeats is wired only through the verified public `/v1/audio-features` lookup using Spotify track IDs. Production queueing remains tracked as a separate hardening follow-up.

**Tech Stack:** Cloudflare Worker, TypeScript, Hono, Spotify Web API, ReccoBeats API, Kivy/KivyMD frontend, Python backend adapter.

---

## Historical Context

SpotiBye had a working ReccoBeats integration when the app was still a monolithic Python/Kivy application. That path lived under the old `src/spotify_playlist_exporter_v2/` package and called ReccoBeats directly from Python, with local disk caching. The active repository no longer contains that package; current code only keeps compatibility names such as `ReccoBeatsBackendService` and `ReccoBeatsAPI` in `src/frontend/services/reccobeats_backend.py`.

Do not treat ReccoBeats as a new feature invented for the backend rewrite. Treat this as restoring a previously available analysis capability, but re-validate the API contract because the old source is no longer present in the active tree.

## Current State

- `src/backend/routes/analysis.ts` now persists completed results to KV via `executionCtx.waitUntil(...)`; older notes saying `/results` always returns 404 are stale.
- `src/backend/services/analysis.ts` computes local analysis from playlist tracks and artist metadata, then adds best-effort ReccoBeats audio-feature averages from `GET https://api.reccobeats.com/v1/audio-features`.
- The old dead `callReccoBeatsAPI()` helper and typo host have been replaced with `fetchReccoBeatsAudioFeatures(...)`.
- `src/backend/services/spotify.ts#getArtists()` now fetches individual `GET /artists/{id}` requests with bounded concurrency; `done/fix-analysis-403-spotify-api-migration.md` completed that dependency.
- Current pagination in `AnalysisService.analyzePlaylist()` already uses `rawCount`; do not replace it with logic based on normalized `page.items.length`.
- `src/frontend/ui/backend_playlist_card.py#_update_analysis_ui()` already handles the planned result shape: `overview.formatted_duration`, `genre_distribution`, `artists.unique_artists`, `artists.diversity`, and `artists.top_artists`.
- Active backend code, tests, workflows, and setup docs no longer require `RECOCOBEATS_API_KEY` or `RECCOBEATS_API_KEY`. Remaining mentions are historical notes or this plan's verification text.

## Scope Split

| Track | Scope | Status |
|---|---|---|
| A | Restore reliable Spotify-backed backend analysis | Complete |
| B | ReccoBeats API contract spike and backend adapter design | Complete for `/v1/audio-features` |
| C | Remove stale ReccoBeats key/config references | Complete for active backend config/docs |
| D | Queue-based production hardening for large playlists | Follow-up plan created: `dev-docs/plans/analysis-queue-hardening.md` |

---

## Track A - Restore Reliable Spotify-Backed Backend Analysis

This track depended on `dev-docs/plans/done/fix-analysis-403-spotify-api-migration.md`; that dependency is complete. Continue with the remaining Track A schema/route coverage before Track B.

### A1. Keep Current Pagination and Add Regression Coverage

**Files:**
- Modify: `src/backend/tests/analysis.test.ts`
- Reference: `src/backend/services/analysis.ts`

- [x] Add a service-level test that calls `AnalysisService.analyzePlaylist()` with mocked Spotify pages where:
  - page 1 returns `rawCount: 100`, `total: 150`, and fewer than 100 normalized `items`
  - page 2 is still fetched at `offset=100`
  - unavailable/local items are ignored in analysis totals
- [x] Do not apply the older plan's `if (page.items.length < limit) break` logic; that can stop early after filtering.

### A2. Persist the Existing KV Result Shape

**Files:**
- Modify: `src/backend/tests/analysis.test.ts`
- Reference: `src/backend/routes/analysis.ts`

- [x] Add a route-level test for `POST /analysis/playlist/:id` using a fake `executionCtx.waitUntil`.
- [x] Assert the background promise writes:
  - `analysis:{playlistId}:{userId}:results`
  - `analysis:{playlistId}:{userId}:status` with `status: "completed"`
- [x] Keep the route response fast and asynchronous: initial response should remain `status: "processing"`.

### A3. Stabilize the Canonical Result Schema

**Files:**
- Modify: `src/backend/services/analysis.ts`
- Modify: `src/backend/tests/analysis.test.ts`
- Verify: `src/frontend/ui/backend_playlist_card.py`

- [x] Keep the KV result as a flat object, not nested under `results`:

```json
{
  "job_id": "...",
  "playlist_id": "...",
  "user_id": "...",
  "status": "completed",
  "computed_at": "2026-06-19T00:00:00.000Z",
  "completed_at": "2026-06-19T00:00:00.000Z",
  "overview": {
    "total_tracks": 266,
    "total_duration_ms": 75672000,
    "average_duration_ms": 284481,
    "formatted_duration": "21h 1m 12s"
  },
  "artists": {
    "unique_artists": 224,
    "diversity": 0.84,
    "top_artists": [
      { "artist": "Solvent", "count": 22 }
    ]
  },
  "genre_distribution": {
    "Electronic": { "count": 92, "percentage": 34.6 }
  },
  "insights": ["Genre diversity note"]
}
```

- [x] Treat `genre_distribution` as best-effort. Spotify `GET /artists/{id}` currently still exposes `genres`, but Spotify marks that field deprecated.
- [x] Confirm the frontend parser still accepts this object when returned as `GET /analysis/.../results` response data.

### A4. Defer Synchronous Partial Results

The older Phase 2-B proposed computing Spotify-only stats synchronously in the POST handler. Keep this item, but do not implement it in the immediate repair.

Reason: full playlist pagination plus individual artist fetches conflicts with the goal that `POST /analysis/playlist/:id` returns quickly. If partial results are still desired later, write a separate plan for one of these safer designs:

- Store a cheap `status: "processing"` object only and let the popup keep polling.
- Compute only playlist metadata already available from the request path.
- Move partial/full work to a queue and write partial status from the consumer.

---

## Track B - ReccoBeats Contract Spike Before Wiring

Completed before changing the backend adapter.

### B1. Verify the Current ReccoBeats API Contract

**Files:**
- Create or update: `dev-docs/reccobeats-api-contract.md`
- Reference: `src/frontend/services/reccobeats_backend.py`
- Reference: `docs/project-summary-cloud-migration.md`

- [x] Confirm the current base URL. Public docs list `https://api.reccobeats.com`.
- [x] Confirm whether ReccoBeats accepts Spotify track IDs directly, ReccoBeats track IDs, ISRCs, uploaded audio files, or query search.
- [x] Confirm the endpoint for multiple track audio features. Public docs list `GET /v1/audio-features`, but the required query parameter shape must be verified.
- [x] Confirm whether any endpoint returns genre distribution. If not, do not claim ReccoBeats is the genre source.
- [x] Confirm rate-limit behavior and whether `Retry-After` is returned on 429.
- [x] Record one minimal request/response example for each endpoint SpotiBye would need.

### B2. Decide the ReccoBeats Backend Shape

After B1, choose one implementation path and document it before coding:

| Option | Use When | Notes |
|---|---|---|
| Track metadata lookup | ReccoBeats can resolve Spotify IDs or ISRCs | Use playlist track IDs/ISRCs from Spotify, cache by track ID |
| Audio features lookup | ReccoBeats has stored features for track IDs | Aggregate averages for energy, danceability, tempo, valence |
| Uploaded audio extraction | ReccoBeats only analyzes audio files | Likely not viable: Spotify content cannot be downloaded for this purpose |
| No ReccoBeats backend path | No supported endpoint matches the product need | Keep Spotify-only analysis and update UI/docs language |

Selected path: **Audio features lookup**. `dev-docs/reccobeats-api-contract.md` verifies that ReccoBeats accepts Spotify track IDs in `GET /v1/audio-features`.

### B3. Replace or Remove `callReccoBeatsAPI()`

**Files:**
- Modify: `src/backend/services/analysis.ts`
- Test: `src/backend/tests/analysis.test.ts`

- [x] If B1 finds a valid endpoint, replace `callReccoBeatsAPI()` with a typed method named for the actual operation, e.g. `fetchReccoBeatsAudioFeatures(...)`.
- [x] Not applicable: B1 found a valid endpoint, so `callReccoBeatsAPI()` was replaced rather than simply deleted.
- [x] Never call unverified `POST /v1/analyze`; public docs checked on 2026-06-19 did not show that endpoint.

### B4. Merge ReccoBeats Data Without Breaking Spotify-Only Results

**Files:**
- Modify: `src/backend/services/analysis.ts`
- Test: `src/backend/tests/analysis.test.ts`

- [x] Keep Spotify overview and artist stats available even when ReccoBeats fails or returns partial data.
- [x] Do not store raw ReccoBeats data; the verified response is aggregated into a compact `audio_features` section instead.
- [x] Add a derived section only for fields the popup actually renders or will render soon; avoid storing unbounded raw payloads in KV unless needed for debugging.

---

## Track C - ReccoBeats Key and Naming Cleanup

Preserve this older plan item, but perform it after Track B confirms no auth key is needed.

**Files to audit:**
- `src/backend/types/env.ts`
- `src/backend/tests/**/*.ts`
- `src/backend/tests/setup.ts`
- `.github/workflows/*.yml`
- `src/backend/wrangler.toml`
- `src/backend/README.md`
- `src/backend/docs/*.md`
- `docs/**/*.md`
- `dev-docs/**/*.md`

- [x] Remove `RECOCOBEATS_API_KEY` from active backend types/tests/workflows if no longer used.
- [x] Remove or rewrite `RECCOBEATS_API_KEY` docs that claim ReccoBeats requires a secret.
- [x] Keep a changelog/docs note explaining that the old misspelled `RECOCOBEATS` config was unused.
- [x] Verify with `rg -n "RECOCOBEATS|RECCOBEATS_API_KEY"` and intentionally classify any remaining historical references.

---

## Track D - Deferred Queue Hardening Plan

The older Phase 3 queue work is still valid as a production hardening concern, but it is not part of the immediate analysis repair.

Track D planning is complete in `dev-docs/plans/analysis-queue-hardening.md`. That follow-up plan covers:

- Worker export structure: whether the existing Hono worker and queue consumer live in the same module or separate Worker entry points.
- `wrangler.toml` queue producer/consumer config for development and production.
- `Env` typing for `ANALYSIS_QUEUE`.
- Queue message type and token lifetime strategy. Do not enqueue an access token if it can expire before processing; consider session lookup or refresh in the consumer.
- Status transitions: `queued -> processing -> completed` and retry-visible failure states.
- Idempotency: repeated queue deliveries must not corrupt status or overwrite newer jobs.
- Tests for retry, duplicate delivery, and completed result persistence.

Queue implementation remains deferred to that separate plan.

---

## Verification Checklist

After Track A:

- [x] `cd src/backend && npm run test:run`
- [x] `cd src/backend && npm run lint`
- [x] `cd src/backend && npm run build`
- [x] `POST /analysis/playlist/{id}` returns `status: "processing"` without waiting for full analysis.
- [x] `GET /analysis/playlist/{id}/status` eventually returns `completed` for a small playlist.
- [x] `GET /analysis/playlist/{id}/results` returns the canonical schema, not 404.
- [ ] Double-clicking a playlist card opens the Playlist Analysis popup.
- [ ] Duration and artist sections populate.
- [ ] Genre distribution either populates or shows "No genre data available" without failing the job.

After Track B/C:

- [x] `dev-docs/reccobeats-api-contract.md` records the verified endpoint contract.
- [x] No code calls `https://api.recocbeats.com`.
- [x] No code calls unverified `/v1/analyze`.
- [x] No active code/test env requires `RECOCOBEATS_API_KEY` or `RECCOBEATS_API_KEY` unless B1 proves auth is required.

After Track D:

- [ ] Analysis for a 300-track playlist completes without Worker timeout.
- [ ] If a Worker restarts mid-analysis, the job retries automatically.
- [ ] Duplicate queue delivery is idempotent.
- [ ] Status correctly transitions `queued -> processing -> completed`.
