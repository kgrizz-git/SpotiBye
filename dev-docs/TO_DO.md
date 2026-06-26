# To-Do List

## Auth & Token Lifecycle

- [ ] Handle Spotify refresh token expiration (6-month limit, enforced July 20, 2026): discard tokens on `invalid_grant`, redirect to re-sign-in, audit all token storage/refresh logic, test reauthorization flow

## Playlist Analysis — End-to-End

- [ ] Add visual progress indicator for playlist analysis (wire `analysis_task` progress into UI)
- [ ] Refactor playlist analysis to fan-out queue architecture (distributed batches for >40 artists per Worker invocation) — basic queue processing done via Track D, this is further scale-out

**Related notes:** [API enrichment](spotify-api-enrichment.md) · [ReccoBeats contract](reccobeats-api-contract.md)

## Export

- [ ] Split the XLSX render-modes and prebuilt-format slots in `buildExportFileKey` (resolve known smell of mixing 'default', 'rich', 'lite', and 'csv')

## Code Quality / Tech Debt

- [ ] Fix deprecated `AsyncImage` properties (`allow_stretch`, `keep_ratio`)
- [ ] Check for pyright issues and fix them
- [ ] Track/remove `esbuild` and `uuid` npm overrides in `src/backend/package.json` once upstream ships patched releases

## Repo Cleanup & DevOps

- [ ] Clean up repository: remove unused files, backups, duplicate code, outdated docs, stale references to `src/spotify_playlist_exporter_v2/`
- [ ] Audit `.gitignore` vs tracked files (venv, node_modules, caches, IDE, `.DS_Store`; verify `.github/` and `.skills/` tracking)
- [ ] Decide on default window size and placement
- [ ] Update / verify build pipeline
- [ ] Start new repo (after cleanup, before widespread release-readiness)

See also: agent-first-retrofit, quality review/assessment
