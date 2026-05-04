# Design: Resumable Export Cursor Persistence

**Status:** Implemented
**Date:** 2025
**Full plan:** [`docs/plans/resumable-export-cursor-persistence-plan.md`](../plans/resumable-export-cursor-persistence-plan.md)
**Relevant code:** `src/backend/services/export.ts`, `src/backend/routes/export.ts`

---

## Problem

Spotify playlists can contain thousands of tracks. Fetching all tracks requires many paginated API calls. A single Cloudflare Worker invocation has a CPU time limit (~30 ms on free tier). If the Worker is interrupted mid-export, the user loses all progress and must restart.

---

## Solution: Two-Phase Cursor Export

Export is split into two phases, both driven by persisted state in KV:

### Phase 1: Collection
- A job is created in KV with a cursor at `offset = 0`
- Each invocation fetches one page of tracks (e.g., 100 tracks) and writes a slice to KV
- **The cursor is written to KV before processing the slice** (Golden Principle #3 — cursor before destruction)
- If the Worker is interrupted, the next invocation reads the cursor and resumes from the last successful page
- This continues until `cursor.offset >= total_tracks`

### Phase 2: Assembly
- Once collection is complete, a separate invocation assembles all slices from KV into the final file
- Assembly is idempotent — re-running it produces the same result

---

## Job State Schema (in KV)

```typescript
type ExportJobState = {
  job_id: string;
  user_id: string;
  playlist_ids: string[];
  format: 'csv' | 'xlsx' | 'json';
  status: 'collecting' | 'assembling' | 'completed' | 'failed';
  cursor: {
    playlist_index: number;  // which playlist we're on
    offset: number;          // track offset within that playlist
  };
  slices: string[];          // KV keys of collected track slices
  started_at: string;        // ISO timestamp
  completed_at?: string;
};
```

---

## Idempotency

- Each page fetch is keyed by `<user_id>:export:<job_id>:slice:<playlist_id>:<offset>`
- If a slice key already exists in KV, the collection step skips it
- This makes retries safe: re-running a job after interruption picks up exactly where it left off

---

## Frontend Behavior

1. `POST /export/batch` → creates job, returns `job_id`
2. Frontend polls `GET /export/batch/:job_id` until `status === 'completed'`
3. On `completed`, frontend downloads the assembled file

---

## Error Handling

- If a Spotify API call fails during collection, the job is marked `status: 'failed'` with an error message
- The cursor state is preserved — a future retry can resume from the last successful page
- `ResumableExportConflictError` is thrown if a job for the same user+playlist is already in progress

---

## Agent Notes

- **Never remove cursor persistence.** It is the only safety net against Worker interruption on large exports.
- The cursor write in `services/export.ts` must always happen before the data is consumed, not after.
- KV slice keys must remain namespaced: `<user_id>:export:<job_id>:slice:...`
