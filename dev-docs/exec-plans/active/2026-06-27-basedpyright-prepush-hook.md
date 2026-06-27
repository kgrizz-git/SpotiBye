# Add basedpyright as a Pre-Push Hook

> **Linked from:** [TO_DO.md](../../dev-docs/backlog/TO_DO.md)
>
> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Mark steps complete (`- [x]`) as work is finished.

**Goal:** Add basedpyright as a pre-push hook in `.pre-commit-config.yaml` so type errors are caught before pushing. Add proper `exclude` paths to `pyproject.toml` to prevent the type checker from scanning old backup directories and virtual environments. Since both `src/frontend` and `src/shared` (including tests) are already clean under `--level error`, they will be targeted by the hook from the beginning.

**Prerequisites:**
- `basedpyright` is already installed in the virtual environment (v1.39.6) and on `PATH`, but **not** listed in `pyproject.toml` dev dependencies yet.
- `src/frontend/` and `src/frontend/tests/` are already clean under `--level error` (legitimate type mismatches and `reportUninitializedInstanceVariable` violations in tests have already been resolved via class-level attributes and typing annotations).

---

## Current State

| Path | Errors (`--level error`) | Status |
|------|--------------------------|--------|
| `src/frontend/` (all modules) | 0 | ✅ Clean |
| `src/frontend/tests/` | 0 | ✅ Clean |
| `src/shared/` | 0 | ✅ Clean |
| `backups/` | **37** | ⚠️ **Needs exclusion** |

Currently, running `basedpyright src/frontend src/shared --level error` reports **0 errors**.
Running `basedpyright` globally from the repository root reports **37 errors**, all of which are contained within the `backups/` directory. These are caused by lack of explicit `exclude` paths in the `[tool.basedpyright]` configuration.

---

## Step 1 — Configure basedpyright in `pyproject.toml`

**File:** `pyproject.toml` (around line 23 for dependencies, line 42 for `[tool.basedpyright]`)

Add basedpyright to the development dependencies and configure global exclusions to prevent scanning backups, environments, and other non-active directories.

- [ ] Add `"basedpyright>=1.39.6"` to the `[project.optional-dependencies] development` list.
- [ ] Add `exclude` paths to the `[tool.basedpyright]` section:
  ```toml
  exclude = [
      "**/backups",
      "**/backend-backup",
      "**/SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY",
      "**/docs/old-docs-backup",
      "**/srcamas",
      "**/.venv",
      "**/venv",
      "**/node_modules",
      "**/build",
      "**/dist"
  ]
  ```

## Step 2 — Sync environment and verify CLI

- [ ] Confirm on PATH: `basedpyright --version` (expect `1.39.6`)
- [ ] Sync lock/install dev deps: `.venv/bin/pip install -e ".[development]"`
- [ ] Run global check: `basedpyright --level error` (expect **0 errors** now that `backups/` is excluded)

## Step 3 — Add pre-push hook entry

**File:** `.pre-commit-config.yaml` (append at the end of the file under pre-push hooks)

- [ ] Add the local hook entry to target frontend and shared sources:
  ```yaml
  - repo: local
    hooks:
      - id: basedpyright
        name: basedpyright type check
        description: Run basedpyright type checker on frontend and shared code before push
        entry: basedpyright src/frontend src/shared --level error
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
  ```

> **Why `language: system`?** The hook uses the project's venv (where basedpyright is installed). `system` keeps the dependency managed centrally in `pyproject.toml`.
> **Why `--level error`?** Only actual type errors block the push; warnings/informationals (e.g. Kivy dynamic typing/Any warnings) are suppressed to prevent false-positive blocks.

- [ ] Run `pre-commit install --hook-type pre-push` (to ensure the hook type is registered).

## Step 4 — Clean up stale per-file suppressions

16 `# pyright: ignore[...]` comments exist in source files. Since `reportAttributeAccessIssue` is globally suppressed, **6 are redundant**:

- [ ] Remove from `src/frontend/auth/backend_login_screen.py:116,127`
- [ ] Remove from `src/frontend/app/backend_app.py:159,504-506`

Verify the remaining 10 are still needed:
- [ ] `src/frontend/screens/cache_explorer_adapter.py:55` — `reportReturnType`
- [ ] `src/frontend/screens/main_screen_error_popup.py:124-125` — `reportPossiblyUnboundVariable`
- [ ] `src/frontend/utils/platform_utils.py:92,105,326` — `reportMissingImports` for macOS-only imports
- [ ] `src/frontend/ui/backend_playlist_card.py:823,825,829,830` — `reportArgumentType`

- [ ] Verify no regressions: `basedpyright --level error` (should still be 0)

## Step 5 — Verify Pre-Push Hook

- [ ] Run `pre-commit run --hook-stage pre-push basedpyright --all-files` to confirm the hook passes.
- [ ] Add a deliberate type error to a source file, run the hook, verify it rejects the push, and then revert the error.
- [ ] Run `./scripts/verify-all.sh` to confirm all repo structure, tests, and hooks pass.
- [ ] Update the `TO_DO.md` entry to mark "Add basedpyright as a pre-push hook" as done.

---

## Rollback

If the hook causes issues:
- Remove the hook block from `.pre-commit-config.yaml`.
- Or temporarily bypass hook validation during push with `git push --no-verify`.
