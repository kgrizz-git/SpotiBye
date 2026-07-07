# File Length Pre-Commit Hook Plan

**Status:** NEEDS REVIEW

**Date:** 2026-07-07

**Source:** [Backlog TO_DO.md](../../backlog/TO_DO.md#file-length-pre-commit-hook)

## Goal

Add a pre-commit hook that warns developers when code files exceed the line count limits (700 lines for code files, 300 lines for documentation files), but skips files on an exemptions list to avoid breaking existing workflows.

## Background

Large files can negatively impact:
- Developer productivity (grep, navigation)
- Incremental compilation (bigger rebuild times)
- Code review efficiency
- IDE performance

Current tracking (src/frontend/) includes several files over 700 lines:
- `/Users/kevingrizzard/MyCode/SpotiBye/src/frontend/ui/backends_screen.py` - 728 lines
- `/Users/kevingrizzard/MyCode/SpotiBye/src/frontend/ui/add_playlist_screen.py` - 763 lines
- `/Users/kevingrizzard/MyCode/SpotiBye/src/frontend/ui/screens/main_screen.py` - 1038 lines

## Requirements

### Hook Logic

- Check line count for each file staged for commit
- Apply different limits based on file type:
  - Code files: > 700 lines (warning)
  - Documentation files: > 300 lines (warning)
  - Other files: no limit
- Skip files in exemption list (see exemptions below)
- Fail pre-commit if non-exempt files exceed limits

### Exemptions (by pattern)

- `dev-docs/**` (development documentation)
- `docs/**` (user documentation)
- `src/frontend/tests/**` (test files)
- `src/frontend/ui/ui_test_helpers.py` (test utilities)
- Any file in the root (temporary placeholder for these specific files):
  - `src/frontend/ui/backends_screen.py`
  - `src/frontend/ui/add_playlist_screen.py`
  - `src/frontend/ui/screens/main_screen.py`

### Implementation Details

**File Detection**

- Code files: `.py` extension with standard import patterns (has `import` statements)
- Documentation files: `.py` files with fewer `import` statements and more verbose comments/docstrings, OR any `.md` files

**Integration**

Add to `.pre-commit-config.yaml` with:
```yaml
- id: file-length-check
  name: File length check
  entry: python scripts/check_file_lengths.py
  language: system
  files: \.py$
  pass_filenames: true
```

**Script Implementation**

Create `scripts/check_file_lengths.py`:
- Read staged files from stdin
- Determine file type (code vs documentation)
- Count lines
- Check against appropriate limit
- Output warnings or exit with error for violations

**Development Workflow**

Exemptions should be:
- Configurable via `scripts/check_file_lengths.py`/`init-exemptions-list.sh`
- Added via easy config mechanism
- Reviewed with each exemption (validate rationale)
- Progressively reduced over time

## Implementation Plan

### Phase 0: Analysis & Specs

- [ ] Define precise file type detection logic
- [ ] Catalog all current exempt files and their reasons
- [ ] Document line count thresholds with rationale
- [ ] Create exemption management strategy

### Phase 1: Script Development

- [ ] Create `scripts/check_file_lengths.py` with core logic
- [ ] Implement file type detection based on pattern analysis
- [ ] Add line counting with exclusions (empty lines, comments)
- [ ] Create baseline exemption list from current exempt files
- [ ] Add command line arguments and help text
- [ ] Write unit tests for file detection logic

### Phase 2: Pre-commit Integration

- [ ] Update `.pre-commit-config.yaml` to include new hook
- [ ] Test hook integration locally
- [ ] Verify hooks run correctly on staged files
- [ ] Add hook to CI configuration for enforcement

### Phase 3: Documentation & Training

- [ ] Update developer documentation
- [ ] Add exemption request process
- [ ] Document remediation steps for violations
- [ ] Create guidance for file splitting

### Phase 4: Monitoring & Maintenance

- [ ] Monitor exemption requests and reasons
- [ ] Review exemption list periodically
- [ ] Adjust thresholds if needed based on feedback
- [ ] Ensure hook doesn't create friction

### Phase 5: Enforcement Evolution

- [ ] Expand hook to catch violations pre-commit (Phase 2 completed)
- [ ] Consider refactoring files over limits
- [ ] Review and remove unnecessary exemptions

## Technical Details

### File Type Detection Logic

**Code files pattern:**
- Python extension (`.py`)
- At least 3 import statements (import/, from/)
- Less than 30% lines are comments (lines starting with `#`)

**Documentation files pattern:**
- Python extension (`.py`)
- Fewer than 3 import statements OR high comment density (> 30% lines start with `#`)
- AND/OR markdown files (`.md`)

### Exemption Management

Exemptions should be stored in an easy-to-edit format (e.g., JSON or YAML) for:
- Quick visual browsing
- Programmatic updates
- Documentation of exemption rationale
- Version control

### Line Count Calculation

- Exclude shebang line (first line if it starts with `#!`)
- Exclude empty lines
- Count only non-whitespace content lines
- Comments count toward limit for both types

### Error Messages

Provide clear guidance:
- File exceeded limit (e.g., "File has 750 lines, exceeds 700 line limit for code files")
- Suggest remediation (e.g., "Consider refactoring or splitting this file")
- List exemption process for files that need exemptions

## Quality Criteria

- [ ] Hook runs without false positives
- [ ] Exemptions are easy to add and track
- [ ] Error messages provide clear guidance
- [ ] Hook integrates seamlessly with existing pre-commit
- [ ] Performance impact is minimal
- [ ] Documentation is clear and comprehensive

## Cross-Talking Points

This plan interacts with:
- **Codebase modernization** (File splitting effort)
- **Developer experience** (IDE performance, navigation)
- **Process improvement** (Pre-commit enforcement)
- **Documentation standards** (Documentation file limits)
- **Quality metrics** (Code size, maintainability)

## References

- Current large file inventory (src/frontend/)
- `.pre-commit-config.yaml` for existing hooks
- Git history showing file size growth
- Developer feedback on large file impact
- Related projects with similar length checks

## Removal Criteria

This plan can be archived when:
- Hook is fully integrated and operational for 30 days
- No new exemption requests
- Codebase has been cleaned up (most oversized files refactored)
- All exemptions have been evaluated and justified
- Developer satisfaction surveys are positive
- Version control commit history shows compliance

**Risk Mitigation:**
- Start with warning-only mode before strict enforcement
- Build community support through documentation
- Provide clear exemption request process
- Monitor developer impact and adjust accordingly

## Notes

**Current Over-sized Files (Exempt Placeholder):**
- `src/frontend/ui/backends_screen.py` - 728 lines
- `src/frontend/ui/add_playlist_screen.py` - 763 lines
- `src/frontend/ui/screens/main_screen.py` - 1038 lines

These are temporary exemptions pending full hook integration.

**Alternative Approaches Considered:**
- Per-directory limits instead of global (more precise but harder to manage)
- Warnings only (less friction, more education)
- Automated file splitting (complex, risky)
- Team-based thresholds (customizable but inconsistent)

**Decision:** Global file-length check with configurable exemptions provides the best balance between enforcement and flexibility.

## Next Steps

1. Implement the core script (Phase 1)
2. Test against current codebase
3. Create exemptions configuration
4. Integrate into pre-commit
5. Document and communicate to developers
6. Begin with warning mode, transition to enforcement

This plan represents a step toward code quality and maintainability, acknowledging that the current codebase has some large files that require temporary exemptions while working toward a more sustainable structure.
