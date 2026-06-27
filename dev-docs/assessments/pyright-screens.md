# Pyright Assessment — `src/frontend/screens/` (excluding `adapter_mixins/`)

**NEEDS REVIEW**

## Verified Findings (2026-06-27)

- **Error count:** 307 total (`screens/`) minus 147 (`adapter_mixins/`) = **160**, not "~160" — confirmed exact
- **Issues confirmed:** All categories correct — import cycles (3), implicitly relative import, constant redefinition (3), `dict`/`List`/`tuple` missing type args (~12), unknown widget attributes on Screen classes (~80), `.bind()`/`.setter()` unknown (~25), `before` on `None`, `on_enter` incompatible override, `.load_playlists` on `None`, possibly unbound variables (5), `None` access (~10), return type mismatch, `str` not assignable to `bool | None`
- **All suggestions are appropriate:** `TYPE_CHECKING` guards, relative imports, class attribute declarations, type arguments, None guards

**Command:** `basedpyright --level error src/frontend/screens/`
**Date:** 2026-06-27
**Errors found:** ~160 (307 total for `screens/` minus 147 in `adapter_mixins/`)

---

## `main_screen.py` (39 errors)

### Import cycle detected (lines 3 errors)
Import cycles between `main_screen.py`, `main_screen_search_sort_ui.py`, `main_screen_selection.py`, and `main_screen_ui.py`.

**Suggestion:** Move shared types to a separate module or use `TYPE_CHECKING` for cyclic type references.

### Implicitly relative import (line 38)
`from frontend.screens.cache_explorer_adapter import ...` — should be a relative import.

**Suggestion:** Change to `from .cache_explorer_adapter import ...`.

### `BACKEND_CACHE_EXPLORER_AVAILABLE` constant redefinition (lines 40, 42)
Conditional import fallback pattern.

**Suggestion:** Use lowercase name.

### `dict`/`List` missing type arguments (lines 51, 52, 104, 108, 157, 160, 318)
**Suggestion:** Add type arguments.

### Unknown attributes on `MainScreen` (lines 199, 203, 205, 220, 224, 226, 232, 233, 242, 255, 268, 294, 304, 333, 335, 339, 343, 352, 371, 477, 484, 488)
`filename_input`, `username_label`, `status_label`, `playlist_layout` — these are Kivy widget IDs set dynamically in KV or `__init__`.

**Suggestion:** Declare as class attributes with proper Kivy types.

### `on_enter` incompatible override (line 217)
Missing `args` parameter. `on_enter` should accept `*args` or `args`.

**Suggestion:** Add `*args` parameter: `def on_enter(self, *args):`.

### `.load_playlists` on `None` (lines 239, 299)
Unwrapped optional accessed without None check.

### `create_cache_explorer` possibly unbound (line 462)
Conditional import.

---

## `main_screen_ui.py` (72 errors)

### Unknown attributes on `MainScreen` — the vast majority
All attributes like `playlist_layout`, `username_label`, `sort_spinner`, `by_label`, `sort_direction_btn`, `search_input`, `select_all_btn`, `selection_label`, `bg_rect`, `filename_input`, `format_spinner`, `export_btn`, `cancel_btn`, `progress_bar`, `status_label`, `clear_cache_btn`, `cache_explorer_btn` are assigned via `self.X = ...` but pyright cannot resolve them.

**Suggestion:** Same as above — declare class attributes with proper types.

### `.bind()` / `.setter()` on Kivy widgets (many lines)
Same cross-cutting Kivy issue.

### `before` on `None` (line 297)

### `.bg_rect` not known on `BoxLayout` (lines 299, 303, 304)
`bg_rect` is dynamically assigned to a `BoxLayout` instance.

**Suggestion:** Subclass `BoxLayout` and declare the attribute there.

---

## `main_screen_search_sort_ui.py` (13 errors)

### Unknown attributes on `MainScreen` (lines 83, 102, 125, 143, 150, 153)
`sort_direction_btn`, `sort_spinner`, `status_label`, `search_input`, `playlist_layout`.

### `cancel` not known on `object` (lines 112, 130, 147)
Calling `cancel` on an `object` (likely a threading primitive).

**Suggestion:** Annotate the variable as `threading.Event` or similar.

### `dict` missing type arguments (lines 24, 159, 169)

---

## `main_screen_selection.py` (1 error)

### `selection_label` not known on `MainScreen` (line 37)

---

## `main_screen_sort_filter.py` (4 errors)

### `dict` missing type arguments (lines 8, 40)

---

## `backend_main_screen.py` (20 errors)

### `dict` missing type arguments (line 23)

### Unknown attributes on `BackendMainScreen` (lines 32, 34, 43, 61, 63, 64, 71, 91, 92, 108, 114, 115, 122, 134, 136, 138, 141)
`playlist_layout`, `status_label`.

### `.bind()` not known on `CheckBox` (lines 51, 102)

---

## `backend_main_screen_adapter.py` (1 error)

### `dict` missing type arguments (line 59)

---

## `cache_explorer_adapter.py` (5 errors)

### `BACKEND_AVAILABLE` constant redefinition (line 16)

### `resolve_startup_backend_url` possibly unbound (line 31)

### Return type mismatch (line 41) — `BackendCacheExplorerPopup` not assignable to `CacheExplorerPopup`
If using fallback classes, the return type should be a union.

### `str` not assignable to `bool | None` (line 63)
Likely setting `md_bg_color` or similar with a string.

---

## `main_screen_cache.py` (2 errors)

### `.bind()` not known on `Button` (lines 61–62)

---

## `main_screen_error_popup.py` (8 errors)

### `None` not subscriptable (lines 114–115)
`self.some_optional_dict[key]` where the dict may be `None`.

### `.bind()` not known on `Button` / `Popup` (lines 119–120, 122–124)

### `resume_btn` / `discard_btn` possibly unbound (lines 122–123)

---

## `main_screen_export.py` (2 errors)

### `.bind()` not known on `Button` (lines 137–138)

---

## `main_screen_logout.py` (2 errors)

### `.bind()` not known on `Button` (lines 66–67)

---

## `main_screen_scheduler.py` — no errors

## Cross-cutting Themes

| Theme | Occurrences | Suggestion |
|---|---|---|
| **Kivy `.bind()`/`.setter()` unknown** | ~25 | Suppress `reportAttributeAttributeAccessIssue` for Kivy modules, or `# type: ignore` each call |
| **Unknown widget attributes on Screen classes** | ~80 | Declare attributes in class body with Kivy types (e.g. `status_label: Label`) |
| **`dict`/`List`/`tuple` missing type args** | ~12 | Add type arguments |
| **Conditional import constant redefinition** | 3 | Use lowercase names |
| **Import cycles** | 3 | Use `TYPE_CHECKING` guards |
| **Possibly unbound variables** | 5 | Initialize before conditional blocks |
| **`None` access** | ~10 | Add None guards |
