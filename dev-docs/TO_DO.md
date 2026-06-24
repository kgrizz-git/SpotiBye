# To-Do List

## Critical / Active

- [ ] Handle Spotify refresh token expiration (6-month limit, enforced July 20, 2026): discard tokens on `invalid_grant`, redirect to re-sign-in, audit all token storage/refresh logic, test reauthorization flow
- [ ] Fix ReccoBeats pipeline and wire to backend route — [Plan](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md) · [Notes](playlist-analysis-popup.md) · [API enrichment](spotify-api-enrichment.md) · [Backend analysis routes](backend-analysis-routes.md)

## Backend

- [x] Refactor `routes/export.ts` (1,050 lines) — [Plan](../docs/exec-plans/completed/2026-06-24-refactor-routes-export-ts.md) (Completed 2026-06-24)
- [ ] Split the XLSX render-modes and prebuilt-format slots in `buildExportFileKey` (resolve known smell of mixing 'default', 'rich', 'lite', and 'csv')
- [ ] Refactor playlist analysis to fan-out queue architecture (distributed batches to handle >40 artists per Worker invocation)
- [ ] Track/remove `esbuild` and `uuid` npm overrides in `src/backend/package.json` once upstream ships patched releases

## Frontend

- [ ] Refactor `backend_main_screen_adapter.py` (1,116 lines)
- [ ] Refactor `main_screen.py` (1,041 lines)
- [ ] Fix UI handling of queued analysis jobs: recognize `queued`/`processing` states, display ReccoBeats audio feature data (currently only top artists show)
- [ ] Add visual progress indicator for playlist analysis (wire `analysis_task` progress into UI)
- [ ] Fix deprecated `AsyncImage` properties (`allow_stretch`, `keep_ratio`)

## DevOps / Build / Repo

- [ ] Clean up repository: remove unused files, backups, duplicate code, outdated docs, stale references to `src/spotify_playlist_exporter_v2/`
- [ ] Audit `.gitignore` vs tracked files (venv, node_modules, caches, IDE, `.DS_Store`; verify `.github/` and `.skills/` tracking)
- [ ] Check for pyright issues and fix them
- [ ] Decide on default window size and placement
- [ ] Update / verify build pipeline
- [ ] Start new repo (after cleanup, before widespread release-readiness)

See also: agent-first-retrofit, quality review/assessment

## Deferred

- [x] **BM-11** — Done 2026-06-24: `no-explicit-any` is now `error` for non-test code; test files retain `warn`.
