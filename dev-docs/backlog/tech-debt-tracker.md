# Technical Debt Tracker

> Structured log of known shortcuts, brittle areas, and deferred cleanup.
> Update this when you introduce debt. Resolve entries and mark them Done when addressed.

| # | Area | Issue | Severity | First Noted | Status |
|---|------|-------|----------|-------------|--------|
| 1 | `src/backend/services/cache.ts` | Uses `any` in `set()` parameter — should be generic `<T>` | Low | 2026-05 | Open |
| 2 | `src/backend/services/jwt.ts` | Hand-rolled HMAC-SHA256 JWT — not tested against edge cases like expired tokens with clock skew | Medium | 2026-05 | Open |
| 3 | `src/backend/` | `console.log` / `console.error` used throughout instead of structured logging | Medium | 2026-05 | Open |
| 7 | `src/frontend/` | No structural test enforcing Python layer boundaries | Low | 2026-05 | Open |

### Open notes

- **#1 (2026-09-19):** `set()` signature now uses `value: unknown` instead of `any` (verified at `src/backend/services/cache.ts:18`). The "should be generic `<T>`" aspect remains open.
- **#2 (2026-09-19):** Hand-rolled JWT remains the only Workers-compatible option; clock-skew and revocation gaps are documented inline at `src/backend/services/jwt.ts:8-11`. Acceptable as a platform constraint until Workers supports a standard library.
- **#3 (2026-09-19):** `console.error` is still used extensively in `src/backend/` source files (verified via grep, 77 matches in non-test, non-docs files). `src/backend/utils/logger.ts:11` still delegates to `console.error`. Migration to structured logging is pending.
- **#7 (2026-09-19):** No Python layer-boundary structural test found in `src/frontend/tests/` (only `test_main_screen_search_sort_ui.py` and Kivy UI tests exist). Backend has `architecture.test.ts`; frontend equivalent not yet implemented.

---

## Done

| # | Area | Issue | Resolved |
|---|------|-------|----------|
| 4 | `src/frontend/` | Bare `except:` clauses may exist — needs audit against Golden Principle #6 | 2026-09-19 |
| 5 | `backups/`, `srcamas/`, `spotify_playlist_exporter_v2/` | Legacy dead-code directories in repo; should be removed after confirming nothing is referenced | 2026-09-19 |
| 6 | `src/backend/.eslintrc.json` | No-restricted-imports rule not yet covering all layer boundaries | 2026-09-19 |
| 8 | General | No CI workflow — tests only run locally | 2026-09-19 |
| 9 | `src/backend/services/reccobeats.ts` | Marked as "mock" — unclear if this is a real integration or stub | 2026-09-19 |
| 10 | `docs/plans/` migrated | Legacy plan files consolidated under `dev-docs/exec-plans/completed/legacy/`; active/completed indexes updated | 2026-06-19 |

### Resolution evidence

- **#4 (2026-09-19):** No bare `except:` clauses found in `src/frontend/` (grep returned 0 matches). Debt moot.
- **#5 (2026-09-19):** Directories `backups/`, `srcamas/`, `spotify_playlist_exporter_v2/` do not exist in the current tree (glob returned no matches). Debt moot.
- **#6 (2026-09-19):** `no-restricted-imports` rule migrated from legacy `.eslintrc.json` (file no longer exists) to active flat config `src/backend/eslint.config.mjs:23-39` (service→route/middleware) and `:45-56` (route→route). Rule is enforced as `error`. Debt satisfied.
- **#8 (2026-09-19):** CI workflows present at `.github/workflows/` (`build.yml`, `ci.yml`, `deploy-backend.yml`, `deploy-production.yml`, `security.yml`, `dependency-review.yml`). Debt closed.
- **#9 (2026-09-19):** `src/backend/services/reccobeats.ts` does not exist in the current tree. Replaced by real integration modules `src/backend/services/reccobeats-track-cache.ts` and `src/backend/services/analysis.ts` (verified via import graph and `dev-docs/code-map.md:296`). Debt satisfied.

---

## Notes

- **Severity:** High = blocks functionality or correctness; Medium = degrades maintainability or agent legibility; Low = cosmetic or low-impact.
- When closing an item, move it to the Done table and add the resolution date.
- When opening a PR that introduces known debt, add a row here in the same PR.
