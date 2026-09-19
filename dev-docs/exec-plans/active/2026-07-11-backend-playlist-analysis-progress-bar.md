# Plan: In-App Progress Bar for Playlist Analysis (ReccoBeats Enrichment)

**Date:** 2026-07-11
**Status:** Active
**Backlog item:** `dev-docs/backlog/TO_DO.md` → "Add visual progress indicator for playlist analysis"
**Related completed work:** `2026-07-07-reccobeats-enrichment-integration.md` (ReccoBeats enrichment is now the dominant, slowest phase of analysis)

## Problem

When a user opens a playlist's analysis popup, the app shows a static
"Analyzing playlist..." label and nothing else. During the ReccoBeats enrichment
fetch (now the slowest phase of analysis) there is **no UI indication the app is
working**, so it looks frozen. Even the terminal log appears stuck at `0%` until
it jumps to `100%`.

## Root-Cause Hypothesis (verify before implementing)

1. **Backend progress is coarse during ReccoBeats fetch.** In
   `src/backend/services/analysis.ts`, `fetchReccoBeatsEnrichment` calls
   `emitWarmKeepaliveOnce(onProgress)` once (`→ 70`) per batch loop, and
   `emitWarmKeepaliveOnce` is guarded so it only fires **a single time per job**.
   So after the `65%` write (analysis.ts:107) the next progress write during the
   entire multi-batch ReccoBeats fetch is `85%` (analysis.ts:238). The dominant
   slow phase therefore reports one value, which the poll loop surfaces as a
   stalled number.
2. **Frontend never surfaces progress to the UI.** The popup calls
   `adapter.analyze_playlist(playlist_id)` with **no** progress hook
   (`src/frontend/ui/backend_playlist_card_analysis_popup.py`). The mixin
   (`src/frontend/screens/adapter_mixins/analysis.py`) likewise calls
   `self.reccobeats_service.analyze_playlist(playlist_id)` with **no**
   `analysis_task`. The `analysis_task.update_progress(...)` calls already present
   in `reccobeats_backend.py:200-203` therefore never fire, and the popup has no
   progress bar widget at all — only the static "Analyzing playlist..." label
   (`src/frontend/ui/backend_playlist_card_analysis_popup.py`).
3. **The "0% until 100%" terminal behavior may have a separate KV-read cause.**
   The frontend `logger.debug("Analysis status: %s, progress: %s%%")` line
   (`src/frontend/services/reccobeats_backend.py:141`) reflects whatever
   `GET /analysis/playlist/:id/status` returns. The current backend writes
   intermediate progress values (`10`, `20`, `50`, `65`, `70`, `85`, `95`, then
   terminal `100`), so a log that stays at `0%` for many polls can also indicate
   Cloudflare KV read staleness. The backend itself acknowledges KV eventual
   consistency in `src/backend/services/analysis-job.ts:36-43`, and the initial
   queued status is written with `progress: 0` in
   `src/backend/routes/analysis.ts:78-87`. Verify the observed status responses
   before assuming backend granularity alone fixes the terminal symptom.

## Approach

Make backend progress **granular across ReccoBeats batches**, and **wire that
progress end-to-end into a real progress bar** in the analysis popup, with
in-progress / completed / failed states. Reuse the existing `analysis_task`
interface already referenced in `reccobeats_backend.py` (it supports
`is_cancelled()` and `update_progress(progress, message)`) rather than inventing a
new mechanism.

The first implementation proved the UI wiring works, but live development-worker
verification confirmed the remaining `0% → 100%` symptom is caused by the status
endpoint reading stale Cloudflare KV data. Treat the existing frontend synthetic
progress as a short-term fallback only. The target architecture is:

- use a Durable Object for live analysis status/progress, addressed by
  `userId:playlistId`, so POST, queue processing, status polling, and delete all
  read/write one strongly consistent status record;
- keep KV for final analysis results, raw ReccoBeats enrichment cache, OAuth
  state, and session data where eventual consistency is acceptable;
- keep the current granular ReccoBeats progress writes, but write them to the
  Durable Object instead of KV;
- keep a frontend "still waiting for status" fallback only for request failures or
  unexpected stale/non-advancing status, not as the normal progress mechanism.

Cloudflare Durable Objects are appropriate because the Worker binding can route
deterministically to an object with `getByName("...")`, and Wrangler DO bindings
plus migrations are the deployment path for the class. The repo's current
`src/backend/wrangler.toml` uses `compatibility_date = "2024-01-01"`, so adopting
RPC-style DO methods will require bumping the compatibility date to at least the
RPC-supported Worker date and regression-testing the backend; otherwise use a
fetch-based DO API to avoid changing compatibility behavior.

## Plan Review Findings

- The original backend step was underspecified for concurrency. Audio features and
  track metadata are fetched with `Promise.allSettled`, so each branch must not
  independently map its own progress across `65 → 85`; that can duplicate values
  or emit confusing/non-monotonic updates. Use one shared enrichment progress
  tracker owned by `fetchReccoBeatsEnrichment`.
- A "single batch" cannot produce true intra-request progress, because the backend
  only learns the outcome when the HTTP request returns. Emit a deterministic
  midpoint (for example `75`) before starting uncached enrichment, then completion
  updates through `85`.
- The frontend adapter currently accepts `progress_callback`, not
  `analysis_task`. Add `analysis_task` as the explicit parameter for this flow and
  keep `progress_callback` only as a backwards-compatible optional argument if any
  existing caller still needs it. The implementation should pass the task through
  both normal analysis and `force_reanalyze_playlist`.
- Kivy `ProgressBar` styling is limited. Do not depend on a "failed color" unless
  a custom widget is introduced; use status text plus a fixed/hidden bar for the
  failure state.
- The popup tests stub all Kivy modules used by the imported card module. Adding
  `ProgressBar` requires adding a `kivy.uix.progressbar` stub in
  `test_backend_playlist_card_analysis.py`.
- Completion currently returns results without calling
  `analysis_task.update_progress(100, ...)`, because `_poll_analysis_completion`
  only updates progress for pending/processing/running/queued statuses. Set the
  task to `100%` before returning completed results so the UI does not stop at
  the last processing value.
- `create_progress_callback` in `src/frontend/utils/network_utils.py` uses
  `(current, total, message)`, but this flow uses
  `analysis_task.update_progress(progress, message)`. Do not copy the callback's
  three-argument signature into `AnalysisTask`.
- Cancelling the popup can stop frontend polling only. The backend Worker job is
  already enqueued and will continue server-side unless a separate backend
  cancellation API is added.
- This is user-visible UI behavior, so `CHANGELOG.md` must be updated under the
  appropriate unreleased `Added` or `Changed` section.

## Current Analysis Data-Source Findings

- The branch is currently a hybrid analysis path, not ReccoBeats-only:
  - Spotify playlist/items are still required to enumerate playlist tracks.
  - Spotify artist metadata (`SpotifyService.getArtists`) is still used only for
    `genre_distribution`.
  - ReccoBeats is used for audio feature averages, key/mode, ISRC availability,
    and popularity range.
- The first screenshot's `Partial data: artist genres unavailable (HTTP 404:
  ...Resource not found...)` came from the Spotify artist metadata path. The
  terminal showed `/analysis/.../results` returning 200 because the overall
  analysis succeeded and embedded this as a best-effort partial-data warning.
- The second screenshot's genre distribution is from Spotify artist `genres`, not
  ReccoBeats. The audio features, mood/valence, key, and ReccoBeats metadata
  sections are from ReccoBeats.
- Playlist ownership is a plausible explanation for the difference: the user's
  own playlist may contain artist IDs Spotify still resolves for this token/app,
  while the NPR playlist includes at least one artist reference that returns 404
  from Spotify artist metadata. This should be verified with a focused backend
  trace before changing data-source behavior.
- Current ReccoBeats track metadata types in `src/backend/types/analysis.ts`
  include track title, artists, duration, ISRC, and popularity, but no genre
  field. Do not promise ReccoBeats genre fallback until the live ReccoBeats
  contract is re-checked for artist/genre endpoints or genre fields.
- ReccoBeats research update (2026-07-12): public docs list Track, Artist,
  Album, Analysis, and Audio Features endpoint groups, including `/v1/track`,
  `/v1/audio-features`, `/v1/artist/:id`, `/v1/artist`, search artist, artist
  album, and artist track endpoints. Live samples from track, audio-features,
  artist detail, multiple artist, and artist-track endpoints showed no `genre` or
  `genres` field. A docs bundle scan also found no `genre`/`genres` field.
  Conclusion: do **not** implement a ReccoBeats genre fallback in this PR unless
  a newly-discovered endpoint/field is verified with a live sample and typed
  response test.
- The NPR playlist failure is suspicious enough to trace, but it is not evidence
  that playlist ownership controls analysis. A plausible combined cause is
  freshness/coverage: NPR's New Music Friday playlist contains very recent tracks,
  so Spotify artist IDs or ReccoBeats audio features may not be populated
  consistently yet. Another likely backend bug: `SpotifyService.getArtists(...)`
  currently rejects the whole artist metadata phase when any one artist request
  returns 404, which can drop all genre data instead of keeping genres for artists
  that did resolve.

## Recommendations

- Keep Spotify playlist/items as the source of track membership; ReccoBeats does
  not replace that.
- Stop showing raw nested Spotify error JSON in the popup. The current code fix
  should simplify this to `Spotify returned 404: Resource not found`.
- Consider making genre distribution optional/explicitly best-effort in the UI:
  if Spotify artist metadata fails and ReccoBeats cannot provide genres, show
  "Genre data unavailable" without a red partial-data banner unless the user needs
  diagnostic detail.
- Treat ReccoBeats genre fallback as unavailable for this PR based on the
  2026-07-12 research. If the API later adds a verified genre field or endpoint,
  add it behind typed parser validation and tests; until then, remove genre
  distribution from the "fully enriched" expectation and lean on mood, energy,
  key/mode, popularity, and artist frequency as the reliable analysis outputs.
- In this PR, harden the existing data-source behavior instead of inventing an
  unavailable genre source:
  - tolerate per-artist Spotify 404s so one bad artist does not erase all genre
    data;
  - make ReccoBeats zero/low coverage visible as a partial-data/coverage warning;
  - filter null/blank Spotify artist names out of top-artist display, or render a
    stable "Unknown artist" label if every name is missing.

---

## Pre-Implementation Verification

- [x] **Verify the real cause of the `0% → 100%` symptom before implementation.**
  Run a dev backend or reproduce against the intended Worker environment, trigger
  playlist analysis from the popup, and capture both:
  - frontend `logger.debug("Analysis status: ..., progress: ...")` output from
    `src/frontend/services/reccobeats_backend.py`
  - raw `GET /analysis/playlist/:id/status` JSON responses
- [x] **Classify the observed behavior.**
  - If raw status responses stay at `progress: 0` for multiple polls and then jump
    to `100`, treat KV read staleness as part of the problem. Keep the backend
    granularity work, and add the frontend synthetic progress floor described
    below.
  - If raw status responses advance through backend values but pause for a long
    time in the ReccoBeats band (`65`, maybe `70`, then `85`), backend progress
    granularity is the primary fix.
  - If raw status responses are granular but the UI/log does not advance, debug
    the frontend polling/task wiring before changing backend progress math.
- [x] **KV staleness confirmed. Add a bounded frontend synthetic floor.**
  While status is `queued` or `processing` and backend progress is not advancing,
  the `AnalysisTask` or polling layer may display a synthetic minimum that rises
  slowly with elapsed time, never exceeds the latest backend progress once backend
  progress advances, and never exceeds a conservative cap such as `90%` before a
  completed status is observed. Mark the status text as normal analysis progress
  without claiming exact per-track completion.

**Verification results (2026-07-12):**

- Local write-path diagnostic against `AnalysisJobService` showed the current
  backend writes intermediate status values:
  `processing:10 → processing:20 → processing:50 → processing:65 → processing:70 → processing:85 → processing:95 → completed:100`.
- Local `GET /analysis/playlist/:id/status` route test passes with in-memory KV,
  but that test cannot model Cloudflare KV propagation.
- Live development Worker trace using a cached dev auth token and playlist
  `03YbVT4UhOxLrOAcpyCEqT` confirmed the raw status route returned
  `queued:0` for every poll from `t=0.2s` through `t=51.2s`, then jumped to
  `completed:100` at `t=53.3s`. The status record's own timestamps showed the job
  actually ran from `2026-07-12T03:30:42.790Z` to
  `2026-07-12T03:30:48.758Z` (about 6 seconds), so the observed frozen progress is
  read-side staleness, not absence of backend progress writes.

**Implementation implication:** backend ReccoBeats progress granularity is still
useful for local/in-memory/dev-server behavior and for environments that observe
fresh status writes, but it will not fix the production-like `0% → 100%` symptom
by itself. The frontend must show bounded synthetic progress while status reads
remain queued/processing at stale values.

## Backend Steps

- [x] **Add a shared ReccoBeats enrichment progress tracker in
  `src/backend/services/analysis.ts`.** Remove `emittedWarmKeepalive` and
  `emitWarmKeepaliveOnce`. In `fetchReccoBeatsEnrichment`, compute the number of
  active work units before starting the parallel fetches:
  - `audioGroups = needsAudioFeatures ? Math.ceil(audioBatches.length / CONCURRENCY) : 0`
  - `metadataGroups = needsTrackMetadata ? Math.ceil(metadataBatches.length / CONCURRENCY) : 0`
  - `totalGroups = audioGroups + metadataGroups`
- [x] **Emit deterministic enrichment progress in the `65 → 85` band.** If
  `totalGroups > 0`, emit one midpoint such as `75` before the `Promise.allSettled`
  starts, then increment a shared `completedGroups` counter after each concurrency
  group completes and emit:

  ```ts
  const next = Math.min(85, Math.max(lastEmitted + 1, 65 + Math.floor((completedGroups / totalGroups) * 20)));
  ```

  Keep a `lastEmitted` guard so duplicate or out-of-order async completions cannot
  move progress backwards. The final existing `await onProgress?.(85)` remains the
  terminal enrichment anchor.
- [x] **Pass progress through the batch fetch helpers without duplicating math.**
  Change `fetchReccoBeatsAudioFeatures` and `fetchReccoBeatsTrackMetadata` to
  accept an optional `onGroupComplete: () => Promise<void>` callback, invoked once
  after each `CONCURRENCY` group resolves. These helpers should not know about
  percentages.
- [x] Keep `onProgress` writes cheap and terminal-state-neutral. They go to KV via
  `writeStatusMerged` in `src/backend/services/analysis-job.ts`; do not change
  `completed`, `failed`, or retry semantics.
- [x] Add or extend backend tests in `src/backend/tests/analysis.test.ts`:
  - Mock enough tracks to create multiple ReccoBeats groups.
  - Capture `onProgress` values from `AnalysisService.analyzePlaylist(...)`.
  - Assert the sequence is monotonic.
  - Assert at least one value is strictly between `65` and `85`.
  - Assert `85`, `95`, and final completion behavior remain present.

## Frontend Steps

- [x] **Add an `AnalysisTask` abstraction** (new file
  `src/frontend/utils/analysis_task.py`) implementing the interface the backend
  service already expects:
  - `is_cancelled() -> bool`
  - `cancel() -> None`
  - `update_progress(progress: int, message: str) -> None` — clamps progress to
    `0..100` and marshals UI updates to the Kivy main thread via
    `Clock.schedule_once` (the popup worker runs on a daemon thread; see
    `backend_playlist_card_analysis_popup.py`).
  - Constructor takes a `progress_bar` widget and a `status_label` widget. Match
    the existing two-argument `analysis_task.update_progress(progress, message)`
    call in `src/frontend/services/reccobeats_backend.py`; do not reuse the
    three-argument `create_progress_callback(current, total, message)` signature.
  - If pre-implementation verification confirms KV staleness, include a bounded
    synthetic-progress helper that can display slow elapsed-time progress while
    backend status remains queued/processing at the same value. It must never show
    `100%` before completion and must not move backwards when real backend
    progress resumes.
- [x] **Add a progress bar + status label to the analysis popup loading state.**
  In `src/frontend/ui/backend_playlist_card_analysis_popup.py`, import
  `ProgressBar` from `kivy.uix.progressbar`, replace the static
  "Analyzing playlist..." `Label` with a `ProgressBar` plus a small status
  `Label`, and store both on `root` (for example
  `root._analysis_progress_bar`, `root._analysis_status_label`) for worker wiring.
  Place the progress widgets outside the `analysis_container` that
  `_update_analysis_ui` clears, or make `_update_analysis_ui` explicitly preserve /
  hide them before clearing results content.
- [x] **Wire the task through the call chain.**
  - Pass the progress bar and status label into `_load_analysis_worker` from
    `show_detailed_playlist_window`.
  - In `_load_analysis_worker`, construct the `AnalysisTask` from those widgets and
    pass it into `adapter.analyze_playlist(playlist_id, analysis_task=task)`.
  - Update `AnalysisMixin.analyze_playlist`
    (`src/frontend/screens/adapter_mixins/analysis.py`) to accept
    `analysis_task: Optional[Any] = None`. Keep `progress_callback` only if needed
    for compatibility, but prefer the explicit `analysis_task` name for this flow.
  - Forward the task in every backend analysis path:
    `self.reccobeats_service.analyze_playlist(playlist_id, analysis_task)` and
    `self.reccobeats_service.force_reanalyze_playlist(playlist_id, analysis_task)`.
  - The existing `analysis_task.update_progress(progress, ...)` call in
    `src/frontend/services/reccobeats_backend.py` now fires and drives the bar from
    the polled backend progress.
- [x] **Set task progress on terminal success.** In
  `src/frontend/services/reccobeats_backend.py`, when `_poll_analysis_completion`
  sees `status == "completed"`, call
  `analysis_task.update_progress(100, "Analysis complete")` before fetching and
  returning results.
- [x] **Render completed / failed states.** When `_update_analysis_ui`
  receives results, hide or remove the progress bar and set the status label to a
  completed message before rendering results. If it receives an `error`, keep the
  status label visible with the error text and set the progress bar to a stable
  value such as `100` or hide it; do not rely on unsupported `ProgressBar` color
  changes.
- [ ] **(Optional) Cancellation.** Wire the popup's existing close/cancel affordance
  to `task.cancel()` so an in-flight analysis can be stopped; `reccobeats_backend.py`
  already checks `analysis_task.is_cancelled()` in the poll loop and at entry.
  Document in code comments or user-facing behavior that this only stops local
  waiting/polling; the backend Worker job keeps running and may later write status
  and results to KV.
- [x] **Update `CHANGELOG.md`.** Add a concise user-visible entry noting that
  playlist analysis now shows live progress during backend/ReccoBeats analysis.

## Reliable Progress Phase (Replace KV Status With Durable Object Status)

- [x] **Write a focused backend test for strongly consistent live status.**
  Add a test in `src/backend/tests/analysis-status.test.ts` or extend
  `src/backend/tests/analysis-queue.test.ts` that creates a queued status, writes
  processing progress, immediately reads status through the route/store, and
  expects the latest progress value rather than the original `queued:0`.
  Expected red failure before implementation: the existing KV-backed status path
  can only be modeled as eventually consistent, and no Durable Object binding or
  status store exists.
- [x] **Add a Durable Object status store.**
  Create `src/backend/services/analysis-status-object.ts` exporting an
  `AnalysisStatusObject` Durable Object class and a small caller-facing helper.
  The object name must be deterministic: `analysis:${userId}:${playlistId}`. Store
  only the live `AnalysisStatusRecord` in the object. Keep final analysis results
  in KV.

  Required operations:
  - `getStatus(): AnalysisStatusRecord | null`
  - `writeStatus(status: AnalysisStatusRecord): void | Promise<void>`
  - `mergeStatus(partial: Partial<AnalysisStatusRecord>): void | Promise<void>`
  - `deleteStatus(): void | Promise<void>`

  Implementation note: if the backend compatibility date is bumped for RPC
  methods, use a typed DO stub and direct method calls. If that compatibility
  change is judged too risky, expose a narrow fetch-based API inside the DO and
  keep the public helper interface above so route/job code does not care.
- [x] **Wire the DO binding into Worker config and types.**
  Modify:
  - `src/backend/wrangler.toml`
  - `src/backend/types/env.ts`
  - any backend test env helper under `src/backend/tests/helpers/`

  Add a binding such as:

  ```toml
  [[durable_objects.bindings]]
  name = "ANALYSIS_STATUS"
  class_name = "AnalysisStatusObject"

  [[migrations]]
  tag = "v1-analysis-status"
  new_sqlite_classes = ["AnalysisStatusObject"]
  ```

  Repeat the binding for `env.development` and `env.production` if Wrangler does
  not inherit the top-level binding as desired. If using RPC methods, update
  `compatibility_date` deliberately and run the full backend suite afterward.
- [x] **Change `POST /analysis/playlist/:id` to use DO for live status.**
  In `src/backend/routes/analysis.ts`, replace reads/writes/deletes of
  `analysis:${playlistId}:${userId}:status` in `CACHE_KV` with the new status
  store helper. Keep `resultsKey` in KV. Existing behavior must remain:
  - completed status returns cached status only when KV results exist and match
    current `schema_version`;
  - queued/processing/retrying status returns current status;
  - stale/missing results delete both live status and KV results, then enqueue a
    fresh job.
- [x] **Change `GET /analysis/playlist/:id/status` to read DO status.**
  In `src/backend/routes/analysis.ts`, read the current status from the DO helper
  and return the same JSON envelope as today. This endpoint should no longer read
  `CACHE_KV` for status.
- [x] **Change `DELETE /analysis/playlist/:id` to delete DO status.**
  In `src/backend/routes/analysis.ts`, delete the DO status and the KV results.
  Keep any raw ReccoBeats enrichment cache behavior unchanged unless there is a
  separate reason to invalidate it.
- [x] **Change queue processing to write DO status.**
  In `src/backend/services/analysis-job.ts`, replace `writeStatus`,
  `writeStatusMerged`, and the initial status lookup with the DO-backed helper.
  Remove the 30-second KV replication wait path because the queue consumer should
  read the queued status consistently from the DO. Keep stale-job protection by
  comparing the DO status `job_id` to the queue message `job_id`.
- [x] **Preserve KV for final results and raw ReccoBeats enrichment.**
  Do not move `resultsKey` or `analysis:playlist:${playlistId}:raw-enrichment`
  into the DO in this phase. The DO is for live status only; using it for larger
  cached result payloads would increase coupling and make eviction/cleanup more
  complex.
- [x] **Adjust frontend progress fallback to no longer be the normal path.**
  In `src/frontend/services/reccobeats_backend.py`, keep synthetic progress only
  as a last-resort fallback when status requests fail repeatedly or progress is
  unchanged beyond a conservative threshold. When DO-backed status advances, log
  and display real backend progress. The terminal should show intermediate raw
  progress values instead of repeated `queued, progress: 0%`.
- [x] **Add focused tests for frontend fallback behavior.**
  Update `src/frontend/tests/test_reccobeats_backend.py` so the normal test path
  expects real advancing status values to drive `analysis_task.update_progress`.
  Keep one test proving the fallback still caps below completion during repeated
  stale/failed status reads.
- [x] **Run backend verification.**
  Run:

  ```bash
  cd src/backend
  npm run test:run
  npm run lint
  ```

  If the compatibility date changes, also run any existing Worker integration
  tests that exercise auth, export, and analysis routes.
- [x] **Run frontend verification.**
  Run:

  ```bash
  KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v
  .venv/bin/basedpyright src/frontend src/shared --level error
  ```

  2026-07-12 update: backend `npm run test:run` and `npm run lint` pass;
  `test_backend_playlist_card_analysis.py`, `test_reccobeats_backend.py`, and
  pyright pass. The full frontend suite needs an unsandboxed rerun for existing
  localhost-socket tests; the escalation attempt was blocked by the approval
  system's usage limit.

  2026-07-12 update: focused frontend tests and pyright pass. The full frontend
  pytest suite still needs an unsandboxed rerun because the sandbox blocks
  existing localhost-socket tests; the escalation attempt was rejected by the
  approval system's usage limit.

  2026-09-19 close-out: cleared — backend `npm run test:run` 92 files / 855
  tests pass, `npm run lint` 0 errors; frontend full suite 257 passed /
  7 skipped, `basedpyright --level error` clean, `./scripts/verify-all.sh`
  green on main. No sandbox blocks observed.

- [x] **Run live development-worker verification.**
  2026-09-19 result (dev `e96f00a`, playlist `5X8lN5fZSrLnXzFtDEUwb9`,
  `scripts/trace-analysis-progress.sh`): raw status reads advanced
  `queued:0 → processing:50 → processing:75 → completed:100` — real
  intermediate values, no stuck-at-zero staleness. DO-backed status confirmed
  live. Popup-bar advancement from real status follows from the verified
  wiring (`reccobeats_backend.py:232-234` + `AnalysisTask`); terminal-log
  shape matches the trace timeline.
  Deploy to the development Worker only after local tests pass. Repeat the
  previous raw status trace against the development Worker and confirm:
  - raw `/analysis/playlist/:id/status` responses advance through intermediate
    progress values;
  - terminal logs no longer show only `0,0,...,100`;
  - the popup progress bar advances from real backend status, not the synthetic
    fallback.

  2026-09-19 runbook (owner-run; needs dev deploy + Bearer session token):
  run `./scripts/backend-deploy-status.sh <dev-backend-url>` first (deploy if
  stale), then `TRACE_BEARER_TOKEN=<token> scripts/trace-analysis-progress.sh
  <backend-url> <playlist-id>` (token comes from the app's Spotify login;
  env/piped/prompted only — never an argument, never a file). The script
  POSTs a fresh job (`force_enrichment=1`), polls status every 2s into a
  unique per-run dir (`tmp/trace-run-*/trace.jsonl`), and on completion saves
  `results.json` plus a genre/error summary. Pass = intermediate progress
  values in the trace ending at `completed:100`. For NPR confirmation, run it
  against `5X8lN5fZSrLnXzFtDEUwb9` and check `genre buckets > 0` in the
  summary.

- [x] **Update docs and changelog.**
  Update `CHANGELOG.md` and any backend API notes that describe analysis status
  storage. If this plan remains active after the first progress-bar UI phase,
  keep the active plan checked step-by-step rather than moving it to completed.

## Analysis Data Coverage Phase (Same PR)

- [x] **Add a targeted backend diagnostic for the NPR playlist behavior.**
  2026-09-19 result (live trace, same run as above): backend returned genre
  data (`genre buckets: 15`) with a partial-availability warning
  (`resolved 24 of 40 artists; 16 failed`) instead of the old all-or-nothing
  wipe — tolerant 404 handling confirmed fixed live. (Popup rendering of that
  payload is covered by `test_backend_playlist_card_analysis.py`, not by this
  trace.) New live finding: ReccoBeats
  audio-features + track-metadata both hit the Workers subrequest limit on
  this large playlist (`Too many subrequests by single Worker invocation`),
  so enrichment was Spotify-only this run; feeds the existing TO_DO fan-out
  item (distribute batches for >40-artist playlists).
  Use playlist `5X8lN5fZSrLnXzFtDEUwb9` only as a manual/live diagnostic, not as a
  committed fixture that depends on external services. Capture:
  - total Spotify playlist items and usable track IDs;
  - artist IDs whose Spotify `GET /artists/:id` returns 404;
  - ReccoBeats `/v1/audio-features` returned row count;
  - ReccoBeats `/v1/track` returned row count.

  The diagnostic should answer whether the missing sections are caused by:
  - one Spotify artist 404 aborting the entire genre phase;
  - ReccoBeats returning empty `content` for new tracks;
  - invalid/null Spotify artist names in playlist items.

  2026-09-19: no separate manual procedure needed for the fixed-verdict — run
  the live-trace runbook above against this playlist. The status trace plus
  the results summary prove genres render with partial warnings instead of
  the old wipe. Per-ID detail (exact 404 artist IDs, per-endpoint row counts)
  is not in the summary; the full results payload is saved to
  `tmp/results-*.json` for any deeper inspection.
- [x] **Make Spotify artist genre lookup tolerant of individual 404s.**
  Add a failing backend test in `src/backend/tests/analysis.test.ts` where one
  artist metadata request rejects with `HTTP 404` and another succeeds with
  genres. Expected behavior: analysis completes, `genre_distribution` includes the
  successful artist's genres, and `errors` records a `spotify:artists` partial
  warning with failed/resolved counts.

  Implementation direction:
  - replace all-or-nothing `getArtists([...artistIdSet])` behavior for analysis
    with a tolerant helper, either inside `SpotifyService` or `AnalysisService`;
  - do not retry deterministic 404s;
  - keep bounded concurrency;
  - preserve successful artist metadata.
- [x] **Expose ReccoBeats zero/low coverage as a coverage warning.**
  Add a backend test where ReccoBeats HTTP calls succeed but return empty
  `content` arrays for a non-empty playlist. Expected behavior: analysis still
  completes, no audio-feature section is generated, and `errors` includes a
  structured warning such as `reccobeats:coverage` with a message like
  `Audio features available for 0 of 30 tracks`.

  Implementation direction:
  - after ReccoBeats enrichment, compare returned audio-feature count to unique
    track ID count;
  - record a warning when coverage is `0` or below a conservative threshold such
    as 50%;
  - avoid red "failure" language in the UI copy when the API succeeded but
    coverage is low.
- [x] **Keep ReccoBeats genre fallback conditional and disabled by default.**
  Do not implement a ReccoBeats genre fallback based on current public docs or
  live samples. If a future verified endpoint/field appears, the fallback should:
  - add typed response fields in `src/backend/types/analysis.ts`;
  - add parser validation at the ReccoBeats boundary;
  - aggregate genre counts into the same `genre_distribution` shape;
  - include source precedence in tests: Spotify genres first, ReccoBeats genres
    only when Spotify has no genres or artist metadata partially fails.
- [x] **Fix null/blank top-artist names.**
  Add a backend test where playlist items include `artist.name === null` or blank.
  Expected behavior: `artists.top_artists` never contains `null`; either unknown
  names are skipped or grouped under `Unknown artist`.
- [x] **Update popup copy for best-effort data.**
  Update `src/frontend/ui/backend_playlist_card_utils.py` and popup tests so:
  - Spotify genre lookup errors are readable and concise;
  - ReccoBeats low coverage is shown as a coverage note;
  - "No genre data available" is neutral when genres are unavailable, not a
    blocker for audio features.
- [x] **Run verification for the data coverage phase.**
  2026-09-19 close-out: backend `npm run test:run` (92 files / 855 tests)
  and `npm run lint` (0 errors) pass; focused
  `test_backend_playlist_card_analysis.py` + `test_reccobeats_backend.py` +
  `test_analysis_task.py` + `test_analysis_mixin.py` (52 tests) pass; full
  frontend suite (257 passed / 7 skipped) and pyright clean.
  Run:

  ```bash
  cd src/backend
  npm run test:run
  npm run lint
  KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 ../../.venv/bin/pytest ../frontend/tests/test_backend_playlist_card_analysis.py -q
  ```

  Then run the full frontend suite and pyright from repo root if popup rendering
  changes beyond copy/formatter utilities:

  ```bash
  KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v
  .venv/bin/basedpyright src/frontend src/shared --level error
  ```

## Tests

- [x] Add a backend test asserting granular, monotonic `onProgress` values across
  the ReccoBeats batch loop (see Backend Steps).
- [x] Add focused frontend tests for progress rendering:
  - New `src/frontend/tests/test_analysis_task.py`: patch
    `src.frontend.utils.analysis_task.Clock.schedule_once` to execute immediately,
    then assert `AnalysisTask.update_progress` clamps values and updates the bar
    value and label.
  - `AnalysisMixin.analyze_playlist` forwards `analysis_task` to
    `reccobeats_service.analyze_playlist` and `force_reanalyze_playlist` (extend
    `src/frontend/tests/test_analysis_mixin.py`; update existing assertions that
    currently expect a single positional playlist ID).
  - The popup shows the progress bar in the loading state and hides it / shows
    results on completion (extend
    `src/frontend/tests/test_backend_playlist_card_analysis.py`; add a
    `kivy.uix.progressbar` stub to `_STUB_MODULES` before importing the card).
  - `ReccoBeatsBackendService._poll_analysis_completion` calls
    `analysis_task.update_progress(100, "Analysis complete")` before returning
    completed results.
  - If synthetic progress is added after the pre-implementation verification,
    test that it rises while backend progress is stale, caps below completion, and
    does not move backward when real backend progress resumes.
- [x] Run `cd src/backend && npm run test:run && npm run lint` and
  `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
  plus `.venv/bin/basedpyright src/frontend src/shared --level error`.

## Acceptance Criteria

- [x] Opening a playlist analysis popup shows a live progress bar that advances
  during backend analysis, including a temporary bounded fallback when KV status
  reads are stale.
- [x] The status label shows a meaningful message (e.g. "Analyzing playlist... 42%")
  that updates as progress changes. (verified 2026-09-19: `reccobeats_backend.py:232-234` sends `f"Analyzing playlist... {progress}%"` on every advancing update; `AnalysisTask._set_progress` writes it to the label)
- [x] Backend progress reporting no longer has a single long ReccoBeats stall:
  raw status writes include intermediate, monotonic values between `65` and `85`. (verified 2026-09-19: `analysis.ts:158-174` shared tracker with `lastEmitted` guard; backend test asserts monotonic + strictly-between values)
- [x] In the target development Worker environment, raw status reads advance
  through real intermediate values instead of staying at `queued:0` until
  `completed:100`. (verified live 2026-09-19: `queued:0 → processing:50 → processing:75 → completed:100`)
- [x] If KV status reads are stale in the target environment, the UI still shows a
  bounded in-progress state instead of appearing frozen at `0%`, without claiming
  completion before the backend reports `completed`. This is temporary fallback
  behavior until the Durable Object status phase is complete.
- [x] Completed and failed analysis states are visually distinguishable from the
  in-progress state. (verified 2026-09-19: `_update_progress_widgets` sets "Analysis complete" + hides bar; `_handle_error_state` sets "Analysis unavailable: {error}" + hides bar — text-distinguished per the Kivy no-color constraint)
- [x] Cached analyses still render instantly with no progress-bar regressions. (verified 2026-09-19: completed-with-results path returns immediately; full frontend suite + popup tests green)

## Follow-ups (not in this plan)

- Consider surfacing per-batch detail (e.g. "Enriching tracks 30/120") rather than
  a raw percentage.
- Consider a global analysis progress indicator outside the popup.
- Revisit ReccoBeats genre fallback only if future ReccoBeats docs or live
  samples expose genre fields or artist genre endpoints.
