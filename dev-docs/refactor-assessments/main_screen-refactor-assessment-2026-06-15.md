# Refactor Assessment: main_screen.py

**Date:** 2026-06-15
**File:** `src/frontend/screens/main_screen.py`
**Lines:** 1,940 | **Methods:** ~45 | **Public methods:** ~25

> **2026-06-19 status:** This refactor has been completed and verified. `main_screen.py` is now 1,053 lines, the planned helper modules exist, cancellation branch coverage was added, and completion details are tracked in [Main Screen Refactor Completion Implementation Plan](../../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md).

---

## Current State

| Metric | Value |
|--------|-------|
| Lines | 1,940 |
| Class methods | ~45 |
| Public methods | ~25 |
| Biggest method | `backend_export_worker` (~270 lines) |
| Biggest section | Export logic (~600 lines, lines 1133-1685) |

---

## What the file does

The file defines `MainScreen(Screen)`, a Kivy screen that is subclassed by `BackendMainScreen`. It is the central UI component for playlist selection and export. Seven distinct responsibilities are mixed into one class:

1. **UI construction** — `build_ui`, `_create_header`, `_create_controls`, `_create_scroll_view`, `_create_export_section` (~460 lines)
2. **Sorting** — 6 methods for sort UI state, debouncing, and execution (~80 lines)
3. **Search/filtering** — 5 methods for debounced search, filtering, and display (~130 lines)
4. **Playlist selection** — 6 methods for checkbox state, select all/clear, counter (~160 lines)
5. **Export orchestration** — The dominant concern: `start_export`, `backend_export_worker`, `_backend_export_fallback_sequential`, `_show_backend_overwrite_confirmation`, `cancel_export`, `cleanup_after_export`, `handle_export_cancelled`, plus filename helpers (~600 lines)
6. **Error handling & diagnostics** — `_show_backend_error_popup`, `_get_recoverable_backend_export_context`, `_show_error_dialog`, `_log_error`, `_update_export_status` (~250 lines)
7. **Cache management** — `show_clear_cache_confirmation`, `clear_all_cache`, `open_cache_explorer` (~100 lines)
8. **Logout** — `logout`, `_show_logout_confirmation`, `_handle_logout_confirmed`, `_perform_logout` (~60 lines)
9. **Filename helpers** — `_generate_default_filename`, `_refresh_filename_after_export`, `_increment_filename_suffix`, `_get_file_extension`, `_selected_export_format` (~60 lines)

---

## Proposed file decomposition

```
src/frontend/screens/
├── main_screen.py                    ← MainScreen base class (~400 lines)
│                                      ← UI construction + sort + search + selection lifecycle
├── main_screen_export.py             ← Export orchestration (~350 lines)
│                                      ← Mixin or composed service for export flow
├── main_screen_error_popup.py        ← Error popup builder (~150 lines)
│                                      ← _show_backend_error_popup, _get_recoverable_export_context
├── main_screen_cache.py              ← Cache management (~80 lines)
│                                      ← clear_cache, cache_explorer
├── main_screen_logout.py             ← Logout flow (~60 lines)
│                                      ← confirmation popup + perform_logout
├── main_screen_filenames.py          ← Filename utilities (~50 lines)
│                                      ← generate, refresh, increment, extension helpers
└── __init__.py                       ← Re-exports
```

---

## Modularization strategy

### Approach: Composition over deep inheritance

The current `BackendMainScreen` subclass overrides 3 methods to swap in `BackendPlaylistCard`. This works but the base class is so large the subclass feels like a band-aid.

**Option A — Mixin modules (recommended):** Extract each responsibility into a mixin class. `MainScreen` inherits from the base screen + relevant mixins. `BackendMainScreen` inherits from `MainScreen` + mixins and overrides only the widget factory.

**Option B — Service objects:** Extract behavior into standalone service classes (e.g., `ExportOrchestrator`, `ErrorPopupBuilder`) that the screen composes via dependency injection. Cleaner separation but requires changing how the screen holds state.

---

## Key issues flagged

### 1. `backend_export_worker` is a god method

270 lines with 3 major branches (combined export, sequential fallback, recovery), each with nested `Clock.schedule_once` chains. Should be split into state-machine steps or extracted to a service.

### 2. `_show_backend_error_popup` builds an entire popup

90 lines of UI construction nested inside an error handler. Should be a separate builder function.

### 3. Export logic is duplicated

The success/partial-failure/full-failure branches appear in both `backend_export_worker` and `_backend_export_fallback_sequential`. Same status update pattern repeated 6+ times.

### 4. `Clock.schedule_once` abuse

Dozens of `Clock.schedule_once(lambda _: setattr(...))` calls scattered throughout. A small helper or context manager would reduce noise and prevent thread-safety bugs.

### 5. No separation between UI and business logic

Export orchestration, backend API calls, and UI updates are all intermingled. The adapter layer exists but the screen still knows about chunked exports, sequential fallback, resumable jobs, and circuit breakers.

### 6. `_create_export_section` builds too much

90 lines including filename input, format spinner, progress bar, status bar, cache buttons, and two action buttons. Could be split into sub-section builders.

### 7. `_on_backend_error` handles auth recovery

20 lines of `prompt_reauthentication`/`logout`/`switch_to_login` branching on app capabilities. This is a cross-cutting concern that doesn't belong in the screen.

### 8. State is scattered

`selected_playlist_ids` is a `Set[str]` but selection state is also tracked via widget checkboxes. Two sources of truth for the same concept.

---

---

## 1. Dependency Map

### Module-Level Imports

| Import | Used In |
|--------|---------|
| `os` | `_create_export_section`, `_start_backend_export`, `_build_backend_output_path`, `backend_export_worker`, `_backend_export_fallback_sequential`, `_generate_default_filename` |
| `re` | `_sanitize_export_filename_component` |
| `threading` | `begin_backend_export` |
| `time` | `backend_export_worker` |
| `uuid` | `begin_backend_export` |
| `datetime` | `_show_backend_error_popup` |
| `App` (kivy) | `_create_header`, `on_enter`, `_start_backend_export`, `_generate_default_filename`, `_perform_logout` |
| `Clipboard` (kivy) | `_show_backend_error_popup` |
| `Clock`, `mainthread` (kivy) | ~25 methods |
| `Color`, `Rectangle` (kivy) | `_create_export_section` |
| `dp` (kivy) | ~30 methods (UI construction) |
| `BoxLayout` (kivy) | `_create_header`, `_create_controls`, `_create_export_section`, `_show_backend_error_popup`, `_show_backend_overwrite_confirmation`, `_show_logout_confirmation`, `show_clear_cache_confirmation` |
| `Button` (kivy) | `_create_controls`, `_create_export_section`, `_show_backend_error_popup`, `_show_backend_overwrite_confirmation`, `_show_logout_confirmation`, `show_clear_cache_confirmation` |
| `Label` (kivy) | `_create_header`, `_create_controls`, `_create_export_section`, `_show_error_dialog`, `_show_backend_error_popup`, `_show_backend_overwrite_confirmation`, `_show_logout_confirmation`, `show_clear_cache_confirmation` |
| `Popup` (kivy) | `start_export`, `_show_error_dialog`, `_show_backend_error_popup`, `_show_backend_overwrite_confirmation`, `_show_logout_confirmation`, `show_clear_cache_confirmation`, `clear_all_cache` |
| `ProgressBar` (kivy) | `_create_export_section` |
| `RelativeLayout` (kivy) | `_create_header`, `_create_export_section` |
| `ScrollView` (kivy) | `_create_scroll_view` |
| `Spinner` (kivy) | `_create_controls`, `_create_export_section` |
| `TextInput` (kivy) | `_create_controls`, `_create_export_section`, `_show_backend_error_popup` |
| `Widget` (kivy) | `_create_controls`, `_create_export_section`, `_show_backend_overwrite_confirmation`, `_show_logout_confirmation`, `show_clear_cache_confirmation` |
| `Screen` (kivy) | Base class |
| `logger` | 15+ methods (error/warning logging) |
| `current_export_job` | `cancel_export` |
| `ResponsiveGridLayout` | `build_ui` |
| `CacheExplorerPopup` | `open_cache_explorer` |
| `EXPORT_DIR` | `_create_export_section` |
| `create_cache_explorer` | `open_cache_explorer` (conditional) |

### Method-by-Method Call Map

#### `__init__`
- **Calls self:** `build_ui()`
- **Writes:** `backend_adapter`, `playlists`, `playlist_widgets`, `selected_playlist_ids`, `filtered_playlists`, `current_sort_key`, `current_sort_reverse`, `search_query`, `_search_trigger`, `_search_debounce_seconds`, `_sort_trigger`, `_sort_debounce_seconds`, `_backend_error_phase`, `_backend_error_step`, `trace_mode_enabled`, `_current_trace_id`, `_backend_resume_popup`
- **External:** `Screen.__init__()`

#### `initialize_with_backend(backend_adapter)`
- **Calls self:** none
- **Calls external:** `backend_adapter.set_callbacks()` → registers `_on_backend_playlists_loaded`, `_on_backend_error`, `_on_backend_progress`
- **Writes:** `backend_adapter`

#### `build_ui()`
- **Calls self:** `_create_header()`, `_create_controls()`, `_create_scroll_view()`, `_create_export_section()`
- **Writes:** `playlist_layout`

#### `_create_header()` → `RelativeLayout`
- **Calls self:** none
- **External:** `App.get_running_app()`, `getattr(app, "username")`
- **Writes:** `username_label`

#### `_create_controls()` → `BoxLayout`
- **Calls self:** none
- **Writes:** `sort_spinner`, `by_label`, `sort_direction_btn`, `search_input`, `select_all_btn`, `selection_label`
- **Event bindings:** `configure_dropdown`, `on_sort_change`, `toggle_sort_direction`, `clear_search`, `toggle_select_all`, `deselect_all`, `load_playlists_with_cache`, `logout`

#### `_create_scroll_view()` → `ScrollView`
- **Calls self:** none

#### `_create_export_section()` → `BoxLayout`
- **Calls self:** `_generate_default_filename("xlsx")`, `_get_file_extension()` (via `on_format_change` binding)
- **Writes:** `filename_input`, `format_spinner`, `export_btn`, `cancel_btn`, `progress_bar`, `status_label`, `clear_cache_btn`, `cache_explorer_btn`
- **Event bindings:** `on_format_change`, `start_export`, `cancel_export`, `show_clear_cache_confirmation`, `open_cache_explorer`
- **External:** `EXPORT_DIR`

#### `on_sort_change(spinner, text)`
- **Calls self:** `update_sort_controls_visibility()`, `update_sort_direction_button()`, `sort_playlists()`
- **Writes:** `current_sort_key`

#### `sort_playlists()`
- **Calls self:** `_perform_sort()` (via Clock debounce)
- **Writes:** `_sort_trigger`

#### `_perform_sort()`
- **Overrides:** abstract — raises `NotImplementedError`

#### `on_format_change(spinner, text)`
- **Calls self:** `_get_file_extension()`, `_generate_default_filename()`
- **Writes:** `filename_input` (text)

#### `_get_file_extension(format_type)` → `str`
- Pure utility. Returns `.xlsx`, `.csv`, or `.json`.

#### `_selected_export_format()` → `str`
- Reads `format_spinner`. Returns `xlsx`, `csv`, or `json`.

#### `on_enter()` — **OVERRIDES `Screen.on_enter`**
- **Calls self:** `update_sort_controls_visibility()`, `_generate_default_filename()`, `load_playlists_with_cache()`
- **External:** `App.get_running_app()`, `app.username`, `filename_input`, `username_label`

#### `load_playlists_with_cache(*_args)`
- **Calls self:** `update_sort_direction_button()`, `update_selection_counter()`
- **Reads:** `backend_mode_enabled`, `backend_adapter`
- **Writes:** `current_sort_key`, `current_sort_reverse`, `sort_spinner` (text), `status_label` (text), `playlist_layout` (clear_widgets), `playlist_widgets`, `filtered_playlists`
- **Calls external:** `backend_adapter.load_playlists()`

#### `_on_backend_playlists_loaded(playlists)` — **callback from backend_adapter**
- **Calls self:** `display_playlists_with_cache()`
- **Writes:** `playlists`

#### `_on_backend_error(error_msg)` — **callback from backend_adapter**
- **Calls self:** `_show_backend_error_popup()`, `_refresh_filename_after_export()` (indirect via error paths)
- **Reads:** `App.get_running_app()`, `app.prompt_reauthentication`, `app.logout`, `app.switch_to_login`
- **Writes:** `status_label` (text)

#### `_show_backend_error_popup(message)`
- **Calls self:** `_get_recoverable_backend_export_context()`, `begin_backend_export()` (via resume button), `backend_adapter.clear_active_export_job()` (via discard button)
- **Reads:** `backend_adapter`, `_backend_error_phase`, `_backend_error_step`, `_current_trace_id`, `_backend_resume_popup`, `status_label`
- **Writes:** `status_label` (text), `_backend_resume_popup`
- **External:** `Clipboard.copy()`, `datetime.now()`

#### `_get_recoverable_backend_export_context()` → `Optional[Dict]`
- **Reads:** `backend_adapter`, `_backend_error_phase`, `backend_adapter.get_active_export_job()`
- **Returns:** resumable export data or None

#### `_on_backend_progress(status)` — **callback from backend_adapter**
- **Reads:** `_current_trace_id`, `status_label`
- **Writes:** `status_label` (text)

#### `display_playlists_with_cache()`
- **Overrides:** abstract — raises `NotImplementedError`

#### `_get_filtered_playlists()` → `List[dict]`
- Reads `search_query`, `playlists`. Returns filtered copy.

#### `_sort_playlists(playlists)` → `List[dict]`
- Reads `current_sort_key`, `current_sort_reverse`.

#### `update_status_with_cache_info()`
- Reads `playlists`, `search_query`, `filtered_playlists`, `status_label`.

#### `on_search_text(instance, value)`
- **Calls self:** `_perform_search()` (via Clock debounce)
- **Writes:** `_search_trigger`

#### `_perform_search(search_text)`
- **Calls self:** `display_playlists_with_cache()`
- **Writes:** `search_query`, `status_label` (text)

#### `clear_search(instance)`
- **Calls self:** `display_playlists_with_cache()`
- **Reads:** `_search_trigger`, `search_input`, `playlist_layout.parent` (scroll_y)
- **Writes:** `_search_trigger`, `search_input` (text), `search_query`

#### `toggle_select_all(instance)`
- **Calls self:** `update_selection_counter()`
- **Reads:** `playlist_widgets`

#### `update_selection_counter()`
- **Calls self:** `_update_select_all_button_label()`
- **Reads:** `selected_playlist_ids`, `playlists`, `selection_label`
- **Writes:** `selection_label` (text)

#### `_update_select_all_button_label()`
- **Reads:** `select_all_btn`, `playlist_widgets`
- **Writes:** `select_all_btn` (text)

#### `_on_playlist_checkbox_changed(playlist_id, is_active)`
- **Calls self:** `update_selection_counter()`
- **Writes:** `selected_playlist_ids`

#### `select_all(*_args)`
- **Calls self:** `update_selection_counter()`
- **Reads:** `playlist_widgets`

#### `deselect_all(*_args)`
- **Calls self:** `update_selection_counter()`
- **Writes:** `selected_playlist_ids`, `playlist_widgets` (checkbox.active)

#### `start_export(*_args)`
- **Calls self:** `_start_backend_export()`, `_refresh_filename_after_export()` (on error)
- **Reads:** `backend_mode_enabled`, `playlists`, `selected_playlist_ids`, `status_label`, `export_btn`
- **Writes:** `status_label` (text)
- **External:** `Popup`

#### `_start_backend_export(playlists)`
- **Calls self:** `_get_file_extension()`, `_selected_export_format()`, `_generate_default_filename()`, `_show_backend_overwrite_confirmation()`, `begin_backend_export()`
- **Reads:** `backend_adapter`, `filename_input`, `status_label`, `SAVE_DIR`
- **Writes:** `status_label` (text)

#### `_show_backend_overwrite_confirmation(playlists, output_path, filename)`
- **Calls self:** `_handle_backend_overwrite_confirmed()` (via button)
- **External:** `Popup`, `BoxLayout`, `Label`, `Button`, `Widget`

#### `_handle_backend_overwrite_confirmed(popup, playlists, output_path)`
- **Calls self:** `begin_backend_export()`
- **External:** `popup.dismiss()`

#### `begin_backend_export(playlists, output_path, resume_saved_job)`
- **Calls self:** `backend_export_worker()` (via threading.Thread)
- **Reads:** `trace_mode_enabled`, `backend_adapter`, `_current_trace_id`
- **Writes:** `_current_trace_id`, `export_btn` (disabled), `cancel_btn` (opacity, disabled), `status_label` (text), `progress_bar` (value)
- **External:** `uuid.uuid4()`, `threading.Thread`

#### `_sanitize_export_filename_component(value)` → `str`
- Pure utility. Uses `re.sub()`.

#### `_build_backend_output_path(playlist, base_output_path, multiple)`
- **Calls self:** `_get_file_extension()`, `_selected_export_format()`

#### `backend_export_worker(playlists, output_path, resume_saved_job)`
- **Calls self:** `cleanup_after_export()`, `_refresh_filename_after_export()`, `_set_backend_error_context()`, `_backend_export_fallback_sequential()`, `_show_backend_error_popup()`
- **Reads:** `backend_adapter`, `status_label`, `progress_bar`
- **Writes:** `status_label` (text), `progress_bar` (value)
- **Calls external:** `backend_adapter.generate_batch_export_chunked()`, `backend_adapter.download_batch_export()`, `backend_adapter.clear_active_export_job()`, `backend_adapter.set_trace_id()`, `time.sleep()`, `Clock.schedule_once()`

#### `_backend_export_fallback_sequential(playlists, base_output_path)` → `Dict`
- **Calls self:** `_sanitize_export_filename_component()`, `_get_file_extension()`, `_selected_export_format()`, `_set_backend_error_context()`
- **Reads:** `backend_adapter`, `status_label`, `progress_bar`
- **Writes:** `status_label` (text), `progress_bar` (value)
- **Calls external:** `backend_adapter.generate_export()`, `backend_adapter.download_export()`, `time.sleep()`, `Clock.schedule_once()`

#### `cancel_export(*_args)`
- **Calls self:** `cleanup_after_export()`, `_refresh_filename_after_export()` (via Clock 3s)
- **External:** `current_export_job` (global)
- **Writes:** `cancel_btn` (disabled, text), `status_label` (text)

#### `cleanup_after_export()`
- **Writes:** `export_btn` (disabled), `cancel_btn` (opacity, disabled, text), `progress_bar` (value)
- **Calls external:** `backend_adapter.set_trace_id(None)`

#### `handle_export_cancelled()`
- **Calls self:** `cleanup_after_export()`, `_refresh_filename_after_export()`
- **Writes:** `status_label` (text)

#### `logout(*_args)`
- **Calls self:** `_show_logout_confirmation()`, `_perform_logout()`
- **Reads:** `playlist_widgets`

#### `_show_logout_confirmation(selected_count)`
- **Calls self:** `_handle_logout_confirmed()` (via button)
- **External:** `BoxLayout`, `Label`, `Button`, `Widget`, `Popup`

#### `_handle_logout_confirmed(popup)`
- **Calls self:** `_perform_logout()`
- **External:** `popup.dismiss()`

#### `_perform_logout()`
- **External:** `App.get_running_app()`, `app.logout()`

#### `show_clear_cache_confirmation(*_args)`
- **Calls self:** `clear_all_cache()` (via button)
- **External:** `BoxLayout`, `Label`, `Button`, `Widget`, `Popup`

#### `clear_all_cache(popup)`
- **Calls self:** `update_status_with_cache_info()`
- **External:** `Popup`, `Label`, `logger`
- **Writes:** `status_label` (text)

#### `open_cache_explorer(*_args)`
- **External:** `create_cache_explorer()`, `CacheExplorerPopup()`, `logger`
- **Writes:** `status_label` (text)

#### `_generate_default_filename(format_type)` → `str`
- **External:** `App.get_running_app()`, `datetime.now().strftime()`
- **Reads:** `app.username`

#### `_refresh_filename_after_export()`
- **Calls self:** `_generate_default_filename()`, `_increment_filename_suffix()`
- **Writes:** `filename_input` (text)

#### `_increment_filename_suffix(filename)` → `str`
- Pure utility. String operations.

### Dead / Unused Code

The following methods are defined but never called from anywhere in this file:

| Method | Notes |
|--------|-------|
| `_show_error_dialog()` | Standalone popup helper, no caller |
| `_log_error()` | Structured logging helper, no caller (file uses `logger.*` directly) |
| `_update_export_status()` | Status updater, no caller (file uses `status_label.text` directly) |
| `_get_filtered_playlists()` | Filter helper, no caller |
| `_sort_playlists()` | Sort helper, no caller |
| `select_all()` | Select all, no caller (only `toggle_select_all` is bound) |

### Cross-File References

#### `backend_adapter` methods called:

| Method | Called From |
|--------|-------------|
| `set_callbacks()` | `initialize_with_backend()` |
| `load_playlists()` | `load_playlists_with_cache()`, `load_playlists_worker_with_cache()` |
| `generate_batch_export_chunked()` | `backend_export_worker()` |
| `download_batch_export()` | `backend_export_worker()` |
| `generate_export()` | `_backend_export_fallback_sequential()` |
| `download_export()` | `_backend_export_fallback_sequential()` |
| `clear_active_export_job()` | `_show_backend_error_popup()`, `cancel_export()`, `backend_export_worker()` |
| `get_active_export_job()` | `_get_recoverable_backend_export_context()` |
| `set_trace_id()` | `begin_backend_export()`, `cleanup_after_export()` |

#### App methods called:

| Method | Called From |
|--------|-------------|
| `App.get_running_app()` | `_create_header()`, `on_enter()`, `_on_backend_error()`, `_perform_logout()`, `_generate_default_filename()` |
| `app.username` | `_create_header()`, `on_enter()`, `_generate_default_filename()` |
| `app.prompt_reauthentication()` | `_on_backend_error()` |
| `app.logout()` | `_on_backend_error()`, `_perform_logout()` |
| `app.switch_to_login()` | `_on_backend_error()` |

#### Other cross-file references:

| Reference | Called From |
|-----------|-------------|
| `current_export_job` (global, from `frontend/state.py`) | `cancel_export()` |
| `create_cache_explorer()` (from `cache_explorer_adapter.py`) | `open_cache_explorer()` |
| `CacheExplorerPopup` (from `frontend/ui/cache_explorer.py`) | `open_cache_explorer()` |
| `ResponsiveGridLayout` (from `frontend/ui/layouts.py`) | `build_ui()` |
| `EXPORT_DIR` (from `frontend/config/backend_config.py`) | `_create_export_section()` |
| `logger` (from `shared/logging_config.py`) | 15+ methods |

### Most Connected Methods

| Rank | Method | Internal Calls | External Calls | Attrs Read | Attrs Written |
|------|--------|---------------|---------------|------------|---------------|
| 1 | `backend_export_worker` | 6 | 8 | 3 | 2 |
| 2 | `_show_backend_error_popup` | 2 | 6 | 5 | 2 |
| 3 | `begin_backend_export` | 1 | 3 | 3 | 5 |
| 4 | `build_ui` | 4 | 2 | 0 | 1 |
| 5 | `_create_controls` | 0 | 15+ | 0 | 7 |
| 6 | `_create_export_section` | 1 | 12+ | 0 | 7 |
| 7 | `start_export` | 1 | 3 | 4 | 1 |
| 8 | `_backend_export_fallback_sequential` | 4 | 5 | 3 | 2 |
| 9 | `on_enter` | 3 | 2 | 2 | 2 |
| 10 | `load_playlists_with_cache` | 2 | 1 | 1 | 6 |

---

## 2. Coupling Analysis

### 2.1 Dependencies on `BackendMainScreenAdapter`

**Import:** `from ..screens import BackendMainScreenAdapter, create_backend_adapter`

**Initialization:** `initialize_with_backend(adapter: BackendMainScreenAdapter)` — receives adapter as constructor argument, stores as `self.backend_adapter`

**Methods called on adapter:**

| Method | Called From | Purpose |
|--------|-------------|---------|
| `set_callbacks()` | `initialize_with_backend()` | Register callback handlers |
| `load_playlists()` | `load_playlists_with_cache()`, `load_playlists_worker_with_cache()` | Fetch playlist list |
| `generate_batch_export_chunked()` | `backend_export_worker()` | Trigger chunked backend export |
| `download_batch_export()` | `backend_export_worker()` | Download combined export file |
| `generate_export()` | `_backend_export_fallback_sequential()` | Fallback single-file export |
| `download_export()` | `_backend_export_fallback_sequential()` | Download fallback export |
| `clear_active_export_job()` | `_show_backend_error_popup()`, `cancel_export()`, `backend_export_worker()` | Clean up job state |
| `get_active_export_job()` | `_get_recoverable_backend_export_context()` | Retrieve cached job metadata |
| `set_trace_id()` | `begin_backend_export()`, `cleanup_after_export()` | Trace ID propagation |

**Tight coupling: HIGH.** MainScreen directly references concrete `BackendMainScreenAdapter`. The adapter is passed via `initialize_with_backend()` (thin DI — only one concrete type is ever passed). The screen knows about 9 adapter methods and calls them with specific argument shapes.

### 2.2 Dependencies on `BackendSpotifyExporterApp`

**Access pattern:** `App.get_running_app()` — Kivy class method singleton lookup

**Methods/attributes called on app:**

| Method/Attribute | Called From | Purpose |
|------------------|-------------|---------|
| `app.username` | `_create_header()`, `on_enter()`, `_generate_default_filename()` | Display name / filename generation |
| `app.prompt_reauthentication()` | `_on_backend_error()` | Re-auth on 401 |
| `app.logout()` | `_on_backend_error()`, `_perform_logout()` | Full logout |
| `app.switch_to_login()` | `_on_backend_error()` | Navigate to login screen |

**Tight coupling: HIGH.** The app singleton is accessed via a class method, making it a global dependency. `_on_backend_error()` has 3 branching paths on app capabilities (`prompt_reauthentication`, `logout`, `switch_to_login`).

### 2.3 Dependencies on `BackendClient`

Direct usage: **NONE.** MainScreen does not import or reference `BackendClient`. All `BackendClient` interactions go through `BackendMainScreenAdapter`. This is a clean boundary.

### 2.4 Global State Dependencies

| Global | Module | Used In |
|--------|--------|---------|
| `current_export_job` | `frontend/state.py` | `cancel_export()` — read and write |

`current_export_job` is a module-level mutable dict. It is set in `_begin_backend_export()` with `job_id`, `playlist_ids`, `format`, `status`, `progress`, `cancelled` flag, and read in `cancel_export()`. This creates implicit coupling between MainScreen instances and any other code that reads/writes it (e.g., `BackendSpotifyExporterApp.on_stop()` in `backend_app.py:343`).

### 2.5 UI Component Dependencies

| Component | Import | Used For |
|-----------|--------|----------|
| `BackendPlaylistCard` | `from ..ui.backend_playlist_card` | Displaying playlist cards (abstracted via `_make_playlist_widget`) |
| `ResponsiveGridLayout` | `from ..ui.layouts` | Auto-sizing grid container |
| `CacheExplorerPopup` | `from ..ui.cache_explorer` | Cache inspection popup |
| `EXPORT_DIR` | `from ..config.backend_config` | Export directory constant |
| `create_cache_explorer` | `from ..caching.cache_explorer_adapter` | Cache explorer factory |

### 2.6 Export Logic Coupling Assessment

**Current architecture:**
```
MainScreen.begin_backend_export()
  └─> threading.Thread → backend_export_worker()
       ├─> backend_adapter.generate_batch_export_chunked()
       ├─> polling loop with Clock.schedule_once
       ├─> current_export_job state management
       ├─> UI updates (progress bar, buttons)
       └─> fallback: _backend_export_fallback_sequential()
            └─> backend_adapter.generate_export() + download_export()
```

**What could be tested independently if extracted:**
- The polling loop logic (progress updates, cancellation checks) — if extracted to a pure function
- The state machine for export phases (collecting → exporting → finalizing)
- Error handling and retry logic

**What cannot be tested independently (tightly coupled):**
- `backend_adapter.generate_batch_export_chunked()` — calls real HTTP endpoints
- `Clock.schedule_once()` — Kivy framework coupling
- `current_export_job` — global state mutation
- UI widget updates — Kivy framework coupling

### 2.7 Interface-Based Refactoring Options

| Current | Interface | Rationale |
|---------|-----------|-----------|
| `BackendMainScreenAdapter` | `PlaylistService` interface | Decouple from concrete adapter |
| `BackendSpotifyExporterApp.get_running_app()` | `AppProvider` interface | Decouple from app singleton |
| `current_export_job` (global) | `ExportJobStore` interface | Decouple from module-level global |
| `Clock.schedule_once()` | `Scheduler` interface | Decouple from Kivy for testing |
| `BackendPlaylistCard` | `PlaylistCardFactory` interface | Swap card implementations |

---

## 3. Test Coverage Audit

### 3.1 Test Files Found

| File | Type | Lines |
|------|------|-------|
| `src/frontend/tests/test_ui.py` | Integration (backend services) | 79 |
| `src/frontend/tests/test_framework.py` | Test utility framework (not pytest tests) | 83 |
| `src/frontend/tests/test_resumable_export_cache.py` | Unit (cache manager) | 52 |
| `src/frontend/tests/mock_backend.py` | Test infrastructure (mock server) | 470 |
| `src/frontend/tests/conftest.py` | Pytest fixtures | 16 |

**No other test directories or test files found** in `src/frontend/tests/` or elsewhere in the repo.

### 3.2 What Each Test File Covers

#### `test_ui.py` — Backend Service Integration
- `test_playlist_loading` — `BackendClient.get_playlists()`
- `test_playlist_details` — `BackendClient.get_playlist_details()`
- `test_track_loading` — `BackendClient.get_playlist_tracks()`
- `test_analysis_functionality` — `ReccoBeatsBackendService.analyze_playlist()`
- `test_export_functionality` — `BackendClient.generate_export()`
- `test_caching_functionality` — `BackendCacheManager.cache/get/clear`
- `test_error_handling` — `BackendClient` error paths for invalid IDs

**Does NOT test:** Any screen, any UI component, MainScreen, BackendMainScreenAdapter

#### `test_resumable_export_cache.py` — Cache Manager Unit
- `test_cache_and_clear_active_export_job` — `BackendCacheManager.cache_active_export_job()`, `get_active_export_job()`, `clear_active_export_job()`

**Does NOT test:** MainScreen, screens, export orchestration, UI

#### `test_framework.py` — Not Actually Tests
This is a `BackendTestFramework` class (not pytest test classes). It defines test infrastructure methods but contains zero `test_*` methods. It is never imported or run by pytest.

### 3.3 Configuration

| File | Exists? | Notes |
|------|---------|-------|
| `src/frontend/pytest.ini` | No | |
| `src/frontend/pyproject.toml` (pytest config) | No | |
| `src/frontend/tests/conftest.py` | Yes | Provides `mock_backend_server` session fixture |
| `src/frontend/setup.cfg` | No | |

### 3.4 MainScreen Test Coverage: 0%

MainScreen public methods and test status:

| Method | Tested? |
|--------|---------|
| `__init__()` | No |
| `initialize_with_backend()` | No |
| `backend_mode_enabled` (property) | No |
| `on_enter()` | No |
| `load_playlists_with_cache()` | No |
| `_on_backend_playlists_loaded()` | No |
| `_on_backend_error()` | No |
| `_on_backend_progress()` | No |
| `start_export()` | No |
| `cancel_export()` | No |
| `logout()` | No |
| `show_clear_cache_confirmation()` | No |
| `open_cache_explorer()` | No |

**Result: 0/13 public methods tested = 0%**

### 3.5 Other Components: 0%

| Component | Tested? |
|-----------|---------|
| `BackendMainScreenAdapter` | No |
| `BackendPlaylistCard` | No |
| `ResponsiveGridLayout` | No |
| `CacheExplorerPopup` | No |
| `LoginScreen` | No |
| `BackendSpotifyExporterApp` | No |
| Screen transitions | No |
| Export orchestration flow | No |
| Error handling in UI | No |

### 3.6 Summary

| Category | Status |
|----------|--------|
| `BackendClient` | Partially tested (core methods via mock server) |
| `BackendCacheManager` | Partially tested (export job caching) |
| `ReccoBeatsBackendService` | Tested (analyze_playlist) |
| `MockBackendServer` | Used as test infrastructure |
| `MainScreen` / `BackendMainScreen` | **0%** |
| `BackendMainScreenAdapter` | **0%** |
| All UI components | **0%** |
| All screen logic | **0%** |
| Export orchestration | **0%** |

---

## 4. Risk Matrix

Risk is assessed along two axes: **difficulty of extraction** (how hard is it to safely extract without breaking things) and **impact of failure** (what breaks if the extraction goes wrong).

### Risk Levels

| Level | Difficulty | Impact |
|-------|-----------|--------|
| **Low** | Straightforward, self-contained, no external callers | Cosmetic or internal helper only |
| **Medium** | Requires understanding of callers, some external dependencies | Affects a feature but not the whole flow |
| **High** | Deeply intertwined with other code, many callers, global state | Could break the entire export flow or UI |

### Extraction Risk Matrix

| Extraction | Difficulty | Impact | Risk | Rationale |
|------------|-----------|--------|------|-----------|
| **Filename utilities** | Low | Low | **Low** | Pure functions, no side effects, no external callers. Safe to extract first. |
| **Cache management** | Low | Low | **Low** | Self-contained popup + clear logic. Only writes `status_label`. |
| **Logout flow** | Low | Medium | **Low-Medium** | Self-contained popup + `app.logout()` call. Only risk is if logout popup UI changes. |
| **Error popup builder** | Medium | Medium | **Medium** | 90 lines of popup UI construction. Called from `_on_backend_error()` (public API). Needs careful callback binding. |
| **Sort/Search** | Low | Low | **Low** | Already mostly isolated. `_perform_sort()` and `display_playlists_with_cache()` are abstract — already a mixin pattern in spirit. |
| **Selection state** | Low | Medium | **Low-Medium** | `selected_playlist_ids` is read by 6 methods. Extracting to a `SelectionManager` class requires wiring all readers/writers. |
| **UI construction** | Medium | High | **Medium** | `_create_header`, `_create_controls`, `_create_export_section` are called by `build_ui()`. Each builds a large widget tree. Extracting sub-sections is safe but extracting the whole thing risks layout breakage. |
| **Export orchestration** | High | High | **High** | `backend_export_worker` is the most connected method (rank 1). Calls 6 internal + 8 external methods. Uses threading, Clock, global state, and adapter. This is the highest-risk extraction. |
| **Export state machine** | High | High | **High** | The 3-branch structure (combined → fallback → recovery) is deeply woven into `backend_export_worker`. Splitting requires rewriting the control flow. |
| **Clock.schedule_once pattern** | Medium | High | **Medium** | Dozens of scattered calls. Replacing with a helper is low-risk individually but risky as a bulk refactor if any call is missed. |

### Recommended Risk Mitigation

1. **Start with pure functions** (filenames) — zero risk, builds confidence
2. **Extract self-contained flows** (cache, logout) — isolated, easy to verify
3. **Extract the error popup builder** — medium risk but the popup UI is self-contained
4. **Extract export state machine** — high risk, requires test scaffolding first
5. **Tackle Clock pattern last** — low individual risk but high aggregate risk if done in the same PR as other changes

---

## 5. Recommended Extraction Order

A sequence of 8 steps, each producing a working, testable state. Steps are ordered by increasing complexity and risk.

### Step 1: Extract filename utilities → `main_screen_filenames.py`

**What moves:**
- `_generate_default_filename(format_type)` → `generate_default_filename(app, format_type)`
- `_increment_filename_suffix(filename)` → `increment_filename_suffix(filename)`
- `_get_file_extension(format_type)` → `get_file_extension(format_type)`
- `_selected_export_format()` → removed (screen reads spinner directly, or becomes `get_export_format(spinner)`)
- `_sanitize_export_filename_component(value)` → `sanitize_filename_component(value)`
- `_refresh_filename_after_export()` → `refresh_filename_after_export(filename_input, format_type)`

**Changes to MainScreen:** Import the module. Replace `self._generate_default_filename()` with `generate_default_filename(App.get_running_app(), fmt)`. Replace `self._refresh_filename_after_export()` with a call to the extracted function.

**Verification:** Run the app, trigger an export, verify filename generation and increment work. No behavioral change.

**Risk:** Low. Pure functions.

### Step 2: Extract cache management → `main_screen_cache.py`

**What moves:**
- `show_clear_cache_confirmation()`
- `clear_all_cache()`
- `open_cache_explorer()`

**Changes to MainScreen:** Import the module. Replace method bodies with calls to extracted functions: `show_clear_cache_confirmation(self, update_status)`.

**Verification:** Click "Clear Cache" and "Cache Explorer" buttons. Verify popups appear and cache is cleared.

**Risk:** Low. Self-contained popup flows.

### Step 3: Extract logout flow → `main_screen_logout.py`

**What moves:**
- `logout()`
- `_show_logout_confirmation()`
- `_handle_logout_confirmed()`
- `_perform_logout()`

**Changes to MainScreen:** Import the module. Replace with `perform_logout(self)`.

**Verification:** Click logout. Verify confirmation popup and logout flow.

**Risk:** Low-Medium. Only dependency is `App.get_running_app().logout()`.

### Step 4: Extract error popup builder → `main_screen_error_popup.py`

**What moves:**
- `_show_backend_error_popup(message)`
- `_get_recoverable_backend_export_context()`
- `_set_backend_error_context()` (if it exists — check for this method)

**Changes to MainScreen:** Import the module. `_show_backend_error_popup` becomes `show_backend_error_popup(message, adapter, status_label, begin_export_fn)`.

**Verification:** Trigger a backend error. Verify the popup appears with correct message, trace ID, and resume/discard buttons.

**Risk:** Medium. Called from `_on_backend_error()` (a public callback registered with the adapter). Needs careful callback binding for resume/discard buttons.

### Step 5: Extract sort and search → `main_screen_sort_search.py`

**What moves:**
- `on_sort_change()`
- `update_sort_controls_visibility()`
- `update_sort_direction_button()`
- `toggle_sort_direction()`
- `sort_playlists()`
- `_perform_sort()` (keep as abstract)
- `on_search_text()`
- `_perform_search()`
- `clear_search()`
- `_get_filtered_playlists()`
- `_sort_playlists()`
- `update_status_with_cache_info()`

**Changes to MainScreen:** Import as mixin or compose. The abstract methods `_perform_sort()` and `display_playlists_with_cache()` remain in the base class.

**Risk:** Low. These methods are already somewhat isolated. The main coupling is to `self.status_label` and `self.filtered_playlists`.

### Step 6: Extract selection state → `main_screen_selection.py`

**What moves:**
- `toggle_select_all()`
- `update_selection_counter()`
- `_update_select_all_button_label()`
- `_on_playlist_checkbox_changed()`
- `select_all()`
- `deselect_all()`
- `selected_playlist_ids` (move to a `SelectionManager` class)

**Changes to MainScreen:** `self.selected_playlist_ids` becomes `self.selection_manager`. All reads/writes go through the manager. `update_selection_counter()` becomes `self.selection_manager.update_counter(selection_label, playlists)`.

**Risk:** Low-Medium. `selected_playlist_ids` is read by 6 methods. Extracting requires wiring all references, but each reference is a simple attribute access.

### Step 7: Extract UI construction → `main_screen_ui.py`

**What moves:**
- `build_ui()`
- `_create_header()`
- `_create_controls()`
- `_create_scroll_view()`
- `_create_export_section()`
- `configure_dropdown()`
- `on_format_change()`

**Changes to MainScreen:** `build_ui()` becomes a thin wrapper: `self.ui_builder.build(self)`. Each `_create_*` method becomes a standalone function that receives widgets to populate.

**Risk:** Medium. Extracting sub-section builders (`_create_filename_section`, `_create_action_buttons`, `_create_cache_section` from `_create_export_section`) is safer than extracting the whole method at once.

### Step 8: Extract export orchestration → `main_screen_export.py`

**What moves:**
- `start_export()`
- `_start_backend_export()`
- `_show_backend_overwrite_confirmation()`
- `_handle_backend_overwrite_confirmed()`
- `begin_backend_export()`
- `backend_export_worker()`
- `_backend_export_fallback_sequential()`
- `cancel_export()`
- `cleanup_after_export()`
- `handle_export_cancelled()`
- `_build_backend_output_path()`
- `current_export_job` global (move to `ExportJobStore` interface)

**Changes to MainScreen:** The screen retains a thin `begin_export()` method that delegates to `self.export_orchestrator.begin(playlists, output_path)`. The orchestrator owns the threading, polling, fallback logic, and global state.

**Risk:** High. This is the most complex extraction. The threading model (`threading.Thread` + `Clock.schedule_once`) must be preserved exactly. The `current_export_job` global must continue to be written by the orchestrator and read by `cancel_export()`.

**Mitigation:** Before Step 8, add a thin test harness using `mock_backend.py` to verify export behavior. The mock server already exists in `tests/mock_backend.py`.

---

## Questions for review

1. **Composition vs mixin** — Do you prefer extracting into service objects (cleaner separation, more refactoring) or mixins (preserves current patterns, less change)?

2. **Test strategy** — There are no unit tests for `main_screen.py` currently. Should the assessment include a test scaffolding plan, or keep it to the refactor plan only?

3. **Scope of `BackendMainScreen`** — The 141-line subclass currently overrides 3 methods. After refactoring, it may only need to override 1 (the widget factory). Should the assessment address whether the subclass can be eliminated?

4. **File count preference** — The proposed decomposition creates 6 new files. Less granular (2-3 files) or more granular (8-10 files) be preferable?

1. **Composition vs mixin** — Do you prefer extracting into service objects (cleaner separation, more refactoring) or mixins (preserves current patterns, less change)?

2. **Test strategy** — There are no unit tests for `main_screen.py` currently. Should the assessment include a test scaffolding plan, or keep it to the refactor plan only?

3. **Scope of `BackendMainScreen`** — The 141-line subclass currently overrides 3 methods. After refactoring, it may only need to override 1 (the widget factory). Should the assessment address whether the subclass can be eliminated?

4. **File count preference** — The proposed decomposition creates 6 new files. Less granular (2-3 files) or more granular (8-10 files) be preferable?
