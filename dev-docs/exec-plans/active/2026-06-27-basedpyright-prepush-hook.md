# Add basedpyright as a Pre-Push Hook

> **Linked from:** [TO_DO.md](../../dev-docs/backlog/TO_DO.md)
>
> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Mark steps complete (`- [x]`) as work is finished.

**Goal:** Add basedpyright as a pre-push hook in `.pre-commit-config.yaml` so type errors are caught before pushing. Start with directories that are already clean, then expand coverage as remaining issues are fixed.

**Prerequisites:**
- `[tool.basedpyright]` section exists in `pyproject.toml` (line 42) with `reportAttributeAccessIssue = "none"`, `reportIncompatibleMethodOverride = "none"`, `reportOptionalMemberAccess = "none"`, and `reportImportCycles = "none"`
- `basedpyright` is already installed in the venv (v1.39.6) and on `PATH`, but **not** listed in `pyproject.toml` dev dependencies yet

---

## Current State

| Path | Errors | Status |
|------|--------|--------|
| `src/frontend/` root `__init__.py` | 0 | ✅ Clean |
| `src/frontend/state.py` | 0 | ✅ Clean |
| `src/frontend/config/` | 0 | ✅ Clean |
| `src/frontend/caching/` | 0 | ✅ Clean |
| `src/frontend/app/` | 0 | ✅ Clean |
| `src/frontend/auth/` | 0 | ✅ Clean |
| `src/frontend/services/` | 0 | ✅ Clean |
| `src/frontend/utils/` | 0 | ✅ Clean |
| `src/frontend/ui/` | 0 | ✅ Clean |
| `src/frontend/screens/` | 0 | ✅ Clean |
| `src/frontend/screens/adapter_mixins/` | 0 | ✅ Clean |
| `src/frontend/tests/` | **27** | ⚠️ **See Step 5** |

All source dirs report **0 errors**. `src/frontend/tests/` has **27 errors** across 8 test files (was 49 at assessment time, 42 when plan was drafted). Errors fall into four categories:

| Error code | Count | Root cause |
|---|---|---|
| `reportUninitializedInstanceVariable` | 20 | unittest pattern: instance vars set in `setUp()`, not `__init__` |
| `reportArgumentType` | 3 | Passing `None` where `str` expected in test helpers |
| `reportOptionalSubscript` | 1 | `get_current_export_job()` returns `dict \| None`, not narrowed |
| `reportMissingTypeArgument` | 1 | `queue.Queue()` used without type args |
| `reportOperatorIssue` | 1 | `float()` on `Any` dict values typed as `float \| int \| str` |
| `reportCallIssue` | 1 | `assertAlmostEqual` overloads mismatch from same source |

Remaining `# pyright: ignore[...]` comments in source code (16 total):
- 6 are `reportAttributeAccessIssue` — **now globally suppressed** in `pyproject.toml` → redundant
- 10 are for other codes (`reportReturnType`, `reportPossiblyUnboundVariable`, `reportMissingImports`, `reportArgumentType`) — verify each still needed

---

## Step 1 — Add basedpyright to dev dependencies

**File:** `pyproject.toml` (`[project.optional-dependencies] development`, line 23)

basedpyright is already installed in the venv but **not tracked** as a project dependency.

- [ ] Add `"basedpyright>=1.21.0"` to the `development` list (alongside existing entries)

## Step 2 — Verify basedpyright CLI

Already installed — just confirm it works:

- [ ] Confirm on PATH: `basedpyright --version` (expect `1.39.6`)
- [ ] Reinstall dev deps to sync lock: `.venv/bin/pip install -e ".[development]"`

## Step 3 — Verify basedpyright on clean directories

- [ ] Run `basedpyright src/frontend --level error` (expect **27 errors**, all in `tests/`)
- [ ] Run `basedpyright src/frontend/app src/frontend/auth src/frontend/caching src/frontend/config src/frontend/services src/frontend/utils src/frontend/ui src/frontend/screens src/frontend/state.py src/frontend/__init__.py --level error` to confirm these 10 paths report **0 errors**

## Step 4 — Add pre-push hook entry

**File:** `.pre-commit-config.yaml` (append after line 137, before the final newline)

- [ ] Add a local hook entry (without `tests/` initially):

```yaml
      - id: basedpyright
        name: basedpyright type check
        description: Run basedpyright type checker on clean directories before push
        entry: basedpyright src/frontend/app src/frontend/auth src/frontend/caching src/frontend/config src/frontend/services src/frontend/utils src/frontend/ui src/frontend/screens src/frontend/state.py src/frontend/__init__.py --level error
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

> **Why `language: system` and not `language: python`?** The hook uses the project's venv (where basedpyright is installed). `language: python` with `additional_dependencies` would install a separate basedpyright in pre-commit's managed env, which works but duplicates the install. Either approach is valid — `system` keeps the dependency managed centrally in `pyproject.toml`. If you prefer isolation, switch to `language: python` with `additional_dependencies: ['basedpyright>=1.21.0']`.

> **Why `--level error`?** Only actual errors block the push; informationals and warnings are suppressed. If desired, omit `--level error` to catch all diagnostics, but this increases the chance of noisy false positives blocking pushes.

- [ ] Run `pre-commit install --hook-type pre-push` (re-register; the pre-push hook file already exists from other hooks)

## Step 5 — Fix remaining errors in `src/frontend/tests/` (27 errors)

Errors span **8 test files** with different profiles:

### File-by-file breakdown

| File | Errors | Codes | Fix strategy |
|---|---|---|---|
| `test_cache_explorer_mock.py` | 8 | `reportUninitializedInstanceVariable` (5), `reportOperatorIssue` (1), `reportCallIssue` (1), `reportArgumentType` (1) | Fix `float()` casts on dict values (lines 98-101); suppress `reportUninitializedInstanceVariable` per-path |
| `test_auth.py` | 2 | `reportUninitializedInstanceVariable` | per-path suppression or `# pyright: basic` |
| `test_cache.py` | 2 | `reportUninitializedInstanceVariable` (2) | per-path suppression or `# pyright: basic` |
| `test_main_screen_filenames.py` | 2 | `reportArgumentType` (2) | Fix call sites: wrap `None` in `assert selected_export_format(None)` with explicit type or add `# pyright: ignore` inline |
| `test_performance.py` | 3 | `reportUninitializedInstanceVariable` (2), `reportMissingTypeArgument` (1) | Add `queue.Queue[Any]()` type arg; suppress uninitialized vars |
| `test_resumable_export_cache.py` | 3 | `reportUninitializedInstanceVariable` (3) | per-path suppression |
| `test_ui.py` | 3 | `reportUninitializedInstanceVariable` (3) | per-path suppression |
| `test_ui_responsiveness.py` | 2 | `reportUninitializedInstanceVariable` (2) | per-path suppression |
| `test_main_screen_state.py` | 1 | `reportOptionalSubscript` (1) | Narrow return with `assert` or `# pyright: ignore` inline |
| `test_backend_cache_explorer.py` | 1 | `reportUninitializedInstanceVariable` (1) | per-path suppression |

**20 of 27 errors** are `reportUninitializedInstanceVariable` — the standard unittest pattern where instance variables are assigned in `setUp()` not `__init__()`. The cleanest fix: add a per-path `[tool.basedpyright]` override in `pyproject.toml` for tests only, rather than suppressing per-file.

**Remaining 7 errors** are legitimate type mismatches in test code that should be fixed individually:

- [ ] **test_cache_explorer_mock.py:98-101** — Replace `float(cache_status["cache_hits"])` with explicit typed local vars or add `# pyright: ignore[reportOperatorIssue, reportCallIssue, reportArgumentType]` on the `assertAlmostEqual` line
- [ ] **test_main_screen_filenames.py:24,63** — Wrap `None` args in `assert selected_export_format(None)` — either fix the helper signatures to accept `None` (if intentional), or suppress inline
- [ ] **test_main_screen_state.py:27** — Narrow with `assert job is not None; assert job["cancelled"]` or use `# pyright: ignore[reportOptionalSubscript]`
- [ ] **test_performance.py:55** — Change `queue.Queue()` to `queue.Queue[Any]()` or `queue.Queue[SomeType]()`

After individual fixes:
- [ ] Triage remaining `reportUninitializedInstanceVariable` errors (approx 20). Options:
  - **Best:** Add per-path config in `pyproject.toml`:
    ```toml
    [tool.basedpyright]
    # ...existing settings...
    
    # Tests use unittest setUp() pattern — instance vars assigned outside __init__
    reportUninitializedInstanceVariable = "none"
    ```
    *(But this would apply to ALL files under `src/frontend` — need a sub-config mechanism.)*
  - **Alternative:** Add `# pyright: basic` at the top of each affected test file
  - **Alternative:** Configure via CLI flags — basedpyright supports `--pythonpath` and project-based config, but per-directory config requires a separate `pyrightconfig.json` or per-file headers
- [ ] Verify final count reaches 0: `basedpyright src/frontend/tests --level error`
- [ ] Once at 0, add `src/frontend/tests` to the hook `entry` string in `.pre-commit-config.yaml`

## Step 6 — Clean up stale per-file suppressions

16 `# pyright: ignore[...]` comments exist in source files. Now that `reportAttributeAccessIssue` is globally suppressed, **6 are definitely redundant**:

- [ ] `src/frontend/auth/backend_login_screen.py:116,127` — `# pyright: ignore[reportAttributeAccessIssue]` — **redundant, remove**
- [ ] `src/frontend/app/backend_app.py:159,504-506` — `# pyright: ignore[reportAttributeAccessIssue]` — **redundant, remove**

Verify the remaining 10 are still needed:

- [ ] `src/frontend/screens/cache_explorer_adapter.py:53` — `reportReturnType` — still needed? If code compiled, remove.
- [ ] `src/frontend/screens/main_screen_error_popup.py:124-125` — `reportPossiblyUnboundVariable` — still needed?
- [ ] `src/frontend/utils/platform_utils.py:92,105,326` — `reportMissingImports` for macOS-only imports — still needed (non-macOS dev)?
- [ ] `src/frontend/ui/backend_playlist_card.py:825-832` — `reportArgumentType` on `size_hint`/`text_size` tuples — still needed (Kivy dynamic typing)?

- [ ] Verify no regressions: `basedpyright src/frontend --level error` (should still be 0 on source, 27 on tests until Step 5 is done)

## Step 7 — Verify

- [ ] Run `pre-commit run --hook-stage pre-push basedpyright --all-files` to confirm the hook passes
- [ ] Add a deliberate type error, verify the hook rejects it, then revert
- [ ] Run `./scripts/verify-all.sh` to confirm nothing is broken
- [ ] Update the TO_DO.md entry to mark "Add basedpyright as a pre-push hook" as done
- [ ] **Note:** `scripts/check-repo-structure.sh` (line 69) warns when an active plan has all boxes checked and >3 total. If all steps here are checked, either move this file to `dev-docs/exec-plans/completed/` and update `completed/README.md`, or leave a few admin steps unchecked to suppress the warning.

---

## Rollback

If the hook causes issues:
- Remove the hook block from `.pre-commit-config.yaml`
- Or temporarily bypass with `git push --no-verify`
