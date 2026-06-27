# Pyright Assessment — `src/frontend/services/`

**NEEDS REVIEW**

## Verified Findings (2026-06-27)

- **Error count:** 3 ✓ — confirmed matches actual
- **Issues confirmed:**
  - `Dict` missing type arguments at line 23 ✓
  - Return type mismatch (`Unknown | str` not assignable to `Dict[str, Any]`) at line 144 ✓
  - `NetworkTimeoutError` not defined at line 131 — **real runtime bug risk** ✓
- **All suggestions are correct:** add type args, widen return type, add the import for `NetworkTimeoutError`

**Command:** `basedpyright --level error src/frontend/services/`
**Date:** 2026-06-27
**Errors found:** 3

---

## `backend_client.py`

### `Dict` missing type arguments

**Line 23:** `Dict` used without type arguments.

```python
from typing import Dict
...
some_var: Dict  # error
```

**Suggestion:** Add type arguments, e.g. `Dict[str, Any]`.

### Return type mismatch — `Unknown | str` not assignable to `Dict[str, Any]`

**Line 144:** A return value of type `Unknown | str` is returned where `Dict[str, Any]` is expected.

The function's return type is narrowed to `Dict[str, Any]`, but the actual returned value could be a `str`.

**Suggestion:** Ensure all return paths return `Dict[str, Any]` or widen the return type to `Dict[str, Any] | str`.

---

## `reccobeats_backend.py`

### `NetworkTimeoutError` not defined

**Line 131:** `NetworkTimeoutError` is referenced but not imported.

```python
raise NetworkTimeoutError(...)  # NameError at runtime
```

**Suggestion:** Add the import: `from ..utils.network_utils import NetworkTimeoutError`.
