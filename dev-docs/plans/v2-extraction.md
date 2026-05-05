# v2 Extraction Plan

> Goal: progressively extract all code the `src/frontend/` layer actually needs out of
> `src/spotify_playlist_exporter_v2/` so that module can eventually be left as a
> self-contained standalone-mode package with zero coupling to the backend path.
>
> Each phase is independently releasable. Do not start a phase until the previous one is
> merged and tests are green.

---

## Current coupling snapshot

| Frontend file | v2 symbol imported | v2 source |
|---|---|---|
| `app/backend_app.py` | `MainScreen` | `screens/main_screen.py` (4 269 lines) |
| `app/backend_app.py` | `logger` | `logging_config.py` (21 lines) |
| `app/backend_app.py` | `diagnose_macos_issues`, `set_window_basics` | `utils/platform_utils.py` |
| `app/backend_app.py` | `current_export_job` | `state.py` (17 lines) |
| `screens/backend_main_screen_adapter.py` | `logger` | `logging_config.py` |
| `screens/cache_explorer_adapter.py` | `logger`, `CacheExplorerPopup` | `logging_config.py`, `ui/cache_explorer.py` |
| `ui/backend_cache_explorer.py` | `logger`, `CacheExplorerPopup` | `logging_config.py`, `ui/cache_explorer.py` |

The v2 files with no v2-internal imports at all (safe to move with a shim left behind):

| File | Lines | Internal deps |
|---|---|---|
| `logging_config.py` | 21 | none |
| `state.py` | 17 | none |
| `utils/platform_utils.py` | 412 | none |
| `config.py` | 56 | none |

---

## Phase 1 — Leaf extractions (zero risk)

**What:** Move files that have no internal v2 dependencies into `src/shared/` (for things
used by both v2 and frontend) or `src/frontend/utils/` (for things only used by
frontend). Leave a one-line re-export shim in the v2 location so the standalone path
keeps working without any changes.

### 1-A  `logging_config.py` → `src/shared/logging_config.py`

`logging_config.py` is imported by every single frontend file and by most of v2. It has
no deps inside the project. It belongs in `src/shared/`.

Steps:
1. Create `src/shared/__init__.py` (empty).
2. Create `src/shared/logging_config.py` — copy the 21-line file verbatim.
3. Replace `src/spotify_playlist_exporter_v2/logging_config.py` with a one-liner shim:
   ```python
   from src.shared.logging_config import configure_logging, logger  # noqa: F401
   ```
4. Update all four frontend import sites to use `from src.shared.logging_config import logger`.
5. Run tests. If green, done.

Files changed:
- `src/shared/logging_config.py` (new)
- `src/spotify_playlist_exporter_v2/logging_config.py` (shim)
- `src/frontend/app/backend_app.py` (import)
- `src/frontend/screens/backend_main_screen_adapter.py` (import)
- `src/frontend/screens/cache_explorer_adapter.py` (import)
- `src/frontend/ui/backend_cache_explorer.py` (import)

### 1-B  `utils/platform_utils.py` → `src/frontend/utils/platform_utils.py`

`platform_utils.py` is only imported by `backend_app.py` in the frontend path. v2 itself
never imports it directly (only `app.py` does, which is the standalone entrypoint). It
logically belongs in frontend utilities.

Steps:
1. Copy `src/spotify_playlist_exporter_v2/utils/platform_utils.py` to
   `src/frontend/utils/platform_utils.py` verbatim.
2. Replace the v2 original with a shim:
   ```python
   from src.frontend.utils.platform_utils import *  # noqa: F401,F403
   ```
3. Update `backend_app.py` imports to `from src.frontend.utils.platform_utils import ...`.
4. Run tests.

Files changed:
- `src/frontend/utils/platform_utils.py` (new)
- `src/spotify_playlist_exporter_v2/utils/platform_utils.py` (shim)
- `src/frontend/app/backend_app.py` (import)

### 1-C  `state.py` → `src/frontend/state.py`

`backend_app.py` imports `current_export_job` from `state.py` only to cancel in-flight
exports. That state variable is only written by `main_screen.py` (v2) but read by the
frontend. Long-term the backend path should own its own job state.

For now, a minimal safe move:
1. Create `src/frontend/state.py` containing only the variables the frontend cares about:
   ```python
   from typing import Any, Dict, Optional
   current_export_job: Optional[Dict[str, Any]] = None
   ```
2. In `src/spotify_playlist_exporter_v2/state.py`, import and re-export it so `main_screen.py`
   still writes to the same object:
   ```python
   from src.frontend.state import current_export_job  # noqa: F401
   # remaining v2-only state below
   auth_token = None
   ...
   ```
3. Update `backend_app.py` to import from `src.frontend.state`.
4. Run tests.

Files changed:
- `src/frontend/state.py` (new)
- `src/spotify_playlist_exporter_v2/state.py` (partial shim)
- `src/frontend/app/backend_app.py` (import)

---

## Phase 2 — Exception class extraction

**What:** The top of `screens/main_screen.py` (lines 81–120) defines six exception
classes that conceptually belong to the export domain, not to the UI layer:

```
ExportError, InsufficientDiskSpaceError, PermissionError,
NetworkError, ExportFormatError, ValidationError
```

These are not imported by any frontend file today, but they should be before we start
breaking up `main_screen.py`.

Steps:
1. Create `src/shared/exceptions.py` with those six classes copied verbatim.
2. At the top of `main_screen.py` add:
   ```python
   from src.shared.exceptions import (
       ExportError, InsufficientDiskSpaceError, PermissionError,
       NetworkError, ExportFormatError, ValidationError,
   )
   ```
   and remove the class bodies from `main_screen.py`.
3. Run tests — standalone mode must still work (the classes are defined in the same
   namespace they were before from v2's perspective).

Files changed:
- `src/shared/exceptions.py` (new)
- `src/spotify_playlist_exporter_v2/screens/main_screen.py` (remove class bodies, add import)

---

## Phase 3 — CacheExplorerPopup: replace inheritance with composition

**What:** `backend_cache_explorer.py` and `cache_explorer_adapter.py` both import
`CacheExplorerPopup` from v2's `ui/cache_explorer.py`.  `CacheExplorerPopup` depends on
`PersistentCache` and `track_cache` — disk-level caches that don't exist in the backend
path.

`backend_cache_explorer.py` already subclasses `CacheExplorerPopup` with backend-aware
overrides. The cleanest path is to promote the backend version to a fully self-contained
class that doesn't inherit from `CacheExplorerPopup` at all.

### 3-A  Audit what `BackendCacheExplorer` actually overrides

Read `ui/backend_cache_explorer.py` and identify every method that is either overridden
or called from the parent. Anything not overridden is a v2 disk-cache behaviour that
needs a backend-API equivalent or can be removed in the backend path.

### 3-B  Rewrite `BackendCacheExplorer` as a standalone Kivy popup

1. Duplicate the relevant UI structure from `CacheExplorerPopup` into
   `backend_cache_explorer.py` (layout, labels, buttons) — no inheritance from v2.
2. Replace all disk-cache method calls with `BackendClient` API calls (the cache
   inspection endpoints the backend already exposes, or raw requests if needed).
3. Delete the `from ... import CacheExplorerPopup` line from `backend_cache_explorer.py`.

### 3-C  Update `cache_explorer_adapter.py`

Once `BackendCacheExplorer` is self-contained, `cache_explorer_adapter.py` no longer
needs to import `CacheExplorerPopup` either. Update it to instantiate
`BackendCacheExplorer` directly.

Files changed:
- `src/frontend/ui/backend_cache_explorer.py` (rewrite, no v2 inheritance)
- `src/frontend/screens/cache_explorer_adapter.py` (remove v2 import)

---

## Phase 4 — Decompose `main_screen.py` (multi-step)

**Context:** `main_screen.py` is 4 269 lines and is the last hard dependency between
`backend_app.py` and v2. It already has the `initialize_with_backend()` seam, so the
screen *runs* in backend mode, but it still pulls in `LoginScreen`, `ReccoBeatsAPI`,
`PersistentCache`, `TrackCache`, `AnalysisTask`, and every UI component in v2.

The strategy is extract-and-replace in vertical slices, not a full rewrite at once.

### 4-A  Extract `PlaylistCard` logic needed by the backend path

`main_screen.py` creates `PlaylistCard` widgets (from `ui/playlist_card.py`, 4 552
lines). In backend mode, `PlaylistCard` still tries to use local disk cache and direct
ReccoBeats HTTP. The goal is a `BackendPlaylistCard` in `src/frontend/ui/` that:

- Takes `BackendClient` as its data source.
- Removes the direct ReccoBeats / PersistentCache calls.
- Is instantiated by `MainScreen` when `backend_mode_enabled` is True (branch on
  `self.backend_mode_enabled` in `_create_playlist_widgets()` or equivalent).

Steps:
1. Read `playlist_card.py` lines 207+ (`PlaylistCard` class) and identify which methods
   hit disk cache or ReccoBeats directly.
2. Create `src/frontend/ui/backend_playlist_card.py` — a subclass or full replacement
   that delegates those calls to `BackendClient`.
3. In `main_screen.py`, conditionally import and use `BackendPlaylistCard` when in
   backend mode.

### 4-B  Replace standalone login flow in `main_screen.py` backend path

`main_screen.py` imports `LoginScreen` from v2's auth module and uses it for the
standalone OAuth flow. In backend mode, the login is already handled by
`BackendLoginScreen`. Audit all references to `login_screen` / `LoginScreen` inside
`main_screen.py` behind `backend_mode_enabled` checks, and short-circuit or skip them
when in backend mode so the import can eventually be removed.

### 4-C  Create `src/frontend/screens/backend_main_screen.py`

Once 4-A and 4-B are done, the only reason `main_screen.py` is still used in backend
mode is that `backend_app.py` instantiates it directly. At that point:

1. Create `src/frontend/screens/backend_main_screen.py` that subclasses `MainScreen`
   but:
   - Overrides `build_ui()` to inject backend-only widgets where needed.
   - Removes all conditional `if not self.backend_mode_enabled` dead paths.
   - Does not import `LoginScreen`, `ReccoBeatsAPI`, `PersistentCache`, or `TrackCache`.
2. Update `backend_app.py` to instantiate `BackendMainScreen` instead of `MainScreen`.
3. The v2 `MainScreen` now has no frontend callers. Leave it in place for the standalone
   path.

Files changed across 4-A–4-C:
- `src/frontend/ui/backend_playlist_card.py` (new)
- `src/frontend/screens/backend_main_screen.py` (new)
- `src/frontend/app/backend_app.py` (swap import to `BackendMainScreen`)
- `src/spotify_playlist_exporter_v2/screens/main_screen.py` (add backend-mode guards,
  no removals until Phase 5)

---

## Phase 5 — Remove v2 shims and verify standalone still works

After all phases above are merged:

1. All `from src.shared.*` and `from src.frontend.*` imports in the v2 shim files can
   be replaced with the original local definitions (reverting the shims), OR the shims
   can be left permanently — either is fine. The standalone path was never broken.
2. Run the full test suite including the standalone entrypoint (`python -m
   spotify_playlist_exporter_v2`) to confirm nothing regressed.
3. `backend_app.py` should no longer import anything from `src/spotify_playlist_exporter_v2/`.
   Verify with:
   ```
   grep -r "spotify_playlist_exporter_v2" src/frontend/
   ```
   Expected result: no output.
4. Update `dev-docs/dependency-graph.json` and `dev-docs/code-map.md` to remove all
   frontend→v2 edges.

---

## Ordering and risk summary

| Phase | Effort | Risk | Can merge independently |
|---|---|---|---|
| 1-A  logging_config | 30 min | very low | yes |
| 1-B  platform_utils | 30 min | very low | yes |
| 1-C  state.py | 45 min | low | yes |
| 2    exceptions | 30 min | low | yes |
| 3-A  audit cache explorer | 1 h | low | yes (no code changes) |
| 3-B/C  BackendCacheExplorer rewrite | 2–3 h | medium | yes |
| 4-A  BackendPlaylistCard | 3–4 h | medium | yes |
| 4-B  login flow guards | 1–2 h | medium | yes |
| 4-C  BackendMainScreen | 2–3 h | medium | yes |
| 5    cleanup + verify | 1 h | low | yes |

Do phases 1-A, 1-B, 1-C, and 2 first — they are mechanical moves with shims and impose
zero regression risk. Phase 3 and 4 require reading the large files carefully before
touching them.
