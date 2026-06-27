# Pyright Assessment — `src/frontend/utils/`

**FIXED (2026-06-27)**

## Resolution (2026-06-27)

- **Status:** Fixed. `basedpyright --level error src/frontend/utils/` now reports 0 errors.
- **Fixes applied (`network_utils.py`):**
  - Changed `retryable_errors` parameter from `Optional[List[type]]` to `Optional[tuple[type[BaseException], ...]]` so it can be used directly in `except` clauses.
  - Replaced 5 unparameterized `Callable` annotations with `Callable[..., Any]`.
  - Replaced 2 `last_error`/`raise last_error` pattern with `last_error: BaseException | None = None` plus `assert last_error is not None` before raising.
  - Used a local `status` variable in `is_connected` so `.get()` doesn't see `Optional[Dict]`.
  - Replaced `status_label: Optional[str]` with `status_label: Any` in `create_progress_callback` (it's a Kivy widget at runtime).
- **Fixes applied (`platform_utils.py`):**
  - Changed `from shared.logging_config import logger` to relative `from ...shared.logging_config import logger`.
  - Added explicit `import importlib.util` at the top.
  - Changed `# type: ignore` to `# pyright: ignore[reportMissingImports]` on the 3 `Quartz`/`AppKit` imports (lines 91, 104, 325) — `# type: ignore` did not suppress `reportMissingImports` in basedpyright, the explicit `pyright:` prefix with diagnostic code does.
- **Verification:** Full frontend test suite `pytest src/frontend/tests/` — 126 passed, 7 skipped (pre-existing skips).

## Antigravity Verification (2026-06-27)

- **Validation:** Confirmed.
- **Findings:**
  - Actual error count matches the 16 errors reported.
  - Verified 6 occurrences of `Callable` missing type arguments.
  - Confirmed `platform_utils.py:325` AppKit import needs `# type: ignore` (and note that while `# type: ignore` was present on AppKit, it did not suppress `reportMissingImports` inside the checked environment - standard configuration or stub override is recommended).
  - All suggested resolutions (using `ParamSpec`, None guards, local variables, relative imports) are correct and appropriate.

## Verified Findings (2026-06-27)

- **Error count:** 16 ✓ — confirmed matches actual
- **Callable occurrences:** Assessment says "5 occurrences" but actual count is **6** (lines 51, 66×2, 97×2, 322). Minor count inaccuracy, content is otherwise correct.
- **Line 325 `# type: ignore`:** Assessment claims line 325 is missing `# type: ignore` for `from AppKit import NSApplication`, but the file already has `# type: ignore` on that line. Despite the comment, basedpyright still reports `reportMissingImports` — the comment does not suppress the error. The suggestion to add it is already applied but insufficient.
- **All other suggestions are correct:** adding type args to `Callable`, fixing `tuple[type, ...]` exception handling, guarding `last_error` with `None`, using local variable for `last_status`, properly typing `status_label`, fixing the implicit relative import, adding `import importlib.util`, and adding `# type: ignore` to the AppKit imports.

**Command:** `basedpyright --level error src/frontend/utils/`
**Date:** 2026-06-27
**Errors found:** 16

---

## `src/frontend/utils/`

### `network_utils.py`

#### `Callable` missing type arguments (5 occurrences)

**Lines:** 51, 66 (x2), 97 (x2), 322

```python
# Line 51 — return type of decorator factory
) -> Callable:

# Line 66 — decorator param and return
def decorator(func: Callable) -> Callable:

# Line 97 — decorator param and return
def handle_network_errors(func: Callable) -> Callable:

# Line 322 — return type of factory
) -> Callable:
```

**Suggestion:** Use `ParamSpec` and `TypeVar` from `typing` for proper decorator typing, or at minimum annotate with `Callable[..., Any]` / `Callable[..., ReturnType]`.

---

#### `tuple[type, ...]` is not a valid exception class

**Line 74:** `except tuple(retryable_errors) as e:`

`retryable_errors` is typed `Optional[List[type]]`, and `tuple(...)` creates `tuple[type, ...]`, which is not a legal `except` target type. The runtime code works fine, but pyright can't verify it.

**Suggestion:** Accept the parameter as `tuple[type, ...]` directly instead of `List[type]`, or use `# type: ignore` on this line.

---

#### `None` does not derive from `BaseException`

**Line 89–90:** `raise last_error`

`last_error` is initialized as `None` (line 69). If the loop never catches an exception (theoretically possible if `max_retries < 0`), `raise None` would crash with `TypeError`.

**Suggestion:** Change line 69 to `last_error: Exception | None = None` and add `assert last_error is not None` before raising, or use `raise last_error or RuntimeError("unexpected")`.

---

#### `.get()` on possibly-`None` `last_status`

**Line 173:** `return self.last_status.get("status") == "healthy"`

`self.last_status` is `Optional[Dict[str, Any]]` (line 150). In the `try` block, line 171 assigns a non-`None` value, but pyright can't narrow the type across the exception boundary.

**Suggestion:** Use a local variable: `status = self.backend_client.health_check()` then operate on `status`.

---

#### Assigning `.text` on a `str`

**Line 341:** `status_label.text = message`

`status_label` is typed as `Optional[str]` (line 321), which has no `.text` attribute. At runtime it is presumably a Kivy widget.

**Suggestion:** Add a proper type alias for the widget type (e.g., `from kivy.uix.label import Label` and use `Optional[Label]`), or use `Any` if the widget union is too broad.

---

### `platform_utils.py`

#### Implicitly relative import

**Line 12:** `from shared.logging_config import logger`

Other files at this package depth use `from ...shared.logging_config import logger` (3 dots from `utils` → root `src`).

**Suggestion:** Change to `from ...shared.logging_config import logger`.

---

#### `importlib.util` not a known attribute

**Lines 31, 38:** `importlib.util.find_spec(...)`

The `util` submodule must be imported explicitly to satisfy the type checker.

**Suggestion:** Add `import importlib.util` at the top of the file (keep the existing `import importlib` or replace it).

---

#### `Quartz` / `AppKit` imports not resolved (3 occurrences)

**Lines 91, 104, 325:**

```python
from Quartz import CGDisplayBounds, CGMainDisplayID  # type: ignore
from AppKit import NSScreen                          # type: ignore
from AppKit import NSApplication                     # type: ignore
```

These are macOS PyObjC packages not available in the type-checking environment (and not installed in CI). The `# type: ignore` comments already suppress the error on lines 91 and 104, but **line 325** is missing the comment.

**Suggestion:** Add `# type: ignore` to line 325 to match the pattern already used elsewhere.

```python
from AppKit import NSApplication  # type: ignore
```
