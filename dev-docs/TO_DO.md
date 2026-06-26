# To-Do List

## Auth & Token Lifecycle

- [ ] Handle Spotify refresh token expiration (6-month limit, enforced July 20, 2026): discard tokens on `invalid_grant`, redirect to re-sign-in, audit all token storage/refresh logic, test reauthorization flow

## Playlist Analysis — End-to-End

All backend tracks (A–D) from the [ReccoBeats wiring plan](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md) are complete. Remaining work is wiring the popup UI to the finished backend and fixing a backend batching bug. See the [assessment](2026-06-26-reccobeats-wiring-assessment.md) for details.

- [ ] **Analysis popup e2e wiring** — verify double-click opens popup, duration/artist/genre sections populate, queued/processing states are handled correctly (covers plan verification items + queued-state UI fix) — [Plan](../docs/exec-plans/active/2026-06-26-analysis-popup-e2e.md) · [Popup notes](playlist-analysis-popup.md) · [Backend routes](backend-analysis-routes.md)
- [ ] **Display audio-feature data in popup** — backend returns `audio_features` averages from ReccoBeats but the popup only renders duration, genre, and artist sections ([Backend routes §Known Gaps](backend-analysis-routes.md))
- [ ] **ReccoBeats HTTP 414 risk** — `fetchReccoBeatsAudioFeatures()` appends all track IDs to one GET query string; large playlists (300+ tracks) exceed URL limits; chunk into batches of ~50 ([Assessment §2](2026-06-26-reccobeats-wiring-assessment.md))
- [ ] **Legacy stub crash guard** — `reccobeats_backend.py#get_multiple_track_audio_features_safe` raises `NotImplementedError`; ensure no UI code path reaches it accidentally ([Assessment §2](2026-06-26-reccobeats-wiring-assessment.md))
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
