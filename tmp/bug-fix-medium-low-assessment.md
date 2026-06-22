# Assessment of active/2026-06-21-bug-fix-medium-low.md

This assessment reviews the active execution plan for fixing medium and low issues: [2026-06-21-bug-fix-medium-low.md](file:///Users/kevingrizzard/MyCode/SpotiBye/docs/exec-plans/active/2026-06-21-bug-fix-medium-low.md).

---

## 🚨 Errors in the Plan

### 1. Missing Delegation Signature Update in FL-5 (`_build_backend_output_path`)
* **File to Modify:** [main_screen.py](file:///Users/kevingrizzard/MyCode/SpotiBye/src/frontend/screens/main_screen.py#L960-L964)
* **The Error:** The plan modifies the signature of `_build_backend_output_path` in [main_screen_export.py](file:///Users/kevingrizzard/MyCode/SpotiBye/src/frontend/screens/main_screen_export.py#L56) to drop the `playlist: dict` parameter. However, `main_screen.py` defines a delegation method with the old signature that forwards three arguments:
  ```python
  def _build_backend_output_path(self, playlist: dict, base_output_path: str, multiple: bool) -> str:
      return self.export_orchestrator._build_backend_output_path(playlist, base_output_path, multiple)
  ```
  If `main_screen.py` is not updated alongside the orchestrator, any invocation of this delegation will throw a `TypeError: _build_backend_output_path() takes 3 positional arguments but 4 were given`.
* **Correction:** Update `main_screen.py` to drop the `playlist` parameter from the signature and the delegation call.

### 2. Invalid Localhost Check in FL-2 (`is_valid_backend_url`)
* **File to Modify:** [backend_config.py](file:///Users/kevingrizzard/MyCode/SpotiBye/src/frontend/config/backend_config.py#L153-L155)
* **The Error:** The plan checks if `parsed.netloc` contains `.` or equals `localhost`. However, for a standard local development URL like `http://localhost:8787`, `parsed.netloc` evaluates to `"localhost:8787"`. This string does not contain a `.` and does not equal `"localhost"`, meaning valid localhost setups will be rejected.
* **Correction:** Check `parsed.hostname` (which correctly parses as `"localhost"` for `"localhost:8787"`) instead of `parsed.netloc`. Ensure to guard against `None` hostnames (e.g. `http:///path`):
  ```python
  parsed = urllib.parse.urlparse(url)
  return parsed.scheme in {"http", "https"} and parsed.hostname is not None and (
      "." in parsed.hostname or parsed.hostname == "localhost"
  )
  ```

### 3. Hallucinated Cookie Clearing in BM-8 (`safeParseSession`)
* **File to Modify:** [auth.ts (middleware)](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/middleware/auth.ts) and [auth.ts (routes)](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/auth.ts)
* **The Error:** The plan states that on session parse failure we should "clear the cookie (`Set-Cookie: session=; Max-Age=0`)". However, SpotiBye does not use HTTP cookies; it relies on JWT Bearer tokens in the `Authorization` header and a cache file on the client's filesystem. Setting `Set-Cookie` in the backend routes is dead/meaningless code.
* **Correction:** Remove any instructions regarding cookies from BM-8. Treating the session as missing via a 401 response is sufficient.

---

## 🔍 Gaps in the Plan

### 1. Broken Backend Test Assertions for `/health` Shape Change (BL-8 & FM-5)
* **Files to Update:**
  1. [integration.test.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/tests/integration.test.ts#L19-L21)
  2. [api-coverage.test.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/tests/api-coverage.test.ts#L213-L215)
  3. [workflows.test.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/tests/workflows.test.ts#L216-L218)
* **The Gap:** BL-8 changes the health check response format to return a nested `{ data: { status, service, timestamp } }` envelope. The plan updates the frontend client (FM-5), but does not mention updating the test files. All three test files check `data.status` and `data.service` directly on the root response and will fail under the new shape.
* **Resolution:** Update all three test files to assert properties on `data.data` instead of `data`.

### 2. Broken Backend Test Assertion for `/spotify/refresh` Shape Change (BL-9)
* **File to Update:** [auth.test.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/tests/auth.test.ts#L170)
* **The Gap:** BL-9 removes the duplicate `token` key from the refresh token response, keeping only `access_token`. The test suite in `auth.test.ts` explicitly asserts:
  ```ts
  expect(data.data).toHaveProperty('token', 'test-jwt-token');
  ```
  This assertion will fail when the key is removed.
* **Resolution:** Remove this expectation from `auth.test.ts`.

### 3. Broken Test Expectation for `_build_backend_output_path` Signature Change (FL-5)
* **File to Update:** [test_main_screen_export.py](file:///Users/kevingrizzard/MyCode/SpotiBye/src/frontend/tests/test_main_screen_export.py#L54-L56)
* **The Gap:** The plan drops the `playlist: dict` parameter from `_build_backend_output_path`. However, the unit test `test_build_backend_output_path_single` passes three arguments to it:
  ```python
  path = orchestrator._build_backend_output_path({"id": "1"}, "/tmp/file.xlsx", False)
  ```
  The test will crash with a `TypeError`.
* **Resolution:** Update `test_main_screen_export.py` to call `_build_backend_output_path("/tmp/file.xlsx", False)`.

### 4. Overwriting KV Progress with Stale Snapshots in Success/Retry States (BM-3)
* **File to Update:** [analysis-job.ts](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/services/analysis-job.ts#L81-L98)
* **The Gap:** BM-3 addresses stale snapshot overrides in the progress callback closure by fetching the latest status from KV. However, the final completion status write (`status: 'completed'`) and the catch-block retry write (`status: 'retrying'`) still use the stale `current` snapshot captured at the start of the job. This means any progress, `started_at`, and `updated_at` timestamps recorded during the job's run will be overwritten/erased by the final write.
* **Resolution:** Change both completion and retry writes to fetch the latest KV status and merge with it, just like the progress callback.

### 5. Violation of Golden Principle #7 in BM-10 Tests
* **File to Create:** `src/backend/tests/helpers/kv.ts`
* **The Gap:** BM-10 suggests copying/adapting the hand-rolled mock `kvNamespace` factory from `tests/analysis-queue.test.ts`. Copying this helper to the new test file `tests/auth-middleware.test.ts` violates Golden Principle #7 ("No Hand-Rolled Helpers - if the same logic appears in two places, extract it").
* **Resolution:** Extract `kvNamespace` and `envWithKv` into `src/backend/tests/helpers/kv.ts` and import them in the tests.

### 6. Settings and Authentication Loss in FL-9 Cache Clearing
* **File to Update:** [backend_cache.py](file:///Users/kevingrizzard/MyCode/SpotiBye/src/frontend/caching/backend_cache.py#L413)
* **The Gap:** FL-9 calls `screen.backend_adapter.cache_manager.clear_cache(None)`. When the pattern argument is `None`, `clear_cache` calls `self.cache_dir.glob("*.json")`, which matches all JSON files. This will delete the user's active session (`backend_token_{env_hash}.json`) and their configurations (`backend_selection.json`), resulting in an unexpected logout and configuration reset.
* **Resolution:** Update `clear_cache` so that when `pattern` is `None` it defaults to matching env-hash-prefixed data files (`f"{env_hash}_*.json"`). This safely clears playlist, track, analysis, and export data without affecting sessions or application settings.

---

## 💡 Suggested Improvements

### 1. Caught-Error Type Checking in BM-7
* **File to Update:** [auth.ts (routes)](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/routes/auth.ts#L139-L142)
* **Recommendation:** In TypeScript `catch (error)` blocks, the `error` variable is typed as `unknown`. Accessing `error.message` directly causes a compilation error. Make sure to check `error instanceof Error` before accessing `.message`, falling back to `String(error)` if it is not an `Error` instance.

### 2. Remove Boilerplate in FM-2
* **File to Update:** [backend_playlist_card.py](file:///Users/kevingrizzard/MyCode/SpotiBye/src/frontend/ui/backend_playlist_card.py#L523-L555)
* **Recommendation:** Since `_update_analysis_ui` will be decorated with `@mainthread`, we can clean up the callers in `_load_analysis_worker`. The boilerplate `Clock.schedule_once(lambda dt: self._update_analysis_ui(...), 0)` wrapping can be removed entirely, calling the method directly on the background thread.
