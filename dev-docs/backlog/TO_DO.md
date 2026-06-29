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



## Code Quality / Tech Debt

- [ ] Fix deprecated `AsyncImage` properties (`allow_stretch`, `keep_ratio`)
- [x] Add basedpyright as a pre-push hook in `.pre-commit-config.yaml` ([plan](../exec-plans/completed/2026-06-27-basedpyright-prepush-hook.md)) — **done 2026-06-27**
- [ ] Run pyright and triage type issues **NEEDS REVIEW**
  - [x] Document the exact command and current issue count
    - [`dev-docs/assessments/pyright-utils.md`](../assessments/pyright-utils.md) — `src/frontend/utils/` (16 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-config.md`](../assessments/pyright-config.md) — `src/frontend/config/` (1 error) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-caching.md`](../assessments/pyright-caching.md) — `src/frontend/caching/` (2 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-app.md`](../assessments/pyright-app.md) — `src/frontend/app/` (4 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-auth.md`](../assessments/pyright-auth.md) — `src/frontend/auth/` (14 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-services.md`](../assessments/pyright-services.md) — `src/frontend/services/` (3 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-ui.md`](../assessments/pyright-ui.md) — `src/frontend/ui/` (110 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-screens.md`](../assessments/pyright-screens.md) — `src/frontend/screens/` (~160 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-adapter-mixins.md`](../assessments/pyright-adapter-mixins.md) — `src/frontend/screens/adapter_mixins/` (147 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-tests.md`](../assessments/pyright-tests.md) — `src/frontend/tests/` (49 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-root.md`](../assessments/pyright-root.md) — `src/frontend/` root files (0 errors)
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
  - [ ] Bump CI Node version from 20 (EOL Apr 2026) to 24 LTS ([plan](../exec-plans/active/2026-06-28-bump-ci-node-24.md))
- [ ] Decide whether to start a new repository before wider release-readiness work
  - [ ] Complete repository cleanup prerequisites
  - [ ] Decide what history, issues, and release artifacts must be retained
  - [ ] Document the migration decision before creating a new repository

See also: agent-first-retrofit, quality review/assessment
