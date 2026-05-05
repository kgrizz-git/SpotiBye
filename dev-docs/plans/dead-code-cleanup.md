# Dead Code & Orphan File Cleanup

> Assessment of files and directories that are no longer used and can be removed.
> Derived from [dependency-graph.json](../dependency-graph.json) and [code-map.md](../code-map.md) plus a full filesystem scan against the import graph.
> Date: 2026-05.

---

## Summary

| Group | Files / Dirs | Action |
|-------|-------------|--------|
| 1 — Delete immediately | 6 files | No dependencies, no risk |
| 2 — Delete after one small prerequisite | 2 targets | Require a single prep step first |
| 3 — Investigate before deleting | 3 targets | Unclear purpose or cross-team dependencies |
| 4 — Keep | 4 targets | Still needed; listed to close the loop |

---

## Group 1 — Delete Immediately - DONE

These files have no imports, no references in any tooling config, and no value at rest.

### `backups/main.py`

A standalone entrypoint (`python run_frontend_backend.py`) that predates the current `run_frontend_backend.py`. Confirmed duplicate by diffing the call site — both call `SpotifyExporterApp().run()`. Nothing imports it.

**Delete:** `backups/main.py`

---

### `backups/test_gridlayout.py`

A throwaway Kivy layout exploration script written to debug `GridLayout` column behavior. It imports `kivy.app`, `kivy.uix.*` directly and has no test assertions — it's a visual debugging aid, not a test. Not collected by pytest (`test_` prefix is present but the file imports Kivy at module level, which fails in CI).

**Delete:** `backups/test_gridlayout.py`

> After both files are removed, `backups/` will be empty and the directory can be removed too.

---

### `src/backend/manual-trigger.txt`, `retry-deploy.txt`, `trigger-deploy.txt`, `trigger-workflow.txt`

Four plain-text files in `src/backend/` with single-line messages like _"Manual trigger for deployment workflow"_. These were committed as dummy file changes to force GitHub Actions workflow runs. They have no runtime or tooling role and will mislead future contributors into thinking they are config.

**Delete:**
- `src/backend/manual-trigger.txt`
- `src/backend/retry-deploy.txt`
- `src/backend/trigger-deploy.txt`
- `src/backend/trigger-workflow.txt`

---

### `src/spotibye.egg-info/`

A build artifact produced by `pip install -e .`. It is already covered by the `.gitignore` rule `*.egg-info/` (line 9), which means it was either committed before the rule was added or the rule was added without a `git rm --cached` pass. It contains auto-generated metadata (`PKG-INFO`, `SOURCES.txt`, `requires.txt`, etc.) that pip regenerates on demand.

**Delete from git tracking:**
```bash
git rm -r --cached src/spotibye.egg-info/
```
No `.gitignore` change needed — the rule already exists.

---

## Group 2 — Delete After One Small Prerequisite - DONE

### `src/backend/services/reccobeats.ts`

This file is a confirmed dead-code stub. Its `ReccoBeatsService.getTrackFeatures()` method throws `Error('Reccobeats API not implemented in test environment')` in any non-test environment and is never imported by any route. The live ReccoBeats calls go through `services/analysis.ts` directly.

**The one prerequisite:** `src/backend/tests/analysis.test.ts` line 7 contains:

```ts
vi.mock('../services/reccobeats', () => ({
  ReccoBeatsService: vi.fn().mockImplementation(() => ({ ... }))
}))
```

This mock was set up to isolate the stub, but since the router never calls `ReccoBeatsService`, the mock has no effect on test outcomes — it's guarding against code that doesn't run. The mock can be safely deleted along with the file.

**Steps:**
1. Remove the `vi.mock('../services/reccobeats', ...)` block from `src/backend/tests/analysis.test.ts`
2. Run `npm run test:run` to confirm tests still pass
3. Delete `src/backend/services/reccobeats.ts`

See also: [backend-analysis-routes.md](../backend-analysis-routes.md#4-reccobeatsservice-stub-in-reccobeats-ts-is-dead-code-in-production)

---

### `backend-backup/`

An entire Python FastAPI backend that predates the current Cloudflare Worker backend. Structure:

```
backend-backup/
├── .env                    ← contains real or near-real credentials — verify before deleting
├── .env.example
├── API_USAGE_EXAMPLES.md
├── AUTHENTICATION_FLOW.md
├── Dockerfile
├── README.md
├── pyproject.toml
├── requirements.txt
├── src/spotibye_backend/   ← full Python app: api/, auth/, caching/, services/
└── tests/                  ← 4 test files with conftest.py
```

The `spotibye_backend` Python package is a Flask/FastAPI server that was replaced by the Cloudflare Worker (`src/backend/`). Nothing in `src/` imports from it. No tooling references it (not in `.pre-commit-config.yaml`, `pyproject.toml`, or any CI config).

**The one prerequisite:** Check `backend-backup/.env` for real secrets before deleting. If it contains live Spotify client secrets or API keys, rotate them first, then delete.

```bash
cat backend-backup/.env   # inspect for real values
```

**Delete:** `backend-backup/` (entire directory)

---

## Group 3 — Investigate Before Deleting - DONE

### `src/frontend/tests/run_tests.py` — FIXED

**Original finding:** pytest collected **0 tests** from the 6 files `run_tests.py` orchestrates because every test class had an `__init__` constructor (causes `PytestCollectionWarning` / silent skip).

**Fix applied (2026-05):** Refactored all 6 test classes to use pytest fixtures instead of the custom `BackendTestFramework` runner:
- Removed `__init__` from all 6 classes (`TestAuthenticationFlow`, `TestUIFunctionality`, `TestPerformance`, `TestCachePerformance`, `TestUIResponsiveness`, `TestConfiguration`)
- Created `conftest.py` with a session-scoped `mock_backend_server` fixture (uses `port=0` for OS-assigned port)
- Added `@pytest.fixture(autouse=True)` setup in each class to inject the server and initialize client objects
- Converted `return False` / `self.framework.end_test()` patterns to `assert` / `pytest.fail()` so test failures propagate correctly
- Updated `mock_backend.py` to capture actual bound port (`self.port = self.server.server_address[1]`) enabling `port=0`
- Rewrote `run_tests.py` as a thin subprocess wrapper around `pytest` (backward compat CLI preserved)
- Fixed a latent test bug: `test_backend_client_configuration` was asserting against `CURRENT_BACKEND_URL` but `BackendClient` hardcodes `http://localhost:8787` as default

**Result:** `pytest src/frontend/tests` now collects and runs **53 tests** (was 0). 52 pass, 1 skipped (psutil not installed).

---

### `.cursor/rules/` and `.windsurf/rules/` — KEEP

Decision made: keep both AI IDE rule sets. They are harmless, read-only config consumed by Cursor/Windsurf and do not affect builds or tests.

---

### `src/backend/docs/` — KEEP (not duplicates)

**Finding:** Diffed all three overlapping files against their root `docs/` counterparts — all are substantively different:

| Backend doc | Root counterpart | Verdict |
|-------------|-----------------|---------|
| `authentication-flow.md` (635 lines) | `docs/authentication-flow.md` | Different audience — backend doc is a frontend *developer integration guide*; root doc explains the flow to end users |
| `troubleshooting-guide.md` (536 lines) | `docs/troubleshooting-network.md` | Backend doc covers Worker-side diagnosis (KV, cold starts, CPU limits); root doc covers user-facing network errors |
| `deployment-configuration.md` (305 lines) | `docs/cloudflare-deployment.md` | Backend doc covers multi-environment config, secrets, wrangler flags; root doc covers the automated deploy pipeline |

All 10 files in `src/backend/docs/` (5040 lines total) are unique developer-facing content — env var references, KV key schema, monitoring/logging setup, the OpenAPI spec, and Swagger UI. None duplicate root `docs/`.

**Decision: Keep all of `src/backend/docs/`.** The location inside the TypeScript source tree is intentional — these docs are for contributors working on the backend, not for users.

---

## Group 4 — Keep (Listed to Close the Loop)

These were scanned and confirmed intentional.

| Path | Why it stays |
|------|-------------|
| `packaging/linux/` | Linux `.desktop` entry and install script — needed for Linux distribution |
| `spotibye.spec` | PyInstaller build spec — needed to produce the distributable macOS/Windows app |
| `resources/` | App icons (`.icns`, `.ico`, `.png`) — referenced by `spotibye.spec` |
| `src/backend/docs/openapi.yaml` | API contract — keep at minimum; move to root `docs/` in a future pass |

---

## Cleanup Order

If executing this plan, use this order to avoid introducing test failures mid-cleanup:

1. **Group 1 — safe deletes first:** Remove the 6 files, `git rm --cached src/spotibye.egg-info/`, confirm CI still green.
2. **Group 2a — reccobeats.ts:** Remove the `vi.mock` block from `analysis.test.ts`, confirm backend tests pass, then delete `src/backend/services/reccobeats.ts`.
3. **Group 2b — backend-backup:** Inspect `.env`, rotate any live keys, then delete the directory.
4. **Group 3 — investigation items:** Assign each as a follow-up task once the safe deletes are done.

---

## Estimated Impact

| Metric | Before | After (Groups 1+2) |
|--------|--------|--------------------|
| Tracked files removed | — | ~50+ (mostly backend-backup) |
| Active source files removed | 1 | `services/reccobeats.ts` |
| Build artifacts removed from git | `src/spotibye.egg-info/` | — |
| CI noise reduced | 4 trigger txt files | — |
