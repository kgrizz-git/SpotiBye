# Plan: Reduce GitHub Actions Billable Minutes

**Date:** 2026-07-22
**Status:** Active (implementation complete on branch; CI verification pending)
**Backlog:** `dev-docs/backlog/TO_DO.md` → "Check GitHub Actions minutes usage and see if any can be trimmed"
**Scope:** `.github/workflows/*.yml`, `.github/dependabot.yml`. **No application code or backend changes.**

## Problem

The repo's GitHub Actions dashboard reports **503 billable minutes for July 2026** (private repo, all `ubuntu-latest`, Linux 1× multiplier). Wall-clock math on per-run duration understates this because parallel jobs in the same run each round up to 1 minute. The dominant cost driver is the Security Scan workflow, which fans out to 6 parallel jobs per run.

Empirical per-job cost for **2026-07-01 → 2026-07-21** (214 workflow runs, 596 total job records of which 120 were skipped and 476 were executed, reconciling to the dashboard's 503 billable minutes exactly):

| Job (workflow → job) | Runs | Billable min | Avg min/run | Failures |
|---|---:|---:|---:|---:|
| Security Scan → Secret Detection (TruffleHog) | 42 | 42 | 1.00 | 0 |
| Security Scan → SAST (Semgrep) | 42 | 42 | 1.00 | 2 |
| Security Scan → Python SAST (Bandit) | 42 | 42 | 1.00 | 0 |
| Security Scan → IaC Security Scan (Checkov) | 42 | 42 | 1.00 | 0 |
| Security Scan → Dependency Vulnerabilities (OSV-Scanner) | 39 | 39 | 1.00 | 0 |
| Security Scan → Security Summary | 42 | 42 | 1.00 | 0 |
| CI → Backend (TypeScript) | 69 | 69 | 1.00 | 3 |
| CI → Frontend (Python) | 69 | 69 | 1.00 | 0 |
| Deploy Backend → test | 32 | 32 | 1.00 | 0 |
| Dependabot dynamic (all ecosystems) | 36 | 63 | 1.75 | 13 |
| OSV PR Scan (`dependency-review.yml`) | 8 | 8 | 1.00 | 1 |
| Old "Dependency Review" runs (pre-rename) | 8 | 8 | 1.00 | 8 |
| Old "Python Dependency Audit" / "Node.js Dependency Audit" (legacy) | 4 | 4 | 1.00 | 0 |
| update-pip-graph | 1 | 1 | 1.00 | 0 |
| **Total** | **476** | **503** | | **27** |

Roll-up by workflow (path):

| Workflow | Billable min | % of July | Runs |
|---|---:|---:|---:|
| `security.yml` | 253 | 50.3% | 42 |
| `ci.yml` | 138 | 27.4% | 69 |
| `deploy-backend.yml` | 32 | 6.4% | 32 |
| `dependency-review.yml` | 16 | 3.2% | 16 (8 old + 8 new) |
| `dynamic/dependabot/dependabot-updates` | 63 | 12.5% | 36 |
| Other (graph update) | 1 | 0.2% | 1 |

Pure failure waste in July (jobs that ran and failed): **~32 min**, of which **11 min** is the 11 `backend-backup`/`SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY` Dependabot PR runs scanning non-existent directories.

> Raw data: `tmp/ci-cost/runs-p*.json` (5 pages of `/actions/runs`), `tmp/ci-cost/jobs/*.json` (214 per-run job listings). These are gitignored under `tmp/` and are not part of this plan's deliverable.

## Why so few billable minutes for so many runs?

Every job in the table rounds up to **1 billable minute** because most jobs complete in 15–60 s. Two structural amplifiers:

1. **Security Scan fans out 6 jobs in parallel** — each scan takes 15–30 s of wall time, but each job is independently billed. The run completes in ~30 s, but the run costs **6 billable minutes**. This is the single largest structural source of waste.
2. **Dependabot's "Dependabot" job** always bills 1–2 min per run, and several runs fail because the configured directory no longer exists.

The **deploy-dev** / **deploy-prod** jobs in `deploy-backend.yml` show 0 billable min in July because they were `skipped` (not actually executed). When they do execute, they cost ~1 min each. This is not a current problem.

## Approach

Three phases, ordered by safety. Each phase is one PR. Stop after any phase if the dashboard trend looks acceptable.

| Phase | Risk | Code touched | Expected non-overlapping savings |
|---|---|---|---:|
| 1. Quick wins | None | `.github/dependabot.yml`, `.github/workflows/ci.yml` | ~13–21 min/mo (~3–4%) |
| 2. Eliminate redundant work | Low (drops duplicate job runs, zero behavior loss) | `.github/workflows/deploy-backend.yml` | ~6–10 min/mo (~1–2%) |
| 3. Restructure Security Scan | Low (verified no branch protection required-checks on Free private repo) | `.github/workflows/security.yml` | ~168–210 min/mo (~35–40%) |
| **All three combined** | | | **~190–240 min/mo (~40–50%)** |

---

## Phase 1 — Quick wins (zero functionality loss)

### 1.1 Stop Dependabot scanning deleted directories

`.github/dependabot.yml` previously referenced `/SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY` and `/backend-backup`, directories that no longer exist in the repo.

- [x] Delete the `pip in /SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY` block
- [x] Delete the `docker in /backend-backup` block
- [x] Verify no remaining references in the repo: `rg "BACKUP-COPY-READ-ONLY|backend-backup" .github/` (no matches)
- [x] Close any remaining open failed Dependabot PRs targeting the deleted directories (none open as of 2026-07-22)
- [ ] Confirm next weekly Dependabot cycle (Monday 09:00 ET) generates no PRs for the removed directories

**Expected:** ~11 failed-job minutes/month eliminated, plus fewer wasted Dependabot notifications. No functioning scan is removed — those entries have never produced a passing run.

### 1.2 Add `concurrency: cancel-in-progress` to `ci.yml`

- [x] Add concurrency block to `.github/workflows/ci.yml` (after `on:`, before `jobs:`)
- [ ] Verify on a rapid double-push test that the older run shows as "cancelled" in the Actions tab

**Expected:** 2–10 min/month depending on push cadence. Defensive against bot pushes (Dependabot rebase runs often double-fire).

### 1.3 Add explicit `timeout-minutes` to every job (insurance only)

- [x] In `.github/workflows/ci.yml`: `timeout-minutes: 15` on `backend` and `frontend`
- [x] In `.github/workflows/deploy-backend.yml`: `timeout-minutes: 10` on `test`, `deploy-dev`, `deploy-prod`
- [x] In `.github/workflows/deploy-production.yml`: `timeout-minutes: 10` on `security-checks`, `test`, `deploy-prod`
- [x] In `.github/workflows/dependency-review.yml`: no change needed
- [x] In `.github/workflows/security.yml`: single consolidated job has `timeout-minutes: 10` (Phase 3 absorbed per-job timeouts)

**Expected:** No direct cost saving. Hard ceiling on per-job billing if a job hangs.

### Phase 1 total expected: ~13–21 min/month (~3–4% of July's billable).

---

## Phase 2 — Eliminate redundant work

### 2.1 Skip duplicate `test` job in `deploy-backend.yml` on PRs (or remove `pull_request` trigger)

- [x] Remove `pull_request` from `on:` in `.github/workflows/deploy-backend.yml`
- [x] Keep `test` job gated to `workflow_dispatch` only (pushes to main/tags skip tests; deploy jobs already accept `skipped`)
- [x] Confirm PRs still get backend test coverage via `ci.yml` (unchanged `pull_request` + backend job)

**Expected:** ~6–10 min/month saved. Zero loss of test coverage.

### 2.2 Concurrency on deploy-backend: Already Present (N/A)

`deploy-backend.yml` already includes `concurrency: cancel-in-progress: true`. No code change required.

### Phase 2 total expected: ~6–10 min/month saved.

---

## Phase 3 — Restructure Security Scan (largest single saving)

**Risk:** Low. This changes the job structure in `security.yml` from 6 parallel jobs to 1 sequential job on a single runner.

**Branch Protection Audit:** Executed `gh api repos/kgrizz-git/SpotiBye/branches/main/protection`. Returned HTTP 403 ("Upgrade to GitHub Pro or make this repository public to enable this feature"). Because SpotiBye is a private repository on a GitHub Free personal account, branch protection required-checks are disabled by GitHub. Changing job names carries zero risk to branch protection rules.

### 3.1 Consolidate scan jobs into a single sequential runner job

- [x] Replace the 6 separate jobs in `.github/workflows/security.yml` with a single `security-scan` job (TruffleHog dual-mode, Semgrep via `docker run -e SEMGREP_RULES=...` without `--config`, Bandit, OSV, Checkov, shell-based summary)
- [x] Delete the old separate jobs (`secret-scan`, `semgrep`, `bandit`, `dependency-scan`, `iac-scan`, `security-summary`)
- [ ] Verify on a test PR that the workflow completes in ≤ 2 billable minutes per run

**Expected:** 42 runs × 6 min billed → 42 runs × 1–2 min billed = **~168–210 min/month saved** (~35–40% total reduction).

### Phase 3 total expected: ~168–210 min/month saved.

---

## Out of scope (do not change)

The following are working as intended and will not be altered:

- **Semgrep, TruffleHog, Bandit, Checkov, OSV scans on PRs** — all PR-time security feedback is retained. (Consolidating them into one sequential runner job retains 100% of signals while reducing billable runner minutes).
- **Weekly scheduled security scan** — cheap baseline (~4 runs/month).
- **Build Executables matrix (Linux/Windows/macOS)** — only fires on tag push and manual dispatch.
- **Frontend pytest** — already running headless (`KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1`).
- **Dependabot for active ecosystems** (`/`, `/src/backend`) — functioning properly.

---

## Verification plan

After each phase lands:

- [ ] Push a test PR and verify Actions tab: confirm expected jobs run cleanly
- [ ] Run a fixed 7-day window billing check via `tmp/ci-cost` script and compare against pre-change baseline
- [ ] Monitor GitHub Actions billing dashboard at month end for overall trend drop

---

## Definition of done

- [x] Phase 1 code complete; no open stale Dependabot PRs for deleted dirs (weekly cycle confirmation still pending)
- [x] Phase 2 complete: `pull_request` removed from `deploy-backend.yml`; duplicate PR tests gone
- [x] Phase 3 complete: Security scan consolidated into single sequential runner job with TruffleHog dual-mode and Semgrep Docker rules intact
- [ ] Billable duration per security run reduced from 6 min to ≤ 2 min (confirm on first PR/Actions run)
- [x] `CHANGELOG.md` updated under "Unreleased" with a "Changed" entry (Security Scan check-name consolidation)
- [ ] When fully verified, remove item from `dev-docs/backlog/TO_DO.md`
- [ ] Move this plan to `dev-docs/exec-plans/completed/` and index in `dev-docs/exec-plans/completed/README.md`

---

## Rollback

Each phase is a single PR. Revert the PR to restore prior workflow files if needed. No branch protection required-checks reconfiguration is required on rollback due to GitHub Free private repo status.

**Pre-change backups (gitignored):** `tmp/backups/2026-07-22-ci-cost/` — delete after merge if desired.
