# Active Execution Plans

> Plans currently in progress. Move a plan to `../completed/` when it is fully executed and all references are updated.

| Plan | Description | Started |
|------|-------------|---------|
| [2026-06-21 Fix medium & low bugs](2026-06-21-bug-fix-medium-low.md) | Address the 30 remaining medium/low findings from the 2026-06-21 audit (BE-SEC-4, BE-TYPE-2/3, FE-MED-2, etc.). Coordinates with the export.ts refactor for shared `export.ts` items. | 2026-06-21 |
| [2026-06-21 Refactor export.ts](2026-06-21-refactor-export-ts.md) | Split `src/backend/services/export.ts` (1,186 lines) into focused, testable modules without changing the public API. | 2026-06-21 |
| [2026-06-21 ReccoBeats wiring](2026-06-21-reccobeats-wiring.md) | Restore backend playlist analysis with ReccoBeats audio features via Spotify track IDs. Mostly complete; 3 frontend verification steps remain. | 2026-06-21 |
