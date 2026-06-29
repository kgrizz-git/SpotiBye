# Fix CI TypeScript Compilation Errors

> **Linked from:** WIP branch CI failure (Run #62, ID: `28312071510`)
>
> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Mark steps complete (`- [x]`) as work is finished.

## TL;DR

- **Step 1 (z-validator.ts):** Use a structural type `{ issues: Array<{ path: Array<PropertyKey>; message: string }> }` for `formatZodMessage` and use `.map(String)` for symbol-safe path joining. Do NOT use `ZodError` from `'zod'` — see the v3→v4 split note below Step 1.
- **Step 2 (routes/spotify.ts):** Option A — replace the standalone `getPlaylistItemsHandler` with a `handleGetPlaylistItems` helper plus two inline route wrappers. Add `limit: number = 50, offset: number = 0` defaults to the helper for future-proofing.
- **Step 3 (validation/schemas/export.ts):** Option B (recommended) — add `cursor`, `chunk_size`, `job_id` as `z.any().optional()` to `ExportBatchChunkBodySchema`, with a per-schema comment explaining the Zod v4 passthrough behavior. **Also update the top-of-file block comment** at lines 3-9 so the "left permissive" claim is scoped to the schemas that actually remain pure passthrough.
- **Tests:** Add the 4 `formatZodMessage` path-formatting subtests to `src/backend/tests/validation.test.ts` (drop-in skeleton provided below).
- **Guardrails (already in working tree):** `.pre-commit-config.yaml` `node-typecheck` hook and `src/backend/vitest.config.ts` `typecheck.enabled: true` are already in place. Do not redo them.
- **Verify:** `./scripts/verify-all.sh`, `pre-commit validate-config`, then `cd src/backend && npm run test:run` (vitest now typechecks automatically).

## Goal

Resolve the 4 TypeScript compilation errors introduced by the Zod v4 upgrade on the Backend (TypeScript) job, ensuring that type-checking (`npx tsc --noEmit`), linting (`npm run lint`), and tests (`npm run test:run`) all pass successfully.

---

## Failure Description & Root Causes

CI run #62 failed during the `tsc --noEmit` build step with 4 compilation errors in 3 files.

### 1. `validation/z-validator.ts:39` — `ZodError` Type Incompatibility
```
validation/z-validator.ts(39,39): error TS2345: Argument of type 'ZodError<T>' is not assignable to parameter of type '{ issues: { path: (string | number)[]; message: string; }[]; }'.
```
* **Root Cause:** Zod v4 changed `ZodIssue.path` from `(string | number)[]` to `PropertyKey[]` (which includes `symbol`). The parameter type signature of the utility `formatZodMessage` in [z-validator.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/validation/z-validator.ts#L9) is too narrow and rejects Zod v4's `ZodError` or `PropertyKey[]` arrays.
* **Production Runtime Risk:** In JavaScript/TypeScript, converting a `symbol` to a string via implicit coercion or `.join('.')` throws a runtime `TypeError: Cannot convert a Symbol value to a string`. The current code at line 15 calls `.join('.')` directly on the path, which is a latent production runtime crash risk under Zod v4 if a symbol key is ever validated. The path formatting logic must safely convert symbol path elements to strings using `.map(String)`.

### 2. `routes/spotify.ts:138-139` — `'param'` and `'query'` Not Assignable to `never`
```
routes/spotify.ts(138,44): error TS2345: Argument of type '"param"' is not assignable to parameter of type 'never'.
routes/spotify.ts(139,43): error TS2345: Argument of type '"query"' is not assignable to parameter of type 'never'.
```
* **Root Cause:** Unlike inline route handlers where Hono propagates middleware-inferred validation targets, `getPlaylistItemsHandler` in [routes/spotify.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/spotify.ts#L134) is declared separately with the type annotation `c: Context<{ Bindings: Env; Variables: Variables }>`. Because this generic Context signature does not declare any validation targets, calling `c.req.valid('param')` and `c.req.valid('query')` inside it evaluates to `never`.

### 3. `routes/export/playlists.ts:139` — `body.cursor` is `unknown`
```
routes/export/playlists.ts(139,58): error TS18046: 'body.cursor' is of type 'unknown'.
```
* **Root Cause:** `ExportBatchChunkBodySchema` in [validation/schemas/export.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/validation/schemas/export.ts#L24) uses `.passthrough()` without explicitly declaring `cursor`, `chunk_size`, or `job_id`. Under Zod v4, any accessed property that is not defined in the schema but allowed by `.passthrough()` is inferred as `unknown` (whereas in Zod v3 it was `any`). Comparing `body.cursor >= 0` fails because relational operators are invalid on `unknown` types.
* **Contextual note:** The jobs `/:jobId/step` sub-route ([routes/export/jobs.ts:92](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/export/jobs.ts#L92)) bypasses Zod validation for the body entirely by using `await c.req.json().catch(() => ({}))`, which is why it does not encounter this compilation issue. The primary `POST /export/jobs` route ([routes/export/jobs.ts:44](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/export/jobs.ts#L44)) does use `zValidator('json', ExportJobBodySchema)` with `.passthrough()` and would have the same `unknown` type issue under Zod v4, but it simply does not access `body.cursor` / `body.chunk_size` / `body.job_id` directly, so the issue does not manifest. The chunk route uses `zValidator` *and* accesses those fields, which is what makes the new Zod v4 typing bite.

---

## Detailed Execution Steps

### Step 1 — Fix ZodError type signature in validation utility

Update `formatZodMessage` in [validation/z-validator.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/validation/z-validator.ts) to accept Zod v4's `PropertyKey[]` path, and map path elements using `String()` to prevent runtime TypeErrors if a symbol is present.

- [x] **Implement the structural-type fix (Recommended):** Use an inline structural type that matches the shape of what `@hono/zod-validator` actually returns. Verified locally — passes `tsc --noEmit` and `npm run lint`:
  ```typescript
  import { zValidator as baseZValidator } from '@hono/zod-validator';
  import type { ValidationTargets } from 'hono';
  import type { ZodSchema } from 'zod';

  function formatZodMessage(error: { issues: Array<{ path: Array<PropertyKey>; message: string }> }): string {
    if (error.issues.length === 0) {
      return 'Request validation failed';
    }
    return error.issues
      .map((issue) => {
        const path = issue.path.length > 0 ? issue.path.map(String).join('.') : 'request';
        return `${path}: ${issue.message}`;
      })
      .join('; ');
  }
  ```

> [!IMPORTANT]
> **Why not `import type { ZodError } from 'zod'`?** In Zod v3, `ZodError` was the public class that validators returned. In **Zod v4, the public `ZodError` is a separate interface that *extends* the internal base interface `$ZodError<T>`** (defined in `zod/v4/core/errors.d.ts`) with extra methods (`format`, `flatten`, `addIssue`, `addIssues`, `isEmpty`). `@hono/zod-validator` returns the *base* `$ZodError<T>`, not the extended `ZodError`. So `function formatZodMessage(error: ZodError)` fails `tsc` with `'$ZodError<unknown>' is missing the following properties from type 'ZodError<unknown>': format, flatten, addIssue, addIssues, isEmpty`. `$ZodError` is not re-exported from the main `'zod'` entry (only from `zod/v4/core`), so the structural-type fix is both correct and avoids a deep import path. The plan was originally written with a Zod v3 mental model on this point; the structural-type fix is what the CI verifier accepts.

### Step 2 — Fix Context validation targets in spotify routes

Resolve the `c.req.valid` type error in `getPlaylistItemsHandler` in [routes/spotify.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/spotify.ts).

- [x] Implement **Option A (Inline Handler wrappers + Helper function - Recommended/Type-Safe)**:

  The root cause is that `getPlaylistItemsHandler` is declared with the generic `c: Context<{ Bindings: Env; Variables: Variables }>` annotation, which erases Hono's middleware-inferred validation targets. The fix is to let the entry-point handler infer `c` (so `c.req.valid('param' | 'query')` resolves to the validated types) and move the shared body into a plain helper.

  - [x] **Define `handleGetPlaylistItems` helper** (new constant — paste this in place of the old handler):
  ```typescript
  const handleGetPlaylistItems = async (
    c: Context<{ Bindings: Env; Variables: Variables }>,
    playlistId: string,
    limit: number,
    offset: number
  ) => {
    try {
      const accessToken = c.get('access_token');
      const userId = c.get('user').id;

      const cacheService = new CacheService(c.env.CACHE_KV);
      const spotifyService = new SpotifyService(accessToken);

      // Scope to user: private/collaborative playlist items must not be served
      // from another user's warmed cache.
      const cacheKey = `user:${userId}:playlist:${playlistId}:tracks:${limit}:${offset}`;
      const cached = await cacheService.get(cacheKey);
      if (cached) {
        return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
      }

      const tracks = await spotifyService.getPlaylistTracks(playlistId, limit, offset);

      // Cache for 5 minutes
      await cacheService.set(cacheKey, tracks, 300);

      return c.json({ data: tracks, meta: { timestamp: new Date().toISOString() } });
    } catch (error) {
      console.error('Failed to get playlist tracks:', error);
      return c.json({ error: { code: 'PLAYLIST_TRACKS_FETCH_FAILED', message: 'Failed to fetch playlist tracks' } }, { status: 500 as ContentfulStatusCode });
    }
  };
  ```

  - [x] **Delete the old `getPlaylistItemsHandler` constant** (lines 134-164 of [routes/spotify.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/spotify.ts)) — otherwise the file ends up with both the old handler and the new helper, leaving dead code.

  - [x] **Replace the route registrations at lines 167-180** of [routes/spotify.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/spotify.ts) with inline handlers that extract validated parameters (leveraging correct, automatic type inference) and invoke the helper. To make the wrapper resilient to a future `PaginationQuerySchema` refactor that drops the `.default(...)` (which would change `c.req.valid('query')` to `{ limit?: number; offset?: number }` and break the strict `number` parameters on the helper), also update the helper signature to give `limit` and `offset` defaults that mirror the schema's defaults:
  ```typescript
  const handleGetPlaylistItems = async (
    c: Context<{ Bindings: Env; Variables: Variables }>,
    playlistId: string,
    limit: number = 50,
    offset: number = 0
  ) => { /* ...unchanged body... */ };

  // GET /spotify/playlists/:id/items - Get playlist items (February 2026 API naming)
  app.get(
    '/playlists/:id/items',
    zValidator('param', IdParamSchema),
    zValidator('query', PaginationQuerySchema),
    async (c) => {
      const { id } = c.req.valid('param');
      const { limit, offset } = c.req.valid('query');
      return handleGetPlaylistItems(c, id, limit, offset);
    }
  );

  // GET /spotify/playlists/:id/tracks - Backward-compatible alias
  app.get(
    '/playlists/:id/tracks',
    zValidator('param', IdParamSchema),
    zValidator('query', PaginationQuerySchema),
    async (c) => {
      const { id } = c.req.valid('param');
      const { limit, offset } = c.req.valid('query');
      return handleGetPlaylistItems(c, id, limit, offset);
    }
  );
  ```
  Defaults here are belt-and-suspenders — today `PaginationQuerySchema` uses `.optional().default(50/0)`, so the wrapper always passes numbers. The defaults are only consumed if a future schema change makes the fields truly optional.

- [ ] Alternatively, implement **Option B (Cast context target parameters - NOT RECOMMENDED)**:
  Keep `getPlaylistItemsHandler` structure as-is, but cast validation calls to bypass the `never` target type check:
  ```typescript
  const { id: playlistId } = c.req.valid('param' as never) as { id: string };
  const { limit, offset } = c.req.valid('query' as never) as { limit?: number; offset?: number };
  ```
  > [!WARNING]
  > Option B completely bypasses type safety at this boundary, making it harder to catch type mismatch regressions at compile time. Option A is preferred.

### Step 3 — Fix `body` unknown type in batch chunk exports

Resolve the `unknown` type issue for `body.cursor`, `body.chunk_size`, and `body.job_id` in [routes/export/playlists.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/export/playlists.ts).

- [x] Choose and implement one of the following approaches (mark exactly one):

  > [!IMPORTANT]
  > The repo's `.eslintrc.json` sets `@typescript-eslint/no-explicit-any: "error"`. Do NOT cast with `as any` or `as Record<string, any>` — both fail the linter and will be rejected by `npm run lint`. If you go the cast route, use `as Record<string, unknown>` and narrow at each call site (see Option A below); the cleanest path is Option B, which keeps the route handler unchanged.

  - [ ] **Option A (Cast body - Minimal Change):** Keep the schema as-is to preserve exact downstream normalization, and cast the validated body in the route handler to a `Record<string, unknown>`. Narrow each property with `typeof` / `Number.isInteger` at the call site so the body itself stays lint-clean.

    Do NOT replace the inline chunk size calculation logic with the helper `resolveStepSize(body)`, because `resolveStepSize` checks `max_playlists_per_step` first (intended for the jobs route) which could conflict with the chunk route's `chunk_size` logic. Keep the inline chunk size logic intact:
    ```typescript
    const body = c.req.valid('json') as Record<string, unknown>;
    // ...then at use sites:
    const providedJobId = typeof body.job_id === 'string' && body.job_id.trim().length > 0
      ? body.job_id.trim()
      : '';
    const startCursor = Number.isInteger(body.cursor) && (body.cursor as number) >= 0
      ? Number(body.cursor)
      : 0;
    const requestedChunkSize = Number.isInteger(body.chunk_size) ? Number(body.chunk_size) : 1;
    ```

  - [x] **Option B (Add permissive fields to Zod Schema - Recommended):** Add optional `cursor`, `chunk_size`, and `job_id` properties to `ExportBatchChunkBodySchema` inside [validation/schemas/export.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/validation/schemas/export.ts) using `z.any().optional()` to keep them permissive. The route handler continues to use the same `body.cursor` / `body.chunk_size` / `body.job_id` accesses unchanged, and the linter stays clean because `z.any()` is a Zod call, not an explicit TypeScript `any` annotation. Add a short comment above the schema documenting the Zod v4 behavior so the next reader doesn't try to "clean up" the explicit fields:
    ```typescript
    // Explicitly declare passthrough fields accessed directly in handlers as z.any().optional().
    // In Zod v4, `.passthrough()` types extra fields as `unknown` (rather than `any`), which
    // prevents direct property access/comparison without explicit schema declaration.
    export const ExportBatchChunkBodySchema = z
      .object({
        playlist_ids: PlaylistIdsSchema,
        cursor: z.any().optional(),
        chunk_size: z.any().optional(),
        job_id: z.any().optional(),
      })
      .passthrough();
    ```

    - [x] **Update the top-of-file block comment** in [validation/schemas/export.ts:3-9](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/validation/schemas/export.ts#L3) so the "Other fields (`format`, `include_audio_features`, `chunk_size`, etc.) are left permissive" claim no longer overstates things. Once `ExportBatchChunkBodySchema` explicitly declares `cursor`/`chunk_size`/`job_id`, the blanket "left permissive" wording is no longer accurate for that one schema. Either scope the comment to `ExportJobBodySchema` and `ExportBatchBodySchema` (the two that remain pure passthrough), or amend it to call out `ExportBatchChunkBodySchema` as the exception. Example edit:
    ```typescript
    /**
     * Body schemas intentionally enforce ONLY the rules the routes enforced before
     * Zod was introduced — i.e. `playlist_ids` must be a non-empty array of
     * non-empty strings. For `ExportJobBodySchema` and `ExportBatchBodySchema`,
     * other fields (`format`, `include_audio_features`, etc.) are left permissive
     * and normalized downstream (`resolveRequestedFormat`, `resolveStepSize`,
     * clamping) exactly as before. `ExportBatchChunkBodySchema` is the exception:
     * it explicitly declares `cursor` / `chunk_size` / `job_id` as `z.any().optional()`
     * because the chunk route reads them directly (see the per-schema comment).
     */
    ```

    Verified locally: this passes both `npx tsc --noEmit` and `npm run lint`, and the existing `tests/export.test.ts` chunk test (which sends `cursor: 0, chunk_size: 1`) still passes because `z.any()` accepts any value.

---

## Verification Checklist

Run these commands to verify all fixes:

- [x] Run the full backend verification script from the repo root: `./scripts/verify-all.sh` (runs `tsc --noEmit` and `npm run lint`; silent on success, errors on failure)
- [x] Pre-commit config is structurally valid: `pre-commit validate-config` (catches malformed `.pre-commit-config.yaml` — useful since this PR adds a new pre-push hook)
- [x] Type check passes: `cd src/backend && npx tsc --noEmit` (must exit 0)
- [x] Linter passes: `cd src/backend && npm run lint` (must exit 0)
- [x] Tests pass: `cd src/backend && npm run test:run` (all tests must pass)
- [x] Integration validation test: Run the existing tests in `src/backend/tests/validation.test.ts` to confirm that the custom error envelope is returned on schema failure and that no regression occurs.
- [x] **Add `formatZodMessage` path-formatting regression tests** in `src/backend/tests/validation.test.ts`. This is the only safety net for the Step 1 fix: it locks the contract (dot-joined paths, array indices, empty-path fallback, multiple-issue joining) so a future Zod upgrade or refactor that drops the `.map(String)` will fail loudly. Add a new `describe('formatZodMessage path formatting', ...)` block with the following four subtests, each going through the public `zValidator` API (no need to export the helper):
  - [x] **Nested object path is dot-joined.** Post `{}` against `z.object({ user: z.object({ name: z.string().min(1) }) })` and assert the error message contains `user.name:` (guards the `path.map(String).join('.')` line).
  - [x] **Array indices appear in the path.** Post `{ items: ['ok', ''] }` against `z.object({ items: z.array(z.string().min(1)) })` and assert the error message contains `items.1:` (guards that numeric path elements are stringified, not rendered as `[object]`).
  - [x] **Empty path falls back to `request:`.** Post `123` (a number) against `z.string().min(1)` and assert the error message starts with `request:` (guards the `issue.path.length > 0 ? ... : 'request'` branch — this is the only way the empty-path branch is reached through the public API).
  - [x] **Multiple issues are joined with `; `.** Post `{}` against `z.object({ a: z.string().min(1), b: z.string().min(1) })` and assert the error message matches `/a:.*; .*b:/` (guards that all issues surface in one message, not just the first).

  Example skeleton (drop into the existing file alongside the current `describe('zValidator error envelope', ...)`):

  ```typescript
  describe('formatZodMessage path formatting', () => {
    it('joins nested object paths with dots', async () => {
      const app = new Hono();
      app.post(
        '/test',
        zValidator('json', z.object({ user: z.object({ name: z.string().min(1) }) })),
        (c) => c.json({ ok: true }),
      );
      const response = await app.request('http://localhost/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: {} }),
      });
      expect(response.status).toBe(400);
      const body = (await response.json()) as { error: { message: string } };
      expect(body.error.message).toContain('user.name:');
    });

    it('renders array indices in the path', async () => {
      const app = new Hono();
      app.post(
        '/test',
        zValidator('json', z.object({ items: z.array(z.string().min(1)) })),
        (c) => c.json({ ok: true }),
      );
      const response = await app.request('http://localhost/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: ['ok', ''] }),
      });
      expect(response.status).toBe(400);
      const body = (await response.json()) as { error: { message: string } };
      expect(body.error.message).toContain('items.1:');
    });

    it('falls back to "request" for empty path (root-level failure)', async () => {
      const app = new Hono();
      app.post('/test', zValidator('json', z.string().min(1)), (c) => c.json({ ok: true }));
      const response = await app.request('http://localhost/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(123),
      });
      expect(response.status).toBe(400);
      const body = (await response.json()) as { error: { message: string } };
      expect(body.error.message).toMatch(/^request:/);
    });

    it('joins multiple issues with semicolons', async () => {
      const app = new Hono();
      app.post(
        '/test',
        zValidator('json', z.object({ a: z.string().min(1), b: z.string().min(1) })),
        (c) => c.json({ ok: true }),
      );
      const response = await app.request('http://localhost/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      expect(response.status).toBe(400);
      const body = (await response.json()) as { error: { message: string } };
      expect(body.error.message).toMatch(/a:.*; .*b:/);
    });
  });
  ```

## Pre-Merge Housekeeping

- [x] Update `dev-docs/exec-plans/active/README.md` to add a row for this plan (the table currently says "No active execution plans"). (Done as part of plan completion: row added in `active/README.md` before move, then this plan is moved to `completed/`.)
- [x] Confirm `CHANGELOG.md` does not need an entry: this is a CI-only fix that does not change shipped behavior, runtime contracts, or user-facing error messages, so per AGENTS.md it likely falls under the "internal-only" exception. Add a "Fixed" entry only if the team prefers to log CI fixes for traceability. **Decision: skip the CHANGELOG entry** — runtime contract unchanged, no shipped artifact impact.

## Why CI Caught It But Pre-Commit/Pre-Push Did Not (Context for the Fix)

The 4 TypeScript errors were not caught locally because **no pre-commit or pre-push hook runs `npx tsc --noEmit` on the backend**:

- **CI** (`.github/workflows/ci.yml:31-38`) runs `npm run lint` → `npx tsc --noEmit` → `npm run test:run` (the failing step is `tsc`).
- **Pre-push** (`.pre-commit-config.yaml:131-138`) only runs `cd src/backend && npm run test:run`. Vitest with the default `src/backend/vitest.config.ts` (no `typecheck.enabled`) transpiles via esbuild/swc, which **strips types without checking them** — so `body.cursor >= 0` on an `unknown` looks fine to vitest but fails `tsc`.
- **ESLint** is configured with only `no-unused-vars` / `no-explicit-any` / etc. (`src/backend/.eslintrc.json:17-39`); none of the `@typescript-eslint/no-unsafe-*` family is enabled, so a type-level mismatch like `argument of type '"param"' is not assignable to parameter of type 'never'` is invisible to ESLint.
- **basedpyright** (pre-push) only covers `src/frontend src/shared` per `AGENTS.md` and `.pre-commit-config.yaml:196` — backend TypeScript is out of scope.

To prevent this class of regression, two local guardrails have been added in the working tree as part of this CI fix work (verified locally with the unfixed code — both reproduce the 4 CI errors and exit non-zero):

- [x] **Pre-push hook** `.pre-commit-config.yaml` — new `node-typecheck` step runs `cd src/backend && npx tsc --noEmit` before push, mirroring the CI `Backend (TypeScript)` job.
- [x] **Vitest typecheck** `src/backend/vitest.config.ts` — `test.typecheck.enabled: true` (checker `tsc`, `include: ['tests/**/*.test.ts']`). With this on, `npm run test:run` automatically runs typecheck and exits 1 on source-file type errors, so the existing `node-tests` pre-push hook also catches this class of failure.

After this, any future change that breaks `tsc --noEmit` will be blocked at `git push` time, not on the CI dashboard.
