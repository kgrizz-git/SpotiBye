# File Length Pre-Commit Hook Plan

**Status:** READY

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
- **First rollout targets `src/frontend/` only** (where the oversized file lives). Backend `.py` and `.md` files are also checked but all currently pass.
- **TypeScript/JavaScript (`.ts`, `.js`, `.tsx`, `.jsx`):** out of scope — backend files are all under 700 lines (max is 621 in tests). Explicitly excluded; revisit if backend file lengths grow.
- **All other file types:** skipped

### Exemptions

Exemptions are stored in `scripts/file-length-exemptions.json`. Each entry has a `pattern` (gitignore-style glob), a `reason`, and an optional `expires` field (ISO date) to prevent permanent exemptions.

**Baseline exemptions:**

| Pattern | Reason | Expires |
|---|---|---|
| `dev-docs/**` | Development documentation | — |
| `docs/**` | User documentation | — |
| `src/frontend/ui/backend_playlist_card.py` | 940 lines — needs refactoring | 2026-10-07 |

Any future exemptions must include a `reason` field. Exemptions with an `expires` field are automatically flagged for review after that date.

**Example exemption file:**

```json
{
  "exemptions": [
    {"pattern": "dev-docs/**", "reason": "Development documentation"},
    {"pattern": "docs/**", "reason": "User documentation"},
    {"pattern": "src/frontend/ui/backend_playlist_card.py", "reason": "940 lines — needs refactoring", "expires": "2026-10-07"}
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
  entry: python scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json
  language: system
  files: \.(py|md)$
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
  - `--ci` — exit 1 on any violation (mutually exclusive with `--warn`)
- Core logic:
  - Read staged file paths from `sys.argv` (positional args — pre-commit with `pass_filenames: true` passes them this way, not stdin)
  - Classify file type by directory path (code / doc / test / skip)
  - Check glob exemption list before counting
  - Count total lines (`wc -l` style — simple, fast, predictable)
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

- [ ] Create `scripts/file-length-exemptions.json` with current exempt files and reasons
- [ ] Create `scripts/check_file_lengths.py` with:
  - [ ] Shebang, docstring, `sys.exit(main())` pattern
  - [ ] `argparse` with `--exemptions`, `--warn`, `--ci` flags
  - [ ] Classify file type by directory path (code / doc / test / skip)
  - [ ] Read filenames from `sys.argv` (positional args from pre-commit)
  - [ ] Glob-matcher for exemption list (support `**` globs)
  - [ ] Line counting via `wc -l` (simple total line count)
  - [ ] Expiry-date warning for exemptions past their `expires` date
  - [ ] Violation output with clear guidance
- [ ] Write unit tests for:
  - [ ] Path-based file classification (code / doc / test / skip)
  - [ ] Glob exemption matching (including `**` wildcards)
- [ ] Test against current codebase: script should report violations for `backend_playlist_card.py` (940 lines) and pass all others
- [ ] Verify with `./scripts/verify-all.sh` that no existing checks break

### Phase 2: Pre-commit Integration

- [ ] Update `.pre-commit-config.yaml` with the new hook (use `--warn` mode initially)
- [ ] Install hook locally and confirm it fires on `.py` and `.md` changes
- [ ] Test with a staged oversized file to confirm warning appears
- [ ] Test with an exempted file to confirm it is skipped
- [ ] Test with no changed files to confirm no-op
- [ ] Update CHANGELOG.md under `## [Unreleased] > ### Added`
- [ ] Verify `./scripts/verify-all.sh` still passes after config change

### Phase 2b: CI Integration

- [ ] Add a CI workflow step that runs `scripts/check_file_lengths.py --ci --exemptions ...` on all changed files in a PR
- [ ] If no suitable existing job exists, add a new job to `.github/workflows/ci.yml`
- [ ] Verify CI passes on a PR with no violations
- [ ] Verify CI fails on a PR introducing a file over the limit
- [ ] CI should use `--ci` mode (exit 1 on violation) regardless of the local `--warn` mode

### Phase 3: Documentation & Training

- [ ] Add exemption request process to developer docs (edit JSON + add reason)
- [ ] Document remediation steps for violations (refactoring guidance)
- [ ] Create guidance for file splitting (when to split, how to preserve public API)

### Phase 4: Rollout & Monitoring

- [ ] **Phase A (days 0–14):** Ship with `--warn` flag. Monitor for false positives and developer feedback.
- [ ] **Phase B (day 14+):** Remove `--warn` flag from `.pre-commit-config.yaml`. Hook now blocks commits with violations.
- [ ] Monitor exemption requests and reasons
- [ ] Review exemption list periodically (suggested quarterly)
- [ ] Adjust thresholds if needed based on feedback
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

```json
{
  "exemptions": [
    {"pattern": "dev-docs/**", "reason": "Development documentation"},
    {"pattern": "docs/**", "reason": "User documentation"},
    {"pattern": "src/frontend/ui/backend_playlist_card.py", "reason": "940 lines — needs refactoring", "expires": "2026-10-07"}
  ]
}
```

Patterns use gitignore-style glob matching (`**` matches zero or more directories). Leading `./` is not required; paths are matched against the repo-relative path as passed by pre-commit. The `expires` field is optional; when present, the script logs a warning if the expiry date has passed.

### Line Count Calculation

- Use total line count (`wc -l` equivalent — simple, fast, predictable)
- No exclusions for shebang, blank lines, or comments
- Rationale: `wc -l` is the industry standard, deterministic, and matches developer intuition. Complex exclusion heuristics create confusion and false negatives.

### Error Messages

Provide clear guidance:
- Violation: `ERROR: src/frontend/ui/backend_playlist_card.py has 940 lines, exceeds 700 line limit for code files`
- Remediation: `Consider refactoring or splitting this file.`
- Exemption: `To add an exemption, edit scripts/file-length-exemptions.json with a reason.`
- In `--warn` mode, prefix with `WARNING:` instead of `ERROR:` and always exit 0.

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
- `scripts/check-dependencies.py` — existing Python script conventions
- `scripts/file-length-exemptions.json` — exemption config (to be created)
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

This is the only file currently over 700 lines that isn't already covered by a glob-pattern exemption (tests, docs, dev-docs).

**Alternative Approaches Considered:**
- Per-directory limits instead of global (more precise but harder to manage)
- Warnings only (less friction, less enforcement — used as transition)
- Automated file splitting (complex, risky)
- Team-based thresholds (customizable but inconsistent)

**Decision:** Global file-length check with configurable exemptions provides the best balance between enforcement and flexibility. Warning-only mode for the first 14 days mitigates rollout risk.

## Next Steps

1. Create the exemptions JSON file
2. Implement the core script (Phase 1)
3. Test against current codebase
4. Update CHANGELOG.md
5. Integrate into pre-commit with `--warn` mode (Phase A)
6. Add CI integration (Phase 2b — CI uses `--ci` immediately)
7. Verify `./scripts/verify-all.sh` passes
8. After 14 days, switch to enforcement mode (Phase B)
9. Track `backend_playlist_card.py` refactoring to remove its exemption

This plan represents a step toward code quality and maintainability, acknowledging that the current codebase has one large file requiring a temporary exemption while working toward a more sustainable structure.
