# Analysis Fan-Out Queue Plan — Large Playlists

**Date:** 2026-09-19
**Branch:** `docs/fanout-queue-plan` (plan only; no code)
**Status:** draft v4 — revised per DeepSeek v3 review (finalizer lease,
force-param split, POST-atomicity hardening)
**Backlog link:** `dev-docs/backlog/TO_DO.md` → "Refactor playlist analysis to fan-out queue architecture for large playlists"

## Goal

Split playlist analysis for large playlists into distributed per-batch queue
messages so no single Worker invocation exceeds the Cloudflare subrequest
budget, while small playlists keep the current single-message fast path
unchanged. Preserve every Track D queue behavior.

## Evidence (why now)

- Live trace 2026-09-19 (dev `e96f00a`, NPR `5X8lN5fZSrLnXzFtDEUwb9`):
  `reccobeats:audio-features` + `reccobeats:track-metadata` both failed with
  `Too many subrequests by single Worker invocation` — zero ReccoBeats
  enrichment that run. Recorded in the progress-bar plan.
- `src/backend/services/analysis.ts:261` silently caps artist metadata at
  `slice(0, 40)` — artists beyond 40 are dropped, not deferred.
- ReccoBeats batches are 30 IDs/request (`analysis.ts:161`); audio + metadata
  branches run `Promise.allSettled` inside ONE consumer invocation, so
  subrequest count scales with playlist size in a single invocation.

## Non-goals

- No frontend polling/status changes (DO status record already supports
  intermediate progress; frontend already renders it).
- No export-format or per-track-cache-key changes.
- No changes to the live status *record shape* (the countdown, failure
  markers, and finalizer claim are new DO-side state alongside it, not
  status fields).

## Constraints (normative)

1. **Track D preserved:** ack on success/invalid-body, up to 3 attempts then
   DLQ (`index.ts:78+`), `AUTH_REQUIRED`/`NON_RETRYABLE` never retried,
   stale-job protection via `job_id` comparison, status writes through the
   DO-backed store only.
2. **One logical change per PR, ≤400 lines** (repo convention).
3. **No `console.log`** in non-test backend code — structured logging.
4. **Types over raw dicts** at the new message/aggregation boundary.
5. All Spotify API calls stay in `services/spotify.ts`.

## Design (proposed — reviewers: challenge this)

Cloudflare Queues have no native fan-out barrier, so aggregate explicitly:

- **Chunking (worker-side seed, not POST):** the seed message's worker
  enumerates tracks (session/token context already exists; keeps POST latency
  flat), then decides single vs fan-out. Fan-out threshold: unique artists
  > 40 OR estimated subrequests > 40 (leave headroom under the 50 limit;
  exact budget math is Phase 0). Chunks split by track groups sized so one
  batch message (Spotify artist slice + ReccoBeats audio + metadata for its
  tracks) fits the budget.
- **Batch messages:** `{ job_id, playlist_id, user_id, chunk_id,
  chunk_index, chunk_count, track_ids[] }` — new Zod-validated type next to
  `AnalysisQueueMessage` (extend, don't break: old single-message shape keeps
  working; consumer routes on presence of `chunk_id`).
- **POST atomicity:** initialize the DO countdown FIRST (expected count,
  `created_at`), then enqueue all chunk messages with ONE `sendBatch`. If the
  batch send throws, a compensating DO op writes terminal user-visible
  `failed` (reason `fan-out enqueue aborted` — a valid `AnalysisJobStatus`,
  no type change) and resets the countdown so nothing hangs. Residual crash-window (die between
  init and send) is accepted: countdowns are keyed per `job_id`, orphaned
  ones never trigger finalize (no workers run), and a DO alarm deletes
  countdown state older than 24h. POST retries mint a fresh `job_id`.
- **`force_enrichment` split (no contradiction):** the flag fans out into two
  distinct behaviors. POST-with-force runs `deleteKnownKeys` for ALL
  enumerated track IDs exactly once, then enqueues. Chunk messages carry
  `force_resolve: true` (skip lookup, refetch their IDs) with
  `force_clear: false` — chunk workers MUST NOT call `deleteKnownKeys`
  (nothing left to delete; keeps sibling absent-sentinel writes safe).
  Finalize performs the post-success export-prefix invalidation (today's
  `analysis-job.ts:86` behavior) when the job-level force flag is set.
- **Aggregation:** each batch worker writes its partial result to a
  chunk-result key and merges progress into the shared DO status record
  (per-chunk progress band, monotonic guard shared with the existing
  tracker). Completion is tracked by an atomic countdown in the same DO:
  each worker calls ONE `registerChunkResult(job_id, chunk_id, ok)` op that
  records success/failure AND returns `isFinalizer` only to the single
  caller that completes the set — the finalizer claim is the atomic
  transition itself, never a post-register zero-read plus status pre-check
  (a redelivered message re-registering after finalize finds the claim taken
  and returns). The claim carries a timestamp: if the set is complete, the
  status is still non-terminal, and the claim is older than a 5-minute lease
  (finalizer crashed mid-finalize), a subsequent registration re-claims and
  re-runs finalize — stuck-finalize recovery without a watchdog process.
  The atomicity mechanism is explicit: ONE Durable Object SQLite storage
  transaction (`transactionSync` where the logic is synchronous, else
  `transaction()`) — DO awaits can interleave across events, so a bare
  read-modify-write is NOT sufficient. The finalizer runs finalize inline.
  A delayed finalize *message* was rejected: queue ordering is not
  guaranteed, so it could run before chunks complete.
- **Chunk failure:** a batch worker that exhausts retries registers `failed`
  for its chunk via the same atomic op before the message DLQs — otherwise
  the countdown hangs and finalize never runs. Chunk markers are
  NON-terminal: the legacy `markFailed` terminal status write must NOT run
  on chunk paths (it would poison finalize's view); finalize alone owns the
  terminal `completed`/`failed` write, naming failed chunks. EVERY terminal
  path registers a marker — including the `AUTH_REQUIRED`/`NON_RETRYABLE`
  fast path in the consumer (`index.ts:108-111`), which today only
  markFailed+acks: on chunk messages it must register the failure marker
  first. If that registration carries the finalizer grant (the completing
  failure — e.g. session revoked mid-fan-out), the consumer runs the
  stuck-finalizer backstop instead of acking into a wedge: complete set +
  non-terminal status forces terminal `failed` naming the stuck job.
- **Stale jobs:** every chunk worker reads DO status first and short-circuits
  on `job_id` mismatch OR terminal status (`completed`/`failed` — covers
  chunks sent by a partially-successful batch after a same-`job_id` cancel)
  before touching KV; merged status writes are guarded the same way
  (`job_id` match + non-terminal) so superseded chunks never clobber the
  new job, and finalize re-checks before the results write.
- **KV read-after-write:** partials live in KV (DO 128KB value limits rule
  out storing them there). Finalize lists expected chunk keys; any missing
  key is retried bounded (3 × 750ms — KV propagation is millisecond-scale;
  total worst case ~2.25s keeps tests under timeout) then fails the job naming
  the missing chunks.
- **Finalize:** merge partials (sum genre buckets, recompute audio-feature
  averages weighted by track count, union errors with per-chunk source tags).
  `schema_version`: all chunks run the same deployed code so versions are
  uniform — finalize takes the max and throws on mismatch, failing the job
  loudly (a mid-flight deploy race must not merge across versions silently),
  and existing bump rules apply to producers unchanged. Write KV
  results + terminal DO status. Idempotent: batch writes keyed by
  `(job_id, chunk_id)`; re-delivered batch messages overwrite identical
  partials and re-register (claim already taken → return); the
  terminal-status check remains as a backstop only, not the finalizer
  election.
- **Failure semantics per batch:** same as Track D (3 attempts → DLQ +
  `markFailed`, plus the DO failure marker above so the countdown completes).
- **Small-playlist fast path:** below threshold, byte-identical behavior to
  today (single message, same code path as now — not a parallel
  implementation).

## Resolved decisions (from kilo + agy v1 reviews)

1. **Finalize mechanism: DO atomic countdown, inline finalize.** Rejected KV
   get-then-set countdown (simultaneous finishers double-merge) and rejected
   delayed finalize message (queue ordering not guaranteed — could run before
   chunks complete). The DO owns an atomic remaining-counter; the worker that
   observes zero runs finalize inline, guarded by the terminal-status check.
2. **Threshold: static** (`unique artists > 40 OR estimated subrequests >
   40`) calibrated from Phase 0 measurements; dynamic per-run accounting only
   if static proves wrong at scale. Predictable and testable.
3. **Partials in KV, countdown in DO.** DO 128KB value limits rule out
   storing partials there; KV eventual consistency is handled by bounded
   finalize retries. DO stays small (status + counter + failure markers) to
   keep call volume bounded.

## Phase 0 — Budget math + message types

- [x] Measure: instrument per-phase subrequest counts on a large playlist
  (reuse `scripts/trace-analysis-progress.sh` + worker logs) to fix the
  fan-out threshold and chunk sizing with data, not guesses.
  (2026-09-20 live dev trace, NPR `5X8lN5fZSrLnXzFtDEUwb9`: completed in
  ~20s with zero subrequest errors; chunk sizing covered by
  `analysis-fanout.test.ts` threshold/budget unit tests.)
- [x] Add `AnalysisChunkMessage` Zod type + tests (valid single, valid chunk,
  reject malformed; old messages still validate).
- [x] Define chunk-result key format + merge-function contract (pure function
  signature first, implementation in Phase 2).

## Phase 1 — Chunking (worker-side seed)

- [x] Enumerate tracks, compute threshold decision, init DO countdown, then
  `sendBatch` N chunk messages or 1 legacy message (compensating failed-write
  on send failure — see Design). `force_enrichment` clears the per-track cache
  ONCE at seed time before enqueue; chunks carry `force_resolve` (lookup
  skip) with `force_clear: false`. Small playlists: zero behavior change
  (assert with existing tests + new threshold-boundary tests).
- [x] Tests: threshold boundaries, chunk coverage (every track in exactly one
  chunk), legacy-shape passthrough, force split (single pre-enqueue clear,
  no per-chunk deletes, export invalidation in finalize), send-failure
  countdown cancel.

## Phase 2 — Batch worker + finalize

- [x] Split the shared `force` boolean into `force_resolve` (lookup skip +
  refetch) and `force_clear` (deleteKnownKeys) through
  `resolveAudioFeatures`/`resolveTrackMetadata`
  (`reccobeats-track-cache.ts:161-191`) and the `analysis.ts:177-180` call
  sites, including the coalesce key. Without this, a chunk with
  `force_resolve: true` still calls `deleteKnownKeys` and races sibling
  absent-sentinel writes. Existing single-message callers pass both true
  (behavior unchanged); chunk workers pass resolve-only.
- [x] Batch worker: verify `job_id` against DO status first (short-circuit on
  mismatch OR terminal status before any KV touch); process one chunk (artist slice +
  ReccoBeats groups for its tracks); write partial keyed by
  `(job_id, chunk_id)`; update shared DO progress band; register
  success/failure in the DO countdown exactly once; ack semantics per
  Track D (failure marker written before DLQ).
- [x] Finalize (inline, ONLY the worker whose atomic `registerChunkResult`
  returns `isFinalizer`): collect partials with bounded missing-key retries,
  merge, write results + terminal status (owns ALL terminal writes,
  including `failed`), run export-prefix invalidation when the job-level
  force flag is set. Failure markers or unrecovered missing chunks fail the
  job naming them.
- [x] Tests: merge unit tests (averages weighting, genre sums, error union,
  version-max + uniformity assertion), idempotent redelivery, stale `job_id`
  short-circuit, failure-marker countdown completion, DLQ propagation,
  missing-partial retry-then-fail.

## Phase 3 — Verification + rollout

- [x] `cd src/backend && npm run test:run && npm run lint`; existing Track D
  tests green unchanged.
- [x] Live dev trace on the NPR playlist via `scripts/trace-analysis-progress.sh`:
  ReccoBeats sections present (no subrequest errors), progress advances.
  (2026-09-20, dev `96c0acb`: `queued:0 → 10 → 20 → 72 → 78 → 85 →
  completed:100` in ~20s, zero errors in status polls; results `schema 1.1`,
  27 tracks, audio 27, meta 18, 15 genre buckets, 4 upstream-coverage notes.)
- [x] CHANGELOG entry (user-visible: large playlists now fully enrich).
- [x] Same-PR housekeeping: plan → `completed/`, indexes, TO_DO line removed.

## Acceptance

- [x] Playlists ≤ threshold: byte-identical behavior (all existing tests pass
  unmodified).
- [x] NPR-scale playlist on dev: full enrichment, no subrequest-limit errors,
  monotonic progress.
- [x] Batch redelivery never double-counts; chunk DLQ fails the job loudly.
- [x] Track D semantics (ack/retry/DLQ/auth/stale-job) covered by tests for
  both message shapes.
