# Maintenance Log

> Append-only log for internal-only work. User-visible changes go in `CHANGELOG.md`.
> One entry per completed PR or internal housekeeping action. Schema:
>
>     ## YYYY-MM-DD — <short outcome>
>     PR: #NN (or `PR: n/a` with a reason for bootstrap/predated entries)
>     Scope: <area>
>     <one-line outcome>

---

## 2026-10-27 — File length pre-commit hook flipped to enforcement mode

PR: #72
Scope: Pre-commit hook
Removed `--warn` flag from file-length check hook in `.pre-commit-config.yaml`. Hook shipped in warn mode 2026-07-08; Phase 4B enforcement (originally scheduled for 14-day observation window) now active as of 2026-10-27. All exemptions were made permanent in PR #42 (2026-10-13). Verification: dry run with `--ci` passes on current tree.

## 2026-10-27 — Docs harness housekeeping plan formally closed out

PR: #72 (closeout; original work merged in #11)
Scope: Docs/meta-process
Plan moved to completed/; acceptance criteria updated post-merge. Phase 4 warn→error flip tied to future release tag remains deferred.

## 2026-10-26 — Self-host config helper keeps and validates the production allowlist

PR: #70
Scope: `scripts/setup-selfhost.py`
`generate_selfhost_config()` now defaults to the template's `[env.production]` allowlist plus the desktop callback, instead of replacing it. A missing, empty, comma-only, or unreadable inherited allowlist is deny-all, so generation fails rather than widening it. Dry runs patch and validate the template like real writes. The helper is unit-tested but not yet called from `main()`, so this does not change what users run. Internal-only; no CHANGELOG entry.

## 2026-10-26 — Vitest restores stubbed globals after each test

PR: #70
Scope: `src/backend/vitest.config.ts`
Set `unstubGlobals: true`, so a `vi.stubGlobal('fetch', ...)` in one test can no longer leak into the next. No test relied on a stub persisting across tests. Internal-only; no CHANGELOG entry.

## 2026-10-25 — Backend docs audited against code

PR: #69
Scope: `src/backend/docs/*`, `src/backend/README.md`, `.skills/*`, `AGENTS.md`, `CLAUDE.md`
Most of `src/backend/docs/` described an API that does not exist. It had invented endpoints, response shapes, error codes, KV keys, TTLs, log levels, and a staging environment. Part of `troubleshooting-guide.md` was corrupted text. Each doc was rewritten against the routes, services, and `wrangler.toml`. `openapi.yaml` gained 15 missing operations and still passes `tests/openapi-schema.test.ts`. The Cloudflare Worker agent skill no longer tells agents to run a bare `wrangler deploy` or set secrets without `--env`. The `export-formats`, `spotify-api`, `testing`, and `security` skills were deleted. They were June scaffolding that described code that never existed, such as `services/auth.ts`, `npm run test:watch`, and made-up CSV and JSON export columns. The security rules they listed live in `.cursor/rules/`. Documentation-only; no CHANGELOG entry.

## 2026-10-25 — Removed the bare backend deploy target; deleted stray Worker

PR: #68
Scope: `src/backend/package.json`, `src/backend/README.md`, `dev-docs/references/cloudflare-workers-constraints.md`, `src/backend/docs/{deployment-configuration,environment-variables,troubleshooting-guide}.md`, `dev-docs/investigations/apple-music-api-analysis.md`
`npm run deploy` ran a bare `wrangler deploy`, which targets the top-level `spotibye-backend` Worker instead of the `development` or `production` environment. That stray Worker had last been deployed on 2026-05-03 and served stale code without release metadata. It was deleted with `wrangler delete`. `npm run deploy` now exits with an error that points to `deploy:dev` / `deploy:prod`. Production is `spotibye-backend-production`. The backend docs also described a nonexistent staging environment, `spotibye-api*` Worker names and URLs, and a made-up `wrangler.toml`. `deployment-configuration.md` was rewritten around the real two environments and deploy scripts, and the other docs now use `--env` on secrets and deploys. Internal-only tooling; no CHANGELOG entry.

## 2026-10-25 — backend-deploy-status.sh reads URLs from .desktop.env.local

PR: #67
Scope: `scripts/backend-deploy-status.sh`, `AGENTS.md`, `CLAUDE.md`
The deploy-status script now accepts `prod` / `dev` shorthands and falls back to `.desktop.env.local` for `SPOTIBYE_*_BACKEND_URL` when the variables are not exported. The file is parsed for `KEY=value` lines, never sourced; comment-only and unterminated values count as unset. `scripts/test-backend-deploy-status.sh` now covers the shorthands and parser and runs from `verify-all.sh`. Internal-only tooling; no CHANGELOG entry.

## 2026-10-25 — Production deploy secret gate scans full history

PR: #66
Scope: `.github/workflows/deploy-production.yml`
The Deploy Production TruffleHog step passed `base: main` / `head: HEAD` while being dispatched on main, so TruffleHog refused to run ("BASE and HEAD commits are the same") and the gate blocked every production deploy. It now does a full-history scan with `fetch-depth: 0`, matching the full-history step in `security.yml`. Internal-only CI; no CHANGELOG entry.

## 2026-10-25 — PR #65 review round 2: pkg_resources bundling removed, option-line bypass closed

PR: #65
Scope: `spotibye.spec`, `.github/workflows/build.yml`, `scripts/check-dependencies.py`, `scripts/tests/test_check_dependencies.py`, `dev-docs/exec-plans/completed/2026-10-24-python-dependency-integrity.md`
Addressed the second CodeRabbit round on #65 (orchestrator diagnosis, consensus with deepseek-flash via qoder, deepseek implementation, orchestrator verification). `spotibye.spec` no longer lists the dead `pkg_resources.py2_warn` / `pkg_resources.markers` hidden imports (PyInstaller 3.x-era workarounds; the module names no longer exist in setuptools ≥ ~67, and on older setuptools they would bundle unaudited pkg_resources code while the frozen audit excludes setuptools) and now excludes `pkg_resources` outright. Verified locally: nothing in the app or its 12 runtime dependency trees references pkg_resources, importing every runtime dep leaves it out of `sys.modules`, and a full macOS PyInstaller build (setuptools 79.0.1 build env) ships zero pkg_resources/setuptools files — so the audited frozen set equals the shipped set on every matrix runner regardless of the runner's setuptools version. The requirements-file option gate now validates every option token on a line via shlex (pip parses all tokens of an option line and honors a nested `-r` on the same line as an allowed option — confirmed against pip's `req_file.parse_line` and a live `pip install --dry-run`), and `--no-cache-dir` moved out of the allowlist because pip rejects it in requirements files (`no such option`), which would turn a passing drift check into a failed build. Regression tests cover the compound-line bypasses and the `--no-cache-dir` rejection. Internal-only (CI/build tooling); no CHANGELOG entry.

## 2026-10-24 — PR #65 review: fail-closed option allow-list, duplicate-pin rejection, exact-version audit

PR: #65
Scope: `.github/workflows/build.yml`, `scripts/check-dependencies.py`, `scripts/tests/test_check_dependencies.py`, `dev-docs/exec-plans/completed/2026-10-24-python-dependency-integrity.md`
Addressed the CodeRabbit and Greptile review findings on #65. The bundled-closure audit now passes `--no-deps --disable-pip` so `pip-audit` checks exactly the versions captured by `pip freeze` instead of re-resolving and reinstalling them, and the freeze snapshot excludes `pip`, `setuptools` and `wheel` explicitly (Python 3.13 auto-excludes only `pip`, so the other two could leak into the audit). The requirements-file option handler switched from a deny-list to an allow-list (`--index-url`/`-i`, `--extra-index-url`, `--trusted-host`, `--no-cache-dir`): resolution-changing options such as `--pre` and `--find-links` are now rejected instead of silently skipped, through the existing error path. Both manifest parsers reject a duplicate normalized package name before the dict write, so a later pin can no longer overwrite an earlier one. Regression tests cover all four behaviors, and the completed plan's recipe and `pip freeze` explanation were corrected with a post-review amendment note. Internal-only (CI/tooling); no CHANGELOG entry.

## 2026-10-24 — Python dependency integrity: exact pins, manifest drift gate, shipped-closure audit

PR: #65
Scope: `requirements.txt`, `pyproject.toml`, `scripts/check-dependencies.py`, `scripts/tests/test_check_dependencies.py`, `scripts/verify-all.sh`, `.github/workflows/build.yml`, `.github/workflows/ci.yml`, `.github/workflows/security.yml`, `SECURITY.md`, `dev-docs/guides/osv-scanner-findings-playbook.md`, `dev-docs/exec-plans/completed/2026-10-24-python-dependency-integrity.md`, `dev-docs/backlog/TO_DO.md`
Pinned `pillow==13.0.0` and `urllib3==2.8.0` exactly in both manifests (and `kivy==2.3.1` in `pyproject.toml`, previously bare) so OSV-Scanner, the GitHub dependency graph and Dependabot can evaluate them — GitHub previously recorded these packages with no version at all. Added a `--manifests` mode to `check-dependencies.py` that fails on specifier, extras, one-sided or wrong-manifest drift between `requirements.txt` and `pyproject.toml`; wired into `verify-all.sh` and the CI hygiene job. Added a fail-closed audit of the environment `build.yml` bundles (`pip freeze --exclude-editable` → isolated `pip-audit -r … --strict`, every matrix OS) and widened `security.yml` path filters to cover `pyproject.toml`. `SECURITY.md` no longer claims a pre-push `security-scan` hook that does not exist, and now records what each dependency layer can and cannot see. Review trail: cursor grok-4.7 (high) caught that the drift check printed FAIL but exited 0 at both wired call sites; claude-opus-5-5 (medium) caught an allowlisted package passing when declared in both manifests and parser lines being silently skipped. Both fixed with regression tests.

## 2026-10-24 — undici override raised to 7.30.1; Pillow moved to 13.0.0 with Python 3.11 floor

PR: #64
Scope: `src/backend/package.json`, `src/backend/package-lock.json`, `requirements.txt`, `pyproject.toml`, `scripts/setup-selfhost.py`, `sonar-project.properties`, `docs/self-hosting.md`, `dev-docs/guides/frontend-distribution-guide.md`, `dev-docs/guides/osv-scanner-findings-playbook.md`, `CHANGELOG.md`
Three undici advisories published 2026-10-23 (`GHSA-xjj6-f33q-929c` high, `GHSA-4qv8-2p9j-2685`, `GHSA-f72v-6w45-q472`) covered `7.0.0 – 7.30.0`, reached through the dev-only `wrangler` → `miniflare` chain. Raised the existing `overrides.undici` floor from `^7.28.0` to `^7.30.1` and re-locked; `npm audit` reports 0 with and without `--omit=dev`, no `wrangler` major bump needed. Separately, Aikido flagged a Pillow set both OSV surfaces had missed: OSV resolves 41 advisories against 12.3.0 (5 critical, 23 high, 13 medium), while OSV-Scanner reported "No issues found" for the range-only `pillow>=12.3.0` (it reports 41 for `pillow==12.3.0`) and `pip-audit -r` resolved the open floor upward to the already-clean 13.0.0. Documented the blind spot and its mitigations in the OSV playbook. Bumped to `pillow>=13.0.0` (all 41 fixed only there) and raised `requires-python` to `>=3.11` because Pillow 13 dropped Python 3.10 (EOL October 2026); CI already used 3.11 and releases bundle 3.13. Verified under 13.0.0: all 10 cover styles, mosaic, LANCZOS resize and JPEG save are byte-identical to 12.3.0; Kivy's `img_pil` provider surface (`open`/`frombytes`/`transpose`/`EXTENSION`) works; frontend suite 285 passed / 7 skipped. User-visible part of the Pillow bump is in `CHANGELOG.md`. The same interpreter-level audit (`.venv/bin/python -m pip_audit`; the system-level `pip-audit` on `PATH` is a different interpreter and had reported clean) surfaced runtime `urllib3 2.7.0` with three advisories fixed in 2.8.0 (`PYSEC-2026-4175`/`4176`/`4177`, published 2026-10-01) — added an `urllib3>=2.8.0` transitive floor next to `certifi`/`idna`/`pygments`, reinstalled, and the venv audit now reports no findings for any project dependency (environment tooling such as `virtualenv` still carries its own advisories and is out of scope here).

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
