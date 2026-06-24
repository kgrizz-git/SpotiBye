# Refactor main_screen.py

## Objective
Refactor `src/frontend/screens/main_screen.py` (currently ~1,041 lines) to improve maintainability and readability. Export, cache, and logout logic are already extracted; this pass extracts UI construction, search/sort event handling, and selection state into dedicated modules. Target size: **~450–500 lines** (facade surface on `MainScreen` makes tighter targets unrealistic).

## Constraints

1. **Subclass compatibility**: `BackendMainScreen` reads/writes `selected_playlist_ids`, `search_query`, `filtered_playlists`, `current_sort_key`, and `current_sort_reverse` on `self`. Keep backward-compatible property facades on `MainScreen` that delegate to handlers. `selected_playlist_ids` must return the **live mutable set**; `filtered_playlists` needs getter and setter (subclass assigns in `display_playlists_with_cache`; `load_playlists_with_cache` clears it).
2. **Polymorphic dispatch**: Handlers call `self.screen.display_playlists_with_cache()` and sort debounce must end in `self.screen._perform_sort()`. `_perform_sort()` stays on `MainScreen` as an overridable stub (`raise NotImplementedError` — `BackendMainScreen` overrides it).
3. **Init order**: In `MainScreen.__init__`, instantiate managers **before** `build_ui()`. Facade methods/properties must exist before the UI builder binds events:
   ```python
   self.selection_manager = SelectionManager(self)
   self.search_sort = SearchSortUIHandler(self)
   ```
4. **Handler convention**: Both handlers take `screen: MainScreen`, store `self.screen = screen`, and access the screen only via `self.screen.*`. `MainScreen` accesses handlers via `self.selection_manager` / `self.search_sort`.
5. **Event bindings**: UI builder binds Kivy events to `MainScreen` facade methods (e.g. `screen.on_search_text`), not directly to handlers.
6. **Naming**: Rename instance method `sort_playlists()` → `schedule_sort_refresh()` to avoid collision with imported `sort_playlists` from `main_screen_sort_filter.py`.
7. **Imports**: Use `from __future__ import annotations` and `TYPE_CHECKING` guards in new helper modules.

## Widget contract

`MainScreenUIBuilder` must assign these on `screen`:

- **Header & controls**: `username_label`, `sort_spinner`, `by_label`, `sort_direction_btn`, `search_input`, `select_all_btn`, `selection_label`
- **Playlist area**: `playlist_layout` (in `build_ui` when scroll/content layout is created — mirrors current ~line 115)
- **Export**: `filename_input`, `format_spinner`, `export_btn`, `cancel_btn`, `progress_bar`, `status_label`, `clear_cache_btn`, `cache_explorer_btn`

Local-only (no `screen.*` attribute): `clear_search_btn`, `clear_all_btn`, `reload_btn`, `logout_btn`.

**On `MainScreen` (not built by UI builder):** `playlist_widgets` — list of row widgets; initialized in `__init__`, mutated by `load_playlists_with_cache`, `display_playlists_with_cache`, and `_perform_sort`. `SelectionManager` reads it via `self.screen.playlist_widgets` for toggle/deselect/counter logic; the manager owns only `selected_playlist_ids`.

## MainScreen facade API

Complete list — implement on `MainScreen` before `build_ui()`:

| Facade | Delegates to | Bound / called by |
|---|---|---|
| `selected_playlist_ids` (property) | `SelectionManager` live set | `BackendMainScreen`, export |
| `search_query` (property) | `SearchSortUIHandler` | `BackendMainScreen`, `update_status_with_cache_info` |
| `filtered_playlists` (property, get/set) | `SearchSortUIHandler` | `BackendMainScreen.display_playlists_with_cache`, `load_playlists_with_cache` |
| `current_sort_key` (property) | `SearchSortUIHandler` | `BackendMainScreen.display_playlists_with_cache` |
| `current_sort_reverse` (property) | `SearchSortUIHandler` | `BackendMainScreen.display_playlists_with_cache` |
| `update_selection_counter` | `SelectionManager` | checkbox handlers |
| `_on_playlist_checkbox_changed` | `SelectionManager` | `BackendMainScreen` widget bind |
| `toggle_select_all` | `SelectionManager` | `select_all_btn` |
| `deselect_all` | `SelectionManager` | `clear_all_btn` |
| `on_search_text` | `SearchSortUIHandler` | `search_input` |
| `_perform_search` | `SearchSortUIHandler` | debounce callback |
| `clear_search` | `SearchSortUIHandler` | `clear_search_btn` |
| `schedule_sort_refresh` | `SearchSortUIHandler` | sort debounce entry |
| `reset_sort_ui` | `SearchSortUIHandler` | `load_playlists_with_cache` |
| `configure_dropdown` | `SearchSortUIHandler` | `sort_spinner` `on_press` |
| `on_sort_change` | `SearchSortUIHandler` | `sort_spinner` `on_text` |
| `toggle_sort_direction` | `SearchSortUIHandler` | `sort_direction_btn` |
| `update_sort_controls_visibility` | `SearchSortUIHandler` | `on_enter` (`Clock.schedule_once`) |
| `update_sort_direction_button` | `SearchSortUIHandler` | internal / `reset_sort_ui` |
| `_get_filtered_playlists` | `SearchSortUIHandler` logic via property reads | `BackendMainScreen` |
| `_sort_playlists` | `SearchSortUIHandler` logic via property reads | `BackendMainScreen` |
| `_perform_sort` | overridable on `MainScreen` | sort debounce terminus |
| `on_format_change` | thin method on `MainScreen` | `format_spinner` `on_text` |

Methods that stay on `MainScreen` but must route through facades: `load_playlists_with_cache` → `reset_sort_ui()` + `filtered_playlists` setter; `on_enter` → schedule `update_sort_controls_visibility()`; `update_status_with_cache_info` → read `search_query` / `filtered_playlists` via properties.

## Plan

- [ ] **Step 1: File backups**
  - `mkdir -p backups`, then copy `main_screen.py` and `backend_main_screen.py` to `backups/` before edits.

- [ ] **Step 2: Extract `SelectionManager`**
  - Create `src/frontend/screens/main_screen_selection.py` — `__init__(self, screen)` stores `self.screen`, owns `selected_playlist_ids` set.
  - Move selection logic; remove unused `select_all()`. Read `playlist_widgets` via `self.screen.playlist_widgets`.
  - Wire facades from the table (`selected_playlist_ids` property + selection methods).

- [ ] **Step 3: Extract `SearchSortUIHandler`**
  - Create `src/frontend/screens/main_screen_search_sort_ui.py` — same `__init__(self, screen)` convention.
  - Move debounced search/sort UI logic and state (`search_query`, sort keys, `_search_trigger` / `_sort_trigger`, `filtered_playlists`). Guard trigger cancel: `if self._search_trigger: self._search_trigger.cancel()`.
  - Rename method `sort_playlists` → `schedule_sort_refresh()`; debounce terminus calls `self.screen._perform_sort()`.
  - `clear_search`: cancel trigger, clear `self.screen.search_input`, reset `search_query`, set `self.screen.playlist_layout.parent.scroll_y = 1.0`, call `self.screen.display_playlists_with_cache()`.
  - Keep `_get_filtered_playlists` / `_sort_playlists` on `MainScreen` as one-liner facades that read `search_query`, `current_sort_key`, `current_sort_reverse` via **property facades** (not raw attributes). `BackendMainScreen` call sites unchanged.
  - Wire remaining search/sort facades from the table.

- [ ] **Step 4: Extract `MainScreenUIBuilder`**
  - Create `src/frontend/screens/main_screen_ui.py`; move `build_ui` and `_create_*` helpers with their Kivy widget imports (including `RelativeLayout` — currently imported at module top and again inside export section).
  - Builder takes `MainScreen`, assigns widget contract attributes, binds events to `screen.*` facades.
  - Preserve existing `background_color` list literals as-is (Kivy 2.2+ tuple migration is out of scope).
  - `MainScreen.__init__`: managers first (see constraint #3), then `build_ui()`.

- [ ] **Step 5: Consolidate `main_screen.py`**
  - Remove unused top-level `import re` (line 6).
  - Remove duplicate `RelativeLayout` import (now lives in UI builder module).
  - Keep on `MainScreen`: `playlists`, `playlist_widgets`, `backend_adapter`, `on_format_change`, `on_enter`, `load_playlists_with_cache`, `update_status_with_cache_info`, `_perform_sort` stub (`raise NotImplementedError`).
  - Verify ~450–500 lines.

- [ ] **Step 6: Documentation**
  - Update `dev-docs/code-map.md`.
  - Manually update `dev-docs/dependency-graph.json` with new module import edges (no generator script — follow pattern in completed adapter/export plans).
  - On completion: move plan to `docs/exec-plans/completed/` and index in `docs/exec-plans/completed/README.md`.
  - No `CHANGELOG.md` entry (internal refactor).

- [ ] **Step 7: Verification**
  - **Unit tests** (mock `screen` with `selection_manager` / `search_sort`; patch `Clock.schedule_once` for debounce):
    - `SelectionManager`: toggle/deselect all, checkbox → live set, counter label.
    - `SearchSortUIHandler`: debounce + cancel on rapid input; search/clear trigger `display_playlists_with_cache`; sort triggers `screen._perform_sort` once after debounce.
    - `test_main_screen_facades.py`: `screen.selected_playlist_ids is screen.selection_manager.selected_playlist_ids`; mutation via property visible to manager; property round-trip for search/filter/sort state.
  - **Frontend suite**: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
  - **Headed `BackendMainScreen` smoke** (login → search debounce → clear search → sort + direction → select all/clear all → single checkbox + filter persistence → export with selection).
  - Sync `dev-docs/TO_DO.md`.

## Out of scope

- `main_screen_logout.logout` counts selection from visible checkboxes, not `selected_playlist_ids` — pre-existing; fix separately.
- Hardcoded ReccoBeats header text in `_create_header` — stale copy.
- `background_color` list → tuple migration for Kivy 2.2+.
