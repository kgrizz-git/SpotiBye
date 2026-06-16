# Main Screen Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⚠️ Pre-implementation review:** See [2026-06-16-main-screen-refactor-review.md](2026-06-16-main-screen-refactor-review.md). Latest state: 2 critical errors remaining, 5 design gaps, 7 research items complete. Critical issues:
> - Task 4 `open_cache_explorer` calls `create_cache_explorer(cache_manager)` but the real function takes zero arguments.
> - Task 2 `cancel_export` adds cancellation polling to the worker that is not present in current code — needs explicit check-point enumeration and CHANGELOG entry (legitimate bug fix per the original author, but the plan text doesn't frame it that way).
> - Task 1 silently changes the filename format (`Spotify_Playlists_...` → `spotify_playlists_...`) without a CHANGELOG entry, violating the Goal's "no behavior change" promise.

**Goal:** Refactor `src/frontend/screens/main_screen.py` into smaller, testable units without changing playlist loading, selection, export, resume, cache, or logout behavior.

**Architecture:** Start by extracting pure helpers and stabilizing export job state, then split low-risk screen flows, then move export orchestration behind a narrow object. Keep `MainScreen` as the Kivy `Screen` owner and keep `BackendMainScreen` as the playlist-card implementation until the factory seam is real.

**Tech Stack:** Python 3, Kivy/KivyMD, pytest, existing frontend backend adapter and cache manager.

---

## Assessment Accuracy Check

The assessment in `dev-docs/refactor-assessments/main_screen-refactor-assessment-2026-06-15.md` is directionally correct: `main_screen.py` is 1,940 lines, mixes UI construction with export orchestration, has no direct `BackendClient` dependency, uses `Clock.schedule_once` heavily, and has no tests that directly exercise `MainScreen` or `BackendMainScreen`.

Corrections to apply while implementing this plan:

- `src/frontend/screens/main_screen.py` currently has 65 `def` methods, not about 45.
- The assessment says "seven" responsibilities but lists nine.
- `current_export_job` is not set by `main_screen.py` or `backend_app.py`; it is only imported and read/written if already truthy. Treat cancellation state as currently broken or vestigial, not as an active global job store.
- `MainScreen` does not directly import `BackendMainScreenAdapter`; coupling is structural through the untyped `backend_adapter` attribute and nine called methods.
- `BackendPlaylistCard` is imported by `backend_main_screen.py`, not `main_screen.py`. `_make_playlist_widget()` exists only on `BackendMainScreen` and is not currently a real base-class override.
- `_get_filtered_playlists()` and `_sort_playlists()` are not dead code; `BackendMainScreen` calls both. `_show_error_dialog()`, `_log_error()`, and `_update_export_status()` appear unused.
- The test audit is incomplete: there are more frontend test files than listed, but the conclusion that screen/export orchestration is untested still holds.
- The cache explorer adapter lives at `src/frontend/screens/cache_explorer_adapter.py`; do not introduce a `frontend.caching.cache_explorer_adapter` import.

## File Structure Target

- Modify: `src/frontend/screens/main_screen.py` — keep Kivy lifecycle, widget ownership, and thin delegation wrappers.
- Modify: `src/frontend/screens/backend_main_screen.py` — switch display/sort creation to a real widget factory seam.
- Modify: `src/frontend/state.py` — replace raw mutable global access with small job-state functions.
- Create: `src/frontend/screens/main_screen_filenames.py` — pure filename and format helpers.
- Create: `src/frontend/screens/main_screen_scheduler.py` — one Kivy scheduling adapter used by extracted flows.
- Create: `src/frontend/screens/main_screen_cache.py` — cache popup and cache explorer flow.
- Create: `src/frontend/screens/main_screen_logout.py` — logout confirmation flow.
- Create: `src/frontend/screens/main_screen_error_popup.py` — backend error details popup and resume/discard action wiring.
- Create: `src/frontend/screens/main_screen_export.py` — export orchestration object after tests exist.
- Create: `src/frontend/tests/test_main_screen_filenames.py` — pure unit tests.
- Create: `src/frontend/tests/test_main_screen_state.py` — job-state unit tests.
- Create: `src/frontend/tests/test_main_screen_sort_selection.py` — screen-free tests for search/sort/selection helpers if extracted in this phase.
- Modify: `CHANGELOG.md` — required when cancellation or user-visible export behavior changes.

---

### Task 1: Extract Filename And Format Helpers

**Files:**
- Create: `src/frontend/tests/test_main_screen_filenames.py`
- Create: `src/frontend/screens/main_screen_filenames.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Write failing tests**

Create `src/frontend/tests/test_main_screen_filenames.py`:

```python
from __future__ import annotations

from datetime import datetime

from src.frontend.screens.main_screen_filenames import (
    generate_default_filename,
    get_file_extension,
    increment_filename_suffix,
    sanitize_export_filename_component,
)


class DummyApp:
    username = "Ada Lovelace"


def test_get_file_extension_maps_supported_formats() -> None:
    assert get_file_extension("xlsx") == ".xlsx"
    assert get_file_extension("XLSX") == ".xlsx"
    assert get_file_extension("csv") == ".csv"
    assert get_file_extension("json") == ".json"
    assert get_file_extension("unknown") == ".xlsx"


def test_generate_default_filename_uses_username_date_and_extension() -> None:
    now = datetime(2026, 6, 16, 9, 30, 0)
    assert (
        generate_default_filename(DummyApp(), "csv", now=now)
        == "spotify_playlists_Ada_Lovelace_20260616.csv"
    )


def test_increment_filename_suffix_preserves_extension() -> None:
    assert increment_filename_suffix("spotify.xlsx") == "spotify_1.xlsx"
    assert increment_filename_suffix("spotify_1.xlsx") == "spotify_2.xlsx"
    assert increment_filename_suffix("spotify_001.csv") == "spotify_2.csv"


def test_sanitize_export_filename_component_limits_unsafe_characters() -> None:
    assert sanitize_export_filename_component("Road/Trip:*2026") == "Road_Trip_2026"
    assert sanitize_export_filename_component("") == "playlist"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/frontend/tests/test_main_screen_filenames.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.frontend.screens.main_screen_filenames'`.

- [ ] **Step 3: Implement helper module**

Create `src/frontend/screens/main_screen_filenames.py`:

```python
"""Filename and export-format helpers for MainScreen."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Optional


def get_file_extension(format_type: str) -> str:
    normalized = (format_type or "xlsx").strip().lower()
    return { "xlsx": ".xlsx", "csv": ".csv", "json": ".json" }.get(
        normalized, ".xlsx"
    )


def selected_export_format(format_text: str) -> str:
    normalized = (format_text or "XLSX").strip().lower()
    return normalized if normalized in {"xlsx", "csv", "json"} else "xlsx"


def generate_default_filename(
    app: Any, format_type: str = "xlsx", now: Optional[datetime] = None
) -> str:
    username = getattr(app, "username", "user") or "user"
    safe_username = re.sub(r"[^A-Za-z0-9._ -]+", "_", str(username)).strip()
    safe_username = safe_username.replace(" ", "_") or "user"
    current = now or datetime.now()
    return (
        f"spotify_playlists_{safe_username}_{current.strftime('%Y%m%d')}"
        f"{get_file_extension(format_type)}"
    )


def increment_filename_suffix(filename: str) -> str:
    base, extension = os.path.splitext(filename)
    match = re.search(r"_(\d+)$", base)
    if match:
        number = int(match.group(1)) + 1
        base = base[: match.start()]
    else:
        number = 1
    return f"{base}_{number}{extension}"


def sanitize_export_filename_component(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", value or "").strip()
    safe = re.sub(r"_+", "_", safe)
    return safe[:80] if safe else "playlist"
```

- [ ] **Step 4: Wire `MainScreen` to helper module**

In `src/frontend/screens/main_screen.py`, import helpers and replace the five existing helper method bodies with delegation:

```python
from .main_screen_filenames import (
    generate_default_filename,
    get_file_extension,
    increment_filename_suffix,
    sanitize_export_filename_component,
    selected_export_format,
)
```

```python
def _sanitize_export_filename_component(self, value: str) -> str:
    return sanitize_export_filename_component(value)


def _get_file_extension(self, format_type: str) -> str:
    return get_file_extension(format_type)


def _selected_export_format(self) -> str:
    text = getattr(getattr(self, "format_spinner", None), "text", "XLSX")
    return selected_export_format(text)


def _generate_default_filename(self, format_type: str = "xlsx") -> str:
    return generate_default_filename(App.get_running_app(), format_type)


def _increment_filename_suffix(self, filename: str) -> str:
    return increment_filename_suffix(filename)
```

Leave `_refresh_filename_after_export()` in `main_screen.py` for now because it mutates `filename_input`.

- [ ] **Step 5: Run focused tests**

Run: `pytest src/frontend/tests/test_main_screen_filenames.py -q`

Expected: PASS.

- [ ] **Step 6: Run frontend tests**

Run: `pytest src/frontend/tests -q`

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 7: Commit**

```bash
git add src/frontend/tests/test_main_screen_filenames.py src/frontend/screens/main_screen_filenames.py src/frontend/screens/main_screen.py
git commit -m "refactor: extract main screen filename helpers"
```

---

### Task 2: Stabilize Export Job State Before Moving Export Code

**Files:**
- Create: `src/frontend/tests/test_main_screen_state.py`
- Modify: `src/frontend/state.py`
- Modify: `src/frontend/screens/main_screen.py`
- Modify: `src/frontend/app/backend_app.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write failing tests for job state**

Create `src/frontend/tests/test_main_screen_state.py`:

```python
from __future__ import annotations

from src.frontend import state


def teardown_function() -> None:
    state.clear_current_export_job()


def test_set_and_clear_current_export_job() -> None:
    job = state.set_current_export_job(
        job_id="job-1",
        playlist_ids=["playlist-1"],
        export_format="xlsx",
        output_path="/tmp/export.xlsx",
    )

    assert state.get_current_export_job() == job
    assert job["job_id"] == "job-1"
    assert job["playlist_ids"] == ["playlist-1"]
    assert job["format"] == "xlsx"
    assert job["output_path"] == "/tmp/export.xlsx"
    assert job["cancelled"] is False

    state.clear_current_export_job()
    assert state.get_current_export_job() is None


def test_mark_current_export_cancelled_returns_false_without_job() -> None:
    assert state.mark_current_export_cancelled() is False


def test_mark_current_export_cancelled_sets_flag() -> None:
    state.set_current_export_job(
        job_id="job-2",
        playlist_ids=["playlist-1", "playlist-2"],
        export_format="csv",
        output_path="/tmp/export.csv",
    )

    assert state.mark_current_export_cancelled() is True
    assert state.get_current_export_job()["cancelled"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/frontend/tests/test_main_screen_state.py -q`

Expected: FAIL because `set_current_export_job`, `get_current_export_job`, `mark_current_export_cancelled`, and `clear_current_export_job` do not exist.

- [ ] **Step 3: Implement job-state functions**

Replace `src/frontend/state.py` with:

```python
"""Shared mutable state for the backend-integrated frontend."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

current_export_job: Optional[Dict[str, Any]] = None


def set_current_export_job(
    *,
    job_id: str,
    playlist_ids: List[str],
    export_format: str,
    output_path: str,
) -> Dict[str, Any]:
    global current_export_job
    current_export_job = {
        "job_id": job_id,
        "playlist_ids": list(playlist_ids),
        "format": export_format,
        "output_path": output_path,
        "cancelled": False,
    }
    return current_export_job


def get_current_export_job() -> Optional[Dict[str, Any]]:
    return current_export_job


def mark_current_export_cancelled() -> bool:
    if not current_export_job:
        return False
    current_export_job["cancelled"] = True
    return True


def clear_current_export_job() -> None:
    global current_export_job
    current_export_job = None
```

- [ ] **Step 4: Use state functions from `MainScreen`**

In `src/frontend/screens/main_screen.py`, replace `from ..state import current_export_job` with:

```python
from ..state import (
    clear_current_export_job,
    get_current_export_job,
    mark_current_export_cancelled,
    set_current_export_job,
)
```

In `backend_export_worker()`, after `playlist_ids` and `target_path` are computed, add:

```python
job_id = self._current_trace_id or uuid.uuid4().hex[:12]
set_current_export_job(
    job_id=job_id,
    playlist_ids=playlist_ids,
    export_format=self._selected_export_format(),
    output_path=target_path,
)
```

Before each backend generation/download step and inside the sequential loop, check:

```python
job = get_current_export_job()
if job and job.get("cancelled"):
    Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)
    return
```

At every successful terminal path and every failed terminal path that calls `cleanup_after_export()`, call:

```python
clear_current_export_job()
```

Change `cancel_export()` to:

```python
def cancel_export(self, *_args) -> None:
    if mark_current_export_cancelled():
        if self.backend_adapter:
            self.backend_adapter.clear_active_export_job()
        self.cancel_btn.disabled = True
        self.cancel_btn.text = "Cancelling..."
        self.status_label.text = "Cancelling export..."
        Clock.schedule_once(lambda _: self.cleanup_after_export(), 3.0)
        Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 3.0)
    else:
        self.status_label.text = "No active export to cancel"
```

- [ ] **Step 5: Use state function from app shutdown**

In `src/frontend/app/backend_app.py`, replace the local import and mutation in `on_stop()` with:

```python
from ..state import mark_current_export_cancelled

mark_current_export_cancelled()
```

- [ ] **Step 6: Update changelog**

Add under the current `CHANGELOG.md` unreleased section:

```markdown
- Fixed export cancellation state so the frontend records active backend exports and can mark them cancelled during user cancellation or app shutdown.
```

- [ ] **Step 7: Run focused tests**

Run: `pytest src/frontend/tests/test_main_screen_state.py -q`

Expected: PASS.

- [ ] **Step 8: Run frontend tests**

Run: `pytest src/frontend/tests -q`

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 9: Commit**

```bash
git add src/frontend/tests/test_main_screen_state.py src/frontend/state.py src/frontend/screens/main_screen.py src/frontend/app/backend_app.py CHANGELOG.md
git commit -m "fix: stabilize frontend export job state"
```

---

### Task 3: Make The Playlist Widget Factory Seam Real

**Files:**
- Modify: `src/frontend/screens/main_screen.py`
- Modify: `src/frontend/screens/backend_main_screen.py`

- [ ] **Step 1: Add base factory method**

Add to `MainScreen` near `display_playlists_with_cache()`:

```python
def _make_playlist_widget(self, playlist: dict):
    """Create a playlist widget for a playlist row."""
    raise NotImplementedError("_make_playlist_widget must be implemented by subclass")
```

- [ ] **Step 2: Consolidate `BackendMainScreen` widget creation**

In `src/frontend/screens/backend_main_screen.py`, replace both direct `BackendPlaylistCard(playlist)` calls with:

```python
widget = self._make_playlist_widget(playlist)
```

Keep the existing `_make_playlist_widget()` implementation:

```python
def _make_playlist_widget(self, playlist: dict) -> BackendPlaylistCard:
    return BackendPlaylistCard(playlist)
```

- [ ] **Step 3: Run import and frontend tests**

Run: `pytest src/frontend/tests -q`

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/screens/main_screen.py src/frontend/screens/backend_main_screen.py
git commit -m "refactor: add main screen playlist widget factory seam"
```

---

### Task 4: Extract Cache And Logout Flows As Delegated Modules

**Files:**
- Create: `src/frontend/screens/main_screen_cache.py`
- Create: `src/frontend/screens/main_screen_logout.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Create cache module by moving bodies unchanged**

Create `src/frontend/screens/main_screen_cache.py` with functions:

```python
"""Cache-related popup flows for MainScreen."""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from ...shared.logging_config import logger
from ..ui.cache_explorer import CacheExplorerPopup


def show_clear_cache_confirmation(screen, *_args) -> None:
    popup_content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(20))
    popup_content.add_widget(Widget(size_hint_y=0.3))
    popup_content.add_widget(
        Label(
            text="Clear all cached playlists and analysis data?",
            font_size=dp(16),
            size_hint_y=None,
            height=dp(80),
            halign="center",
            valign="center",
            text_size=(dp(400), dp(80)),
        )
    )
    popup_content.add_widget(Widget(size_hint_y=0.4))
    buttons = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(15)
    )
    cancel_btn = Button(text="Cancel", size_hint_x=0.5, font_size=dp(16))
    clear_btn = Button(
        text="Clear Cache",
        size_hint_x=0.5,
        font_size=dp(16),
        background_color=[0.8, 0.3, 0.3, 1],
    )
    buttons.add_widget(cancel_btn)
    buttons.add_widget(clear_btn)
    popup_content.add_widget(buttons)
    popup = Popup(
        title="Clear Cache",
        content=popup_content,
        size_hint=(0.6, 0.4),
        auto_dismiss=False,
    )
    cancel_btn.bind(on_press=lambda *_: popup.dismiss())
    clear_btn.bind(on_press=lambda *_: clear_all_cache(screen, popup))
    popup.open()


def clear_all_cache(screen, popup) -> None:
    popup.dismiss()
    try:
        if screen.backend_adapter and getattr(screen.backend_adapter, "cache_manager", None):
            screen.backend_adapter.cache_manager.clear_all_cache()
        screen.status_label.text = "Cache cleared"
        screen.update_status_with_cache_info()
    except Exception as exc:
        logger.error("Error clearing cache: %s", exc, exc_info=True)
        screen.status_label.text = f"Error clearing cache: {exc}"


def open_cache_explorer(screen, create_cache_explorer, backend_available: bool, *_args) -> None:
    try:
        if backend_available and screen.backend_adapter:
            popup = create_cache_explorer(screen.backend_adapter.cache_manager)
        else:
            popup = CacheExplorerPopup()
        popup.open()
    except Exception as exc:
        logger.error("Error opening cache explorer: %s", exc, exc_info=True)
        screen.status_label.text = f"Error opening cache explorer: {exc}"
```

- [ ] **Step 2: Create logout module by moving bodies unchanged**

Create `src/frontend/screens/main_screen_logout.py` with functions:

```python
"""Logout confirmation flow for MainScreen."""

from __future__ import annotations

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget


def logout(screen, *_args) -> None:
    selected_count = sum(1 for w in screen.playlist_widgets if w.checkbox.active)
    if selected_count:
        show_logout_confirmation(screen, selected_count)
    else:
        perform_logout()


def show_logout_confirmation(screen, selected_count: int) -> None:
    popup_content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(20))
    popup_content.add_widget(Widget(size_hint_y=0.3))
    popup_content.add_widget(
        Label(
            text=f"You have {selected_count} selected playlist(s).\n\nLog out anyway?",
            font_size=dp(16),
            size_hint_y=None,
            height=dp(90),
            halign="center",
            valign="center",
            text_size=(dp(400), dp(90)),
        )
    )
    popup_content.add_widget(Widget(size_hint_y=0.4))
    buttons = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(15)
    )
    cancel_btn = Button(text="Cancel", size_hint_x=0.5, font_size=dp(16))
    logout_btn = Button(
        text="Logout",
        size_hint_x=0.5,
        font_size=dp(16),
        background_color=[0.8, 0.3, 0.3, 1],
    )
    buttons.add_widget(cancel_btn)
    buttons.add_widget(logout_btn)
    popup_content.add_widget(buttons)
    popup = Popup(
        title="Confirm Logout",
        content=popup_content,
        size_hint=(0.6, 0.4),
        auto_dismiss=False,
    )
    cancel_btn.bind(on_press=lambda *_: popup.dismiss())
    logout_btn.bind(on_press=lambda *_: handle_logout_confirmed(popup))
    popup.open()


def handle_logout_confirmed(popup) -> None:
    popup.dismiss()
    perform_logout()


def perform_logout() -> None:
    app = App.get_running_app()
    if app and hasattr(app, "logout"):
        app.logout()
```

- [ ] **Step 3: Delegate existing `MainScreen` methods**

In `src/frontend/screens/main_screen.py`, import:

```python
from . import main_screen_cache, main_screen_logout
```

Replace cache and logout method bodies with:

```python
def logout(self, *_args) -> None:
    main_screen_logout.logout(self, *_args)


def _show_logout_confirmation(self, selected_count: int) -> None:
    main_screen_logout.show_logout_confirmation(self, selected_count)


def _handle_logout_confirmed(self, popup) -> None:
    main_screen_logout.handle_logout_confirmed(popup)


def _perform_logout(self) -> None:
    main_screen_logout.perform_logout()


def show_clear_cache_confirmation(self, *_args) -> None:
    main_screen_cache.show_clear_cache_confirmation(self, *_args)


def clear_all_cache(self, popup) -> None:
    main_screen_cache.clear_all_cache(self, popup)


def open_cache_explorer(self, *_args) -> None:
    main_screen_cache.open_cache_explorer(
        self, create_cache_explorer, BACKEND_CACHE_EXPLORER_AVAILABLE, *_args
    )
```

- [ ] **Step 4: Run frontend tests**

Run: `pytest src/frontend/tests -q`

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/screens/main_screen.py src/frontend/screens/main_screen_cache.py src/frontend/screens/main_screen_logout.py
git commit -m "refactor: extract main screen cache and logout flows"
```

---

### Task 5: Extract Backend Error Popup

**Files:**
- Create: `src/frontend/screens/main_screen_error_popup.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Create error popup module**

Move `_show_backend_error_popup()` and `_get_recoverable_backend_export_context()` into `src/frontend/screens/main_screen_error_popup.py` as functions taking `screen` as the first argument. Preserve the existing `Clock.schedule_once(_open_popup, 0)` timing and preserve the exact resume/discard behavior.

Required function signatures and first lines:

```python
def show_backend_error_popup(screen, message: str) -> None:
    if not message:
        return


def get_recoverable_backend_export_context(screen):
    if not screen.backend_adapter:
        return None
```

The rest of each function is a direct mechanical move from the existing
`MainScreen._show_backend_error_popup()` and
`MainScreen._get_recoverable_backend_export_context()` bodies. During the move,
replace `self.` with `screen.` and keep local nested functions (`_open_popup`,
`_copy_details`, `_clear_resume_job`, `_resume_export`) in the same function.

- [ ] **Step 2: Delegate existing `MainScreen` methods**

In `src/frontend/screens/main_screen.py`, import:

```python
from . import main_screen_error_popup
```

Replace method bodies with:

```python
def _show_backend_error_popup(self, message: str) -> None:
    main_screen_error_popup.show_backend_error_popup(self, message)


def _get_recoverable_backend_export_context(self) -> Optional[Dict[str, Any]]:
    return main_screen_error_popup.get_recoverable_backend_export_context(self)
```

- [ ] **Step 3: Verify auth-error behavior remains in `MainScreen`**

Leave `_on_backend_error()` in `main_screen.py` during this task. It is app/session orchestration, not only popup rendering.

- [ ] **Step 4: Run frontend tests**

Run: `pytest src/frontend/tests -q`

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/screens/main_screen.py src/frontend/screens/main_screen_error_popup.py
git commit -m "refactor: extract backend error popup"
```

---

### Task 6: Extract Export Orchestration Last

**Files:**
- Create: `src/frontend/screens/main_screen_scheduler.py`
- Create: `src/frontend/screens/main_screen_export.py`
- Modify: `src/frontend/screens/main_screen.py`
- Modify: `CHANGELOG.md` if status text, cancellation, overwrite prompts, file naming, or resume behavior changes.

- [ ] **Step 1: Add scheduler adapter**

Create `src/frontend/screens/main_screen_scheduler.py`:

```python
"""Kivy scheduling adapter for MainScreen background workers."""

from __future__ import annotations

from typing import Callable

from kivy.clock import Clock


class KivyScheduler:
    def call_soon(self, callback: Callable[[], None]) -> None:
        Clock.schedule_once(lambda _dt: callback(), 0)

    def call_later(self, delay_seconds: float, callback: Callable[[], None]) -> None:
        Clock.schedule_once(lambda _dt: callback(), delay_seconds)

    def set_attr_soon(self, target, name: str, value) -> None:
        self.call_soon(lambda: setattr(target, name, value))
```

- [ ] **Step 2: Create export orchestrator shell**

Create `src/frontend/screens/main_screen_export.py`:

```python
"""Backend export orchestration for MainScreen."""

from __future__ import annotations

import threading
from typing import Any


class MainScreenExportOrchestrator:
    def __init__(self, screen, scheduler) -> None:
        self.screen = screen
        self.scheduler = scheduler

    def begin(self, playlists: Any, output_path: str, resume_saved_job: bool = False) -> None:
        threading.Thread(
            target=self.worker,
            args=(playlists, output_path, resume_saved_job),
            daemon=True,
        ).start()

    def worker(self, playlists: Any, output_path: str, resume_saved_job: bool = False) -> None:
        self.screen.backend_export_worker(playlists, output_path, resume_saved_job)
```

- [ ] **Step 3: Wire orchestrator without moving behavior**

In `MainScreen.__init__()`, after `_backend_resume_popup` is initialized:

```python
self.scheduler = KivyScheduler()
self.export_orchestrator = MainScreenExportOrchestrator(self, self.scheduler)
```

Import:

```python
from .main_screen_export import MainScreenExportOrchestrator
from .main_screen_scheduler import KivyScheduler
```

Change `begin_backend_export()` to call:

```python
self.export_orchestrator.begin(playlists, output_path, resume_saved_job)
```

and remove the direct `threading.Thread` call from `begin_backend_export()`.

- [ ] **Step 4: Run frontend tests**

Run: `pytest src/frontend/tests -q`

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 5: Move worker body after shell is verified**

Move the body of `backend_export_worker()` into `MainScreenExportOrchestrator.worker()`. Replace `self.` references that refer to screen widgets or screen helper methods with `screen.` after assigning:

```python
screen = self.screen
```

Keep a compatibility wrapper in `MainScreen`:

```python
def backend_export_worker(
    self, playlists, output_path, resume_saved_job: bool = False
) -> None:
    self.export_orchestrator.worker(playlists, output_path, resume_saved_job)
```

- [ ] **Step 6: Move sequential fallback after worker is verified**

Move `_backend_export_fallback_sequential()` into `MainScreenExportOrchestrator` with this signature and opening line:

```python
def fallback_sequential(self, playlists, base_output_path):
    screen = self.screen
```

The remaining body is a direct mechanical move from the existing
`MainScreen._backend_export_fallback_sequential()` body. During the move,
replace `self.` with `screen.` for access to widgets, helper methods, and
backend adapter state.

Update the moved worker to call:

```python
fallback_result = self.fallback_sequential(valid_playlists, output_path)
```

Keep a compatibility wrapper in `MainScreen`:

```python
def _backend_export_fallback_sequential(
    self, playlists: List[Dict[str, Any]], base_output_path: str
) -> Dict[str, Any]:
    return self.export_orchestrator.fallback_sequential(playlists, base_output_path)
```

- [ ] **Step 7: Move export entry and cleanup methods**

After worker and fallback are stable, move these methods into `MainScreenExportOrchestrator` one at a time, preserving wrappers in `MainScreen`:

```python
start_export
_start_backend_export
_show_backend_overwrite_confirmation
_handle_backend_overwrite_confirmed
cancel_export
cleanup_after_export
handle_export_cancelled
_build_backend_output_path
```

Each wrapper should delegate to the orchestrator method with the same arguments.

- [ ] **Step 8: Run verification after each moved method**

Run after each method move:

```bash
pytest src/frontend/tests/test_main_screen_filenames.py src/frontend/tests/test_main_screen_state.py -q
pytest src/frontend/tests -q
```

Expected: PASS or only existing environment-related Kivy display skips/failures already present before this task.

- [ ] **Step 9: Commit**

```bash
git add src/frontend/screens/main_screen.py src/frontend/screens/main_screen_export.py src/frontend/screens/main_screen_scheduler.py CHANGELOG.md
git commit -m "refactor: extract main screen export orchestrator"
```

---

## Final Verification

- [ ] Run `./scripts/verify-all.sh` from repo root.
- [ ] Run `pytest src/frontend/tests -q`.
- [ ] Launch the app locally and manually verify login-to-main-screen, playlist refresh, search, sort, select visible, deselect all, export single playlist, export multiple playlists, cancel export, backend error popup copy, resume/discard, clear cache, cache explorer, and logout.
- [ ] Check `rg -n "current_export_job|BackendPlaylistCard|threading.Thread|Clock.schedule_once" src/frontend/screens/main_screen.py` and confirm remaining hits are intentional thin wrappers or Kivy lifecycle code.
- [ ] Check `rg -n "except:" src/frontend` returns no bare Python exceptions.
- [ ] Check `git diff --stat` and confirm changes are limited to the files named in this plan.

## Execution Recommendation

Use subagent-driven execution for Tasks 1-5. Use inline execution for Task 6 unless a reviewer is available after each method move, because export orchestration is the highest-risk path and small diffs are easier to inspect in one session.
