# Add basedpyright as a Pre-Push Hook

> **Linked from:** [TO_DO.md](../../backlog/TO_DO.md)
>
> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Mark steps complete (`- [x]`) as work is finished.

**Goal:** Add basedpyright as a pre-push hook in `.pre-commit-config.yaml` so type errors are caught before pushing. Add proper `exclude` paths to `pyproject.toml` to prevent the type checker from scanning old backup directories and virtual environments. Since both `src/frontend` and `src/shared` (including tests) are already clean under `--level error`, they will be targeted by the hook from the beginning.

**Prerequisites:**
- `basedpyright` v1.39.6 is resolvable on `PATH` (currently via a pyenv shim, not the project `.venv`), and is **not** yet listed in `pyproject.toml` dev dependencies. Step 1/Step 2 add it to the dev extras and install it into `.venv` so the tool is managed by the project rather than relying on a global/pyenv install.
- `pre-commit` is likewise only available via a global/pyenv shim (not in `.venv`); installing the dev extras in Step 2 also pins it into the project environment.
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

- [x] Add `"basedpyright>=1.39.6"` to the `[project.optional-dependencies] development` list.
- [x] Add `exclude` paths to the `[tool.basedpyright]` section:
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
  > **Note:** Only `backups/` currently exists in the tree (it holds the 37 errors). `backend-backup`, `SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY`, `docs/old-docs-backup`, and `srcamas` do not exist today but are kept as defensive entries that mirror the existing `[tool.bandit] exclude_dirs` and `.pre-commit-config.yaml` exclude regex, so re-introduced backup dirs stay out of scope.

## Step 2 — Sync environment and verify CLI

- [x] Confirm a copy is resolvable on PATH: `basedpyright --version` (expect `1.39.6`)
- [x] Install dev deps into the project venv: `.venv/bin/pip install -e ".[development]"`
- [x] Confirm it is now installed **inside the venv** (not just the pyenv shim): `.venv/bin/basedpyright --version` — installed **1.39.9** (the `>=1.39.6` constraint pulled the latest patch; satisfies the requirement).
- [x] Run global check: `basedpyright --level error` (expect **0 errors** now that `backups/` is excluded) — confirmed **0 errors**.

## Step 3 — Add pre-push hook entry

**File:** `.pre-commit-config.yaml` (append at the end of the file under pre-push hooks)

- [x] Add the local hook entry to target frontend and shared sources:
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

> **Why `language: system`?** `system` runs whatever `basedpyright` is first on `PATH` at push time (the activated `.venv` if active, otherwise the pyenv/global shim) rather than having pre-commit build an isolated env. This matches the existing pre-push hooks (`python-tests`, `node-tests`, `security-scan`) and keeps the dependency declared centrally in `pyproject.toml`. Step 2 ensures the venv copy exists so an activated venv is self-contained.
> **Why `--level error`?** Only actual type errors block the push; warnings/informationals (e.g. Kivy dynamic typing/Any warnings) are suppressed to prevent false-positive blocks.

- [x] Run `pre-commit install --hook-type pre-push` (to ensure the hook type is registered).

## Step 4 — Clean up stale per-file suppressions

16 `# pyright: ignore[...]` comments exist in source files. Since `reportAttributeAccessIssue` is globally suppressed, **6 are redundant**:

- [x] Remove from `src/frontend/auth/backend_login_screen.py:116,127`
- [x] Remove from `src/frontend/app/backend_app.py:159,504-506`

Verify the remaining 10 are still needed:
- [x] `src/frontend/screens/cache_explorer_adapter.py:55` — `reportReturnType`
- [x] `src/frontend/screens/main_screen_error_popup.py:124-125` — `reportPossiblyUnboundVariable`
- [x] `src/frontend/utils/platform_utils.py:92,105,326` — `reportMissingImports` for macOS-only imports
- [x] `src/frontend/ui/backend_playlist_card.py:823,825,829,830` — `reportArgumentType`

(Source files backed up to `backups/*.bak` before editing. 10 ignores confirmed remaining.)

- [x] Verify no regressions: `basedpyright --level error` (should still be 0) — confirmed **0 errors**.

## Step 5 — Verify Pre-Push Hook

- [x] Run `pre-commit run --hook-stage pre-push basedpyright --all-files` to confirm the hook passes. — **Passed**.
- [x] Add a deliberate type error to a source file, run the hook, verify it rejects the push, and then revert the error. — Hook **Failed** on the injected `reportReturnType` error and **Passed** again after revert.
- [x] Run `./scripts/verify-all.sh` to confirm all repo structure, tests, and hooks pass. — "All verifications passed."
- [x] Update developer docs that list verification/hooks (`AGENTS.md` and `CLAUDE.md` "Running Tests & Verification") to mention the new basedpyright pre-push hook. (No `CHANGELOG.md` entry needed — internal tooling change with no user-facing impact.)
- [x] Update the `TO_DO.md` entry to mark "Add basedpyright as a pre-push hook" as done.

---

## Rollback

If the hook causes issues:
- Remove the hook block from `.pre-commit-config.yaml`.
- Or temporarily bypass hook validation during push with `git push --no-verify`.
