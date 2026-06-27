# Pyright Assessment — `src/frontend/ui/`

**NEEDS REVIEW**

## Verified Findings (2026-06-27)

- **Error count:** 110 ✓ — confirmed matches actual
- **Issues confirmed:** All categories are correct — constant redefinition (2), possibly unbound variables from conditional imports (4), `.bind()`/.`setter()` unknown on Kivy classes (~17), widget `.text`/`.active`/`.opacity` on `None` (~25), `add_widget` on `None`, `.get_cache_status` unknown, `self` type mismatch in lambda, `before` on `None`, dynamic attributes on `BoxLayout` (3), incompatible `on_touch_*` override (6 errors across 3 methods), `size_hint`/`text_size` argument type mismatches (4), `__getitem__` on `float` (9), uninitialized instance variables (6), `tuple`/`dict` missing type args (2)
- **All suggestions are appropriate:** type annotations, None guards, `@final` decorators, pyright config suppression for Kivy bind

**Command:** `basedpyright --level error src/frontend/ui/`
**Date:** 2026-06-27
**Errors found:** 110

---

## `backend_cache_explorer.py` (21 errors)

### `BACKEND_AVAILABLE` / `_BACKEND_IMPORT_ERROR` constant redefinition (lines 29–30)
These uppercase names are flagged as constants that cannot be reassigned. The pattern is used for conditional import fallback.

**Suggestion:** Use lowercase names (`backend_available`, `_backend_import_error`) or add `# type: ignore`.

### Possibly unbound variables (lines 46, 132)
`get_cache_manager`, `BackendClient`, `resolve_startup_backend_url` may not be bound (conditional import pattern).

**Suggestion:** Restructure the import fallback to assign `None` defaults, then check at point of use.

### `.bind()` not known on Kivy classes (lines 106, 115, 323)
`Switch.bind()`, `Button.bind()` — Kivy dynamic event system.

### `.text` / `.active` on `None` (lines 119, 124, 133, 134, 137, 168, 176, 184, 251, 262, 266, 276, 280)
Widget references (`Optional[...]`) accessed without None check.

**Suggestion:** Add None guards or assert non-None.

### `add_widget` on `None` (line 119)
**Suggestion:** Guard with `if widget is not None:`.

### Possibly unbound `BackendClient` / `resolve_startup_backend_url` (lines 132–133)
Conditional import pattern.

### `.get_cache_status` not known on `BackendClient` (line 150)
**Suggestion:** Verify `get_cache_status` exists on the class or is dynamically attached.

### `self` type mismatch in lambda/closure (line 244)
`CacheExplorerPopup | None` not assignable to `CacheExplorerPopup`.

**Suggestion:** Add None guard before the call.

---

## `backend_playlist_card.py` (32 errors)

### `.bind()` / `.setter()` not known on Kivy classes (lines 107, 108, 111, 399, 466, 506, 754, 775, 811, 812)
`BoxLayout.bind()`, `BackendPlaylistCard.bind()`, `CheckBox.bind()`, `Button.bind()` — all Kivy dynamic event system.

### `before` on `None` (lines 72, 90, 808)
**Suggestion:** None-guard or `assert` before access.

### `_analysis_container`, `_duration_label`, `_tracks_layout` not known on `BoxLayout` (lines 292, 293, 515, 516, 705, 780)
These attributes are set dynamically on a `BoxLayout` subclass. pyright doesn't know about them.

**Suggestion:** Declare them as class attributes or use `@final` on the subclass.

### Incompatible `on_touch_down` / `on_touch_move` / `on_touch_up` override (lines 178, 195, 210)
Return type `bool` doesn't match base class `Literal[True] | None`.

**Suggestion:** Change return type to `bool | None` and ensure `None` is returned for unhandled events, or return `True` consistently.

### `tuple`/`dict` missing type arguments (lines 55, 548)
**Suggestion:** Add type arguments, e.g. `tuple[int, int]`, `dict[str, Any]`.

### `size_hint` / `text_size` argument type mismatch (lines 825, 828)
`tuple[None, Literal[1]]` not assignable to `float | str`. Widget properties accept tuples but stubs show scalar.

**Suggestion:** Make the stubs aware of Kivy property types, or cast.

---

## `backend_selector_popup.py` (7 errors)

### `.bind()` not known on `Spinner`, `TextInput`, `Button` (lines 58, 68, 84, 88, 92)

### `tuple` missing type arguments (line 257)

---

## `cache_explorer.py` (42 errors)

### Uninitialized instance variables (lines 92, 113, 160, 191, 225, 259)
`search_input`, `breadcrumb_label`, `playlists_content`, `tracks_content`, `details_content`, `features_content` set outside `__init__` in non-`@final` class.

**Suggestion:** Initialize in `__init__` or decorate class with `@final`.

### `.bind()` / `.setter()` not known on Kivy classes (lines 100, 110, 137, 163, 164, 186, 194, 220, 228, 254, 262, 263, 363, 462)
`TextInput`, `Button`, `GridLayout` — same Kivy issue.

### `opacity` on `None` (lines 373–375, 473–474, 537–538, 613, 622, 631)
Widget references that are `Optional` accessed without None check.

### `.get()` on `None` (line 471)
`self.last_selected_playlist.get(...)` when the field may be `None`.

### `Dict[str, Any] | None` not assignable to `Dict[str, Any]` (line 477)
Passing optional dict to a function expecting non-optional.

---

## `layouts.py` (12 errors)

### `.bind()` / `.setter()` not known on `ResponsiveGridLayout` (lines 21–22)

### `__getitem__` not defined on `float` (lines 33, 36, 40, 46, 50, 74, 77)
`self.size[i]` where `size` is typed as `float` rather than a tuple.

**Suggestion:** `size` is a Kivy `ReferenceList` (behaves like a tuple). Declare it as `tuple[float, float]` or use `.width`/`.height` instead of subscript.
