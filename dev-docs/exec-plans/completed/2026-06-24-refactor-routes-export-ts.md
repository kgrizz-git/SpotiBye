# 2026-06-24 Refactor routes/export.ts

> **REVIEWED 2026-06-24 (5th Pass)** — Option A approved. Refactoring plan updated with safety corrections from all five review passes (sub-routing prefix layout, types and imports updates, request-id helper modularization, cache keys uniform signatures, ESLint sibling route rules with explicit route group block lists, Vitest architecture test path mapping with resolved route family same-family checks, mock-path-stability, file-precaching extraction for jobs.ts budget compliance, and CHANGELOG/documentation integration). Ready for execution.

Split `src/backend/routes/export.ts` (1,050 lines) into focused modules so each file has a single responsibility and stays well under the project's implicit ~300-line target.

## Context

The 2026-06-21 refactor of `services/export.ts` (1,186 → 193 lines + 12 modules) is complete. That work is captured in `dev-docs/exec-plans/completed/2026-06-21-refactor-export-ts.md` and intentionally left the HTTP route layer untouched. The route file has since grown — or always carried — ~1,050 lines mixing:

- Key builders and format/header helpers (49-138)
- `generateFileBytes` / `generateFileBytesFromAssembly` byte-builders (140-173)
- 12 route handlers spanning 3 job families (`/jobs`, `/playlists`, `/playlist`) (179-1048)
- Type aliases used only inside the file (`ExportFormat`, `BatchExportStatus`, `ResumableExportJobStatus` alias) (17-38)

The service-layer refactor is a useful precedent: it kept a thin facade (`services/export.ts`) and split helpers into pure modules. This plan applies the same pattern to the route layer using Hono's sub-app routing mechanism.

Sibling route files are 141–234 lines, so a target of **≤ 300 lines per file** is consistent with the existing project.

## Target Structure (Option A Selected)

`routes/export.ts` will serve as a thin facade re-exporting the Hono app composed in `routes/export/index.ts`. All sub-app route handlers will be mounted relative to their prefix, and helpers will live under `routes/export/helpers/`.

The facade is kept to maintain import path stability for `index.ts` and `tests/export.test.ts`, protecting against resolution ambiguities.

### File Layout and Budgets
```
src/backend/routes/export.ts           1 line — re-exports the assembled Hono app
src/backend/routes/export/
  index.ts                            ≤ 30 lines — composes sub-apps, applies authMiddleware once
  helpers/
    cache-keys.ts                     ≤ 50 lines — buildExportJobKey, buildExportJobDataKey, etc.
    format.ts                         ≤ 60 lines — parseXlsxRenderMode, resolveRequestedFormat, etc.
    errors.ts                         ≤ 80 lines — resolveErrorStatus, parseUpstreamStatus, etc.
    file-bytes.ts                     ≤ 120 lines — generateFileBytes, generateFileBytesFromAssembly, and precacheJobFiles
    request-id.ts                     ≤ 10 lines — newRequestId request uuid utility
    types.ts                          ≤ 30 lines — ExportFormat, BatchExportStatus
  jobs.ts                             ≤ 320 lines — /jobs sub-router (resumable)
  playlists.ts                        ≤ 350 lines — /playlists sub-router (combined/batch)
  playlist.ts                         ≤ 300 lines — /playlist sub-router (single)
```

*Line-count note:* Extracting the file-precaching block into a `precacheJobFiles(...)` helper in `helpers/file-bytes.ts` reduces `jobs.ts` line count (saving ~60 lines), keeping it well under a ≤ 320 line budget with ample headroom.

### Facade and Sub-App Composition Specification

**Facade (`src/backend/routes/export.ts`):**
Exactly the following 1-line code block of `exportRoutes` (no comment headers, to maintain the 1-line of code success criterion, though the file will contain a standard trailing newline as required by POSIX):
```typescript
export { exportRoutes } from './export/index';
```

**Composed Sub-App (`src/backend/routes/export/index.ts`):**
Exactly the following 13-line composition (note that sub-app names `jobsApp`, `playlistsApp`, and `playlistApp` are internal and not re-exported):
```typescript
import { Hono } from 'hono';
import { authMiddleware } from '../../middleware/auth';
import { jobsApp } from './jobs';
import { playlistsApp } from './playlists';
import { playlistApp } from './playlist';
import type { Env } from '../../types/env';
import type { Variables } from '../../types/variables';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();
app.use('*', authMiddleware);
app.route('/jobs', jobsApp);
app.route('/playlists', playlistsApp);
app.route('/playlist', playlistApp);

export { app as exportRoutes };
```

### Route Mounting Approach
Each family file exports a `Hono<{ Bindings: Env; Variables: Variables }>` sub-app. The parent `routes/export/index.ts` mounts these sub-apps under their respective path prefixes (`/jobs`, `/playlists`, `/playlist`) and applies `authMiddleware` once at the top level (preserving the `app.use('*', authMiddleware)` semantics).

> [!WARNING]
> Inside each sub-app module, route paths must be registered relative to the mount point (e.g., `jobsApp.post('/', ...)` maps to `POST /export/jobs`, and `jobsApp.post('/:jobId/step', ...)` maps to `POST /export/jobs/:jobId/step`). Retaining the prefix in sub-apps will break routes and cause 404s.

---

## Proposed Module Contents

### `routes/export/helpers/types.ts`
- `ExportFormat` (currently line 17)
- `BatchExportStatus` (currently lines 19-36)
- *Note:* The local `ResumableExportJobStatus` alias is removed to resolve a naming collision with `services/export-types.ts:38`. All route files will directly import and use the standard `ResumableExportJobState` from `../../services/export-types`.

### `routes/export/helpers/cache-keys.ts`
- Uniform signatures taking raw identifiers `(jobId or playlistId, userId)` instead of passing pre-composed strings:
  - `buildExportJobKey(jobId, userId)` (49-51)
  - `buildExportJobDataKey(jobId, userId)` (53-55)
  - `buildExportJobAssemblyKey(jobId, userId)` (57-59)
  - `buildExportFileKey(jobKey, mode)` (61-66) — *Note:* Keep the `'csv'` mode parameter for backwards compatibility. Add a comment explaining that `'csv'` serves as a pre-built CSV slot (written to and read from directly, but excluded from the normal fallback chain).
  - `buildBatchKey(jobId, userId)` (replaces inline string at 674, 776, 887, 909)
  - `buildBatchDataKey(jobId, userId)` (replaces inline string at 707, 777, 927. Note: The local `batchDataKey` variable in `playlists.ts` goes away completely in favor of the helper call).
  - `buildBatchFileKey(jobId, userId)` (replaces inline string at 713, 849, 919, 933)
  - `buildSingleExportKey(playlistId, userId)` (replaces inline string at 538, 959, 980, 1035)
  - `buildSingleExportDataKey(playlistId, userId)` (replaces inline string at 579, 984, 1039)
  - `buildSingleExportFileKey(playlistId, userId)` (replaces inline string at 585, 997, 1010)
- *Note:* The mixing of XLSX render modes ('default', 'rich', 'lite') and 'csv' in `buildExportFileKey` is a known smell. We preserve this signature in the helper for call-site compatibility and note it for a future refactor.
- *Note:* `buildExportFileKey` is the only helper that takes a pre-composed base key. All other helpers accept raw identifiers and compose the key internally. This asymmetry is necessary because the `:file[:mode]` suffix is appended to an already-composed key (e.g., `buildExportJobKey(jobId, userId)`).

### `routes/export/helpers/format.ts`
- `parseXlsxRenderMode` (68-74)
- `resolveRequestedFormat` (76-81)
- `resolveStoredFormat` (84-86)
- `formatHttpMeta` (89-93)
- `resolveIncludeAudioFeatures` (95-97)
- `resolveStepSize` (40-47)

### `routes/export/helpers/request-id.ts`
- `newRequestId()` helper (uses `crypto.randomUUID()` to eliminate duplicate calls across handlers).

### `routes/export/helpers/errors.ts`
- `resolveErrorStatus` (99-110) — returns `ContentfulStatusCode` directly to eliminate call-site casting:
  ```typescript
  import type { ContentfulStatusCode } from 'hono/utils/http-status';
  export function resolveErrorStatus(code: string, message: string): ContentfulStatusCode;
  ```
- `parseUpstreamStatus` (112-119)
- `buildExportErrorPayload` (121-138)

### `routes/export/helpers/file-bytes.ts`
- `generateFileBytes` (141-158)
- `generateFileBytesFromAssembly` (160-173)
- `precacheJobFiles(exportService, cacheService, job, assemblyState, jobKey)` helper:
  Extracts the file-precaching block from the jobs.ts step handler (formerly lines 288-346). Updates job stats and render mode hints in-place, saves the updated job, and pre-builds formats (CSV/JSON/XLSX variants) to cache. Imports `buildExportFileKey` from `./cache-keys` directly (no parameter injection needed).

### `routes/export/jobs.ts`
Sub-router for resumable jobs (`jobsApp`). Instantiated with `<{ Bindings: Env; Variables: Variables }>`.
- `POST /` (formerly `POST /jobs`, lines 179-223)
- `POST /:jobId/step` (formerly `POST /jobs/:jobId/step`, lines 226-362)
- `GET /:jobId/status` (formerly `GET /jobs/:jobId/status`, lines 365-396)
- `GET /:jobId/download` (formerly `GET /jobs/:jobId/download`, lines 399-519)

### `routes/export/playlists.ts`
Sub-router for combined/batch routes (`playlistsApp`). Instantiated with `<{ Bindings: Env; Variables: Variables }>`.
- `POST /` (formerly `POST /playlists`, lines 654-747)
- `POST /chunk` (formerly `POST /playlists/chunk`, lines 750-879)
- `GET /:jobId/status` (formerly `GET /playlists/:jobId/status`, lines 882-899)
- `GET /:jobId/download` (formerly `GET /playlists/:jobId/download`, lines 902-950)

### `routes/export/playlist.ts`
Sub-router for single-playlist routes (`playlistApp`). Instantiated with `<{ Bindings: Env; Variables: Variables }>`.
- `POST /:id` (formerly `POST /playlist/:id`, lines 522-651)
- `GET /:id/status` (formerly `GET /playlist/:id/status`, lines 953-971)
- `GET /:id/download` (formerly `GET /playlist/:id/download`, lines 974-1026)
- `DELETE /:id` (formerly `DELETE /playlist/:id`, lines 1029-1048)

---

## Implementation Steps

- [x] Create folder structure and placeholder files (containing `export {};`) to ensure the project compiles:
  - `src/backend/routes/export/index.ts`
  - `src/backend/routes/export/jobs.ts`
  - `src/backend/routes/export/playlists.ts`
  - `src/backend/routes/export/playlist.ts`
  - *Note:* Creating these placeholders creates a transient non-functional state in the import chain until the handlers and parent index are fully implemented in subsequent steps. Avoid running tests until the index composition is complete.
- [x] Create helper files and implement their actual contents:
  - `src/backend/routes/export/helpers/types.ts`
  - `src/backend/routes/export/helpers/cache-keys.ts`
  - `src/backend/routes/export/helpers/format.ts`
  - `src/backend/routes/export/helpers/errors.ts`
  - `src/backend/routes/export/helpers/file-bytes.ts`
  - `src/backend/routes/export/helpers/request-id.ts`
  - *Note:* From `routes/export/<file>.ts`, use `./helpers/*` for siblings in the same `export/` folder and `../../services|types|middleware/*` for parent-level folders. There is no case requiring `../../../` from any new file.
  - *Note:* Import `ContentfulStatusCode` from `hono/utils/http-status` inside `errors.ts` for `resolveErrorStatus` and in sub-router files where casts are needed. Do not import it in the facade or `index.ts`.
  - *Note:* In `helpers/types.ts`, add a comment noting that `ResumableExportJobState` is imported directly from `services/export-types.ts` (not re-exported) to keep it as a leaf module.
- [x] Add 3 new isolated unit test files in `src/backend/tests/` (`cache-keys.test.ts`, `format.test.ts`, and `errors.test.ts`), bringing the total test files count to 38. Pin key composition backwards compatibility and verify that `parseXlsxRenderMode` defaults to `'auto'` on invalid inputs.
- [x] Extract route handlers into `jobs.ts`, `playlists.ts`, and `playlist.ts` sub-apps. During extraction:
  - Extract the file-precaching block (lines 288-346 of the original) from the jobs step handler into `precacheJobFiles(...)` in `helpers/file-bytes.ts`.
  - Import standard types: `ResumableExportJobState` from `../../services/export-types` and `ResumableExportAssemblyState` from `../../services/export` (the facade).
  - Remove the 9 redundant `resolveErrorStatus(...) as ContentfulStatusCode` casts from handler files. Keep inline numeric casts (such as `{ status: 404 as ContentfulStatusCode }`) unchanged to preserve Hono compatibility.
  - Preserve the pre-existing inconsistency of passing status `400` (no-cast on line 192, explicit cast on lines 668 and 770) to prevent unnecessary diff noise.
  - Replace the 8 request-related `crypto.randomUUID()` calls (lines 180, 227, 513, 523, 655, 751, 944, 1021) with `newRequestId()`. Leave the 4 `jobId` declarations (lines 196, 550, 673, 775) using `crypto.randomUUID()`.
- [x] Implement `routes/export/index.ts` mounting all sub-apps under their respective prefixes with `authMiddleware` applied at the parent level.
- [x] Reduce `routes/export.ts` to exactly the specified 1-line re-export of `exportRoutes` from `routes/export/index.ts`.
- [x] Update the lint rule override in `src/backend/.eslintrc.json` to cover nested routes:
  - Replace the `files: ["routes/*.ts"]` pattern with `["routes/**/*.ts"]`.
  - Update the restricted pattern `group: ["../routes/*"]` to `["../routes/*", "../analysis", "../auth", "../spotify"]` so sibling imports from nested route files to other route families are blocked. Document the maintenance burden of the explicit list in a comment inside `.eslintrc.json`.
- [x] Extend `src/backend/tests/architecture.test.ts` to recursively scan `routes/`. Ensure test names use the relative path prefix (e.g., `routes/export/jobs.ts` instead of `jobs.ts`) to avoid duplicate name collisions.
- [x] Update the architecture test violation pattern for routes. Since nested routes can use relative paths like `../` to reference siblings, resolve import paths relative to the source file. If the resolved absolute path points to a file within `src/backend/routes/` that belongs to a different route family (e.g., `analysis` from `export/`), treat it as a violation. Use a helper function `isSameFamily(sourceFile: string, resolvedImport: string): boolean` that compares the first directory segment under `routes/` (e.g., `export`, `analysis`, or top-level `""` family) and returns `false` if they differ (such as comparing a top-level route with a sub-family route, or different sub-families).
- [x] Update documentation references:
  - In `dev-docs/code-map.md`, update the Mermaid diagram route node and the file index entry for `routes/export.ts` to point to the new folder structure and `routes/export/index.ts`.
  - In `ARCHITECTURE.md`, update the `routes/export.ts` table row to reference `routes/export/index.ts` with sub-routers and helpers details:
    ```
    | `routes/export/index.ts` | Composed Hono sub-app: mounts `jobsApp` at `/jobs`, `playlistsApp` at `/playlists`, `playlistApp` at `/playlist`. Sub-routers live at `routes/export/{jobs,playlists,playlist}.ts`; helpers at `routes/export/helpers/`. Single-playlist export (`POST /export/playlist/:id`), combined export (`POST /export/playlists`), chunked combined export (`POST /export/playlists/chunk`), resumable job API (`POST /export/jobs`, `POST /export/jobs/:jobId/step`, `GET /export/jobs/:jobId/status`, `GET /export/jobs/:jobId/download`), status and download endpoints for each |
    ```
    Also, add definitions for the batch and single-export keys in the KV Keys section.
  - In `dev-docs/architecture/design-decisions/resumable-export-cursors.md`, update the link referencing `routes/export.ts` for accuracy.
  - Leave historical completed plans and bug reviews unchanged.
- [x] Add a follow-up item in `dev-docs/backlog/TO_DO.md` to split the XLSX render-modes and prebuilt-format slots in `buildExportFileKey` as noted in the known smell follow-up.
- [x] Run full backend verification suite: `npm run test:run && npm run lint && npm run build` (should run all 38 test files cleanly).
- [x] Run `./scripts/verify-all.sh` from the repo root.
- [x] Add entry to `CHANGELOG.md` under the most recent `### Changed` block of the `## [Unreleased]` section:
  > Refactored `routes/export.ts` (1,050 lines) into a Hono sub-app composition at `routes/export/` with helper modules under `routes/export/helpers/` (types, cache-keys, format, errors, request-id, file-bytes). The public `exportRoutes` export is preserved; no call-site or test-assertion changes. The local `ResumableExportJobStatus` alias is removed in favor of the service-layer `ResumableExportJobState`; both name and shape are now sourced from `services/export-types.ts`.
- [x] Manually update `dev-docs/dependency-graph.json` to replace the `src/backend/routes/export.ts` entry with the new structure. Ensure the new keys are inserted in alphabetical order under the `src/backend/` prefix:
  - *Before:*
    ```json
    "src/backend/routes/export.ts": [
      "src/backend/middleware/auth.ts",
      "src/backend/services/export.ts",
      "src/backend/services/cache.ts",
      "src/backend/types/env.ts",
      "src/backend/types/variables.ts"
    ]
    ```
  - *After:*
    ```json
    "src/backend/routes/export.ts": [
      "src/backend/routes/export/index.ts"
    ],
    "src/backend/routes/export/index.ts": [
      "src/backend/middleware/auth.ts",
      "src/backend/routes/export/jobs.ts",
      "src/backend/routes/export/playlists.ts",
      "src/backend/routes/export/playlist.ts",
      "src/backend/types/env.ts",
      "src/backend/types/variables.ts"
    ],
    "src/backend/routes/export/jobs.ts": [
      "src/backend/services/export.ts",
      "src/backend/services/cache.ts",
      "src/backend/types/env.ts",
      "src/backend/types/variables.ts",
      "src/backend/routes/export/helpers/cache-keys.ts",
      "src/backend/routes/export/helpers/format.ts",
      "src/backend/routes/export/helpers/errors.ts",
      "src/backend/routes/export/helpers/file-bytes.ts",
      "src/backend/routes/export/helpers/request-id.ts",
      "src/backend/routes/export/helpers/types.ts"
    ],
    "src/backend/routes/export/playlists.ts": [
      "src/backend/services/export.ts",
      "src/backend/services/cache.ts",
      "src/backend/types/env.ts",
      "src/backend/types/variables.ts",
      "src/backend/routes/export/helpers/cache-keys.ts",
      "src/backend/routes/export/helpers/format.ts",
      "src/backend/routes/export/helpers/errors.ts",
      "src/backend/routes/export/helpers/file-bytes.ts",
      "src/backend/routes/export/helpers/request-id.ts",
      "src/backend/routes/export/helpers/types.ts"
    ],
    "src/backend/routes/export/playlist.ts": [
      "src/backend/services/export.ts",
      "src/backend/services/cache.ts",
      "src/backend/types/env.ts",
      "src/backend/types/variables.ts",
      "src/backend/routes/export/helpers/cache-keys.ts",
      "src/backend/routes/export/helpers/format.ts",
      "src/backend/routes/export/helpers/errors.ts",
      "src/backend/routes/export/helpers/file-bytes.ts",
      "src/backend/routes/export/helpers/request-id.ts",
      "src/backend/routes/export/helpers/types.ts"
    ],
    "src/backend/routes/export/helpers/cache-keys.ts": [],
    "src/backend/routes/export/helpers/format.ts": [
      "src/backend/routes/export/helpers/types.ts"
    ],
    "src/backend/routes/export/helpers/errors.ts": [],
    "src/backend/routes/export/helpers/file-bytes.ts": [
      "src/backend/routes/export/helpers/types.ts"
    ],
    "src/backend/routes/export/helpers/request-id.ts": [],
    "src/backend/routes/export/helpers/types.ts": []
    ```
- [x] Update `dev-docs/backlog/TO_DO.md`, move this plan to `dev-docs/exec-plans/completed/`, and update the index.

## Risks and Mitigations

- **Hono sub-app composition**: If sub-routes retain prefixes, Hono maps duplicate sub-paths (e.g. `/export/jobs/jobs`). Mitigation: Use relative routes (`/`) inside sub-apps and register prefixes in the parent `index.ts` routing layer.
- **Cache key consistency**: Changing keys will break active in-flight jobs. Mitigation: Write explicit unit tests asserting that key composition generates exact byte-identical strings (e.g. `expect(buildSingleExportKey('abc', 'user-1')).toBe('export:abc:user-1')`).
- **Middleware inheritance**: `authMiddleware` must only be declared once at the parent `index.ts` level. Declare Hono sub-routers with explicit env type parameters `<{ Bindings: Env; Variables: Variables }>` to prevent casting in handlers.
- **Mock path stability**: Vitest's `vi.mock` resolves paths relative to the test file. Mocks inside `tests/export.test.ts` targeting `../services/export` and `../middleware/auth` must remain unchanged by design even as the imports in code are deepened.
- **Logging Violations**: The 9 pre-existing `console.info` statements violate Golden Principle #5. They are explicitly accepted as "out of scope" for this structural refactoring to prevent diff noise. The 16 `console.warn`/`console.error` calls are also out of scope.
- **Commit strategy**: While execution will follow sequential commits to keep tests passing at each step, the final payload will be merged as a single atomic PR.
- **Pre-existing test defects**: Unrelated test defects (such as the mismatched status assertion in `tests/export.test.ts:255-270`) must not be touched in this PR to keep diff reviews focused.

## Success Criteria

- No file under `routes/export/` exceeds 300 lines (with `jobs.ts` at ≤ 320 and `playlists.ts` at ≤ 350).
- `routes/export.ts` is exactly 1 line (re-export facade).
- All existing tests in `src/backend/tests/` pass cleanly without modifications to their assertions.
- 3 new test files (`cache-keys.test.ts`, `format.test.ts`, `errors.test.ts`) are added in `src/backend/tests/`, and all 38 test files pass cleanly.
- Redundant `resolveErrorStatus(...) as ContentfulStatusCode` casts are removed from handler files (9 sites). Inline numeric status casts are unchanged.
- No sub-app file (`jobs.ts`, `playlists.ts`, `playlist.ts`) imports or uses `authMiddleware`.
- `src/backend/tests/architecture.test.ts` is extended recursively, detects sibling/cross-family route import violations, and passes cleanly.
- `CHANGELOG.md`, `ARCHITECTURE.md`, `dev-docs/code-map.md`, `dev-docs/architecture/design-decisions/resumable-export-cursors.md`, and `dev-docs/dependency-graph.json` are updated.
- `npm run build`, `npm run lint`, and `npm run test:run` are 100% clean.
