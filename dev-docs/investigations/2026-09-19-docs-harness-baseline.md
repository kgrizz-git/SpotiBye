# Docs Harness Baseline — 2026-09-19

## 1. TO_DO.md `[x] done` line count

**39** lines in `dev-docs/backlog/TO_DO.md` contain a checked `- [x]` checkbox (active work only; excludes `- [ ]` pending items).

Breakdown by section:
- Auth & Token Lifecycle: 20 (top-level parent + nested subtasks)
- Playlist Analysis: 8
- Code Quality / Tech Debt: 4
- Repo Cleanup & DevOps: 7

All 39 are candidates for migration under the `done = log + delete` rule (Phase 1). This chunk does not migrate them.

---

## 2. CHANGELOG.md Unreleased duplicate `###` sections

`CHANGELOG.md` lines 7–173 (`[Unreleased]` block through the start of `[0.1.5]`):

| Section | Occurrences | Lines |
|---------|-------------|-------|
| `### Added` | 2 | 9, 117 |
| `### Fixed` | 4 | 25, 55, 142, 166 |
| `### Changed` | 3 | 37, 124, 155 |
| `### Security` | 1 | 30 |
| `### Removed` | 1 | 150 |

The plan Phase 5 squash target is to dedupe to one heading each (Added, Changed, Fixed, Security, Removed) by concatenating bullets under a single heading, preserving order.

---

## 3. Stale `tech-debt-tracker.md` Open rows

All 9 Open rows in `dev-docs/backlog/tech-debt-tracker.md` are stale as of 2026-09-19 — every one carries `First Noted: 2026-05` with no resolved date.

| # | Area | Issue | Severity |
|---|------|-------|----------|
| 1 | `src/backend/services/cache.ts` | `any` in `set()` parameter | Low |
| 2 | `src/backend/services/jwt.ts` | Hand-rolled HMAC JWT, untested edge cases | Medium |
| 3 | `src/backend/` | `console.log` / `console.error` instead of structured logging | Medium |
| 4 | `src/frontend/` | Bare `except:` clauses may exist | Medium |
| 5 | `backups/`, `srcamas/`, `spotify_playlist_exporter_v2/` | Legacy dead-code directories | Low |
| 6 | `src/backend/.eslintrc.json` | No-restricted-imports rule not covering all layer boundaries | Medium |
| 7 | `src/frontend/` | No structural test enforcing Python layer boundaries | Low |
| 8 | General | No CI workflow — tests only run locally | High |
| 9 | `src/backend/services/reccobeats.ts` | Marked "mock" — unclear if stub or real integration | Medium |

One Done row exists: #10 (legacy plans migrated, 2026-06-19).

---

## 4. Unindexed `dev-docs/*.md` root files

Correction 2026-09-19 (garden pass): the two files originally listed here
(`bug-fix-plan-2026-06-15.md`, `bug-review-2026-06-15-112416.md`) were
verified to be already indexed in the `dev-docs/README.md` current-notes
table. There are no unindexed root `dev-docs/*.md` files. The initial
miscount came from matching on bare filenames instead of the table's
existing rows.

---

## 5. Plan ↔ TODO ↔ Index cross-reference table

### Active plans vs. active/README.md

| Plan file | In active/README.md | Has TO_DO backlink |
|-----------|---------------------|-------------------|
| `2026-07-05-backend-url-defaulting-fix.md` | **Yes** | No (TO_DO references the completed copy) |
| `2026-07-06-spotify-token-expiration-handling.md` | **Yes** | Yes (completed copy) |
| `2026-07-11-backend-playlist-analysis-progress-bar.md` | **Yes** | Yes |
| `2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md` | **Yes** | Yes |
| `2026-07-22-reduce-github-actions-billable-minutes.md` | **Yes** | Yes |
| `2026-07-07-file-length-pre-commit-hook-plan.md` | **No** | Yes |
| `2026-07-09-split-dependabot-dev-deps-pr20.md` | **No** | Yes |
| `2026-09-15-self-host-guides-and-scripts.md` | **No** | Yes |
| `2026-09-19-docs-harness-housekeeping.md` | **No** | Yes |

### Confirmed mismatches (from plan Phase 0 known list)

1. **`2026-09-15-self-host`**: TO_DO references it (line 124); missing from `active/README.md`. **Verified** — plan exists in `active/` but README does not index it.
2. **`2026-07-22-reduce-minutes`**: Listed in `active/README.md` as `2026-07-22-reduce-github-actions-billable-minutes.md`. **Verified** — TO_DO does have a backlink (line 118), so the plan's "no TO_DO backlink" claim is stale/incorrect; the mismatch is the truncated name in the plan, not a real gap.
3. **`2026-07-05`/`2026-07-06`**: Both listed in `active/README.md`. **Verified** — both plans are actually in `completed/`, not `active/`. The active README indexes two completed plans.
4. **Additional mismatches found during verification**: `2026-07-07-file-length-pre-commit-hook-plan.md` and `2026-07-09-split-dependabot-dev-deps-pr20.md` are active but unindexed in README. `2026-09-15-self-host-guides-and-scripts.md` is active but unindexed.

### Enforcement baseline

`scripts/check-repo-structure.sh` current checks (line-by-line grep of the script) constitute the enforcement baseline for this plan. No changes to that script are in scope for Chunk 1.

---

## 6. Aging investigations triage recommendations (as of 2026-09-19)

> Cutoff: 60 days before 2026-09-19 = 2026-07-21. Files with explicit date prefixes strictly older than the cutoff (dated ≤2026-07-20) are listed below with a per-note recommendation. No files were mass-moved.

| File | Age | Recommendation | Rationale |
|------|-----|----------------|-----------|
| `2026-07-05-reccobeats-enrichment-gaps.md` | 76 days | **Archive** | Header states "Resolved: 2026-07-09" and "Kept for historical context." All gaps closed; kept for reference only. |
| `2026-07-07-reccobeats-ui-mockup.md` | 74 days | **Archive** | UI mockup for completed plan `2026-07-07-reccobeats-enrichment-integration.md`. Implementation is done; mockup is historical. |
| `2026-07-09-reccobeats-enrichment-failure.md` | 72 days | **Archive** | Header states "Resolved — root cause identified and fixed locally." Historical record of a fixed bug. |

### Root `dev-docs/*.md` files older than 60 days (correction: already indexed)

| File | Age | Action taken | Rationale |
|------|-----|--------------|-----------|
| `bug-fix-plan-2026-06-15.md` | ~96 days | **None — already indexed** | Pre-existing row in `dev-docs/README.md` current-notes; the §4 "unindexed" claim was a miscount, corrected above. |
| `bug-review-2026-06-15-112416.md` | ~96 days | **None — already indexed** | Same as sibling file. |

### Root `dev-docs/*.md` files already indexed but older than 60 days

| File | Age | Recommendation | Rationale |
|------|-----|----------------|-----------|
| `2026-06-22-backend-deployment-tracking.md` | 89 days | **Keep** | Backend deployment tracking is ongoing operational reference; still relevant. |
| `2026-06-26-reccobeats-wiring-assessment.md` | 85 days | **Keep** | Indexed in `dev-docs/README.md` current-notes; still the authoritative wiring assessment. (Correction: not linked from `AGENTS.md`, which points only at `reccobeats-api-contract.md`.) |

---

*Baseline captured 2026-09-19. Phase 1–5 remediation is tracked in the parent plan.*
