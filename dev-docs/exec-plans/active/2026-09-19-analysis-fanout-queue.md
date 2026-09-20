# Analysis Fan-Out Queue Plan — Large Playlists

**Date:** 2026-09-19
**Branch:** `docs/fanout-queue-plan` (plan only; no code)
**Status:** draft v2 — revised per kilo + agy reviews (v1 used a racy KV
countdown; v2 uses a DO atomic countdown — see Resolved decisions)
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
- No DO schema changes.

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

- **Chunking (POST path):** after Spotify track enumeration (cheap: paginated
  reads only), decide single vs fan-out. Fan-out threshold: unique artists
  > 40 OR estimated subrequests > 40 (leave headroom under the 50 limit;
  exact budget math is Phase 0). Chunks split by track groups sized so one
  batch message (Spotify artist slice + ReccoBeats audio + metadata for its
  tracks) fits the budget.
- **Batch messages:** `{ job_id, playlist_id, user_id, chunk_id,
  chunk_index, chunk_count, track_ids[] }` — new Zod-validated type next to
  `AnalysisQueueMessage` (extend, don't break: old single-message shape keeps
  working; consumer routes on presence of `chunk_id`).
- **Aggregation:** each batch worker writes its partial result to a
  chunk-result key and merges progress into the shared DO status record
  (per-chunk progress band, monotonic guard shared with the existing
  tracker). Completion is tracked by an atomic countdown in the same DO
  (strongly consistent — no KV get-then-set race): each worker registers
  success or failure exactly once; the worker that observes the count reach
  zero runs finalize inline. Finalize is idempotent via a terminal-status
  guard (a second trigger — redelivery race — sees `completed`/`failed` and
  returns). A delayed finalize *message* was rejected: queue ordering is not
  guaranteed, so it could run before chunks complete.
- **Chunk failure:** a batch worker that exhausts retries writes a
  `failed` marker for its chunk into the DO (same atomic countdown path)
  before the message DLQs — otherwise the countdown hangs and finalize never
  runs. Finalize seeing any failure marker fails the job naming the failed
  chunks (no silent partial success).
- **Stale jobs:** every chunk worker reads DO status first and short-circuits
  on `job_id` mismatch before touching KV; the DO rejects progress writes
  for superseded `job_id`s.
- **KV read-after-write:** partials live in KV (DO 128KB value limits rule
  out storing them there). Finalize lists expected chunk keys; any missing
  key is retried bounded (3 × 2s) then fails the job naming the missing
  chunks.
- **Finalize:** merge partials (sum genre buckets, recompute audio-feature
  averages weighted by track count, union errors with per-chunk source tags).
  `schema_version`: all chunks run the same deployed code so versions are
  uniform — finalize takes the max, asserts uniformity (warn + log on
  mismatch), and existing bump rules apply to producers unchanged. Write KV
  results + terminal DO status. Idempotent: batch writes keyed by
  `(job_id, chunk_id)`; re-delivered batch messages overwrite identical
  partials; inline finalize re-entry hits the terminal-status guard.
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

- [ ] Measure: instrument per-phase subrequest counts on a large playlist
  (reuse `scripts/trace-analysis-progress.sh` + worker logs) to fix the
  fan-out threshold and chunk sizing with data, not guesses.
- [ ] Add `AnalysisChunkMessage` Zod type + tests (valid single, valid chunk,
  reject malformed; old messages still validate).
- [ ] Define chunk-result key format + merge-function contract (pure function
  signature first, implementation in Phase 2).

## Phase 1 — Chunking (POST path)

- [ ] Enumerate tracks, compute threshold decision, enqueue N chunk messages
  or 1 legacy message. `force_enrichment` clears the per-track cache ONCE at
  POST time before enqueue (never per-chunk) and the flag propagates on every
  chunk message for worker-behavior parity. Small playlists: zero behavior
  change (assert with existing tests + new threshold-boundary tests).
- [ ] Tests: threshold boundaries, chunk coverage (every track in exactly one
  chunk), legacy-shape passthrough, force flag present on all chunks with a
  single pre-enqueue clear.

## Phase 2 — Batch worker + finalize

- [ ] Batch worker: verify `job_id` against DO status first (short-circuit on
  mismatch before any KV touch); process one chunk (artist slice +
  ReccoBeats groups for its tracks); write partial keyed by
  `(job_id, chunk_id)`; update shared DO progress band; register
  success/failure in the DO countdown exactly once; ack semantics per
  Track D (failure marker written before DLQ).
- [ ] Finalize (inline, last-counter worker): re-check terminal status,
  collect partials with bounded missing-key retries, merge, write results +
  terminal status; failure markers or unrecovered missing chunks fail the job
  naming them.
- [ ] Tests: merge unit tests (averages weighting, genre sums, error union,
  version-max + uniformity assertion), idempotent redelivery, stale `job_id`
  short-circuit, failure-marker countdown completion, DLQ propagation,
  missing-partial retry-then-fail.

## Phase 3 — Verification + rollout

- [ ] `cd src/backend && npm run test:run && npm run lint`; existing Track D
  tests green unchanged.
- [ ] Live dev trace on the NPR playlist via `scripts/trace-analysis-progress.sh`:
  ReccoBeats sections present (no subrequest errors), progress advances.
- [ ] CHANGELOG entry (user-visible: large playlists now fully enrich).
- [ ] Same-PR housekeeping: plan → `completed/`, indexes, TO_DO line removed.

## Acceptance

- [ ] Playlists ≤ threshold: byte-identical behavior (all existing tests pass
  unmodified).
- [ ] NPR-scale playlist on dev: full enrichment, no subrequest-limit errors,
  monotonic progress.
- [ ] Batch redelivery never double-counts; chunk DLQ fails the job loudly.
- [ ] Track D semantics (ack/retry/DLQ/auth/stale-job) covered by tests for
  both message shapes.
