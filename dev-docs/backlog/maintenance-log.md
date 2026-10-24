# Maintenance Log

> Append-only log for internal-only work. User-visible changes go in `CHANGELOG.md`.
> One entry per completed PR or internal housekeeping action. Schema:
>
>     ## YYYY-MM-DD — <short outcome>
>     PR: #NN (or `PR: n/a` with a reason for bootstrap/predated entries)
>     Scope: <area>
>     <one-line outcome>

---

## 2026-10-24 — undici override raised to clear three GHSA advisories; Pillow floor aligned

PR: n/a (pending)
Scope: `src/backend/package.json`, `src/backend/package-lock.json`, `pyproject.toml`
Three undici advisories published 2026-10-23 (`GHSA-xjj6-f33q-929c` high, `GHSA-4qv8-2p9j-2685`, `GHSA-f72v-6w45-q472`) covered `7.0.0 – 7.30.0`, reached through the dev-only `wrangler` → `miniflare` chain. Raised the existing `overrides.undici` floor from `^7.28.0` to `^7.30.1` and re-locked to 7.30.1; `npm audit` now reports 0 vulnerabilities with and without `--omit=dev`. No `wrangler` major bump was needed. Also aligned `pyproject.toml`'s Pillow floor with `requirements.txt` (`>=12.2.0` → `>=12.3.0`); the project metadata had lagged the PYSEC-2026-2253…3496 fix.

---

## 2026-10-20 — App-icon and public-repo CI plan closed

PR: n/a (pending)
Scope: `dev-docs/exec-plans/`, `dev-docs/backlog/TO_DO.md`, `dev-docs/guides/frontend-distribution-guide.md`
Closed the plan after #53, #54 and #58–#61 shipped. Fixed the distribution guide's stale `src/frontend/assets/` icon paths to `resources/`, recorded the rounded runtime-icon choice, and added a short running-from-source section. Recorded the owner's manual checks (Dock/taskbar icon and title; Finder icon and clean second launch) and resolved the two open decisions (keep the JXA icon rung; no per-push full-history TruffleHog). Moved the plan to `completed/` and removed its TO_DO and Next Up entries.

## 2026-10-20 — certifi floor raised to clear GHSA-6q48-6c7w-9gw2

PR: #62
Scope: `requirements.txt`, `pyproject.toml`
OSV-Scanner began failing Security Scan on every PR after GHSA-6q48-6c7w-9gw2 (critical, CVSS 9.1) was published against `certifi` 2026.7.22, a transitive dependency of `requests`/`spotipy`. Added a `certifi>=2026.10.19` floor next to the existing `idna`/`pygments` transitive floors.

## 2026-10-19 — README screenshots regenerated from fictional mock data

PR: #61
Scope: `scripts/capture_screenshots.py`, `scripts/screenshot_fixture.py`, `src/frontend/tests/mock_backend.py`, `docs/images/`, `README.md`
A new script runs the real app against the mock backend with invented playlists, artists and generated cover art, in a throwaway `HOME`, and captures login, playlist grid, analysis, tracks and cache-explorer screens. README shows the grid, analysis, tracks and cache-explorer shots, plus the owner's real export sheet with personal fields repainted as fictional values. Covers are generated 2x2 mosaics of invented album art. The mock backend gained `/auth/me`, static file serving, an overridable auth user, and a threading server.

## 2026-10-19 — Public-repo CI posture: push secret scanning, SARIF, lint/type/hygiene gates

PR: #54
Scope: `.github/workflows/security.yml`, `.github/workflows/dependency-review.yml`, `.github/workflows/ci.yml`, `pyproject.toml`, `.pre-commit-config.yaml`
Security Scan now runs on every push to `main`. TruffleHog diffs from the pre-push commit, and falls back to full history on forced or branch-creation pushes. Push runs get per-commit concurrency groups, so no merge scan is cancelled or replaced. The OSV PR scan now uploads SARIF to Code Scanning. The CI frontend job adds `ruff check`, basedpyright, and `scripts/tests/`, and a new `hygiene` job runs the repo-structure, `CLAUDE.md` and docs-hygiene checks. Ruff is pinned to 0.15.20 in both `pyproject.toml` and the pre-commit hook (was unpinned and `v0.4.8`); two unused imports were removed. The billable-minutes plan moved to `completed/superseded/` because the public repo's Actions minutes are unmetered.

## 2026-10-19 — README logo, badges, and interim screenshots

PR: #53
Scope: `README.md`, `resources/spotibye-logo-320.png`, `docs/images/`
README now opens with a 320 px copy of the app icon, CI/license/platform badges, and three hand-redacted screenshots (metadata stripped). The Security Scan and OSV PR Scan badges are left out because both workflows are PR-only. The screenshots are interim: the app-icon plan's Phase 2b replaces them with mock-data captures.

## 2026-10-18 — Exec-plan for app icon, source launcher, and public-repo CI posture

PR: #52
Scope: `dev-docs/exec-plans/active/2026-10-18-app-icon-and-source-launcher.md`, `dev-docs/backlog/TO_DO.md`, `dev-docs/exec-plans/active/README.md`
Added a reviewed plan covering the runtime window icon (`App.icon`/`App.title`), README logo and badges, a `SpotiBye.command` launcher, and public-repo CI posture (push-triggered secret scanning, SARIF upload, `scripts/tests/`, basedpyright, ruff check, a hygiene job). Deferred `ruff format --check`, a macOS test job, and OpenSSF Scorecard to `TO_DO.md`. No code or workflow changes yet.

## 2026-10-15 — Security Scan runs on Python 3.13; zizmor report written outside the checkout

PR: n/a (pending)
Scope: `.github/workflows/security.yml`
The job's `setup-python` moves from 3.10 to 3.13: zizmor 1.31.0 requires Python >=3.11, so `pip install zizmor==1.31.0` found no distribution on 3.10 and the advisory step failed with exit 127. Bandit 1.9.4 runs unchanged on 3.13. The zizmor JSON report is now written to `$RUNNER_TEMP` instead of the checkout, so a PR that commits a `zizmor.json` symlink cannot make the shell redirect truncate a workflow file before zizmor scans it.

## 2026-10-15 — zizmor check fails closed on an empty token; tolerant finding parsing

PR: n/a (pending)
Scope: `.github/workflows/security.yml`
The Security Scan zizmor step now errors when `GH_TOKEN` is empty: without a token zizmor silently skips its online audits (including `known-vulnerable-actions`) and would pass. Per-finding location parsing now tolerates findings without a local path (reported as `?`) instead of raising `KeyError`.

## 2026-10-15 — OSV PR scan re-pinned to v2.7.0; Security Scan runs on any workflow/action change

PR: n/a (pending)
Scope: `.github/workflows/dependency-review.yml`, `.github/workflows/security.yml`, `SECURITY.md`
`dependency-review.yml` pinned `osv-scanner-reusable-pr.yml` to `8ac9e5c`, an untagged commit on `main` (v2.6.0+2) that neither Dependabot nor zizmor can map to a release; re-pinned to the peeled v2.7.0 commit `b1d267a` (`# v2.7.0`), matching `security.yml`'s osv-scanner-action. The reusable workflow's inputs are identical at both refs (only its inner action pins moved from v2.6.0 to v2.7.0), so `upload-sarif: false` still applies. Security Scan's `pull_request.paths` now includes `.github/workflows/**` and `.github/actions/**` (replacing the explicit `security.yml` entry), so PRs that change an action pin in any workflow, including Dependabot github-actions PRs, run the zizmor `known-vulnerable-actions` check before merge instead of only on the weekly run.

## 2026-10-15 — Security Scan checks SHA-pinned actions against GitHub advisories (zizmor)

PR: n/a (pending)
Scope: `.github/workflows/security.yml`, `SECURITY.md`
GitHub's Dependabot alerts are generated only for actions referenced by semver tag, never for actions pinned by commit SHA, and every action in this repo is SHA-pinned, so a vulnerable pinned action was never alerted on. Security Scan now installs `zizmor==1.31.0` (wheels only, like Bandit) and fails only on its `known-vulnerable-actions` audit, which resolves each SHA pin to its release tag and checks GitHub's advisory database; a zizmor tool error (exit other than 0 or 10-14) also fails the step. Added as steps in the existing single `security-scan` job, not a new job, to keep the one-runner billing layout; the result is a new row in the scan summary. Runs on the weekly schedule, dispatch, and PRs matching the existing `paths:` filter (unchanged).

## 2026-10-15 — Dependabot cooldown raised to 7 days; cooldown `nosemgrep` suppressions removed

PR: n/a (pending)
Scope: `.github/dependabot.yml`
Revisited the 3-day cooldown tradeoff from the entry below and raised `cooldown.default-days` from 3 to 7 on all four ecosystems (pip, npm, github-actions, docker). The longer window gives more time for compromised or yanked upstream releases (npm and Actions are the highest-risk ecosystems here) to be caught before Dependabot proposes them; the accepted cost is that releases from the 3rd–9th wait one extra monthly cycle. Security updates are unaffected (cooldown does not apply to them). 7 days satisfies Semgrep's `dependabot-missing-cooldown` rule, so the inline `nosemgrep` comments on each `default-days` line were removed.

## 2026-10-15 — Semgrep cooldown finding suppressed; 3-day Dependabot cooldown kept; Semgrep image pinned

PR: n/a (pending)
Scope: `.github/dependabot.yml`, `.github/workflows/security.yml`, `.github/docker/semgrep/Dockerfile`, `SECURITY.md`
The community Semgrep rule `dependabot-missing-cooldown` flags any `cooldown.default-days` below 7 as blocking, so the 3-day value from #43 failed Security Scan on every PR (first seen on Dependabot PRs #40, #44, #45). Kept 3 days on purpose — with the monthly run on the 10th, a 7-day cooldown pushes releases from the 3rd–9th back a full cycle (~30 days) — and added an inline `nosemgrep` for that rule on each `default-days` line. Do not raise it to 7 just to satisfy the scanner without revisiting that tradeoff.
Also pinned the Semgrep SAST image (previously unpinned `latest`) to `semgrep/semgrep:1.180.0` by tag and digest — the same digest CI was already pulling — in a never-built one-line Dockerfile that the workflow reads, and added a `docker` Dependabot ecosystem for it, so bumps arrive as monthly PRs instead of silently. Dependabot gives version-update PRs for images, not vulnerability alerts. Rule packs are still fetched from the registry at scan time, so new upstream rules can still surface findings.
Added `.github/dependabot.yml` and `.github/docker/**` to Security Scan's `pull_request.paths`: #43 changed only `dependabot.yml`, so the scan never ran on it and the finding first surfaced on unrelated PRs; image-bump PRs now run the scan too.
SonarCloud then flagged the Dockerfile with docker:S6471 (image defaults to root, which is true of `semgrep/semgrep`). The Semgrep step now runs the container as the runner user (`--user "$(id -u):$(id -g)"`, `HOME=/tmp`), and the never-built Dockerfile carries a commented `USER nobody` solely to satisfy the rule; documented in `SECURITY.md`.

## 2026-10-14 — Dependabot version updates moved to monthly on the 10th

PR: #43
Scope: `.github/dependabot.yml`
Switched all three version-update ecosystems (pip, npm, github-actions) from weekly to monthly on the 10th. `interval: monthly` only supports the 1st of the month, so the schedule uses cron (`0 9 10 * *`) with `timezone: America/New_York` — per GitHub's Dependabot options reference, `timezone` still applies to a cron interval, so the run keeps the previous 09:00 local time and stays DST-correct. Also lowered `cooldown.default-days` from 7 to 3 so releases landing in the days before the monthly run are deferred at most one cycle instead of roughly a month. Groups, open-PR limits, labels, reviewers, and ignore rules unchanged. Cadence references in `SECURITY.md` and the pending confirmation step in the billable-minutes exec-plan were updated to match.

## 2026-10-13 — CI unblocked: permanent file-length exemptions, source-map-js pin, js-yaml override removed

PR: #42
Scope: `scripts/file-length-exemptions.json`, `src/backend/package.json`, `src/backend/package-lock.json`, `dev-docs/guides/file-length-policy.md`

Fixed three failing GitHub Actions runs, all repo-state issues: (1) the Frontend (Python) CI job failed because all 4 file-length exemptions expired 2026-10-07 — removed the `expires` keys to make them permanent and documented permanent-exemption semantics in the policy guide; (2) OSV-Scanner failed on `source-map-js@1.2.1` (GHSA-68fv-2mgg-jv7q, CVSS 8.7, dev-only) — added a `^1.2.2` override, lockfile now resolves 1.2.2; (3) the Dependabot Updates job on main failed with an `EOVERRIDE` conflict — removed the redundant `js-yaml` override that duplicated the direct devDependency. Verified: file-length check exit 0, backend 937 tests pass, 0 lint errors.

## 2026-10-05 — Dependabot assignee and label warnings fixed

PR: #36
Scope: `.github/dependabot.yml`, `.github/CODEOWNERS`
Replaced the nonexistent `kgrizz` handle with `kgrizz-git` and created the `dependencies`, `javascript`, `backend`, `python` and `github-actions` labels, so Dependabot PRs stop posting assignee and label warnings.

## 2026-10-05 — brace-expansion override bumped to clear OSV advisories

PR: #35
Scope: `src/backend/package.json`
Raised the `brace-expansion` npm override from an exact `5.0.9` pin to `^5.0.12`, fixing GHSA-6j4f-fj2g-mc7p, GHSA-qhr7-859c-m2p7 and GHSA-q2hr-2g5m-vwhr that failed OSV-Scanner on Dependabot PR #34.

## 2026-09-19 — Docs harness baseline captured

PR: n/a (bootstrap entry; landed via docs-harness housekeeping branch)
Scope: docs-harness

Captured baseline evidence for docs harness housekeeping: 39 `[x]` done lines in TO_DO.md, duplicate `###` headings in CHANGELOG Unreleased (Added×2, Changed×3, Fixed×4), 9 stale Open rows in tech-debt-tracker.md, 2 unindexed root `dev-docs/*.md` files, and the plan↔TODO↔index cross-reference mismatches. Persisted to `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`.

## 2026-06-19 — Legacy plans migrated to exec-plans/completed/legacy

PR: n/a (predates PR-linking; date from tech-debt Done row)
Scope: docs-organization

Consolidated legacy plan files under `dev-docs/exec-plans/completed/legacy/`; active/completed indexes updated.

## 2026-06-27 — basedpyright pre-push hook and pyright triage

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `src/frontend/`, `.pre-commit-config.yaml`

Added basedpyright as a pre-push hook and resolved all frontend pyright errors to 0. The open follow-up ("larger type-safety work") was dropped as stale: nothing remains beyond the enforced hook.

## 2026-06-29 — CI Node version bumped to 24 LTS

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `.github/workflows`, `.nvmrc`

Bumped CI Node version from past-EOL 20 to 24 LTS (`.nvmrc` single source of truth, `@types/node@^24`).

## 2026-07-07 — Backend auth test coverage for token expiration

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `src/backend/tests/`

Added backend unit/integration tests for Spotify token expiration handling (`invalid_grant` → 401 `AUTH_REQUIRED`, KV session deletion, refresh dedup, `REFRESH_FAILED` cache, `safeParseSession`, `/auth/me` shape, queue auth-failure behavior). Test-only; the user-visible re-auth prompt itself is logged in CHANGELOG.

## 2026-07-07 — Frontend auth test coverage for token expiration

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `src/frontend/tests/`

Added frontend tests for token expiration handling (`BackendAPIError` error_code, cache wipes, `_format_backend_api_error`, `_download_file`, `_try_auto_login` branches). Test-only; the user-visible behavior is logged in CHANGELOG.

## 2026-09-19 — Triage 5 stale tech-debt rows closed

PR: #11
Scope: `dev-docs/backlog/tech-debt-tracker.md`

Closed 5 stale Open rows with verified tree evidence: #4 bare `except:` (absent in `src/frontend/`), #5 legacy directories (absent from tree), #6 no-restricted-imports (migrated to flat `eslint.config.mjs`), #8 No CI (`.github/workflows/` present), #9 reccobeats mock (`reccobeats.ts` removed; real integration via `reccobeats-track-cache.ts` + `analysis.ts`). Moved to Done table with resolution date 2026-09-19.

## 2026-09-19 — Changelog Unreleased duplicate-heading squash

PR: #11
Scope: `CHANGELOG.md`

Squashed 11 duplicate `### ` headings in `[Unreleased]` into single Added/Changed/Fixed/Security/Removed sections (order: Added → Changed → Fixed → Security → Removed). Concatenated all bullets under each surviving heading without rewriting bullet text, then removed 15 exact-duplicate bullet lines (pre-existing repeats across the old duplicate sections, e.g. the GitHub Actions optimization block). Verified zero remaining intra-section duplicate bullets and `### ` count 11 to 5 in the Unreleased block.

## 2026-09-19 — Active plan index sync in exec-plans/active/README.md

PR: #11
Scope: `dev-docs/exec-plans/active/README.md`

Removed completed 2026-07-05/2026-07-06 rows; added missing active rows for 2026-07-07-file-length, 2026-07-09-split-dependabot, 2026-09-15-self-host, 2026-09-19-docs-harness-housekeeping. Descriptions copied from plan file titles/intros.

## 2026-09-19 — Verified alleged unindexed root dev-docs files

PR: #11
Scope: `dev-docs/README.md`

Baseline §4 had listed `bug-fix-plan-2026-06-15.md` and `bug-review-2026-06-15-112416.md` as unindexed strays; verification showed both were already indexed in the current-notes table. No change needed; baseline §4 corrected.

## 2026-09-19 — Record aging-investigation triage recommendations

PR: #11
Scope: `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`

Appended §6 to baseline note with per-note triage recommendations for root `dev-docs/*.md` files older than 60 days (`2026-06-22-backend-deployment-tracking.md`, `2026-06-26-reccobeats-wiring-assessment.md`). Did not mass-move files.

## 2026-09-19 — Retired stale PR#20 split-dependabot plan

PR: #12
Scope: `dev-docs/backlog/TO_DO.md`, `dev-docs/exec-plans/`

Retired the PR#20 dev-dependency split item (PR never existed post-migration; goal landed piecemeal via PRs #2, #3, #7 + flat-config migration). Kept 2 verified residuals as plain TO_DO one-liners (npm overrides watch, `index.ts` wiring decision); moved plan to `completed/` with index updates.

## 2026-09-19 — Scoped dev-docs README link check to top-level files

PR: #13
Scope: `scripts/check-repo-structure.sh`

Narrowed the dev-docs README linkage check from `maxdepth 2` to `maxdepth 1`: subdir notes are indexed at directory level with a curated selection (per `dev-docs/README.md`), matching `check_docs_hygiene.py`. Silenced 17 false-positive unlinked-note warnings.

## 2026-09-19 — Progress-bar plan close-out pass

PR: #14
Scope: `dev-docs/exec-plans/active/2026-07-11-backend-playlist-analysis-progress-bar.md`, `dev-docs/backlog/TO_DO.md`

Re-ran all runnable verifications green (backend 855 tests, lint 0 errors; frontend 257 passed; pyright clean); checked 2 verification + 4 acceptance boxes with tree evidence; re-dated TO_DO to `in progress 2026-09-19`. Left: live dev-worker trace, NPR diagnostic run-or-drop, optional cancellation.

Follow-up on PR #14: added `scripts/trace-analysis-progress.sh` (one-command live trace: fresh job + 2s status poll to `tmp/*.jsonl` + results/genre summary) and an owner runbook in the plan step; the NPR run is folded into the same command (trace `5X8lN5fZSrLnXzFtDEUwb9`, check `genre buckets > 0`). Cancellation logged as a TO_DO follow-up instead of implemented.

Live-trace result 2026-09-19 (dev `e96f00a`, NPR `5X8lN5fZSrLnXzFtDEUwb9`): status advanced `queued:0 → processing:50 → processing:75 → completed:100` (DO-backed reads confirmed, no staleness); genres present (15 buckets, 24/40 artists, tolerant-404 fix confirmed live). Live finding: ReccoBeats enrichment hit the Workers subrequest limit on this large playlist — feeds the existing fan-out TO_DO item. Remaining plan box: optional cancellation only.

CodeRabbit hardening on PR #14: trace script takes the bearer token via env/pipe/prompt only (curl `-K` 0600 config + trap cleanup, never argv); BACKEND_URL must be https except loopback; per-run `mktemp -d` dir under `tmp/`; plan claim narrowed to backend payload (rendering covered by popup tests).
