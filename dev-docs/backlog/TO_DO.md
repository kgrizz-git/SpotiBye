# To-Do List

Active work only; no completed items retained here. Done = log + delete: user-visible outcomes go to `CHANGELOG.md` Unreleased, internal-only work goes to `dev-docs/backlog/maintenance-log.md`, and plan-backed items move to `dev-docs/exec-plans/completed/` in the same PR. Every active exec-plan has a backlink from a TO_DO entry; small items may exist without a plan. `in progress YYYY-MM-DD` = last confirmed state; `NEEDS REVIEW` = needs a second pair of eyes before proceeding. Staleness is flagged by `scripts/check_docs_hygiene.py` (warn-only).

## Playlist Analysis — End-to-End

- [ ] Add visual progress indicator for playlist analysis ([plan](../exec-plans/active/2026-07-11-backend-playlist-analysis-progress-bar.md)) — **in progress 2026-07-11**
  - [ ] Make backend report granular progress across ReccoBeats batches (replace single `emitWarmKeepaliveOnce`)
  - [ ] Wire `analysis_task` progress into the frontend state
  - [ ] Render in-progress, completed, and failed states in the UI
  - [ ] Add focused frontend tests for progress rendering
- [ ] Refactor playlist analysis to fan-out queue architecture for large playlists
  - [ ] Preserve existing Track D queue behavior
  - [ ] Split work into distributed batches for playlists with more than 40 artists per Worker invocation
  - [ ] Add backend tests for batch fan-out and aggregation
- [ ] Explore optional user-choice client-side ReccoBeats fetch
  - [ ] Treat as a future enhancement, not a blocker for the current ReccoBeats failure fix
  - [ ] Make it opt-in: a visible "Retry enrichment from this device" action only when backend enrichment is still incomplete
  - [ ] Add a per-session privacy notice because direct fetch sends the user's IP to ReccoBeats
  - [ ] Gate behind `SPOTIBYE_ENABLE_CLIENT_RECCOBEATS` / `FeatureFlags.ENABLE_CLIENT_RECCOBEATS`
  - [ ] Reuse the deferred frontend-fetch design notes in [`../exec-plans/completed/2026-07-09-reccobeats-egress-diagnosis-and-frontend-fetch.md`](../exec-plans/completed/2026-07-09-reccobeats-egress-diagnosis-and-frontend-fetch.md)
- [ ] Make text on playlist details windows selectable and copyable
  - [ ] Audit which playlist detail popups/windows render text in non-selectable `Label` widgets (analysis popup, tracks popup, cache explorer)
  - [ ] Choose a copyable-text approach (e.g. Kivy `TextInput` readonly, or a copy-to-clipboard action per text block) that preserves layout/styling
  - [ ] Wire a copy action (and/or native text selection) into the relevant windows
  - [ ] Add focused frontend tests for selection/copy behavior
- [ ] Investigate `GET /v1/track/recommendation` for mood/energy-based track recommendations — deferred from the enrichment integration plan above; needs separate UI/caching design (Phase 5 in that plan).
- [ ] Consolidate `SpotifyService.fetchWithRetry` with `utils/http-retry.ts`'s `createFetchWithRetry` (added for ReccoBeats fetches) so there is one retry/backoff implementation instead of two. Deferred from the enrichment integration plan above.
- [ ] **Optional:** Backend playlist composition manifest KV (`analysis:playlist:{id}:manifest`, 24h) — deferred from [per-track ReccoBeats cache plan](../exec-plans/active/2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md) **B2.5** (skipped for B2 PR; not required for correctness).
  - [ ] Store `{ track_ids: unique[], snapshot_id }` when analysis completes or tracks are refreshed
  - [ ] Use manifest for a lightweight online composition check before full paginated track fetch
  - [ ] Invalidate on composition change; fall back to tracks/details fetch when manifest missing (current B2 behavior)
  - [ ] Add backend tests + note in `dev-docs/reccobeats-api-contract.md` or cache docs if shipped

**Related notes:** [API enrichment](spotify-api-enrichment.md) · [ReccoBeats contract](reccobeats-api-contract.md) · [ReccoBeats enrichment gaps](../investigations/2026-07-05-reccobeats-enrichment-gaps.md)



## Code Quality / Tech Debt

- [ ] Fix deprecated `AsyncImage` properties (`allow_stretch`, `keep_ratio`)
- [ ] Reduce backend test `@typescript-eslint/no-explicit-any` warnings (low priority; CI-nonblocking)
  - [ ] Note: production TS is already `error`; tests are intentionally `warn` in `src/backend/eslint.config.mjs`
  - [ ] Type common offenders (parsed JSON responses, mock KV/env returns, analysis result fixtures) instead of `as any`
  - [ ] Prefer shared typed helpers (`createTestEnv`, typed result fixtures) over one-off casts
  - [ ] After the warning count is near zero, consider promoting the test override from `warn` to `error`
- [ ] Split the dependabot dev-dependency bundle in PR #20 into safe, individually-mergeable bumps, easiest/highest-priority first ([plan](../exec-plans/active/2026-07-09-split-dependabot-dev-deps-pr20.md)) — **NEEDS REVIEW**
  - [ ] Track/remove `esbuild` and `uuid` npm overrides in `src/backend/package.json` once upstream ships patched releases
 - [ ] Architecturally resolve the `src/backend/index.ts` routes/middleware imports (previously masked by a mis-scoped `no-restricted-imports` exemption)
   - [ ] Background: `index.ts` is the Worker entry point and wires `./routes/*` and `./middleware/*` directly. The `eslint.config.mjs` override `files: ['index.ts']` never matched `src/backend/index.ts`, so these imports were unlinted until a real edit surfaced them.
   - [ ] Decide whether the entry point should keep wiring routes/middleware (and the override glob should be `**/index.ts`), or whether route wiring belongs in a dedicated bootstrap module so `index.ts` stays thin.
   - [ ] If keeping the wiring in `index.ts`, widen the ESLint override glob to `**/index.ts` (the current interim fix) and document the intent.
- [ ] Add a pre-commit hook that checks for code files over 700 lines and doc files over 300 lines and gives a warning unless the file is in an exempted list ([plan](../exec-plans/active/2026-07-07-file-length-pre-commit-hook-plan.md))
- [ ] Apply the shared test helpers (`tests/helpers/spotify.ts`, `tests/helpers/hono.ts`) to `export*.test.ts` — same `track()`/request-builder patterns, not on the Sonar hotspot list yet

## Repo Cleanup & DevOps

- [ ] Remove unused tracked backup and generated files
- [ ] Remove stale references to `src/spotify_playlist_exporter_v2/`
- [ ] Audit duplicate code candidates and create focused follow-up plans
- [ ] Review outdated docs now that `docs/` and `dev-docs/` are split
- [ ] Docs harness housekeeping: TO_DO active-only lifecycle, maintenance log, same-PR gardening ([plan](../exec-plans/active/2026-09-19-docs-harness-housekeeping.md)) — **in progress 2026-09-19**
- [ ] Audit `.gitignore` vs tracked files (venv, node_modules, caches, IDE, `.DS_Store`; verify `.github/` and `.skills/` tracking)
- [ ] Decide on default window size and placement
- [ ] Verify release build pipeline
  - [ ] Confirm frontend packaging command and output artifact
  - [ ] Confirm backend deployment workflow and required secrets
  - [ ] Confirm CI runs the expected frontend, backend, and structure checks
- [ ] Check GitHub Actions minutes usage and see if any can be trimmed ([plan](../exec-plans/active/2026-07-22-reduce-github-actions-billable-minutes.md))
- [ ] Decide whether to start a new repository before wider release-readiness work
  - [ ] Complete repository cleanup prerequisites
  - [ ] Decide what history, issues, and release artifacts must be retained
  - [ ] Document the migration decision before creating a new repository

- [ ] Consider releasing as public open-source with instructions on how users can set up their own backend ([plan](../exec-plans/active/2026-09-15-self-host-guides-and-scripts.md)) — docs + setup script shipped; remaining is the hosted-backend evaluation below
  - [ ] Evaluate if a hosted backend option should be offered for users who don't want to self-host

- [ ] Add screenshots to README for the public release
  - [ ] Redact Spotify username and any other personal data from source images (currently in a separate folder outside the repo)
  - [ ] Copy redacted images into the repo and reference them from README

See also: agent-first-retrofit, quality review/assessment
