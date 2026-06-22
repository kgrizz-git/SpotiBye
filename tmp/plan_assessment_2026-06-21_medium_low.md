# Medium/Low Bug Fix Plan — Assessment

**Plan:** `docs/exec-plans/active/2026-06-21-bug-fix-medium-low.md`
**Date:** 2026-06-21
**Scope:** 36 findings (21 backend, 15 frontend)

---

## Errors

### E-1: BL-5 and BM-3 are in different commits but touch the same file

**Severity:** High — likely merge conflict

BM-3 (commit 1) modifies `services/analysis-job.ts` (progress callback closure).
BL-5 (commit 2) also modifies `services/analysis-job.ts` (KV wait increase from 15s to 30s).

The execution grouping table places these in separate commits. If commit 1 lands first, commit 2 will need to rebase over it. The plan should either group both changes into the same commit or add a note about the expected rebase.

### E-2: BM-7 line number references are inconsistent

The plan header says "OAuth callback catch block, currently ~line 139-142" but the body text references `auth.ts:117-120` in the description. The bug review source says `BE-ERR-2` is at `auth.ts:117-120`. The post-critical-high shift is acknowledged on line 7, but the two line references within BM-7 itself should be reconciled.

---

## Gaps

### G-1: FL-5 — "inline the `multiple=True` branch" is a behavior change, not dead-code removal

The plan says to "delete the function entirely and inline the `multiple=True` branch at the two call sites." However, the callers currently pass `multiple=False`, meaning the function returns `base_output_path` unchanged. Inlining the `multiple=True` branch (which builds a new path with `os.path.join(...)`) would **change the output path behavior** for those callers.

The plan should clarify: should the callers instead be updated to use the path-building logic from the `multiple=True` branch? Or should the function be replaced with just the identity behavior (removing the `multiple` parameter entirely)? The current description is ambiguous about whether this is a pure cleanup or a behavior change.

### G-2: FL-1 — proposed fix is unclear and potentially wrong

The plan suggests:
> `self.cache_manager.clear_cache(str(self.cache_manager._cache_file_path("playlists.json").name))`

This is confusing. `_cache_file_path` returns a `Path` object. Calling `.name` on it returns just the filename (e.g., `"playlists.json"`), which defeats the purpose — you'd be clearing unhashed files that don't exist. The actual fix should either:
- Add a `clear_file(filename)` method that internally uses `_cache_file_path` and calls `unlink()` on the resolved path (as the plan also suggests as "better")
- Or change `clear_cache` to accept a filename and internally apply the hash prefix

The "better" suggestion (new `clear_file` method) is the right approach but the first suggestion in the same sentence is misleading.

### G-3: FL-9 — `screen.cache_manager` attribute not verified

The plan says to call `screen.cache_manager.clear_cache(None)` but the `screen` parameter is a `MainScreen` instance. The plan correctly notes "confirm it has a `.cache_manager` or proxy through `screen.backend_adapter.cache_manager`" but does not actually verify which is correct.

Looking at the adapter code (`backend_main_screen_adapter.py`), the adapter has `cache_manager`, but the `screen` is the `MainScreen`, not the adapter. The plan needs to confirm whether `MainScreen` has a `cache_manager` attribute directly or whether it needs to go through `screen.backend_adapter.cache_manager`.

### G-4: BM-5 coordination with refactor-export-ts is one-way

The medium-low plan correctly says "defer BM-5 until after `2026-06-21-refactor-export-ts.md` completes." However, the refactor-export-ts plan does **not** list BM-5 as a post-refactor dependency or reminder. If someone executes the refactor plan without cross-referencing the medium-low plan, BM-5's `any` removal in `routes/export.ts` will be missed.

The refactor plan should include a note like "After this refactor, apply BM-5 type guards to the new module boundaries in `routes/export.ts`."

### G-5: BL-10 ordering — refactor plan doesn't list it as pre-requirement

The medium-low plan says "Do this in the monolithic file BEFORE the refactor-export-ts plan lands" and the coordination notes say "The refactor moves `generatePlaylistExportSlice` to `export-collect.ts` and the fix is easier to verify in the original." However, the refactor-export-ts plan does not list BL-10 as a pre-condition or note it anywhere.

If the refactor runs first, BL-10's fix location changes (the guard moves to `export-collect.ts`). The refactor plan should note this as a pre-requirement.

### G-6: BM-8 — scope expansion beyond original bug finding

The original bug (BE-ERR-3) is about unprotected `JSON.parse`. The plan correctly adds try/catch but also adds:
- Shape validation (`typeof parsed === 'object'`, `parsed !== null`, required fields)
- A shared helper `safeParseSession`
- Cookie clearing on failure

These are all good additions but represent scope expansion. The plan should note that this goes beyond the original finding, as it affects the implementation complexity and test coverage requirements.

### G-7: FM-6 — RuntimeError could break existing deployments

The plan says to change from silent no-op to `raise RuntimeError("App is missing logout method — credentials remain in memory")`. While this is the right direction, it's a breaking change for any deployment where the running app doesn't have a `logout` method. The plan acknowledges the `app is None` branch is "defensive only" but doesn't assess whether there are legitimate cases where `hasattr(app, "logout")` is `False`.

A safer approach would be to log a warning and show a user-visible popup instead of raising an exception that could crash the logout flow.

### G-8: BM-10 test — `Promise.all` timing is not deterministic in Workers

The plan says to test concurrent refreshes with `Promise.all([mw(req1), mw(req2)])` and assert `fetch` was called exactly once. In Cloudflare Workers (single-threaded event loop), `Promise.all` schedules both microtasks, but the actual ordering depends on event loop timing. The test should use `vi.advanceTimersByTime` or similar if using `vi.useFakeTimers()`, or the test should explicitly await both and check the fetch mock call count after both resolve.

The plan should clarify the test harness setup (real timers vs fake timers) to ensure the deduplication logic is actually exercised.

### G-9: Missing coordination with critical-high plan on FT-5 dependency

The medium-low plan correctly notes "FL-1 and FL-9 explicitly rely on the `_cache_file_path` helper introduced by FT-5" and says "finish FT-5 first." However, the critical-high plan's FT-5 section doesn't mention this downstream dependency. If the critical-high plan is not completed before the medium-low plan starts, FL-1 and FL-9 cannot proceed.

Both plans should cross-reference each other on this dependency.

### G-10: BM-3 test — `createTestEnv` helper not yet created

The plan says "Use the `createTestEnv` helper from `src/backend/tests/helpers/env.ts`" but the critical-high plan's pre-flight checklist shows that `tests/helpers/env.ts` with `createTestEnv` is a pre-flight task that must be completed **before** any bug-fix work starts. If the pre-flight hasn't been done, BM-3's test setup will fail.

The medium-low plan should note that BM-3's test depends on the critical-high pre-flight being complete.

---

## Minor Observations (not errors, but worth noting)

### O-1: BM-2 uses `console.warn` for dropped items

Golden Principle #5 says "No `console.log` in non-test backend code — use structured logging." The plan interprets this as permitting `console.warn` in catch blocks. This is consistent with the established pattern (e.g., `middleware/auth.ts:52` uses `console.error`), but worth noting that if a structured logger is introduced later, these calls will need migration.

### O-2: BL-8 backward-compat shape is awkward

The plan proposes `{ data: { status, service, timestamp }, status: 'healthy' }` for backward compatibility. The outer `status: 'healthy'` is redundant since `data.status` already provides the same value. A cleaner approach would be to return `{ data: { status, service, timestamp } }` and update all frontend consumers in the same pass (which the plan does via FM-5 coordination). The backward-compat shim adds complexity for minimal benefit.

### O-3: Execution groupings are mostly sound but commit 2 is heavy

Commit 2 ("tighten service validation and types") includes 13 items across 7 files. This is the heaviest commit and may benefit from being split further (e.g., type safety items vs. dead-code removal). Not an error, but a practical risk for review and rollback.

### O-4: CHANGELOG grouping is reasonable

The suggested CHANGELOG groups (line 318-326) are well-organized and scannable. The grouping by functional area (auth, type safety, service hardening, etc.) is better than a flat list of 36 items.

---

## Summary

| Category | Count |
|----------|-------|
| Errors (will cause problems if unaddressed) | 2 |
| Gaps (missing info, unverified assumptions) | 8 |
| Observations (minor, informational) | 4 |

**Verdict:** The plan is thorough and well-researched overall. The two errors (E-1, E-2) are fixable. The eight gaps are mostly about missing cross-references, unverified assumptions, and ambiguous instructions. None are showstoppers, but several should be resolved before execution to avoid rework or merge conflicts.

**Top 3 priorities before execution:**
1. **E-1:** Move BL-5 to commit 1 (same file as BM-3) or add rebase note
2. **G-1:** Clarify FL-5 — is this dead-code removal or a behavior change?
3. **G-3/G-9:** Verify `screen.cache_manager` path and ensure FT-5 dependency is bidirectional
