# Technical Debt Tracker

> Structured log of known shortcuts, brittle areas, and deferred cleanup.
> Update this when you introduce debt. Resolve entries and mark them Done when addressed.

| # | Area | Issue | Severity | First Noted | Status |
|---|------|-------|----------|-------------|--------|
| 1 | `src/backend/services/cache.ts` | Uses `any` in `set()` parameter — should be generic `<T>` | Low | 2026-05 | Open |
| 2 | `src/backend/services/jwt.ts` | Hand-rolled HMAC-SHA256 JWT — not tested against edge cases like expired tokens with clock skew | Medium | 2026-05 | Open |
| 3 | `src/backend/` | `console.log` / `console.error` used throughout instead of structured logging | Medium | 2026-05 | Open |
| 4 | `src/frontend/` | Bare `except:` clauses may exist — needs audit against Golden Principle #6 | Medium | 2026-05 | Open |
| 5 | `backups/`, `srcamas/`, `spotify_playlist_exporter_v2/` | Legacy dead-code directories in repo; should be removed after confirming nothing is referenced | Low | 2026-05 | Open |
| 6 | `src/backend/.eslintrc.json` | No-restricted-imports rule not yet covering all layer boundaries (added 2026-05 for route→route, service→route) | Medium | 2026-05 | Open |
| 7 | `src/frontend/` | No structural test enforcing Python layer boundaries | Low | 2026-05 | Open |
| 8 | General | No CI workflow — tests only run locally | High | 2026-05 | Open |
| 9 | `src/backend/services/reccobeats.ts` | Marked as "mock" — unclear if this is a real integration or stub; needs clarification and a design doc | Medium | 2026-05 | Open |

---

## Done

| # | Area | Issue | Resolved |
|---|------|-------|---------|
| 10 | `docs/plans/` migrated | Legacy plan files consolidated under `docs/exec-plans/completed/legacy/`; active/completed indexes updated | Low | 2026-06-19 | Done |

---

## Notes

- **Severity:** High = blocks functionality or correctness; Medium = degrades maintainability or agent legibility; Low = cosmetic or low-impact.
- When closing an item, move it to the Done table and add the resolution date.
- When opening a PR that introduces known debt, add a row here in the same PR.
