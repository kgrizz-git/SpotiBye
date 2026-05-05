# v2 Extraction Plan

> Goal: progressively extract all code the `src/frontend/` layer actually needs out of
> `src/spotify_playlist_exporter_v2/` so that module can eventually be left as a
> self-contained standalone-mode package with zero coupling to the backend path.
>
> Each phase is independently releasable. Do not start a phase until the previous one is
> merged and tests are green.

---

## Coupling snapshot — after Phase 1–3

All items below were resolved. The only remaining v2 import in `src/frontend/` is:

| Frontend file | v2 symbol | v2 source |
|---|---|---|
| `app/backend_app.py` | `MainScreen` | `screens/main_screen.py` (4 269 lines) |

Original coupling (for reference):

| Frontend file | v2 symbol imported | v2 source | Status |
|---|---|---|---|
| `app/backend_app.py` | `MainScreen` | `screens/main_screen.py` | **Phase 4** |
| `app/backend_app.py` | `logger` | `logging_config.py` | ✅ Phase 1-A |
| `app/backend_app.py` | `diagnose_macos_issues`, `set_window_basics` | `utils/platform_utils.py` | ✅ Phase 1-B |
| `app/backend_app.py` | `current_export_job` | `state.py` | ✅ Phase 1-C |
| `screens/backend_main_screen_adapter.py` | `logger` | `logging_config.py` | ✅ Phase 1-A |
| `screens/cache_explorer_adapter.py` | `logger`, `CacheExplorerPopup` | `logging_config.py`, `ui/cache_explorer.py` | ✅ Phase 1-A / 3 |
| `ui/backend_cache_explorer.py` | `logger`, `CacheExplorerPopup` | `logging_config.py`, `ui/cache_explorer.py` | ✅ Phase 1-A / 3 |

---

## ✅ Phase 1 — Leaf extractions (DONE, 2026-05-05)

### ✅ 1-A  `logging_config.py` → `src/shared/logging_config.py`

- Created `src/shared/__init__.py` and `src/shared/logging_config.py`.
- `src/spotify_playlist_exporter_v2/logging_config.py` replaced with a 1-line shim:
  `from shared.logging_config import configure_logging, logger`.
- All four frontend import sites updated to `from ...shared.logging_config import logger`.

Files changed:
- `src/shared/logging_config.py` (new)
- `src/spotify_playlist_exporter_v2/logging_config.py` (shim)
- `src/frontend/app/backend_app.py`
- `src/frontend/screens/backend_main_screen_adapter.py`
- `src/frontend/screens/cache_explorer_adapter.py`
- `src/frontend/ui/backend_cache_explorer.py`

### ✅ 1-B  `utils/platform_utils.py` → `src/frontend/utils/platform_utils.py`

- Copied file with internal logger import updated to `from ...shared.logging_config import logger`.
- `src/spotify_playlist_exporter_v2/utils/platform_utils.py` replaced with a 1-line shim:
  `from frontend.utils.platform_utils import *`.
- `backend_app.py` import updated to `from ..utils.platform_utils import ...`.

Files changed:
- `src/frontend/utils/platform_utils.py` (new)
- `src/spotify_playlist_exporter_v2/utils/platform_utils.py` (shim)
- `src/frontend/app/backend_app.py`

### ✅ 1-C  `state.py` → `src/frontend/state.py`

- Created `src/frontend/state.py` with `current_export_job: Optional[Dict[str, Any]] = None`.
- `backend_app.py` lazy import updated to `from ..state import current_export_job`.
- v2's `state.py` left as-is (its `current_export_job` was already effectively disconnected
  from the frontend due to `global` rebinding in `main_screen.py`).

Files changed:
- `src/frontend/state.py` (new)
- `src/frontend/app/backend_app.py`

---

## ✅ Phase 2 — Exception class extraction (DONE, 2026-05-05)

- Created `src/shared/exceptions.py` with all six classes:
  `ExportError`, `InsufficientDiskSpaceError`, `PermissionError`,
  `NetworkError`, `ExportFormatError`, `ValidationError`.
- Replaced the 40-line class bodies in `main_screen.py` (lines 80–119) with
  `from shared.exceptions import (...)`.

Files changed:
- `src/shared/exceptions.py` (new)
- `src/spotify_playlist_exporter_v2/screens/main_screen.py`

---

## ✅ Phase 3 — CacheExplorerPopup: frontend-native version (DONE, 2026-05-05)

**What was discovered:** `BackendCacheExplorerPopup` already inherited from `Popup`
directly — not from `CacheExplorerPopup`. It embedded `CacheExplorerPopup` as a child
widget and populated it via `cache_data` attribute + `populate_playlists_column()` calls.
The disk-cache calls (`PersistentCache`, `get_cached_spotify_track`) lived entirely inside
the embedded v2 class.

**What was done:**
- Created `src/frontend/ui/cache_explorer.py` — a full reimplementation of
  `CacheExplorerPopup` with no disk-cache dependencies. Data is injected via:
  - `cache_data["playlists"]` — playlist list (set by `BackendCacheExplorerPopup`)
  - `cache_data["tracks_by_playlist"][playlist_id]` — per-playlist track list
  - `cache_data["features_by_track"][spotify_id]` — per-track ReccoBeats features
  - Background worker returns an empty structure immediately (no filesystem access).
- `backend_cache_explorer.py`: updated import to `from .cache_explorer import CacheExplorerPopup`.
  The monkey-patch on `_on_cache_data_loaded` is retained — it prevents the Clock-scheduled
  empty payload from overwriting backend playlist data already set synchronously.
- `cache_explorer_adapter.py`: updated import to `from ..ui.cache_explorer import CacheExplorerPopup`.
  The no-backend fallback now returns the frontend version (shows empty state gracefully
  rather than attempting disk access).
- `test_cache_explorer_mock.py`: updated stale `sys.modules` patch keys to
  `frontend.ui.cache_explorer` and `shared.logging_config`.

Files changed:
- `src/frontend/ui/cache_explorer.py` (new)
- `src/frontend/ui/backend_cache_explorer.py` (import only)
- `src/frontend/screens/cache_explorer_adapter.py` (import only)
- `src/frontend/tests/test_cache_explorer_mock.py` (mock paths)

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

1. All `from shared.*` and `from frontend.*` imports in the v2 shim files can
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

| Phase | Effort | Risk | Status |
|---|---|---|---|
| 1-A  logging_config | 30 min | very low | ✅ done |
| 1-B  platform_utils | 30 min | very low | ✅ done |
| 1-C  state.py | 45 min | low | ✅ done |
| 2    exceptions | 30 min | low | ✅ done |
| 3    frontend CacheExplorerPopup | 2–3 h | medium | ✅ done |
| 4-A  BackendPlaylistCard | 3–4 h | medium | pending |
| 4-B  login flow guards | 1–2 h | medium | pending |
| 4-C  BackendMainScreen | 2–3 h | medium | pending |
| 5    cleanup + verify | 1 h | low | pending |
