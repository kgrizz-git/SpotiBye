# File Length Pre-Commit Hook Plan

**Status:** IN PROGRESS (Phase 1, Phase 2, Phase 2b, and Phase 3 complete — script, exemptions config, unit tests, `.pre-commit-config.yaml` hook in `--warn` mode using `.venv/bin/python`, verification script integration, `setup-hooks.sh` dev-extras installation, CI workflow checks, developer policy guide `dev-docs/guides/file-length-policy.md`, and CHANGELOG all updated and passing. Phase 4 Phase A warn-mode rollout ready)

**Date:** 2026-07-07

**Source:** [Backlog TO_DO.md](../../backlog/TO_DO.md#file-length-pre-commit-hook)

## Goal

Add a pre-commit hook that warns developers when code files exceed the line count limits (700 lines for code files, 300 lines for documentation files, 1000 lines for test files), but skips files on an exemptions list to avoid breaking existing workflows.

Initial rollout uses `--warn` mode (warnings only, never blocks). After 14 days, the hook switches to enforcement mode where violations block the commit.

## Background

Large files can negatively impact:
- Developer productivity (grep, navigation)
- Incremental compilation (bigger rebuild times)
- Code review efficiency
- IDE performance

## Requirements

### Hook Logic

- Check line count for each `.py` and `.md` file staged for commit
- Apply limits based on **directory path** (deterministic, no heuristics):
  - `**/tests/**`, `**/test_*.py`, `**/*_test.py` → test files (1000-line limit)
  - `docs/**`, `dev-docs/**` → documentation (300-line limit)
  - All other `.py` files → code (700-line limit)
  - All `.md` files → documentation (300-line limit)
- Skip files in exemption list (see exemptions below)
- **Initial behavior (`--warn` mode):** print warnings, exit 0 always
- **Final behavior (enforcement):** fail pre-commit if non-exempt files exceed limits
- Support `--ci` mode: exit 1 on any violation (for CI enforcement)
- Only the hook entry flag changes between warn and enforcement; script supports both modes

### Scope

- **Python (`.py`):** fully checked with path-based classification
- **Markdown (`.md`):** checked at 300-line doc limit
- **First rollout — `.py` violations only expected from `src/frontend/`** (that is where the oversized file lives). Backend has no `.py` files (it is TypeScript-only); all `.ts`/`.js`/`.tsx`/`.jsx` files are explicitly out of scope.
- **Markdown is checked repo-wide**, not scoped to `src/frontend/`. Existing `.md` files in `dev-docs/` exceed the 300-line limit (see exemptions below), so `--warn` mode is essential to avoid blocking dev-docs work during Phase A.
- **TypeScript/JavaScript (`.ts`, `.js`, `.tsx`, `.jsx`):** out of scope — backend files are all under 700 lines (max is 621 in tests). Explicitly excluded; revisit if backend file lengths grow.
- **All other file types:** skipped

### Exemptions

Exemptions are stored in `scripts/file-length-exemptions.json`. Each entry has a `pattern` (gitignore-style glob), a `reason`, and an optional `expires` field (ISO date) to prevent permanent exemptions.

**Baseline exemptions:**

> **Note:** `dev-docs/**` and `docs/**` are already classified as documentation (300-line limit) by file-type detection, so they do not need classification exemptions. Only files that would otherwise violate a limit need listing. **27 existing `dev-docs/` `.md` files exceed 300 lines** (ranging from 301–1220 lines). Rather than exempting each individually, a blanket `dev-docs/**/*.md` exemption covers all developer-internal docs. `docs/**/*.md` files are all under 300 lines (max 232) and need no exemption.
>
> **Update (2026-07-08):** During implementation, two additional violation sources were discovered when scan-mode was tested against the repo and added to the exemptions file: **6 `src/backend/docs/**/*.md`** files over 300 lines (backend architecture docs, not end-user) and **1 `.github/instructions/**/*.md`** file over 300 lines (internal agent-instructions). These bring the exemption list from 2 → 4 entries. The technical-details section below still shows the original 2-entry example; the real file has 4 entries (see `scripts/file-length-exemptions.json`).

| Pattern | Reason | Expires |
|---|---|---|
| `src/frontend/ui/backend_playlist_card.py` | 940 lines — needs refactoring | 2026-10-07 |
| `dev-docs/**/*.md` | 27 existing files over 300 lines — dev-internal docs, not user-facing | 2026-10-07 (reassess then) |
| `src/backend/docs/**/*.md` | 6 existing files over 300 lines — backend docs, not end-user docs | 2026-10-07 |
| `.github/instructions/**/*.md` | 1 existing file over 300 lines — internal agent instructions | 2026-10-07 |

**Example exemption file:**

> **Update (2026-07-08):** The real `scripts/file-length-exemptions.json` now contains 4 entries (the two below plus `src/backend/docs/**/*.md` and `.github/instructions/**/*.md`, discovered during implementation). This example shows the originally-planned 2 entries; see the actual file for the current set.

```json
{
  "exemptions": [
    {"pattern": "src/frontend/ui/backend_playlist_card.py", "reason": "940 lines — needs refactoring", "expires": "2026-10-07"},
    {"pattern": "dev-docs/**/*.md", "reason": "27 existing files over 300 lines — dev-internal docs, not user-facing", "expires": "2026-10-07"}
  ]
}
```

### Implementation Details

**File Detection (path-based)**

Classification is deterministic — no import-count or comment-density heuristics:

- Documentation: any `.md` file, or any `.py` under `docs/` or `dev-docs/`
- Test: any `.py` under a directory named `tests/` or matching `test_*.py` / `*_test.py`
- Code: all other `.py` files
- Skipped: all other file types

**Integration**

Add to `.pre-commit-config.yaml` with a local hook:

```yaml
- id: file-length-check
  name: File length check
  entry: .venv/bin/python scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json --warn
  language: system
  files: \.(py|md)$
  types: [file]
  pass_filenames: true
  stages: [pre-commit]
```

**Script Implementation (`scripts/check_file_lengths.py`)**

Follow conventions from `scripts/check-dependencies.py`:
- Shebang `#!/usr/bin/env python3`
- Module docstring with description and usage
- `argparse` for CLI arguments
- `sys.exit(main())` pattern
- CLI flags:
  - `--exemptions PATH` (required) — path to exemptions JSON file
  - `--warn` — print warnings, exit 0 regardless
  - `--ci` — exit 1 on any violation (mutually exclusive with `--warn`); semantically identical to default enforcement except that it also implies full-scan mode when no filenames are passed
  - `--count-only` — print a summary of active, expired, and soon-to-expire (within 7 days) exemptions, then exit 0 (used for monitoring in Phase 4; no violation reporting)
- Default mode (no flags): enforce — exit 1 on violation. This is the Phase B local hook behavior.
- Core logic:
  - Read staged file paths from `sys.argv` (positional args — pre-commit with `pass_filenames: true` passes them this way, not stdin)
  - Classify file type by directory path (code / doc / test / skip)
  - Check glob exemption list before counting
  - Count total lines via Python `sum(1 for _ in f)`
  - Compare against limit
  - Output violations or pass silently

**Development Workflow**

Exemptions are:
- Stored in version-controlled `scripts/file-length-exemptions.json`
- Added by editing the JSON file with a `reason` field
- Reviewed during PR review
- Progressively reduced as files are refactored

**Transition strategy:**

1. **Phase A (`--warn` mode, days 0–14):** Hook prints warnings but exits 0. CI in `--ci` mode is the only enforcer. This lets developers see violations without being blocked.
2. **Phase B (enforcement, day 14+):** Remove `--warn` flag from the hook entry. Hook now exits 1 on violations, blocking the commit. CI continues to use `--ci` mode (unchanged).
3. **Rollback:** If enforcement causes developer friction, re-add `--warn` and address feedback before retrying.

## Implementation Plan

### Phase 0: Analysis & Specs

- [x] Define precise file type detection logic
- [x] Catalog all current exempt files and their reasons
- [x] Document line count thresholds with rationale
- [x] Create exemption management strategy

### Phase 1: Script Development

- [x] Add `pathspec` to `pyproject.toml` under `[project.optional-dependencies]development` (append to the existing `development` array; not currently a direct dependency — black stopped vendoring pathspec in v24+) — **implemented (uncommitted):** `pathspec>=0.12` added to the development extras (`pyproject.toml:34`)
- [x] Create `scripts/file-length-exemptions.json` with current exempt files and reasons — **implemented (uncommitted):** file contains four baseline exemptions (the two planned entries plus two discovered during implementation: `src/backend/docs/**/*.md` for 6 backend docs over 300 lines, and `.github/instructions/**/*.md` for 1 agent-instructions file over 300 lines — both discovered when scan-mode was tested against the repo)
- [x] Create `scripts/check_file_lengths.py` with: — **implemented (uncommitted):** script created at 379 lines with all required functionality (note: the actual `lines` count is 379, not the 378 logged in the earlier tool output)
  - [x] Shebang, docstring, `sys.exit(main())` pattern
  - [x] `argparse` with `--exemptions`, `--warn`, `--ci` flags — **note:** `argparse` also supports `--count-only` and `--exclude` as described in the plan
  - [x] Enforce `--ci` and `--warn` mutual exclusivity via `argparse.add_mutually_exclusive_group()` (built-in; prints error and exits 1 automatically if both passed); note the default error message is terse ("not allowed with argument") — consider a custom error via manual check for clarity
  - [x] Read filenames from `sys.argv` (positional args from pre-commit with `pass_filenames: true`)
  - [x] **Scan-mode fallback:** when no positional filenames are given (e.g., CI invocation without pre-commit), walk the **repo root** for all `.py` and `.md` files (matching the local hook's repo-wide `files: \.(py|md)$` scope — walking only `src/`+docs would silently miss violations outside those trees). Hardcode the exclusion list (don't parse YAML — overengineered): `.venv/`, `venv/`, `node_modules/`, `build/`, `dist/`, `backups/`, `backend-backup/`, `__pycache__/`, and any path matching `.pre-commit-config.yaml`'s `exclude` regex pattern. Accept an optional `--exclude` CLI flag for ad-hoc overrides.
  - [x] Glob-matcher for exemption list using `pathspec` (chosen over stdlib `fnmatch`/`pathlib` because exemptions use gitignore-style `**` patterns that `pathspec` matches correctly out of the box; `fnmatch` has edge cases with recursive wildcards and leading `./`); wrap the import in `try/except ImportError` and emit a clear message ("install with: pip install -e '.[development]'") before exiting 1 (enforcement/`--ci`) or printing a warning and continuing (`--warn`) — this prevents `ModuleNotFoundError` on a fresh clone where only `setup-hooks.sh` (which installs `pre-commit` but not Python development extras) has been run
  - [x] Line counting via Python `sum(1 for _ in f)` (deterministic, matches `wc -l` for normal files, handles missing trailing newline correctly; avoids subprocess call)
  - [x] Expiry-date warning for exemptions past their `expires` date; in enforcement modes (both default and `--ci`), treat expired exemptions as violations (exit 1); in `--warn` mode, print warning but continue
  - [x] Violation output with clear guidance
  - [x] Error handling: if exemptions JSON is missing or malformed, print error and exit 1 in enforcement modes (both default and `--ci`); print warning and continue (treating no files as exempt) in `--warn` mode
- [x] Handle deleted/renamed files: skip paths that do not exist on disk (pre-commit passes deleted/renamed file paths; the "skip non-existent" rule handles both cases uniformly — process only files on disk, log skipped missing paths at debug level) — **implemented:** present in `check_files()` at `scripts/check_file_lengths.py:248`
- [x] Write unit tests (place in `scripts/tests/` — not `src/frontend/tests/`, since these test a non-Kivy tool): — **implemented (uncommitted):** `scripts/tests/test_check_file_lengths.py` written (206 lines, 5 test functions) covering the cases below
  - [x] Path-based file classification (code / doc / test / skip) — `test_classify_path`
  - [x] Glob exemption matching (including `**` wildcards) — `test_glob_exemption_matching`
  - [x] Glob exemption matching (including `**` wildcards) — explicitly assert both a file directly under `dev-docs/` and a file in a nested subdirectory match `dev-docs/**/*.md` (paths with `**` are zero-or-more-directories; verifying zero-dir matching is critical since ~27 files depend on it) — covered in `test_glob_exemption_matching` (`dev-docs/README.md` and `dev-docs/exec-plans/active/2026-07-07-plan.md`)
  - [x] Scan-mode fallback walks the expected directories and respects the exclusion list (`.venv/`, `node_modules/`, `build/`, `__pycache__/`, etc. — set up a mock `.venv/` with an oversized `.py` and verify it is not reported) — `test_scan_mode_fallback` (sets up `.venv/big.py` at 1500 lines and `node_modules/ignored.py`, asserts neither appears in `walk_repo` output)
  - [x] Expired exemption detection in enforcement vs warn mode — `test_expired_exemption_detection` (asserts exit 1 + `ERROR:` in enforce, exit 0 + `WARNING:` in warn)
  - [x] Mutual exclusivity of `--warn` and `--ci` — `test_mutual_exclusivity_warn_and_ci` (asserts `SystemExit` with non-zero code)
  - [x] Warn-vs-enforce exit codes on oversized files — `test_check_files_warn_vs_enforce` (bonus test: 705-line file, asserts exit 0/`WARNING:` in warn and exit 1/`ERROR:` in enforce)
- [x] Test against current codebase: — **done (2026-07-08):** verified using `.venv/bin/python` (system `python` lacks `pathspec` — see Phase 2 note on `setup-hooks.sh`)
  - [x] `backend_playlist_card.py` (940 lines) → reported as violation for code files (700-line limit) — confirmed: with empty exemptions, `--ci` on that single file prints `ERROR: ... has 940 lines, exceeds 700 line limit for code files` + guidance and exits 1; with the real exemptions file it's skipped (exit 0)
  - [x] All other staged `.py` files pass (under their respective limits) — confirmed via full-scan `--ci` (exit 0, no output); the only `.py` over 700 is the exempted `backend_playlist_card.py`
  - [x] All staged `.md` files under `docs/` pass (under 300-line doc limit); `dev-docs/**/*.md` files are exempted so they do not trigger violations — confirmed: `--ci` full-scan exits 0; `--count-only` reports 4 active exemptions (the `.py` + `dev-docs/**/*.md` + `src/backend/docs/**/*.md` + `.github/instructions/**/*.md` globs)
  - [x] Exempted files are skipped even when over limit — confirmed (`backend_playlist_card.py` skipped; all 3 doc globs cover their over-limit files)
  - [x] In `--warn` mode, exit code is 0 despite violations — confirmed (full-scan `--warn` exits 0, no stderr output because all violators are exempted; the warn-vs-enforce exit-code behavior is also covered by `test_check_files_warn_vs_enforce` unit test)
  - [x] In `--ci` mode, exit code is 1 on any violation — confirmed via the empty-exemptions run above; the full-scan `--ci` with real exemptions exits 0 because every over-limit source is exempted
- [x] Verify with `./scripts/verify-all.sh` that no existing checks break — **done (2026-07-08):** `./scripts/verify-all.sh` passes ("All verifications passed."). Note: `scripts/tests/` is **not** wired into `verify-frontend.sh` yet (that's a Phase 2 task), so this run only confirms existing checks still pass; the 7 script unit tests pass when run directly via `KIVY_WINDOW=headless .venv/bin/pytest scripts/tests/ -v`

### Phase 2: Pre-commit Integration

- [x] Update `.pre-commit-config.yaml` with the new hook (use `--warn` mode initially, using `.venv/bin/python`)
- [x] Install hook locally and confirm it fires on `.py` and `.md` changes
- [x] Test with a staged oversized file to confirm warning appears
- [x] Test with an exempted file to confirm it is skipped
- [x] Test with no changed files to confirm no-op
- [x] Update CHANGELOG.md under `## [Unreleased] > ### Added`
- [x] Add file-length check to `scripts/verify-frontend.sh` (or add a new `verify-file-lengths.sh`) so `./scripts/verify-all.sh` covers it
- [x] Add a pytest step for script tests to `verify-frontend.sh`: `KIVY_WINDOW=headless .venv/bin/pytest scripts/tests/ -q` — this is required because `scripts/tests/` is outside `src/frontend/tests/` and won't be discovered otherwise; the Kivy env vars are harmless for non-Kivy tests and keep the invocation uniform with the rest of `verify-frontend.sh`
- [x] Verify `./scripts/verify-all.sh` passes after config change
- [x] Confirm `scripts/setup-hooks.sh` installs the `[development]` extras (or add it if missing) so the `pathspec` dependency is present after a fresh clone — without this, the local hook fails with `ModuleNotFoundError`
- [x] Verify `pip show pathspec` (or `python -c "import pathspec"`) succeeds in the dev/CI environment before relying on the hook

### Phase 2b: CI Integration

The repository has `.github/workflows/ci.yml` with two jobs: `backend` (TypeScript) and `frontend` (Python). Add the file-length check to the `frontend` job, which already has Python available.

- [x] Add a step to the `frontend` job in `.github/workflows/ci.yml` (after `Install dependencies`, before `Test`):
      ```yaml
      - name: File length check
        run: python scripts/check_file_lengths.py --ci --exemptions scripts/file-length-exemptions.json
      ```
      The script's scan-mode fallback detects no positional filenames and walks the repo for `.py`/`.md` files.
      Ensure the step's working directory is the repo root (the `frontend` job's default is typically the checkout root, but verify).
      Alternately, add a standalone `file-length` or `code-quality` job if Python dependency overhead is a concern.
- [x] Verify CI passes on a PR with no violations
- [x] Verify CI fails on a PR introducing a file over the limit
- [x] CI should use `--ci` mode (exit 1 on violation) regardless of the local `--warn` mode

### Phase 3: Documentation & Training

- [x] Add exemption request process to developer docs (edit JSON + add reason)
- [x] Document remediation steps for violations (refactoring guidance)
- [x] Create guidance for file splitting (when to split, how to preserve public API)
- [x] Create a short rationale doc (`dev-docs/guides/file-length-policy.md`) and link to it from error messages:
      `ERROR: <file> has <N> lines (limit: <M>). See dev-docs/guides/file-length-policy.md for how to split large files.`

### Phase 4: Rollout & Monitoring

- [ ] **Phase A (days 0–14):** Ship with `--warn` flag. Monitor for false positives and developer feedback.
- [ ] **Phase B (day 14+):** Remove `--warn` flag from `.pre-commit-config.yaml`. Hook now blocks commits with violations.
- [ ] Monitor exemption requests and reasons
- [x] Track exemption count automatically: add a CI step that runs `check_file_lengths.py --exemptions scripts/file-length-exemptions.json --count-only` (the `--count-only` flag is defined in Phase 1 argparse; it prints active, expired, and soon-to-expire exemption counts and exits 0 without reporting violations — `--ci` is not needed since `--count-only` suppresses violation enforcement)
- [ ] Add a scheduled (weekly) CI job or manual check that warns when any exemption is within 7 days of its `expires` date, so the team can review and decide to extend or drop before enforcement kicks in
- [ ] Review exemption list periodically (suggested quarterly)
- [ ] Adjust thresholds if needed based on feedback
- [ ] Define a quantitative rollback trigger: if 3+ developers report being blocked by false positives within the first week of Phase B enforcement, revert to `--warn` within 1 hour and address feedback before retrying
- [ ] If enforcement causes friction, revert to Phase A and address feedback before retrying

### Phase 5: Enforcement Evolution

- [ ] Refactor `src/frontend/ui/backend_playlist_card.py` (940 lines) to remove its exemption
- [ ] After refactoring, remove associated exemption entry
- [ ] Consider expanding scope to TypeScript/JS if backend files grow over 700 lines

## Technical Details

### File Type Detection Logic

Classification is based on directory path — no import-count or comment-density heuristics:

| Classification | Rule |
|---|---|
| Documentation | Any `.md` file, or `.py` under `docs/` or `dev-docs/` |
| Test | `.py` under a directory named `tests/`, or matching `test_*.py` / `*_test.py` |
| Code | All other `.py` files |
| Skipped | Everything else (`.ts`, `.js`, `.json`, `.yaml`, `.sh`, etc.) |

### Exemption File Format

Path: `scripts/file-length-exemptions.json`

> **Update (2026-07-08):** The actual file contains 4 entries (see below), not the 2 shown in the original example. The two extra entries cover backend docs and agent-instructions files that exceed the 300-line doc limit and were discovered during implementation.

```json
{
  "exemptions": [
    {"pattern": "src/frontend/ui/backend_playlist_card.py", "reason": "940 lines — needs refactoring", "expires": "2026-10-07"},
    {"pattern": "dev-docs/**/*.md", "reason": "27 existing files over 300 lines — dev-internal docs, not user-facing", "expires": "2026-10-07"},
    {"pattern": "src/backend/docs/**/*.md", "reason": "6 existing files over 300 lines — backend docs, not end-user docs", "expires": "2026-10-07"},
    {"pattern": ".github/instructions/**/*.md", "reason": "1 existing file over 300 lines — internal agent instructions", "expires": "2026-10-07"}
  ]
}
```

Patterns use gitignore-style glob matching (`**` matches zero or more directories). Leading `./` is not required; paths are matched against the repo-relative path as passed by pre-commit. The `expires` field is optional; when present, the script logs a warning if the expiry date has passed, and in enforcement modes (both default and `--ci`) treats an expired exemption as a violation (exits 1).

### Line Count Calculation

- Use Python `sum(1 for _ in f)` (equivalent to `wc -l` for normal files, handles missing trailing newline correctly, avoids subprocess overhead)
- No exclusions for shebang, blank lines, or comments
- Rationale: total line count is deterministic and matches developer intuition. Complex exclusion heuristics create confusion and false negatives.

### Error Messages

Provide clear guidance:
- Violation: `ERROR: src/frontend/ui/backend_playlist_card.py has 940 lines, exceeds 700 line limit for code files`
- Remediation: `Consider refactoring or splitting this file.`
- Exemption: `To add an exemption, edit scripts/file-length-exemptions.json with a reason.`
- In `--warn` mode, prefix with `WARNING:` instead of `ERROR:` and always exit 0.
- In enforcement modes (default or `--ci`), prefix with `ERROR:` and exit 1.

## Quality Criteria

- [ ] Hook runs without false positives on current codebase
- [ ] Exemptions are easy to add and track (edit JSON, add reason)
- [ ] Error messages provide clear guidance
- [ ] Hook integrates seamlessly with existing pre-commit (no conflicts)
- [ ] Performance impact is minimal (sub-second for typical staged files)
- [ ] Documentation is clear and comprehensive

## Cross-Talking Points

This plan interacts with:
- **Codebase modernization** (File splitting effort)
- **Developer experience** (IDE performance, navigation)
- **Process improvement** (Pre-commit enforcement)
- **Documentation standards** (Documentation file limits)
- **Quality metrics** (Code size, maintainability)

## References

- `.pre-commit-config.yaml` — existing hooks and conventions
- `.github/workflows/ci.yml` — existing CI with `frontend` and `backend` jobs
- `scripts/check-dependencies.py` — existing Python script conventions
- `scripts/file-length-exemptions.json` — exemption config (to be created)
- `pyproject.toml` — project config where `pathspec` dependency is declared
- `dev-docs/backlog/TO_DO.md` — source backlog entry

## Removal Criteria

This plan can be archived when:
- Hook is fully integrated and operational for 30 days
- No new exemption requests filed in the last 30 days
- `backend_playlist_card.py` is refactored below 700 lines and its exemption removed
- All exemptions have a documented reason
- `./scripts/verify-all.sh` passes with the hook in enforcement mode

**Risk Mitigation:**
- Start with `--warn` mode for 14 days before switching to enforcement
- Provide clear exemption entry process (edit JSON with reason)
- If enforcement causes developer friction, revert to warn mode immediately
- Monitor exemption growth as a leading indicator of threshold problems

## Notes

**Current Over-sized Files (Exempt Placeholder):**
- `src/frontend/ui/backend_playlist_card.py` — 940 lines (code file, exceeds 700 limit)

This is the only `.py` file currently over 700 lines that isn't already covered by a glob-pattern exemption (tests, docs, dev-docs). 27 `dev-docs/` `.md` files also exceed the 300-line doc limit and are exempted via `dev-docs/**/*.md`.

**Alternative Approaches Considered:**
- Per-directory limits instead of global (more precise but harder to manage)
- Warnings only (less friction, less enforcement — used as transition)
- Automated file splitting (complex, risky)
- Team-based thresholds (customizable but inconsistent)

**Decision:** Global file-length check with configurable exemptions provides the best balance between enforcement and flexibility. Warning-only mode for the first 14 days mitigates rollout risk.

## Next Steps

1. ✅ Create the exemptions JSON file
2. ✅ Implement the core script (Phase 1) — including unit tests
3. ✅ Test against current codebase (Phase 1 — verified 2026-07-08)
4. ✅ Verify `./scripts/verify-all.sh` passes (Phase 1 — verified 2026-07-08)
5. ✅ Update CHANGELOG.md
6. ✅ Integrate into pre-commit with `--warn` mode (Phase 2)
7. ✅ Wire `scripts/tests/` and `check_file_lengths.py` into `verify-frontend.sh` (Phase 2)
8. ✅ Add CI integration steps (`--ci` check + `--count-only` monitoring) (Phase 2b & Phase 4)
9. ✅ Create developer guide `dev-docs/guides/file-length-policy.md` and index it in `dev-docs/README.md` (Phase 3)
10. ⬜ After 14 days of Phase A warn mode, switch to enforcement mode (Phase B — Phase 4)
11. ⬜ Track `backend_playlist_card.py` refactoring to remove its exemption (Phase 5)

> **Update (2026-07-08):** Phases 1, 2, 2b, and 3 are fully complete and verified. The script, exemptions config, unit tests, pre-commit hook (`--warn` mode using `.venv/bin/python`), `setup-hooks.sh` dev-extras installation, `verify-frontend.sh` test and check wiring, GitHub Actions CI steps, developer policy guide `dev-docs/guides/file-length-policy.md`, and CHANGELOG entry are implemented. All verifications pass (`./scripts/verify-all.sh`). Ready for Phase A warn-mode rollout.

This plan represents a step toward code quality and maintainability, acknowledging that the current codebase has one large file requiring a temporary exemption while working toward a more sustainable structure.
