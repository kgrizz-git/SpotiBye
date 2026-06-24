# To-Do List

## Critical / Active

- [ ] Handle Spotify refresh token expiration (6-month limit, enforced July 20, 2026): discard tokens on `invalid_grant`, redirect to re-sign-in, audit all token storage/refresh logic, test reauthorization flow
- [ ] Fix ReccoBeats pipeline and wire to backend route — [Plan](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md) · [Notes](playlist-analysis-popup.md) · [API enrichment](spotify-api-enrichment.md) · [Backend analysis routes](backend-analysis-routes.md)

## Backend

- [ ] Refactor `routes/export.ts` (1,045 lines)
- [ ] Refactor playlist analysis to fan-out queue architecture (distributed batches to handle >40 artists per Worker invocation)
- [ ] Track/remove `esbuild` and `uuid` npm overrides in `src/backend/package.json` once upstream ships patched releases
- [ ] Remaining medium/low bug fixes — [Plan](../docs/exec-plans/active/2026-06-21-bug-fix-medium-low.md) (export.ts refactor complete; critical/high complete; all pre-flight deps confirmed):
  - **BM-4** — Remove pervasive `any` from `export-tracks.ts` (refactor didn't eliminate these; `SpotifyPlaylist` needs `followers` field first)
  - **BM-5** — Remove pervasive `any` from `routes/export.ts` (now unblocked)
  - **BL-2** — Change `buildPlaylistMetadata` signature from `any` to `SpotifyPlaylist | undefined` in `export-tracks.ts` (handle with BM-4)

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

- [ ] **BM-11** — Promote `@typescript-eslint/no-explicit-any` from `warn` to `error` in `.eslintrc.json` (wait until BM-4/5/6 and refactor-export-ts land, then audit remaining `any` usage)
- [ ] **FM-2** — Decorate `_update_analysis_ui` with `@mainthread`, drop redundant `Clock.schedule_once` wrappers. [backend_playlist_card.py:530-557](../src/frontend/ui/backend_playlist_card.py)
- [ ] **FL-3** — Simplify redundant checks in `_format_backend_api_error`. [backend_client.py](../src/frontend/services/backend_client.py)
- [ ] **FL-4** — Hoist `LabelBase` import out of inner loop. [backend_cache_explorer.py](../src/frontend/ui/backend_cache_explorer.py)
- [ ] **FL-8** — Log diagnostics on `ImportError` and surface error in `backend_status_label.text`. [backend_cache_explorer.py:21-29](../src/frontend/ui/backend_cache_explorer.py)
