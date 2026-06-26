# To-Do List

Each top-level checkbox should be one shippable outcome. Use nested checkboxes for acceptance criteria or required follow-up steps. Move anything that needs more than about one day of work to `dev-docs/exec-plans/active/`.

## Auth & Token Lifecycle

- [ ] Handle Spotify refresh token expiration before July 20, 2026
  - [ ] Confirm backend behavior when Spotify returns `invalid_grant`
  - [ ] Discard invalid stored refresh and access tokens
  - [ ] Return an auth-required response shape the frontend can parse
  - [ ] Redirect the user to sign in again
  - [ ] Audit all token storage and refresh paths
  - [ ] Add backend and frontend tests for reauthorization

## Playlist Analysis — End-to-End

- [ ] Add visual progress indicator for playlist analysis
  - [ ] Wire `analysis_task` progress into the frontend state
  - [ ] Render in-progress, completed, and failed states in the UI
  - [ ] Add focused frontend tests for progress rendering
- [ ] Refactor playlist analysis to fan-out queue architecture for large playlists
  - [ ] Preserve existing Track D queue behavior
  - [ ] Split work into distributed batches for playlists with more than 40 artists per Worker invocation
  - [ ] Add backend tests for batch fan-out and aggregation

**Related notes:** [API enrichment](spotify-api-enrichment.md) · [ReccoBeats contract](reccobeats-api-contract.md)

## Export

- [ ] Split XLSX render modes from prebuilt export format slots in `buildExportFileKey`
  - [ ] Separate `default`, `rich`, and `lite` XLSX modes from `csv`/other prebuilt format keys
  - [ ] Preserve existing cache compatibility or add a documented migration path
  - [ ] Add unit tests for generated export file keys

## Code Quality / Tech Debt

- [ ] Fix deprecated `AsyncImage` properties (`allow_stretch`, `keep_ratio`)
- [ ] Run pyright and triage type issues
  - [ ] Document the exact command and current issue count
  - [ ] Fix straightforward issues
  - [ ] Create follow-up backlog items or an execution plan for larger type-safety work
- [ ] Track/remove `esbuild` and `uuid` npm overrides in `src/backend/package.json` once upstream ships patched releases

## Repo Cleanup & DevOps

- [ ] Remove unused tracked backup and generated files
- [ ] Remove stale references to `src/spotify_playlist_exporter_v2/`
- [ ] Audit duplicate code candidates and create focused follow-up plans
- [ ] Review outdated docs now that `docs/` and `dev-docs/` are split
- [ ] Audit `.gitignore` vs tracked files (venv, node_modules, caches, IDE, `.DS_Store`; verify `.github/` and `.skills/` tracking)
- [ ] Decide on default window size and placement
- [ ] Verify release build pipeline
  - [ ] Confirm frontend packaging command and output artifact
  - [ ] Confirm backend deployment workflow and required secrets
  - [ ] Confirm CI runs the expected frontend, backend, and structure checks
- [ ] Decide whether to start a new repository before wider release-readiness work
  - [ ] Complete repository cleanup prerequisites
  - [ ] Decide what history, issues, and release artifacts must be retained
  - [ ] Document the migration decision before creating a new repository

See also: agent-first-retrofit, quality review/assessment
