# v2 Extraction Plan

> Goal: progressively extract all code the `src/frontend/` layer actually needs out of
> `src/spotify_playlist_exporter_v2/` so that module can eventually be left as a
> self-contained standalone-mode package with zero coupling to the backend path.
>
> Each phase is independently releasable. Do not start a phase until the previous one is
> merged and tests are green.

---

## Coupling snapshot — after Phase 1–4

All direct v2 imports from `src/frontend/` are resolved. The only remaining coupling is:

| Frontend file | v2 dependency | nature |
|---|---|---|
| `screens/backend_main_screen.py` | `MainScreen` (base class) | indirect — v2 still loaded at runtime |

This is addressed in Phase 5 by cutting the inheritance and reimplementing (or inlining)
the backend-mode-only logic directly in `BackendMainScreen`.

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

## ✅ Phase 4 — Decompose `main_screen.py` (DONE, 2026-05-06)

**What was discovered:** `PlaylistCard` already branches on `_is_backend_authenticated_app()`
for its refresh flow, so it was mostly backend-aware. The real problems were:

1. `display_playlists_with_cache` and `_perform_sort` both instantiated v2 `PlaylistCard`
   unconditionally — dragging in `ReccoBeatsAPI`, `PersistentCache`, `AnalysisTask` etc.
2. `update_status_with_cache_info` called `persistent_cache.get_cache_stats()` in the
   backend path (meaningless and a v2 dependency).
3. `backend_app.py` imported `MainScreen` directly from v2.
4. `LoginScreen` is not imported by `main_screen.py` — only `create_spotify_client_with_refresh`
   is, and it is already fully guarded by `if self.backend_mode_enabled` / early-raises,
   so 4-B required no changes to `main_screen.py`.

**What was done:**

### ✅ 4-A  `BackendPlaylistCard` — `src/frontend/ui/backend_playlist_card.py`

- Fresh `BackendPlaylistCard(BoxLayout)` — zero v2 imports.
- Builds the same card visual: `AsyncImage` cover, name/tracks/owner labels, `CheckBox`.
- Exposes `self.playlist_data` and `self.checkbox` — the full interface `MainScreen` needs.
- Uses standard Kivy `AsyncImage` in place of v2's `CachedAsyncImage`.

### ✅ 4-B  Login flow audit — no changes needed

- `main_screen.py` imports `create_spotify_client_with_refresh` (not `LoginScreen`).
- Every call site is already behind `if self.backend_mode_enabled` guards or raises
  `NetworkError` immediately in backend mode.  No edits required.

### ✅ 4-C  `BackendMainScreen` — `src/frontend/screens/backend_main_screen.py`

- `BackendMainScreen(MainScreen)` subclasses v2 `MainScreen` and overrides three methods:
  - `display_playlists_with_cache` — uses `BackendPlaylistCard` instead of `PlaylistCard`
  - `_perform_sort` — same swap for the sort/rebuild path
  - `update_status_with_cache_info` — replaces `persistent_cache.get_cache_stats()` with
    a simple playlist-count string
- `backend_app.py` now imports `BackendMainScreen` from `frontend.screens.backend_main_screen`
  and instantiates it.  **The direct v2 import in `backend_app.py` is gone.**

Files changed:
- `src/frontend/ui/backend_playlist_card.py` (new)
- `src/frontend/screens/backend_main_screen.py` (new)
- `src/frontend/app/backend_app.py` (swap import + instantiation)

**Remaining coupling:** `BackendMainScreen` still subclasses v2 `MainScreen`, so v2 is
loaded at runtime via `backend_main_screen.py`.  Breaking that inheritance is Phase 5 work.

---

## ✅ Phase 5 — Remove v2 shims and verify standalone still works (DONE, 2026-05-07)

**What was done:**

1. **`ResponsiveGridLayout`** extracted to `src/frontend/ui/layouts.py`. v2's
   `ui/layouts.py` replaced with a shim: `from frontend.ui.layouts import ResponsiveGridLayout`.

2. **`src/frontend/screens/main_screen.py`** — new backend-mode-only `MainScreen`.
   Copies the full UI + backend-mode methods from v2's `main_screen.py` but strips all
   standalone-only code (export_worker, begin_export, persistent_cache, ReccoBeats analysis,
   PlaylistCard). Zero imports from `spotify_playlist_exporter_v2`. Uses `shared.*`,
   `frontend.*`, and Kivy only.

3. **`BackendMainScreen`** updated: `from .main_screen import MainScreen` (was v2 import).

4. **Grep check passed**: `grep -r "spotify_playlist_exporter_v2" src/frontend/` → no output.

5. **52 tests passed, 1 skipped** (same as pre-phase baseline).

6. **`dev-docs/dependency-graph.json`** and **`dev-docs/code-map.md`** updated — all
   frontend→v2 edges removed.

v2's `main_screen.py` was left as-is (full standalone implementation, untouched). The
existing v2 shims (`logging_config.py`, `utils/platform_utils.py`) were left permanently.

Files changed:
- `src/frontend/ui/layouts.py` (new)
- `src/frontend/screens/main_screen.py` (new)
- `src/frontend/screens/backend_main_screen.py` (import updated)
- `src/spotify_playlist_exporter_v2/ui/layouts.py` (shim)
- `dev-docs/dependency-graph.json`
- `dev-docs/code-map.md`

---

## Ordering and risk summary

| Phase | Effort | Risk | Status |
|---|---|---|---|
| 1-A  logging_config | 30 min | very low | ✅ done |
| 1-B  platform_utils | 30 min | very low | ✅ done |
| 1-C  state.py | 45 min | low | ✅ done |
| 2    exceptions | 30 min | low | ✅ done |
| 3    frontend CacheExplorerPopup | 2–3 h | medium | ✅ done |
| 4-A  BackendPlaylistCard | 3–4 h | medium | ✅ done |
| 4-B  login flow guards | 1–2 h | medium | ✅ done (no-op — already guarded) |
| 4-C  BackendMainScreen | 2–3 h | medium | ✅ done |
| 5    cleanup + verify | 1 h | low | ✅ done |
