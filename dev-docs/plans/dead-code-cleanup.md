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

## Group 1 — Delete Immediately

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

## Group 2 — Delete After One Small Prerequisite

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

## Group 3 — Investigate Before Deleting

### `src/frontend/tests/run_tests.py`

A custom test runner that predates pytest adoption. It instantiates test classes directly (`TestAuthenticationFlow(framework).run_all_tests()`) and manages a `MockBackendServer` lifecycle manually. It is **not** collected by pytest (no `test_` class/function pattern at the top level). However:

- `tests/__init__.py` re-exports `MockBackendServer` from `mock_backend.py`
- `test_framework.py` imports and uses `MockBackendServer`
- `run_tests.py` is the only file that calls `framework.setup_mock_backend()` / `teardown_mock_backend()` end-to-end

**The question:** Are the integration tests in `test_auth.py`, `test_ui.py`, `test_performance.py`, `test_cache.py`, `test_ui_responsiveness.py`, `test_configuration.py` written to work with *both* the custom runner and pytest, or only the custom runner?

If they contain standard `unittest.TestCase` or `def test_*` methods, pytest collects them directly and `run_tests.py` is redundant. If they rely on the `BackendTestFramework` class being pre-configured by `run_tests.py`, they may only run correctly through it.

**Recommended check:**
```bash
python -m pytest src/frontend/tests/test_auth.py -v
```
If all tests pass, `run_tests.py` is safe to delete. If they error on missing framework state, keep `run_tests.py` and document the two-runner situation.

---

### `.cursor/rules/` and `.windsurf/rules/`

Twenty-two CodeGuard security rule files exist in both `.cursor/rules/` (`.mdc` format) and `.windsurf/rules/` (`.md` format). These are AI IDE security guidance files — they are consumed by Cursor and Windsurf respectively, not by any build tooling.

**`.cursor/rules/`** — 22 files covering: authentication/MFA, client-side security, input validation, file handling, session management, DevOps/CI-CD, cloud/Kubernetes, hardcoded credentials, data storage, API security, XML/serialization, supply chain, privacy, access control, frameworks, digital certificates, mobile apps, crypto, additional cryptography, logging, IaC security.

**`.windsurf/rules/`** — identical set in `.md` format.

These files are harmless but they add noise to the tree and may confuse agents into thinking they are project-specific constraints rather than generic IDE plug-in configs.

**Options:**
- If the team uses Claude Code exclusively: delete both directories.
- If Cursor or Windsurf are used by any team member: keep the relevant one.
- If unsure: keep both; they are read-only config and do not affect builds or tests.

There is also a `.vscode/settings.json` — that is active and should stay.

---

### `src/backend/docs/`

A second documentation tree embedded inside the backend source tree. Contents:

| File | Notes |
|------|-------|
| `README.md` | Backend-specific readme |
| `api-examples.md` | HTTP request examples |
| `authentication-flow.md` | May duplicate `docs/authentication-flow.md` |
| `deployment-configuration.md` | May duplicate `docs/cloudflare-deployment.md` |
| `environment-variables.md` | Detailed env var reference |
| `kv-namespace-structure.md` | KV key schema — potentially unique |
| `monitoring-logging.md` | Logging setup |
| `openapi.yaml` | OpenAPI 3.x spec for the Worker API |
| `swagger-ui.html` | Swagger UI served as a static file |
| `troubleshooting-guide.md` | May duplicate `docs/troubleshooting-network.md` |

`openapi.yaml` and `kv-namespace-structure.md` are the most likely to be unique. The others may overlap with root `docs/`.

**Recommended check:** Diff against root `docs/` counterparts to identify true duplicates, then consolidate. At minimum, `openapi.yaml` and `swagger-ui.html` should move to root `docs/` rather than live inside the TypeScript source tree.

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
