# Resumable Export Plan: Continuation Cursor, Persistence, Resume Tokens, Multi-Phase

## Objective

Implement a durable, resumable export pipeline that keeps each Cloudflare Worker invocation within free-tier limits while supporting many playlists and very large playlists.

Core features to implement together:
- Continuation cursor
- Persisted job state
- Resume tokens / idempotent progress
- Multi-phase execution

## Why This Plan

Current export reliability is improved (chunking, sequential fallback, partial saves), but worst-case workloads can still hit per-request CPU limits or transient upstream failures.

This plan converts export into bounded, resumable steps so failures do not require restarting from zero.

## Scope

### In Scope
- Durable export job model with persisted state in KV
- Cursor-driven continuation across small bounded invocations
- Resume-token validation to make retries idempotent
- Two-phase execution model:
  - Phase 1: collect/normalize per-playlist slices
  - Phase 2: assemble final export payload/download from stored slices
- Frontend orchestration updates for resume-first behavior
- Metrics/logging and failure classification for observability
- Test coverage for resume, idempotency, and large workloads

### Out of Scope
- Migrating storage from KV to D1/R2 in this pass
- Full async queue/workflow engine
- New export format redesign

## Architecture Summary

### High-Level Flow
1. Frontend starts export job (`POST /export/jobs`).
2. Backend returns `job_id`, initial `cursor`, and `resume_token`.
3. Frontend repeatedly calls `POST /export/jobs/:jobId/step` with cursor + token.
4. Backend executes bounded work (playlist/track slice budget), persists progress, returns next cursor/token.
5. When Phase 1 completes, backend transitions to Phase 2 assembly steps.
6. On completion, backend returns a download handle and final summary.

### Core Design Principles
- Every step must be replay-safe (idempotent).
- Every response must include enough state to continue without ambiguity.
- No endpoint should attempt full large-job completion in one request.

## Data Model (KV)

Namespace: existing export status namespace (or dedicated export jobs namespace).

Key patterns:
- `export:job:{jobId}:state` - canonical job state
- `export:job:{jobId}:cursor:{cursorId}` - optional explicit cursor snapshots
- `export:job:{jobId}:token:{tokenId}` - optional one-time token metadata
- `export:job:{jobId}:slice:{playlistId}:{sliceIndex}` - persisted normalized slices

Job state shape (proposed):
```json
{
  "job_id": "uuid",
  "user_id": "spotify_user_id",
  "status": "running|assembling|completed|failed|cancelled",
  "phase": "collect|assemble",
  "created_at": "ISO",
  "updated_at": "ISO",
  "playlist_ids": ["..."],
  "playlist_progress": {
    "playlist_id": {
      "next_offset": 0,
      "done": false,
      "slice_count": 0,
      "error": null
    }
  },
  "totals": {
    "playlists_total": 0,
    "playlists_done": 0,
    "tracks_processed": 0,
    "tracks_failed": 0
  },
  "current_cursor": "opaque_cursor",
  "current_resume_token": "opaque_token",
  "result": {
    "download_id": null,
    "filename": null,
    "expires_at": null
  },
  "last_error": null,
  "trace_id": "optional"
}
```

## API Contract Changes

### 1) Create Job
- `POST /export/jobs`
- Request:
  - playlist ids
  - export options (include_audio_features remains false by default)
- Response:
  - `job_id`
  - `status`
  - `cursor`
  - `resume_token`
  - initial progress summary

### 2) Execute One Step
- `POST /export/jobs/:jobId/step`
- Request:
  - `cursor`
  - `resume_token`
  - optional client hints (`max_playlists`, `max_tracks`, `max_ms`)
- Response:
  - `status`
  - `phase`
  - `next_cursor` (or null if done)
  - `next_resume_token`
  - progress delta + cumulative totals
  - `download_id` when completed

### 3) Status Endpoint
- `GET /export/jobs/:jobId/status`
- Response:
  - canonical persisted status for reconnect/restart resume

### 4) Download Endpoint
- Reuse existing download endpoint using returned `download_id`.

## Cursor and Resume Token Strategy

### Continuation Cursor
- Opaque, signed payload (or random id mapped in KV) containing:
  - phase
  - next playlist index/id
  - next track offset
  - expected state version

### Resume Token
- Opaque token bound to:
  - `job_id`
  - `cursor`
  - short TTL
  - monotonic step sequence
- Prevents accidental duplicate processing and stale-step replay.

### Idempotency Rules
- If same `cursor + token` is replayed, backend returns same persisted step result.
- If stale token/cursor submitted, return structured `409` with latest cursor/token in payload.

## Multi-Phase Breakdown

### Phase 1: Collect + Normalize
- Iterate playlists incrementally.
- Fetch tracks in bounded slices (e.g. 50-100 per step target, adaptive).
- Normalize and persist slices immediately (`slice` keys).
- Update playlist progress and totals.

### Phase 2: Assemble
- Read persisted slices incrementally.
- Build export artifact in bounded assembly steps.
- Persist intermediate assembly state if needed.
- Finalize downloadable artifact and set completion metadata.

## Backend Implementation Plan

### A. Routes (`src/backend/routes/export.ts`)
- Add `POST /export/jobs`.
- Add `POST /export/jobs/:jobId/step`.
- Add `GET /export/jobs/:jobId/status` (or adapt existing status route).
- Keep existing routes for backward compatibility during rollout.

### B. Service Layer (`src/backend/services/export.ts`)
- Add job lifecycle functions:
  - `createExportJob()`
  - `runExportStep()`
  - `loadJobState()` / `saveJobState()`
  - `validateCursorAndToken()`
  - `runCollectPhaseStep()`
  - `runAssemblePhaseStep()`
- Keep audio-features optional and disabled by default.

### C. Error Middleware (`src/backend/middleware/error.ts`)
- Preserve structured errors.
- Add explicit types for:
  - stale cursor/token
  - idempotent replay
  - step budget exceeded (normal continuation, not fatal)

### D. Config
- Add env knobs for bounded work:
  - `EXPORT_STEP_MAX_TRACKS`
  - `EXPORT_STEP_MAX_PLAYLISTS`
  - `EXPORT_STEP_MAX_MS`
  - `EXPORT_TOKEN_TTL_SECONDS`

## Frontend Implementation Plan

### A. Backend Client (`src/frontend/services/backend_client.py`)
- Add calls for create-job, step, and status.
- Ensure trace-id propagation remains intact.

### B. Adapter Orchestration (`src/frontend/screens/backend_main_screen_adapter.py`)
- Replace long single-shot calls with step loop:
  - create job
  - run steps until completion
  - recover from transient failures by polling status and resuming with latest cursor/token
- Keep user-visible progress updates per step.

### C. Main Screen (`src/spotify_playlist_exporter_v2/screens/main_screen.py`)
- Show resumable progress model:
  - phase label (`collect` / `assemble`)
  - cumulative playlists/tracks completed
- On failure, offer resume action when job is recoverable.

## Rollout Strategy

### Phase 0: Prep
- Introduce new endpoints behind feature flag:
  - `EXPORT_RESUMABLE_JOBS_ENABLED=true|false`
- Keep old flow available.

### Phase 1: Backend
- Implement job state + step endpoints.
- Validate with backend integration tests.

### Phase 2: Frontend Opt-In
- Frontend uses new flow when backend feature flag indicates support.
- Fallback to existing flow if not supported.

### Phase 3: Default On
- Enable resumable jobs by default.
- Keep old endpoints for one release cycle.

### Phase 4: Cleanup
- Remove dead legacy path once stable in production.

## Test Plan

### Unit Tests (Backend)
- Cursor encode/decode validation.
- Resume token validation and TTL behavior.
- Idempotent replay returns prior result.
- Stale token returns 409 with latest continuation info.

### Integration Tests (Backend)
- Large playlist export across many step calls completes successfully.
- Injected transient failure mid-job resumes correctly.
- Simulated duplicate step request does not duplicate work.
- Assembly phase continuation after interrupted invocation.

### Frontend Tests
- Step-loop orchestration correctness.
- Resume path after temporary network failure.
- Proper user messaging for resumable vs terminal failure.

### Manual Validation
- 25+ playlists mixed sizes export.
- One very large playlist export.
- Force interruption (stop app/process), relaunch, resume via status endpoint.

## Observability and Success Metrics

### Logging
- Log job id, step sequence, phase, cursor hash, and trace id.
- Distinguish transport/backend/upstream failures.

### Metrics
- `export_step_duration_ms`
- `export_step_tracks_processed`
- `export_resume_attempts`
- `export_resume_success_rate`
- `export_jobs_completed`
- `export_jobs_failed_terminal`

### Success Criteria
- 95%+ completion for target large workload profile on free tier.
- Zero restart-from-zero incidents for recoverable failures.
- Reduced CPU-limit failures per job compared with current baseline.

## Risks and Mitigations

- Risk: KV consistency edge cases during rapid retries.
  - Mitigation: versioned state writes + conflict-aware retry.
- Risk: Cursor/token complexity introduces bugs.
  - Mitigation: strict schema validation + deterministic idempotency tests.
- Risk: Assembly still too heavy for edge cases.
  - Mitigation: assembly pagination and bounded assembly steps with continuation.

## Implementation Checklist

- [ ] Add resumable job data model and KV key schema.
- [ ] Add create-job endpoint.
- [ ] Add step endpoint with bounded work budget.
- [ ] Add status endpoint for reconnect/resume.
- [ ] Add cursor + resume token validation/idempotency.
- [ ] Persist collect-phase slices and progress.
- [ ] Implement assemble-phase continuation.
- [ ] Wire frontend to create/step/status loop.
- [ ] Add resume UX and clearer phase progress display.
- [ ] Add backend + frontend automated tests.
- [ ] Run large-workload manual validation.
- [ ] Roll out with feature flag and monitor metrics.

## Definition of Done

- Resumable export flow is default and stable for large workloads.
- Jobs can recover from transient failures without restarting from zero.
- Worker invocations remain bounded and no longer attempt full large-job completion in one request.
- Tests and manual validation pass for many-playlist and very-large-playlist scenarios.
