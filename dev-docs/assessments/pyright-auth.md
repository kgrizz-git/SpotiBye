# Pyright Assessment — `src/frontend/auth/`

**NEEDS REVIEW**

## Verified Findings (2026-06-27)

- **Error count:** 14 claimed, **13 actual** — overcount by 1
  - `backend_auth.py`: 1 ✓
  - `backend_login_screen.py`: 12 (not 13 as breakdown suggests)
- **Discrepancy:** "Attribute access on possibly-None values" claims 8 occurrences but lists only 7 lines (239, 282, 283, 286, 303, 343, 344). Actual count is 7, not 8.
- **All other errors and suggestions are correct:** 2× `.bind()`, 1× `.health_check` on `None`, 2× `tuple`/`dict` missing type args, 1× uninitialized instance variable. Fixes (None guards, `# type: ignore`, type args) are appropriate.

**Command:** `basedpyright --level error src/frontend/auth/`
**Date:** 2026-06-27
**Errors found:** 14

---

## `backend_auth.py`

### Uninitialized instance variable

**Line 232:** `auth_result_container` is assigned outside `__init__` in a class not decorated with `@final`.

```python
class SomeClass:
    ...
    def some_method(self):
        self.auth_result_container = ...  # error
```

**Suggestion:** Declare the attribute in `__init__` or decorate the class with `@final`.

---

## `backend_login_screen.py`

### `.bind()` not known on Kivy classes (2 occurrences)

**Lines 116, 127:** `bind` is not recognized on `Button`.

Same root cause as other Kivy files — Kivy's dynamic event system is invisible to pyright.

**Suggestion:** See `pyright-app.md` for the cross-cutting Kivy `bind` guidance.

### `.health_check` on possibly-`None` `backend_client`

**Line 153:** `self.backend_client.health_check()` — `backend_client` may be `None`.

**Suggestion:** Add a None guard: `if self.backend_client is None: return` before accessing it.

### `tuple` / `dict` missing type arguments (2 occurrences)

**Lines 172, 257:** Generic types `tuple` and `dict` used without type arguments.

**Suggestion:** Add type arguments, e.g. `tuple[str, ...]`, `dict[str, Any]`.

### Attribute access on possibly-`None` values (8 occurrences)

**Lines 239, 282, 283, 286, 303, 343, 344:** Accessing attributes like `.login`, `.token_info`, `.username`, `.set_auth_token`, `.switch_to_main` on objects that could be `None`.

**Lines 282–283:** `token_info` and `username` accessed on `None` (unwrapped optional).

**Suggestion:** Add None checks or use `assert` before each access, or restructure to avoid the optional.
