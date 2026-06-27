# Pyright Assessment — `src/frontend/app/`

**FIXED (2026-06-27)**

## Resolution (2026-06-27)

- **Status:** Fixed. `basedpyright --level error src/frontend/app/` now reports 0 errors.
- **Fix applied:** Added `# pyright: ignore[reportAttributeAccessIssue]` comments to the 4 `.bind()` call sites (`src/frontend/app/backend_app.py:159, 504, 505, 506`). Note: `# type: ignore` did **not** suppress the error — basedpyright requires the explicit `pyright:` prefix with the diagnostic code.
- **Cross-cutting note:** The same `.bind()` pattern recurs across `ui/`, `screens/`, and `adapter_mixins/`. A project-wide basedpyright config to suppress `reportAttributeAccessIssue` for Kivy modules would be a better long-term fix than per-call comments. Track as a follow-up.

## Antigravity Verification (2026-06-27)

- **Validation:** Confirmed.
- **Findings:**
  - Actual error count is 4, as reported.
  - All 4 errors are due to Kivy class `.bind()` attribute accesses that pyright cannot resolve.
  - The suggestions (suppressing `reportAttributeAccessIssue` for Kivy modules or adding `# type: ignore` to the `bind()` calls) are correct and verified.

## Verified Findings (2026-06-27)

- **Error count:** 4 ✓ — confirmed matches actual
- **Issues:** All `.bind()` not known on Kivy classes (lines 159, 504, 505, 506) ✓
- **Suggestion is correct:** use `# type: ignore` on each `bind()` call or suppress `reportAttributeAccessIssue` for Kivy modules in pyright config

**Command:** `basedpyright --level error src/frontend/app/`
**Date:** 2026-06-27
**Errors found:** 4

---

## `backend_app.py`

### `.bind()` not known on Kivy classes (4 occurrences)

**Lines 159, 504, 505, 506:** `bind` is not recognized as an attribute of `BackendSelectorPopup`, `Button`, or `Popup`.

Kivy widgets define `bind` dynamically via their event system; pyright's stubs don't include it.

```python
# Line 159
self.ids.some_widget.bind(...)

# Lines 504-506
button.bind(...)
popup.bind(...)
```

**Suggestion:** This affects all Kivy `bind()` calls across the codebase. Either:
- Add `# type: ignore` to each `bind()` call
- Or use a Kivy-specific pyright plugin/stub override
- Or suppress `reportAttributeAccessIssue` for Kivy modules in a pyright config
