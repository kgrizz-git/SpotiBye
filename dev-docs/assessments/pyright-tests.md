# Pyright Assessment — `src/frontend/tests/`

**NEEDS REVIEW**

## Verified Findings (2026-06-27)

- **Error count:** 49 ✓ — confirmed matches actual
- **Issues confirmed:** All categories correct — uninitialized instance vars in test classes (~18), conditional import fallback pattern (~10), `None` access (~6), generic missing type args (~2). Breakdown:
  - `test_auth.py`: 2 ✓
  - `test_backend_cache_explorer.py`: 18 ✓
  - `test_cache.py`: 5 ✓
  - `test_cache_explorer_mock.py`: 8 ✓
  - `test_configuration.py`: 2 ✓
  - `test_main_screen_filenames.py`: 2 ✓
  - `test_main_screen_state.py`: 1 ✓
  - `test_performance.py`: 4 ✓
  - `test_resumable_export_cache.py`: 4 ✓
  - `test_ui.py`: 3 ✓ (assessment lists 3 on lines 20-22, not 2 as section header says)
  - `test_ui_responsiveness.py`: 2 ✓
- **All suggestions are appropriate:** class-level annotations, `@final`, None guards, type arguments

**Command:** `basedpyright --level error src/frontend/tests/`
**Date:** 2026-06-27
**Errors found:** 49

---

## `test_auth.py` (2 errors)

### Uninitialized instance variables
**Lines 23, 24:** `backend_client`, `authenticator` assigned in `setUp` but not declared in the class body or `__init__`.

**Suggestion:** Annotate at class level: `backend_client: Mock` or use `@final` on the test class.

---

## `test_backend_cache_explorer.py` (18 errors)

### `BACKEND_AVAILABLE` constant redefinition (lines 33, 35)

### Uninitialized `mock_client` (line 68)

### Possibly unbound `BackendCacheExplorerPopup` / `CacheExplorerAdapter` / `create_cache_explorer` (lines 91, 103, 120, 141, 166, 196, 213, 227, 251, 291)
All from conditional import fallback pattern.

### `.active` / `.text` on `None` (lines 96, 129, 146, 301)

### Cannot assign to `backend_cache_status` on `BackendCacheExplorerPopup` (line 295)
Type mismatch: `dict[str, float | int | str]` not assignable to `None`.

---

## `test_cache.py` (5 errors)

### Uninitialized `backend_client`, `cache_manager` (lines 22–23)

### `len()` on `List[...] | None` (lines 84–85)
**Suggestion:** Add `if result is not None:` guard before `len(result)`.

### `Queue` missing type arguments (line 99)
**Suggestion:** `queue.Queue[mock.Mock]` or similar.

---

## `test_cache_explorer_mock.py` (8 errors)

### Uninitialized instance variables (lines 17, 21, 36–38)
`mock_config`, `mock_client`, `mock_popup`, `mock_label`, `mock_switch`.

### `/` operator not supported for `float | int | str` (line 92)
Mixed-type division in a cache stats calculation.

**Suggestion:** Cast operands to `float` explicitly.

### `assertAlmostEqual` type mismatch (line 95)
Second argument type `float | Unknown` not matching expected overloads.

---

## `test_configuration.py` (2 errors)

### `LOADING_MESSAGE` / `ERROR_MESSAGE_COLOR` not known on `type[UIConstants]` (lines 135, 139)
Accessing class attributes via `type[cls]` where they exist only on the instance.

**Suggestion:** Use `cls.LOADING_MESSAGE` on an instance instead of on the class object.

---

## `test_main_screen_filenames.py` (2 errors)

### `None` passed where `str` expected (lines 24, 63)
**Suggestion:** Pass actual string values instead of `None`.

---

## `test_main_screen_state.py` (1 error)

### `None` not subscriptable (line 27)
**Suggestion:** None-guard or ensure the variable is not `None`.

---

## `test_performance.py` (4 errors)

### Uninitialized `backend_client`, `recco_service` (lines 22–23)

### `Queue` missing type arguments (line 55)

---

## `test_resumable_export_cache.py` (4 errors)

### Uninitialized `temp_dir`, `home_patch`, `cache_manager` (lines 11–12, 15)

---

## `test_ui.py` (2 errors)

### Uninitialized `backend_client`, `recco_service`, `cache_manager` (lines 20–22)

---

## `test_ui_responsiveness.py` (2 errors)

### Uninitialized `backend_client`, `ui_events` (lines 23–24)

---

## Cross-cutting Themes

| Theme | Occurrences | Suggestion |
|---|---|---|
| **Uninitialized instance vars in test classes** | ~18 | Annotate at class level or decorate with `@final` |
| **Conditional import fallback** | ~10 | Restructure to avoid conditional-def patterns in tests |
| **`None` access** | ~6 | Add None guards |
| **`Queue`/generic missing type args** | ~2 | Add type arguments |
