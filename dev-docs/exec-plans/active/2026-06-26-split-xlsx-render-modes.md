# 2026-06-26 Split XLSX Render Modes from Prebuilt Format Keys

> **REVIEWED 2026-06-26** — Call site counts corrected (25 call sites across `file-bytes.ts` and `jobs.ts`; jobs.ts alone has 20 helper calls plus 1 hardcoded string). Verification command aligned with `AGENTS.md` (`./scripts/verify-all.sh`). Type-level test approach specified (`expectTypeOf` from vitest). Changelog entry tightened. Backlog cleanup clarified to "remove" per `AGENTS.md` guidance. No behavior change; cache key strings preserved.

Split `buildExportFileKey`'s conflated `mode` parameter into dedicated functions so XLSX render variants (`default`, `rich`, `lite`) and prebuilt format slots (`csv`) are expressed through separate, self-documenting APIs.

## Context

`buildExportFileKey` in `src/backend/routes/export/helpers/cache-keys.ts:16` takes a `mode` parameter of type `'default' | 'rich' | 'lite' | 'csv'`. This single parameter mixes two distinct concepts:

| Value | Concept | Semantics |
|-------|---------|-----------|
| `'default'` | Cache slot designator | The canonical fallback slot (`<baseKey>:file`) |
| `'rich'` | XLSX render variant | Styled XLSX cache slot (`<baseKey>:file:rich`) |
| `'lite'` | XLSX render variant | Reduced-styling XLSX cache slot (`<baseKey>:file:lite`) |
| `'csv'` | Prebuilt format key | CSV-specific cache slot (`<baseKey>:file:csv`) |

The mixing was flagged as a "known smell" during the 2026-06-24 route-layer refactor and a follow-up was added to the backlog.

**25 call sites** across 3 files: `cache-keys.ts` (1 definition), `file-bytes.ts` (5 calls in `precacheJobFiles` — 2 no-arg, 1 `rich`, 1 `lite`, 1 `csv`), and `jobs.ts` (20 calls in status + download endpoints — 9 no-arg, 3 `rich`, 5 `lite`, 2 `csv`, and 1 dynamic via `variant`). The no-arg form is the majority (11 of 25).
There is also **1 hardcoded key string** in `jobs.ts` (`${jobKey}:file` at line 306) that bypassed the helper and should be cleaned up.

**Cache compatibility is critical.** All existing cache entries use keys of the form `<baseKey>:file`, `<baseKey>:file:rich`, `<baseKey>:file:lite`, and `<baseKey>:file:csv`. The new API must produce identical key strings so no migration is needed.

## Approach

Replace the single `mode` parameter with three focused functions that each produce the same cache key strings:

```typescript
export function buildExportFileKey(baseKey: string): string {
  return `${baseKey}:file`;
}

export function buildXlsxVariantKey(baseKey: string, variant: 'rich' | 'lite'): string {
  return `${baseKey}:file:${variant}`;
}

export function buildPrebuiltFormatKey(baseKey: string, format: 'csv'): string {
  return `${baseKey}:file:${format}`;
}
```

Key design choices:

1. **`buildExportFileKey` drops its optional `mode` parameter** — callers that just need the canonical key call it with no arguments. This is the majority (11 of 25 call sites).
2. **`buildXlsxVariantKey`** — takes only `'rich' | 'lite'`, the two valid XLSX render variants. No `'default'` (that's `buildExportFileKey`'s job) and no `'csv'` (it's not an XLSX concept).
3. **`buildPrebuiltFormatKey`** — takes `'csv'` (and is extensible to future prebuilt format slots). The format is a *subset* of `ExportFormat` (currently just `'csv'`), not a render mode. JSON is generated on demand and XLSX uses render variants, so they do not get a prebuilt slot.

All three produce the same key strings as today. No in-flight cache entries are invalidated.

### Call site changes

**`cache-keys.ts`** — Replace the single function with the three functions shown above.

**`file-bytes.ts`** (5 call sites):
- `buildExportFileKey(jobKey, 'csv')` → `buildPrebuiltFormatKey(jobKey, 'csv')`
- `buildExportFileKey(jobKey)` → `buildExportFileKey(jobKey)` (unchanged)
- `buildExportFileKey(jobKey, 'lite')` → `buildXlsxVariantKey(jobKey, 'lite')`
- `buildExportFileKey(jobKey)` → unchanged
- `buildExportFileKey(jobKey, 'rich')` → `buildXlsxVariantKey(jobKey, 'rich')`

**`jobs.ts`** (21 call sites in total: 20 helper calls + 1 hardcoded string replacement):
- All 9 no-arg calls (`buildExportFileKey(jobKey)`) — unchanged
- All 3 `'rich'` calls → `buildXlsxVariantKey(jobKey, 'rich')` (lines 182, 231, 234)
- All 5 `'lite'` calls → `buildXlsxVariantKey(jobKey, 'lite')` (lines 181, 231, 233, 234, 277)
- All 2 `'csv'` calls → `buildPrebuiltFormatKey(jobKey, 'csv')` (lines 227, 292)
- The hardcoded file key string at line 306 (`await cacheService.setBuffer(`${jobKey}:file`, fallbackBytes, 3600);`) → `await cacheService.setBuffer(buildExportFileKey(jobKey), fallbackBytes, 3600);`
- The dynamic call at line 265 (`buildExportFileKey(jobKey, variant as 'default' | 'rich' | 'lite')`) and the subsequent unconditional default write at line 266 are replaced by an optimized conditional to prevent redundant cache writes:
  ```typescript
  if (variant === 'default') {
    await cacheService.setBuffer(buildExportFileKey(jobKey), rendered, 3600);
  } else {
    await cacheService.setBuffer(buildXlsxVariantKey(jobKey, variant), rendered, 3600);
    await cacheService.setBuffer(buildExportFileKey(jobKey), rendered, 3600);
  }
  ```

### String-based key detection (out of scope, left as future work)

The download handler in `jobs.ts:239-245` parses cache keys with `key.endsWith(':file:rich')` / `key.endsWith(':file:lite')` to determine `resolvedMode`. This is fragile but changing it would add scope. Leave it untouched — it continues to work correctly since key strings don't change.

## Verification

- [ ] Before Step 1, run `rg "buildExportFileKey" src/backend/` from the repo root to confirm the call-site census: should match the counts in the Context section (5 calls in `file-bytes.ts`, 20 helper calls in `jobs.ts`, 1 hardcoded `${jobKey}:file` string at `jobs.ts:306`, plus 1 import in each call-site file and 1 definition in `cache-keys.ts`). If the count has drifted, update the plan before proceeding.
- [ ] `npm run test:run` — all existing tests pass (none break since key strings are identical)
- [ ] Update `cache-keys.test.ts` — replace the single `buildExportFileKey` multi-mode test with focused tests for each new function
- [ ] `npm run lint` — no lint errors

## Steps

- [ ] **Step 1:** In `cache-keys.ts` — add `buildXlsxVariantKey` and `buildPrebuiltFormatKey` alongside the existing `buildExportFileKey`. Keep the old `buildExportFileKey` signature unchanged during migration.
- [ ] **Step 2:** Update all call sites in `file-bytes.ts` — replace `buildExportFileKey(…, 'lite')`, `buildExportFileKey(…, 'rich')`, and `buildExportFileKey(…, 'csv')` with the corresponding new functions. Also extend the `buildExportFileKey` import on `file-bytes.ts:6` to include `buildXlsxVariantKey` and `buildPrebuiltFormatKey`.
- [ ] **Step 3:** Update all call sites in `jobs.ts` — same pattern as Step 2. Also extend the `buildExportFileKey` import on `jobs.ts:15` to include `buildXlsxVariantKey` and `buildPrebuiltFormatKey`. Handle the dynamic call at line 265 and the redundant write at line 266 using the optimized conditional block. Update the hardcoded `${jobKey}:file` string at line 306 to use `buildExportFileKey(jobKey)`.
- [ ] **Step 4:** In `cache-keys.ts` — remove the old `mode` parameter from `buildExportFileKey`. It no longer has callers passing modes. Also delete the now-stale 3-line `mode:` documentation comment at `cache-keys.ts:13-15` and replace it (and the comment on the bare `buildExportFileKey`) with concise JSDoc on all three functions explaining their role: `buildExportFileKey` (canonical fallback slot), `buildXlsxVariantKey` (XLSX render variants `rich`/`lite`), `buildPrebuiltFormatKey` (prebuilt format slots like `csv`).
- [ ] **Step 5:** Update `cache-keys.test.ts` — replace the single multi-mode test with:
  - `buildExportFileKey` → no-arg produces `<baseKey>:file`
  - `buildXlsxVariantKey` → `'rich'` and `'lite'` produce correct keys
  - `buildPrebuiltFormatKey` → `'csv'` produces correct key
  - TypeScript rejects invalid variant/format values at compile time — use `expectTypeOf` from `vitest` (e.g., `expectTypeOf(buildXlsxVariantKey).parameter(1).toEqualTypeOf<'rich' | 'lite'>()`) so the test fails the suite when an invalid argument is accepted. Extend the existing `import { describe, it, expect } from 'vitest';` on `cache-keys.test.ts:1` to include `expectTypeOf`, and extend the helper import on `cache-keys.test.ts:6` to include `buildXlsxVariantKey` and `buildPrebuiltFormatKey`.
- [ ] **Step 6:** Update `CHANGELOG.md` under `### Changed`: "Refactored `buildExportFileKey` to split its conflated `mode` parameter into dedicated `buildXlsxVariantKey` (for XLSX render variants `rich` and `lite`) and `buildPrebuiltFormatKey` (for prebuilt format slots like `csv`) functions. Cache key strings are unchanged; no in-flight cache entries are invalidated. Avoided one redundant cache write for the `default` XLSX render variant during download fallback regeneration." *Optional per `AGENTS.md` (changelog entries are not required for refactors with no user-visible behavior change), but kept for project-precedent consistency with `2026-06-21-refactor-export-ts.md` and `2026-06-24-refactor-routes-export-ts.md`, which both logged similar internal backend refactors.*
- [ ] **Step 7:** Run full verification. Note that `./scripts/verify-all.sh` runs `npx tsc --noEmit` and `npm run lint` (via `scripts/verify-backend.sh`) but does **not** execute the Vitest unit tests, so the new and updated tests in `cache-keys.test.ts` (Step 5) must be run separately:
  1. `./scripts/verify-all.sh` — typecheck + lint
  2. `cd src/backend && npm run test:run` — Vitest unit tests (must run explicitly; required to validate the new tests in `cache-keys.test.ts`)
- [ ] **Step 8:** Move this plan to `dev-docs/exec-plans/completed/` and update `dev-docs/exec-plans/completed/README.md`.
- [ ] **Step 9:** Remove the "Split XLSX render modes..." entry from `dev-docs/backlog/TO_DO.md` per `AGENTS.md` ("remove it from the file when the plan is finished").
