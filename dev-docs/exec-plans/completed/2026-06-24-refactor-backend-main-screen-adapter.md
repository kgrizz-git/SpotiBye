# 2026-06-24 Refactor backend_main_screen_adapter.py

Split `src/frontend/screens/backend_main_screen_adapter.py` (~1,100 lines) into a facade + 9 focused mixin modules under `adapter_mixins/`.

## Context

`BackendMainScreenAdapter` bridges `MainScreen` to backend services (playlists, tracks, analysis, export). It has grown to ~1,100 lines mixing:

- Core init, callbacks, error formatting, progress emission (lines 18-112)
- Transient-retry with circuit breaker (lines 114-191)
- Playlist loading with cache/threading (lines 193-265)
- Track fetching (lines 273-338)
- Analysis orchestration (lines 340-397)
- Single-playlist export (lines 399-481)
- Batch/chunked export (lines 483-591)
- Resumable export job state machine (lines 593-762)
- Combined download with recovery logic (lines 764-890)
- Job persistence helpers (lines 892-1010)
- Utility methods: network, cache, auth (lines 1012-1072)
- Factory function + legacy compat (lines 1075-1107)

Public API surface: `screens/__init__.py` re-exports `BackendMainScreenAdapter`, `create_backend_adapter`, `get_reccobeats_api`, and `create_spotify_client_with_refresh`. Direct importers: `backend_app.py` and `test_main_screen_logout.py` import from `backend_main_screen_adapter` explicitly. Runtime consumers: `main_screen_export.py`, `main_screen_cache.py`, and `main_screen_error_popup.py` access the adapter through `screen.backend_adapter` (duck-typed, no direct import). `main_screen.py` receives the adapter via `initialize_with_backend()` and stores it as untyped `self.backend_adapter`. `get_reccobeats_api` and `create_spotify_client_with_refresh` are legacy compat exports with no active in-repo callers beyond `__init__.py`; preserved for external API stability.

The refactored routes/export.ts plan (`dev-docs/exec-plans/completed/2026-06-24-refactor-routes-export-ts.md`) is a useful structural precedent: keep a thin facade, split by concern, keep each module well under ~300 lines.

## Approach: Python Mixin Composition

Each concern becomes a mixin class with methods that reference `self.*` attributes (backend_client, cache_manager, reccobeats_service, network_monitor, progress_callback, error_callback, circuit breaker state). The facade imports all mixins and composes a single `BackendMainScreenAdapter` class via multiple inheritance. Python's MRO resolves cross-mixin method calls at runtime, so `exports.py` can call `self._emit_progress()` from `core.py` or `self._persist_active_export_job()` from `jobs.py` without explicit dependency wiring.

> **File convention:** Every mixin file must include `from __future__ import annotations` as its first importable line (matching the original file and ensuring forward-reference type hints resolve correctly in Python < 3.10). Every mixin file must import its own dependencies directly — MRO only resolves method dispatch, not module-level names. Type hints in extracted code must be preserved verbatim (e.g., the pre-existing bare `func: callable` in `_run_with_transient_retry` stays as-is).

### Cross-Mixin Dependencies

Several methods call `self.*` methods or access `self.*` attributes defined in other mixins. These are resolved by MRO at runtime. Attributes `self.cache_manager`, `self.backend_client`, `self.reccobeats_service`, `self.network_monitor`, `self.progress_callback`, `self.error_callback`, and circuit breaker state (`self._export_circuit_open_until`, `self._export_circuit_reason`) are all set in `core.py.__init__` and are implicitly available to all mixins — they are not repeated in the table below. The table documents only cross-mixin *method* calls for verification during extraction:

| Caller (mixin) | Method | Calls | Target mixin |
|---|---|---|---|
| `ExportsMixin` | `generate_export` | `self._run_with_transient_retry()`, `self._emit_progress()`, `self._format_backend_api_error()` | `core` |
| `ExportsMixin` | `download_export` | `self._run_with_transient_retry()`, `self._emit_progress()`, `self._format_backend_api_error()` | `core` |
| `ExportsMixin` | `generate_batch_export` | `self._run_with_transient_retry()`, `self._emit_progress()`, `self._format_backend_api_error()` | `core` |
| `ExportsMixin` | `generate_batch_export_chunked` | `self._emit_progress()`, `self._run_with_transient_retry()`, `self._format_backend_api_error()` | `core` |
| | | `self._generate_batch_export_resumable()` | `exports_resumable` |
| `ExportsResumableMixin` | `_generate_batch_export_resumable` | `self._emit_progress()`, `self._run_with_transient_retry()`, `self._format_backend_api_error()` | `core` |
| | | `self._load_or_create_resumable_job()`, `self._persist_active_export_job()` | `jobs` |
| `ExportsDownloadMixin` | `download_batch_export` | `self._emit_progress()`, `self._run_with_transient_retry()`, `self._format_backend_api_error()` | `core` |
| | | `self._download_batch_export_any()` | (same mixin) |
| | | `self._generate_batch_export_resumable()` | `exports_resumable` |
| | | `self._persist_active_export_job()`, `self.clear_active_export_job()` | `jobs` |
| `ExportsDownloadMixin` | `_download_batch_export_any` | `self.backend_client` (attribute) | `core` |
| `ExportJobsMixin` | `_load_or_create_resumable_job` | `self._emit_progress()`, `self._run_with_transient_retry()` | `core` |
| | | `self._get_matching_active_export_job()`, `self.clear_active_export_job()` | (same mixin) |
| | | `self.backend_client`, `self.cache_manager` (attributes) | `core` |
| `ExportJobsMixin` | `_persist_active_export_job` | `self.backend_client.trace_id`, `self.cache_manager` (attributes) | `core` |
| `ExportJobsMixin` | `_get_matching_active_export_job` | `self.cache_manager` (attribute) | `core` |
| `ExportJobsMixin` | `clear_active_export_job` | `self.cache_manager` (attribute) | `core` |
| `UtilitiesMixin` | `clear_cache` | `self.cache_manager` (attribute) | `core` |
| `UtilitiesMixin` | `logout` | `self.backend_client`, `self.cache_manager` (attributes) | `core` |
| `PlaylistsMixin` | `load_playlists` | `self.cache_manager`, `self.network_monitor`, `self.backend_client` (attributes) | `core` |
| | | `self._on_playlists_loaded()`, `self._on_error()` | (same mixin) |
| | | `self._format_backend_api_error()` | `core` |
| `TracksMixin` | `get_playlist_details` | `self._format_backend_api_error()` | `core` |
| | | `self.backend_client`, `self.progress_callback` (attributes) | `core` |
| `TracksMixin` | `get_playlist_tracks` | `self.cache_manager`, `self.backend_client` (attributes) | `core` |
| | | `self._format_backend_api_error()` | `core` |
| `AnalysisMixin` | `analyze_playlist` | `self.cache_manager`, `self.reccobeats_service` (attributes) | `core` |

## Target Structure

```
src/frontend/screens/
  backend_main_screen_adapter.py            ~60 lines — facade composing all mixins + factory + legacy compat
  adapter_mixins/
    __init__.py                             ~5 lines  — module docstring
    core.py                                ~175 lines — __init__, callbacks, error formatting, transient retry
    playlists.py                           ~65 lines  — load_playlists, _on_playlists_loaded, _on_error
    tracks.py                              ~66 lines  — get_playlist_details, get_playlist_tracks
    analysis.py                            ~58 lines  — analyze_playlist, get_analysis_status
    exports.py                             ~200 lines — generate_export, download_export, generate_batch_export, generate_batch_export_chunked
    exports_resumable.py                   ~190 lines — _generate_batch_export_resumable
    exports_download.py                    ~130 lines — download_batch_export, _download_batch_export_any
    jobs.py                                ~135 lines — _load_or_create_resumable_job, _persist_active_export_job, _get_matching_active_export_job, get_active_export_job, clear_active_export_job
    utilities.py                           ~65 lines  — get_network_status, refresh_connection, clear_cache, get_cache_stats, is_authenticated, logout
```

### Facade (`backend_main_screen_adapter.py`)

Thin composition that preserves the existing public API surface exactly.

> **Docstring preservation:** The existing class-level docstring on `BackendMainScreenAdapter` and docstrings on `create_backend_adapter`, `get_reccobeats_api`, and `create_spotify_client_with_refresh` must be preserved verbatim in the facade file.

```python
"""Backend integration adapter for existing MainScreen to use backend services."""

from __future__ import annotations

from typing import Optional

from ..services.backend_client import BackendClient
from ..services.reccobeats_backend import ReccoBeatsBackendService
from .adapter_mixins.core import BackendMainScreenAdapterCore
from .adapter_mixins.playlists import PlaylistsMixin
from .adapter_mixins.tracks import TracksMixin
from .adapter_mixins.analysis import AnalysisMixin
from .adapter_mixins.exports import ExportsMixin
from .adapter_mixins.exports_resumable import ExportsResumableMixin
from .adapter_mixins.exports_download import ExportsDownloadMixin
from .adapter_mixins.jobs import ExportJobsMixin
from .adapter_mixins.utilities import UtilitiesMixin


class BackendMainScreenAdapter(
    BackendMainScreenAdapterCore,
    PlaylistsMixin,
    TracksMixin,
    AnalysisMixin,
    ExportsMixin,
    ExportsResumableMixin,
    ExportsDownloadMixin,
    ExportJobsMixin,
    UtilitiesMixin,
):
    # docstring preserved verbatim — see note above
    def __init__(self, backend_client: Optional[BackendClient] = None):
        BackendMainScreenAdapterCore.__init__(self, backend_client)


# docstrings on factory/legacy functions preserved verbatim — see note above
def create_backend_adapter(
    backend_client: Optional[BackendClient] = None,
) -> BackendMainScreenAdapter:
    """..."""
    return BackendMainScreenAdapter(backend_client)


def get_reccobeats_api():
    """..."""
    return ReccoBeatsBackendService()


def create_spotify_client_with_refresh(token_info: dict | None):
    """..."""
    return None


__all__ = [
    "BackendMainScreenAdapter",
    "create_backend_adapter",
    "get_reccobeats_api",
    "create_spotify_client_with_refresh",
]
```

### Mixin Module Contents

#### `adapter_mixins/core.py` — `BackendMainScreenAdapterCore`

- `__init__(self, backend_client)` — original lines 21-38
- `set_callbacks(self, ...)` — original lines 40-56
- `set_trace_id(self, trace_id)` — original lines 58-60
- `_emit_progress(self, message)` — original lines 62-66
- `_format_backend_api_error(self, error, fallback_prefix)` — original lines 68-112
- `_run_with_transient_retry(self, operation_name, func, max_attempts, base_delay)` — original lines 114-191

Imports: `from __future__ import annotations`; `import time`; `from typing import Any, Dict, List, Optional`; `logger` from `....shared.logging_config`; `BackendClient` from `...services.backend_client`; `BackendAPIError` from `...services.backend_client`; `ReccoBeatsBackendService` from `...services.reccobeats_backend`; `get_cache_manager` from `...caching.backend_cache`; `NetworkStatusMonitor` from `...utils.network_utils`.

#### `adapter_mixins/playlists.py` — `PlaylistsMixin`

- `load_playlists(self, force_refresh)` — original lines 193-259
- `_on_playlists_loaded(self, playlists)` — original lines 261-265
- `_on_error(self, error_msg)` — original lines 267-271

Imports: `from __future__ import annotations`; `import threading`; `from typing import Any, Callable, Dict, List, Optional`; `Clock` and `mainthread` from `kivy.clock`; `logger` from `....shared.logging_config`; `BackendAPIError` from `...services.backend_client`; `format_error_message` from `...utils.network_utils`.

#### `adapter_mixins/tracks.py` — `TracksMixin`

- `get_playlist_details(self, playlist_id, force_refresh)` — original lines 273-293
- `get_playlist_tracks(self, playlist_id, force_refresh)` — original lines 295-338

Imports: `from __future__ import annotations`; `from typing import Any, Dict, List, Optional`; `logger` from `....shared.logging_config`; `BackendAPIError` from `...services.backend_client`.

> **Known pre-existing bug:** `get_playlist_tracks` line 330 passes `"Export generation failed"` as the `fallback_prefix` to `_format_backend_api_error` — a copy-paste typo from export logic. **Fix during extraction:** change to `"Failed to load playlist tracks"`.

#### `adapter_mixins/analysis.py` — `AnalysisMixin`

- `analyze_playlist(self, playlist_id, progress_callback)` — original lines 340-381
- `get_analysis_status(self, playlist_id)` — original lines 383-397

Imports: `from __future__ import annotations`; `from typing import Any, Callable, Dict, Optional`; `logger` from `....shared.logging_config`.

#### `adapter_mixins/exports.py` — `ExportsMixin`

- `generate_export(self, playlist_id, format, report_errors, retry_attempts, retry_base_delay)` — original lines 399-443
- `download_export(self, playlist_id, save_path)` — original lines 445-481
- `generate_batch_export(self, playlist_ids, format)` — original lines 483-507
- `generate_batch_export_chunked(self, playlist_ids, format, chunk_size, max_steps, report_errors, resume_context)` — original lines 509-591

Imports: `from __future__ import annotations`; `import time`; `from typing import Any, Dict, List, Optional`; `logger` from `....shared.logging_config`; `BackendAPIError` from `...services.backend_client`.

#### `adapter_mixins/exports_resumable.py` — `ExportsResumableMixin`

- `_generate_batch_export_resumable(self, playlist_ids, format, chunk_size, max_steps, report_errors, resume_context)` — original lines 593-762

Imports: `from __future__ import annotations`; `import time`; `from typing import Any, Dict, List, Optional`; `logger` from `....shared.logging_config`; `BackendAPIError` from `...services.backend_client`.

#### `adapter_mixins/exports_download.py` — `ExportsDownloadMixin`

- `download_batch_export(self, export_id, save_path, report_errors)` — original lines 764-890
- `_download_batch_export_any(self, export_id, mode)` — original lines 896-903 (private helper; stays with its public caller to keep the mixin self-contained)

Imports: `from __future__ import annotations`; `import time`; `from typing import Any, Dict, List, Optional`; `logger` from `....shared.logging_config`; `BackendAPIError` from `...services.backend_client`.

#### `adapter_mixins/jobs.py` — `ExportJobsMixin`

- `get_active_export_job(self)` — original lines 892-894
- `_load_or_create_resumable_job(self, playlist_ids, format, resume_context)` — original lines 905-934
- `_persist_active_export_job(self, status, playlist_ids, format, resume_context)` — original lines 936-966
- `_get_matching_active_export_job(self, playlist_ids, format, resume_context)` — original lines 968-1001
- `clear_active_export_job(self, export_id)` — original lines 1003-1010

Imports: `from __future__ import annotations`; `import time`; `from typing import Any, Dict, List, Optional`; `logger` from `....shared.logging_config`; `BackendAPIError` from `...services.backend_client`.

#### `adapter_mixins/utilities.py` — `UtilitiesMixin`

- `get_network_status(self)` — original lines 1012-1018
- `refresh_connection(self)` — original lines 1020-1022
- `clear_cache(self, cache_type)` — original lines 1024-1046
- `get_cache_stats(self)` — original lines 1048-1050
- `is_authenticated(self)` — original lines 1052-1055
- `logout(self)` — original lines 1057-1072

Imports: `from __future__ import annotations`; `from typing import Any, Dict, Optional`; `logger` from `....shared.logging_config`.

## Implementation Steps

> **Workflow:** Follow Option B incremental delegation (see Risks). After creating each mixin file, temporarily add it to the monolith's inheritance chain, delete the moved methods from the monolith body, and run `pytest`. This validates each extraction independently.

- [ ] Create `src/frontend/screens/adapter_mixins/__init__.py` — needs only a module docstring (no re-exports, no `__all__`; the facade imports individual mixin modules directly)
- [ ] Create `src/frontend/screens/adapter_mixins/core.py` — extract ~175 lines (init, callbacks, error formatting, transient retry) — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/playlists.py` — extract ~65 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/tracks.py` — extract ~66 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/analysis.py` — extract ~58 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/exports.py` — extract ~200 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/exports_resumable.py` — extract ~190 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/exports_download.py` — extract ~130 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/jobs.py` — extract ~135 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Create `src/frontend/screens/adapter_mixins/utilities.py` — extract ~65 lines — **then** inherit in monolith, delete moved methods, run pytest
- [ ] Rewrite `backend_main_screen_adapter.py` as the thin facade (~70–80 lines with docstrings preserved); remove temporary mixin inheritance from prior steps
- [ ] Verify `screens/__init__.py` re-exports still resolve correctly (no changes expected — same module path)
- [ ] Run frontend tests: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
- [ ] Run `./scripts/verify-all.sh` from repo root
- [ ] Update `dev-docs/code-map.md` — add `adapter_mixins/` subdirectory entries to the frontend file index
- [ ] Update `dev-docs/dependency-graph.json` — replace `backend_main_screen_adapter.py` entry with new structure (facade + 9 mixins with correct import edges)
- [ ] Add entry to `CHANGELOG.md` under `## [Unreleased]` → `### Changed`
- [ ] Move this plan to `dev-docs/exec-plans/completed/`, update `dev-docs/exec-plans/completed/README.md`, and check the `[x]` box in `dev-docs/backlog/TO_DO.md`

## Risks and Mitigations

- **Import path stability**: `screens/__init__.py` re-exports from `.backend_main_screen_adapter`. Since the facade keeps the same module path and public names, no caller changes are needed.
- **MRO conflicts**: Multiple mixins all depend on the same `self.*` attributes set in `__init__`. Since `BackendMainScreenAdapterCore` is listed first in the MRO and all other mixins only define methods (no `__init__`), there are no diamond-init issues. Python resolves methods left-to-right in the base class order, so any accidentally duplicated method names would use the leftmost definition.
- **Thread safety**: No logic changes — same `Clock.schedule_once` threading patterns, same `mainthread` decorator placement. All method bodies are extracted verbatim.
- **Test coverage**: `test_main_screen_logout.py` directly imports and inspects `BackendMainScreenAdapter` signatures. `test_main_screen_export.py` and `test_main_screen_cache.py` exercise the adapter indirectly through mocked `screen.backend_adapter` — they serve as regression targets for the export/cache orchestration paths but won't catch mixin wiring bugs on their own. The full frontend suite (step below) is the primary safety net.
- **Commit strategy (Option B — incremental delegation):** After extracting each mixin, temporarily add it to the monolith's inheritance and delete the moved methods from the monolith body. Run `pytest` after each deletion. When only the facade body remains, delete the temporary inheritance and rewrite as the final facade. This gives the "pytest at each step" guarantee and validates each extraction independently. Squash into a single atomic commit/PR at completion.
- **Backup**: Rely on git for rollback. No `backups/` copy needed for this refactor — the monolith is preserved in the pre-refactor commit.

## Success Criteria

- `backend_main_screen_adapter.py` is ≤ 80 lines (thin facade: imports + composition + factory/legacy compat; no business logic)
- No mixin file exceeds 220 lines
- All public names (`BackendMainScreenAdapter`, `create_backend_adapter`, `get_reccobeats_api`, `create_spotify_client_with_refresh`) resolve identically from `screens/__init__.py`
- All existing frontend tests pass without assertion changes
- `./scripts/verify-all.sh` exits clean
- `dev-docs/code-map.md`, `dev-docs/dependency-graph.json`, and `CHANGELOG.md` are updated
