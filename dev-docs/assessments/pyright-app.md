# Pyright Assessment — `src/frontend/app/`

**NEEDS REVIEW**

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
