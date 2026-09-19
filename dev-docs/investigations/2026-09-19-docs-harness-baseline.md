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
| `### Fixed` | 3 | 25, 55, 166 |
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

Files in `dev-docs/*.md` that are not listed in `dev-docs/README.md`:

| File | Status |
|------|--------|
| `bug-fix-plan-2026-06-15.md` | Unindexed |
| `bug-review-2026-06-15-112416.md` | Unindexed |

All other root `dev-docs/*.md` files are referenced from the README Entry Points, References, or Current notes tables. `README.md` itself is the index and is not self-referenced.

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

*Baseline captured 2026-09-19. Phase 1–5 remediation is tracked in the parent plan.*
