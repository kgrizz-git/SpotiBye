# 2026-06-21 Refactor export.ts

> reviewed by opus

> Split `src/backend/services/export.ts` (1,186 lines) into focused, testable modules.

## Problem

`export.ts` is the largest backend source file at 1,186 lines. It mixes:
- Type definitions and interfaces (15-133)
- Cursor encoding/decoding (154-199)
- Resumable job orchestration — the longest method at 145 lines (264-408)
- Assemble phase logic (410-471)
- Single-playlist export (473-506)
- Playlist slice extraction (508-544)
- Progress calculation (562-592)
- CSV chunk building (594-597)
- Worksheet assembly (599-614)
- Combined Excel from assembly — 57 lines with nested loops (616-672)
- Lite Excel renderer — 85 lines of dense ExcelJS cell manipulation (674-758)
- Combined CSV (760-762)
- Combined JSON — two methods, 48 lines (769-816)
- Playlist metadata builder (818-829)
- Track export pipeline — buildExportTracks, loadAudioFeaturesMap, mapTrackForExport (837-918)
- Single-file CSV generation (920-940)
- Single-file Excel generation (942-944)
- Combined Excel generation — 125 lines of ExcelJS workbook/sheet/table manipulation (946-1070)
- Cover image embedding (1072-1103)
- Base64 conversion (1105-1116)
- Format helpers — duration, sheet names, CSV escaping (1118-1180)
- Stub method (1182-1185)

The class has 25+ methods and touches at least 8 distinct concerns. Golden Principle #3 (cursors persisted before destructive steps) is embedded in the orchestration logic but hard to verify in isolation.

## Target Structure

Keep `services/` flat (no `types/` subdirectory — there is no precedent in this repo and the existing `src/backend/types/` is for cross-cutting types). Use a shared helpers file for cross-format utilities instead of placing them in `export-tracks.ts`.

```
src/backend/services/
  export.ts              ~120 lines — ExportService facade + named re-exports
  export-types.ts        ~130 lines — all interfaces (ExportTrack, ExportData, ResumableExportJobState, etc.)
  export-cursor.ts       ~80 lines — encodeCursor, decodeCursor
  export-job-state.ts    ~120 lines — createJobState, validateStepRequest, ResumableExportConflictError, createResumeToken
  export-assemble.ts     ~50 lines — createAssemblyState + shared preAssemblePlaylist() helper
  export-collect.ts      ~200 lines — runCollectStep, generatePlaylistExportSlice, mergeExportSlice, progress calculation
  export-assembly.ts     ~120 lines — runAssembleStep (extract of runAssemblePhaseStep)
  export-xlsx.ts         ~250 lines — generateCombinedExcelFile, generateCombinedExcelFileFromAssembly (rich) + tryAddCoverImage/arrayBufferToBase64 (cover image, rich-only)
  export-xlsx-lite.ts    ~150 lines — generateCombinedExcelFileFromAssemblyLite, buildWorksheetAssembly
  export-csv.ts          ~100 lines — buildCsvChunk, generateCsvFile, generateCombinedCsvFromAssembly, escapeCsvValue
  export-json.ts         ~80 lines — generateCombinedJson, generateCombinedJsonFromAssembly
  export-tracks.ts       ~150 lines — buildExportTracks, loadAudioFeaturesMap, mapTrackForExport, calculateTotalDurationMs, buildPlaylistMetadata
  export-format-helpers.ts ~50 lines — formatDuration, getTrackHeaders, sanitizeSheetName, uniquifySheetName (shared across collect, assembly, xlsx, xlsx-lite, csv, json)
```

The main `export.ts` is a thin facade: it keeps the `ExportService` class (with delegating methods) plus explicit named re-exports of every public type/function. The codebase does not use barrel `export *` patterns — prefer explicit named re-exports so the public API surface is auditable.

### Notes on the target structure

- **`export-xlsx.ts` + `export-xlsx-lite.ts` split** — the rich renderer (125 lines) and lite renderer (85 lines) are independently testable. Splitting keeps both files under 250 lines. **Correction to an earlier draft:** `tryAddCoverImage`/`arrayBufferToBase64` are called *only by the rich renderer* (`generateCombinedExcelFile`, line 1017) — the lite renderer never embeds cover images — so they live in `export-xlsx.ts`, not the lite file. Placing them in lite would have created an `export-xlsx.ts → export-xlsx-lite.ts` runtime edge for no reason.
- **Sheet-name helpers are shared, so they live in `export-format-helpers.ts`** — `sanitizeSheetName`/`uniquifySheetName` are pure string functions used by the rich renderer (xlsx.ts:977-978), by `buildWorksheetAssembly` (xlsx-lite), and indirectly by the lite path. Keeping them in `export-format-helpers.ts` lets both renderers depend only on `format-helpers` + `types` and avoids an `xlsx ↔ xlsx-lite` dependency in either direction.
- **`export-assemble.ts` owns the shared pre-assembly helper** — the inline pre-assembly logic at lines 326-351 (collect) and 430-441 (assemble) is duplicated. Extract a `preAssemblePlaylist(exportData, job, assemblyState)` helper used by both phases.
- **`export-format-helpers.ts`** — `formatDuration` and `getTrackHeaders` are used by collect, assemble, xlsx, csv, and json. Putting them in `export-tracks.ts` would force every format module to import from tracks; keeping them in a tiny shared module avoids a future "tracks depends on csv depends on tracks" cycle if tracks ever needs a format helper.
- **No `types/` subdirectory** — `src/backend/services/` is currently flat. Introducing a `types/` subdirectory for one file creates a new convention with no other occupant.

## Extracted Modules and Responsibilities

### `export-types.ts`
All type definitions currently at lines 15-133, plus `ResumableExportConflictError` (135-145):
- `ExportTrack` (currently `interface` without `export` — must be exported now; it's part of the effective API surface in serialized responses)
- `ExportData`
- `ResumableExportJobStatus`, `ResumableExportJobPhase`
- `ResumablePlaylistProgress`
- `XlsxRenderMode`, `WorksheetAssemblyData`
- `ResumableExportAssemblyState`
- `ResumableExportJobState`
- `ResumableExportStepResult`
- `ExportCellValue`

Use `import type` from this module in every consumer to keep the type-only import graph acyclic.

### `export-cursor.ts`
- `encodeCursor()` (154-161)
- `decodeCursor()` (163-199)
- Pure functions, no class dependency. Easy to unit test.

### `export-job-state.ts`
- `createJobState()` (215-248)
- `validateStepRequest()` (250-262)
- `ResumableExportConflictError` class (135-145) — also re-exported from here
- `createResumeToken()` (211-213)

### `export-assemble.ts`
- `createAssemblyState()` (201-209)
- `preAssemblePlaylist(exportData, job, assemblyState)` — shared helper, extracted from duplicated logic in collect (326-351) and assemble (430-441). Pushes the worksheet/csv chunk, summary row, and increments `next_assemble_index`.

### `export-collect.ts`
- `runCollectStep()` — extracted from `runResumableStep()` collect branch (289-403)
- `generatePlaylistExportSlice()` (508-544)
- `mergeExportSlice()` (546-560)
- `calculateJobProgress()` (562-584)
- `calculateAssembleProgress()` (586-592)

### `export-assembly.ts`
- `runAssembleStep()` — extracted from `runResumablePhaseStep()` (410-471). This is currently `private`; extracted to its own module it becomes an `export`-ed function called by the `ExportService.runResumableStep` dispatcher.

### `export-xlsx.ts`
- `generateCombinedExcelFile()` (946-1070)
- `generateCombinedExcelFileFromAssembly()` (616-672)
- `tryAddCoverImage()` (1072-1103) — called only by `generateCombinedExcelFile` (line 1017); the lite renderer does not embed images.
- `arrayBufferToBase64()` (1105-1116) — used only by `tryAddCoverImage`.
- Imports `exceljs`, `sanitizeSheetName`/`uniquifySheetName`/`getTrackHeaders`/`formatDuration` from `export-format-helpers`, and types from `export-types`.

### `export-xlsx-lite.ts`
- `generateCombinedExcelFileFromAssemblyLite()` (674-758)
- `buildWorksheetAssembly()` (599-614) — converts an `ExportData` into a `WorksheetAssemblyData`. Called by the collect (line 333) and assemble (line 434) phases, not by the rich renderer (which rebuilds `ExportData` inline). Imports `getTrackHeaders`/`sanitizeSheetName`/`uniquifySheetName`/`formatDuration` from `export-format-helpers`.
- Imports `exceljs` (for the lite workbook) and types from `export-types`.
- Does **not** own `sanitizeSheetName`/`uniquifySheetName` (now in `export-format-helpers` — shared with the rich renderer) nor `tryAddCoverImage`/`arrayBufferToBase64` (now in `export-xlsx.ts` — the only caller).

### `export-csv.ts`
- `buildCsvChunk()` (594-597)
- `generateCsvFile()` (920-940)
- `generateCombinedCsvFromAssembly()` (760-762)
- `escapeCsvValue()` (1175-1180)

### `export-json.ts`
- `generateCombinedJson()` (769-786)
- `generateCombinedJsonFromAssembly()` (793-816)

### `export-tracks.ts`
- `buildExportTracks()` (837-847)
- `loadAudioFeaturesMap()` (849-889)
- `mapTrackForExport()` (891-918)
- `calculateTotalDurationMs()` (831-835)
- `buildPlaylistMetadata()` (818-829)

Does **not** own `formatDuration` or `getTrackHeaders` — those live in `export-format-helpers.ts` because they are used by all format modules, not just track processing.

### `export-format-helpers.ts`
- `formatDuration()` (1118-1127)
- `getTrackHeaders()` (1154-1173)
- `sanitizeSheetName()` (1129-1132) — pure string helper, used by both the rich (xlsx.ts) and lite (`buildWorksheetAssembly`) paths.
- `uniquifySheetName()` (1136-1152) — pure string helper, used by both paths.

### `export.ts` (remaining)
- `ExportService` class — thin facade delegating to extracted modules. The constructor keeps `private accessToken: string` so instance methods can thread it into the extracted Spotify-touching functions.
- **Static delegating methods** `encodeCursor`, `decodeCursor`, `createJobState`, `createAssemblyState`, `createResumeToken`, `validateStepRequest` — keep these as one-line `static x(...args) { return xImpl(...args); }` delegations to the extracted pure functions. This preserves the `ExportService.X(...)` call sites in `routes/export.ts:196, 207, 249` and the test mock without changing any callers.
- **Instance delegating methods — every public instance method an external caller invokes must remain on the facade.** Verified external instance call sites (must all keep working unchanged):
  - `generatePlaylistExport()` (473-506) — non-resumable path; `routes/export.ts:561,683,819`, `export-pagination.test.ts:43,58`. Delegates to `export-tracks`/`export-format-helpers`, passing `this.accessToken`.
  - `runResumableStep()` (264-408) — dispatcher; `routes/export.ts:275`. Routes to `runCollectStep(this.accessToken, …)` / `runAssembleStep(…)`.
  - `generateCsvFile()` (920-940) — `routes/export.ts:151`. Delegates to `export-csv`.
  - `generateCombinedExcelFile()` (946-1070) — `routes/export.ts:156`. Delegates to `export-xlsx`.
  - `generateCombinedExcelFileFromAssembly()` (616-672) — `routes/export.ts:171`. Delegates to `export-xlsx`.
  - `generateCombinedCsvFromAssembly()` (760-762) — `routes/export.ts:169`. Delegates to `export-csv`.
  - `generateCombinedJson()` (769-786) — `routes/export.ts:146`, `export-json.test.ts:47`. Delegates to `export-json`.
  - `generateCombinedJsonFromAssembly()` (793-816) — `routes/export.ts:166`, `export-json.test.ts:89`. Delegates to `export-json`.
  - `generateExcelFile()` (942-944) — thin wrapper around `generateCombinedExcelFile`.
  - `generateAdvancedExcelFile()` (1182-1185) — stub, pass-through.
  - (`generatePlaylistExportSlice` is internal-only — called by `runResumableStep`; it can move fully into `export-collect` and does not need a facade method.)
- Named re-exports of every public type and the `ResumableExportConflictError` class.

> **Mechanical-conversion rule (applies to every extraction step):** each extracted instance method becomes a standalone exported function. Replace `this.helper(...)` with a call to the imported function, and `this.formatDuration`/`this.getTrackHeaders`/etc. with the `export-format-helpers` imports. Any method that builds `new SpotifyService(this.accessToken)` (`generatePlaylistExport`, `generatePlaylistExportSlice`, `buildExportTracks`, and therefore `runCollectStep`) takes `accessToken: string` as its first parameter; the facade passes `this.accessToken`.

### Re-export surface (explicit)

`export.ts` must re-export (named, not `export *`):
- From `./export-types`: `ExportTrack`, `ExportData`, `ResumableExportJobStatus`, `ResumableExportJobPhase`, `ResumablePlaylistProgress`, `XlsxRenderMode`, `WorksheetAssemblyData`, `ResumableExportAssemblyState`, `ResumableExportJobState`, `ResumableExportStepResult`, `ExportCellValue`
- From `./export-job-state`: `ResumableExportConflictError`
- (Static methods on `ExportService` cover `encodeCursor` / `decodeCursor` / `createJobState` / `createAssemblyState` / `createResumeToken` / `validateStepRequest` — no separate re-export needed.)

## Execution Steps

Steps are ordered so each step depends only on already-created modules. Format modules (Steps 7-10) come before the orchestrators (Steps 11-12) because the orchestrators call into them.

- [ ] Step 1: Create `export-types.ts` — move all type definitions. Add `export` to `ExportTrack` (currently `interface` without `export` — needed for the effective API surface). Add unit tests confirming types compile.
- [ ] Step 2: Create `export-cursor.ts` — extract `encodeCursor` / `decodeCursor` as pure functions. Add unit tests: null, undefined, malformed JSON, negative integers, missing `phase`, both phase values round-trip, non-numeric `next_playlist_index`.
- [ ] Step 3: Create `export-job-state.ts` — extract `createJobState`, `validateStepRequest`, `createResumeToken`, and the `ResumableExportConflictError` class. Add unit tests: `createJobState` field defaults (status='running', phase='collect', track_page_size=100, continuation_required based on playlistIds.length>0), `validateStepRequest` returns silently for completed jobs, throws conflict on stale cursor or stale token, accepts matching cursor+token.
- [ ] Step 4: Create `export-assemble.ts` — extract `createAssemblyState` and a new shared `preAssemblePlaylist(exportData, job, assemblyState)` helper. The helper must be called from both the collect-phase inline pre-assembly (326-351) and the assemble-phase branch (430-441) — without this dedup, the refactor ships with the same duplication.
- [ ] Step 5: Create `export-tracks.ts` — extract `buildExportTracks`, `loadAudioFeaturesMap`, `mapTrackForExport`, `calculateTotalDurationMs`, `buildPlaylistMetadata`. `buildExportTracks`/`loadAudioFeaturesMap` already receive a `SpotifyService` argument so no `accessToken` parameter is needed here; `mapTrackForExport` imports `formatDuration` from `export-format-helpers`. Add unit tests: `mapTrackForExport` with full audio features, with `null` audio features, with partial features (some keys missing), with `N/A` for invalid types; `formatDuration` at 0 ms, 59 s, 60 s, 3599 s, 3600 s, 3_600_000 ms.
- [ ] Step 6: Create `export-format-helpers.ts` — extract `formatDuration`, `getTrackHeaders`, and the pure sheet-name helpers `sanitizeSheetName` and `uniquifySheetName` (shared by the rich and lite XLSX paths; no ExcelJS dependency). Do this before Steps 7-8 since both depend on it.
- [ ] Step 7: Create `export-xlsx.ts` — extract `generateCombinedExcelFile`, `generateCombinedExcelFileFromAssembly` (rich renderer), and `tryAddCoverImage`/`arrayBufferToBase64` (called only by the rich renderer). Import the sheet-name helpers from `export-format-helpers`. Add unit tests: `generateCombinedExcelFileFromAssembly` uses the rich renderer when `renderMode==='rich'`, the lite renderer when `renderMode==='lite'`, and in `'auto'` mode picks rich only when both `worksheetCount<=18` and `trackRows<=2400` (else lite). Note: this test must import or spy on the lite renderer from `export-xlsx-lite`, so write it after Step 8 even though the module is created here.
- [ ] Step 8: Create `export-xlsx-lite.ts` — extract `generateCombinedExcelFileFromAssemblyLite` and `buildWorksheetAssembly` (importing sheet-name + format helpers from `export-format-helpers`). Sheet-name helpers and cover-image helpers are **not** here (see Steps 6 and 7). Add unit tests: `sanitizeSheetName` strips `\\/*?[]` and trims to 31 chars (empty input → `'Playlist'`); `uniquifySheetName` returns base on first call, appends `' (N)'` on collision with N=2,3,…  — place these in the `export-format-helpers` test file since that is where they now live; `buildWorksheetAssembly` maps `ExportTrack` rows to header-keyed values with `''` fallback for missing keys.
- [ ] Step 9: Create `export-csv.ts` — extract `buildCsvChunk`, `generateCsvFile`, `generateCombinedCsvFromAssembly`, `escapeCsvValue`. Add unit tests: `escapeCsvValue` adds quotes when value contains `,`, `"`, or `\n`; doubles embedded quotes; passes through plain values; `generateCombinedCsvFromAssembly` joins chunks with `'\n\n'`.
- [ ] Step 10: Create `export-json.ts` — extract `generateCombinedJson`, `generateCombinedJsonFromAssembly`. Add unit tests: nested per-playlist object shape; `fromAssembly` reconstructs tracks from worksheet headers+rows; `total_duration` is formatted via `formatDuration`; missing `description` falls back to `''`.
- [ ] Step 11: Create `export-collect.ts` — extract the collect branch of `runResumableStep` (lines 264-408 minus the assemble routing) as `runCollectStep`, plus `generatePlaylistExportSlice`, `mergeExportSlice`, `calculateJobProgress`, `calculateAssembleProgress`. `runCollectStep` and `generatePlaylistExportSlice` take `accessToken: string` as their first parameter (they build `new SpotifyService(accessToken)`); the collect step calls `preAssemblePlaylist` (Step 4), `buildCsvChunk`/`buildWorksheetAssembly` (csv/xlsx-lite), and `formatDuration` (format-helpers) via imports rather than `this.`. Add unit tests: `mergeExportSlice` with `undefined` existing, with partial existing (merges tracks, sums duration, overrides playlist metadata with newer), with tracks-only change (preserves playlist metadata); `calculateJobProgress` returns 100 for empty playlistIds, returns 99 max, `done` playlists count as 1.0, in-progress counts as `min(collected/total, 0.99)`; `calculateAssembleProgress` returns 100 when total=0, ranges 95-99 for 0<assemble/total<1; `generatePlaylistExportSlice` reuses `existingExportData.playlist` when its id matches, otherwise fetches.
- [ ] Step 12: Create `export-assembly.ts` — extract `runAssemblePhaseStep` (currently `private`) as `runAssembleStep`. The `private` access modifier is removed; the function is now an `export`ed module function called by the `ExportService.runResumableStep` dispatcher.
- [ ] Step 13: Rewrite `export.ts` — keep `ExportService` with all current public methods. Add static delegating methods (`encodeCursor`, `decodeCursor`, `createJobState`, `createAssemblyState`, `createResumeToken`, `validateStepRequest`) as one-line pass-throughs to the extracted pure functions. Add explicit named re-exports of every type and the `ResumableExportConflictError` class. Use `import type` for all type-only imports to keep the import graph acyclic.
- [ ] Step 14: Verify no other consumer of `services/export.ts` was missed — `rg "services/export" src/backend/` should return only `routes/export.ts` and the three test files. (`routes/analysis.ts` does not import from `services/export` despite the original plan's mention.) No call site changes are needed if static delegating methods are used.
- [ ] Step 15: Update `tests/export.test.ts` mock — the mock currently provides the static methods `encodeCursor`, `createAssemblyState`, `createResumeToken`, `createJobState`, `validateStepRequest` directly. With static delegating methods on `ExportService`, no mock change is strictly required, but consider also adding `vi.mock` for the new pure-function modules so future tests that import them directly are isolated.
- [ ] Step 16: Run `npm run lint && npm run test:run && npm run build` in `src/backend/`.
- [ ] Step 17: Run `./scripts/verify-all.sh` from repo root.
- [ ] Step 18: Update `CHANGELOG.md` under `## [Unreleased]` with a `### Changed` entry: "Refactored `services/export.ts` into focused modules (`export-types`, `export-cursor`, `export-job-state`, `export-collect`, `export-assembly`, `export-xlsx`, `export-xlsx-lite`, `export-csv`, `export-json`, `export-tracks`, `export-format-helpers`) without changing the public API or output formats." Per `AGENTS.md` Changelog Rule.

## Testing Strategy

- Preserve the existing mock structure in `tests/export.test.ts` — the mock targets `services/export` which continues to export `ExportService` and `ResumableExportConflictError`.
- Add unit tests for extracted pure functions (per the per-step unit-test callouts in the Execution Steps section):
  - `export-cursor.ts` — null/undefined, malformed JSON, negative integers, missing `phase`, both phase values round-trip, non-numeric `next_playlist_index`, fallback parameter behavior.
  - `export-job-state.ts` — `createJobState` defaults (status='running', phase='collect', track_page_size=100, continuation_required=playlistIds.length>0); `validateStepRequest` no-op when completed, throws conflict on stale cursor or token, accepts matching values.
  - `export-tracks.ts` — `mapTrackForExport` with full audio features, with `null` audio features, with partial features (some keys missing), with `N/A` for invalid types; `calculateTotalDurationMs` filters items without a `duration_ms`.
  - `export-format-helpers.ts` — `formatDuration` at 0, 59 s, 60 s, 3599 s, 3600 s, and 3 600 000 ms boundaries; `sanitizeSheetName` strips `\\/*?[]` and clamps to 31 chars (empty input → 'Playlist'); `uniquifySheetName` first call returns base, collisions append ` (N)` with N=2,3,…
  - `export-xlsx-lite.ts` — `buildWorksheetAssembly` maps `ExportTrack` rows to header-keyed values with `''` fallback.
  - `export-xlsx.ts` — `generateCombinedExcelFileFromAssembly` renderer selection: `'rich'`/`'lite'` overrides and the `'auto'` threshold (`worksheetCount<=18 && trackRows<=2400`).
  - `export-csv.ts` — `escapeCsvValue` quotes when value contains `,`/`"`/`\n` and doubles embedded quotes; `generateCombinedCsvFromAssembly` joins chunks with `'\n\n'`.
  - `export-json.ts` — nested per-playlist object shape; `fromAssembly` reconstructs tracks from worksheet headers+rows; `total_duration` uses `formatDuration`.
  - `export-collect.ts` — `mergeExportSlice` (undefined existing, partial merge, tracks-only change preserves playlist metadata); `calculateJobProgress` (100 for empty, 99 max, `done` counted as 1.0, in-progress as `min(collected/total, 0.99)`); `calculateAssembleProgress` (100 when total=0, 95-99 range); `generatePlaylistExportSlice` reuses `existingExportData.playlist` when its id matches.
- The existing integration-level tests in `tests/export.test.ts` exercise the route layer which mocks `ExportService` — these continue to pass without changes (static delegating methods preserve the API).
- The pagination test `tests/export-pagination.test.ts` calls the real `ExportService.generatePlaylistExport` and `SpotifyService` methods — this must continue to pass since `generatePlaylistExport` (473-506) stays in `export.ts` and depends only on `export-tracks.ts` and `export-format-helpers.ts`.
- The JSON test `tests/export-json.test.ts` calls the real `ExportService.generateCombinedJson` and `generateCombinedJsonFromAssembly` — these must continue to pass.

## Risks and Mitigations

- **Static method call sites**: `routes/export.ts:196, 207, 249, 278` and `tests/export.test.ts:9-62` all call `ExportService.encodeCursor`, `ExportService.createJobState`, `ExportService.createAssemblyState`, `ExportService.createResumeToken`, `ExportService.validateStepRequest`, and the mock's `(this.constructor as any).encodeCursor` / `createResumeToken`. Mitigation: keep these as one-line static delegating methods on `ExportService` in `export.ts` that call the extracted pure functions. No call site or mock changes required.
- **Circular imports**: The dependency tree is `collect/assembly → {csv, xlsx-lite, tracks, format-helpers, job-state, cursor, assemble, types}` and `{csv, xlsx, xlsx-lite, json, tracks} → {format-helpers, types}`. Sheet-name helpers live in `format-helpers` (not xlsx-lite) and cover-image helpers live in `xlsx` (their only caller), so there is **no edge between `xlsx` and `xlsx-lite`** in either direction. No cycles by construction. Mitigation: enforce with `import type` for all type-only imports so adding a runtime import later cannot accidentally introduce a cycle.
- **Duplicate pre-assembly logic**: The current code has pre-assembly inline in both the collect branch (326-351) and the assemble branch (430-441). Mitigation: extract as `preAssemblePlaylist(exportData, job, assemblyState)` in `export-assemble.ts` and call from both phases.
- **`runAssemblePhaseStep` access change**: currently `private`. After extraction to `export-assembly.ts` it must be `export`ed so the `ExportService.runResumableStep` dispatcher can call it. Mitigation: rename to `runAssembleStep` to match the new public module convention.
- **SpotifyService coupling**: `generatePlaylistExportSlice` and `buildExportTracks` instantiate `SpotifyService` directly. Mitigation: keep the constructor `accessToken` on `ExportService` and pass it through extracted methods; or inject `SpotifyService` as a dependency in a future step (out of scope for this refactor).
- **ExcelJS integration**: The lite renderer has hardcoded column widths, cell positions, and table references. Mitigation: extract as-is first; style parameters can be configurable later. The `exceljs` import is localized to `export-xlsx.ts` and `export-xlsx-lite.ts`.
- **`ExportTrack` becomes exported**: Currently `interface ExportTrack` (not exported) — but it appears in the serialized response shape, so callers may already be depending on it transitively. After this refactor it is properly `export interface ExportTrack`. Document in CHANGELOG as a non-breaking expansion of the public type surface.
- **Test breakage**: The mock in `tests/export.test.ts` is a simplified stand-in. It already doesn't test the real methods — it tests routes. The refactor must not change the exported API surface (same method signatures, same types).

## Success Criteria

- No file exceeds 300 lines (target was 350; the xlsx split gets both under 250).
- All existing tests pass without modification (static delegating methods + unchanged signatures).
- `npm run build` and `npm run lint` are clean.
- `./scripts/verify-all.sh` passes.
- No behavioral changes — same API, same output formats, same cursor/resume semantics.
- `CHANGELOG.md` updated under `## [Unreleased]`.
