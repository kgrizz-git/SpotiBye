# File Length Policy & Remediation Guide

SpotiBye enforces maximum line-count thresholds across codebase files to maintain developer productivity, code review quality, and maintainability.

## Line Count Thresholds

| Classification | Path / Rule | Limit |
|---|---|---|
| **Code** | All `.py` files outside `tests/`, `docs/`, `dev-docs/` | **700 lines** |
| **Test** | `.py` files under `tests/` or matching `test_*.py` / `*_test.py` | **1000 lines** |
| **Documentation** | All `.md` files, or `.py` files under `docs/` / `dev-docs/` | **300 lines** |

Line counts are deterministic (`sum(1 for _ in file)`) and include comments and whitespace.

---

## Remediation: How to Split Large Files

When a file exceeds its threshold, avoid increasing the limit or filing a permanent exemption. Instead, refactor and split the file into focused modules while preserving public API compatibility.

### 1. Preserve Public API via Facades / Coordinators
When splitting large classes or modules:
- Keep the original public class or entry point at its existing import path.
- Extract domain logic, UI construction, or helper methods into focused modules (`*_ui.py`, `*_helpers.py`, or a subpackage/subdirectory).
- Re-export or compose these extracted modules inside the main coordinator file so external callers do not break.

### 2. Examples in SpotiBye
- **UI Coordinators:** `main_screen.py` delegates selection to `main_screen_selection.py` (`SelectionManager`) and search/sort UI to `main_screen_search_sort_ui.py`, keeping the coordinator under limit.
- **Mixins & Adapters:** `backend_main_screen_adapter.py` composes mixins under `adapter_mixins/` while preserving all public symbols.
- **Route Sub-apps:** TypeScript route files (e.g., `routes/export.ts`) compose sub-routes under `routes/export/` with dedicated helpers under `routes/export/helpers/`.

---

## Exemption Request Process

In rare cases where immediate refactoring is impractical (e.g., a large legacy module undergoing active feature development), a temporary exemption can be added.

1. Open `scripts/file-length-exemptions.json`.
2. Add an entry to `exemptions`:
   ```json
   {
     "pattern": "src/frontend/path/to/large_file.py",
     "reason": "Explain why it cannot be split right now",
     "expires": "YYYY-MM-DD"
   }
   ```
3. Exemption patterns support gitignore-style globs (`**`).
4. Set an `expires` date so the exemption is revisited and refactored.
