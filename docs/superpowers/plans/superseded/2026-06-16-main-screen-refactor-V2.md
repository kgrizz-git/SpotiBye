# Main Screen Refactor Implementation Plan (V2 - IMPROVED)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `src/frontend/screens/main_screen.py` into smaller, testable units without changing playlist loading, selection, export, resume, cache, or logout behavior.

**Architecture:** Start by extracting pure helpers and stabilizing export job state, then split low-risk screen flows, then move export orchestration behind a narrow object. Keep `MainScreen` as the Kivy `Screen` owner and keep `BackendMainScreen` as the playlist-card implementation until the factory seam is real.

**Tech Stack:** Python 3, Kivy/KivyMD, pytest, existing frontend backend adapter and cache manager.

---

## Assessment Accuracy Check (Updated)

- `src/frontend/screens/main_screen.py` is 1,940 lines and has 73 `def` methods.
- `current_export_job` state is currently vestigial/broken; Task 2 will fix this.
- `MainScreen` does not directly import `BackendMainScreenAdapter`; coupling is structural.
- `BackendPlaylistCard` is imported by `backend_main_screen.py`.
- `_show_error_dialog()`, `_log_error()`, and `_update_export_status()` are dead code and will be removed.
- Cache explorer adapter lives at `src/frontend/screens/cache_explorer_adapter.py`.

## File Structure Target

- Modify: `src/frontend/screens/main_screen.py` — keep Kivy lifecycle, widget ownership, and thin delegation wrappers.
- Modify: `src/frontend/screens/backend_main_screen.py` — switch display/sort creation to a real widget factory seam.
- Modify: `src/frontend/state.py` — replace raw mutable global access with small job-state functions.
- Create: `src/frontend/screens/main_screen_filenames.py` — pure filename and format helpers (preserving existing format).
- Create: `src/frontend/screens/main_screen_sort_filter.py` — pure sort and filter functions.
- Create: `src/frontend/screens/main_screen_scheduler.py` — one Kivy scheduling adapter.
- Create: `src/frontend/screens/main_screen_cache.py` — cache popup and cache explorer flow (fixed signature).
- Create: `src/frontend/screens/main_screen_logout.py` — logout confirmation flow.
- Create: `src/frontend/screens/main_screen_error_popup.py` — backend error details popup.
- Create: `src/frontend/screens/main_screen_export.py` — export orchestration object.
- Create: `src/frontend/tests/test_main_screen_filenames.py` — unit tests.
- Create: `src/frontend/tests/test_main_screen_state.py` — job-state unit tests.
- Create: `src/frontend/tests/test_main_screen_sort_filter.py` — unit tests for sort/filter.
- Create: `src/frontend/tests/test_main_screen_export.py` — orchestrator tests with fake scheduler.
- Modify: `CHANGELOG.md` — required for bug fixes and refactor summary.

---

### Task 0: Cleanup Dead Code

**Files:**
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Delete unreachable methods**
Delete `_show_error_dialog`, `_log_error`, and `_update_export_status` from `MainScreen`.

- [ ] **Step 2: Verify no references remain**
Run `rg "_show_error_dialog|_log_error|_update_export_status" src/frontend` to ensure zero hits.

---

### Task 1: Extract Filename And Format Helpers

**Files:**
- Create: `src/frontend/tests/test_main_screen_filenames.py`
- Create: `src/frontend/screens/main_screen_filenames.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Write failing tests**
Create `src/frontend/tests/test_main_screen_filenames.py`. **Note:** Must match existing `Spotify_Playlists_{user}_{YYYY-MM-DD_HH-MM-SSAM/PM}.xlsx` format.

- [ ] **Step 2: Implement helper module**
Create `src/frontend/screens/main_screen_filenames.py`. Ensure `generate_default_filename` and `sanitize_export_filename_component` match existing behavior exactly (no extra underscore collapsing).

- [ ] **Step 3: Wire `MainScreen` to helper module**
Replace existing methods with delegation.

- [ ] **Step 4: Run focused tests**
`pytest src/frontend/tests/test_main_screen_filenames.py -q`

---

### Task 1.5: Extract Sort and Filter Helpers

**Files:**
- Create: `src/frontend/tests/test_main_screen_sort_filter.py`
- Create: `src/frontend/screens/main_screen_sort_filter.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Write tests for sort/filter**
Test `_get_filtered_playlists` and `_sort_playlists` logic with various inputs.

- [ ] **Step 2: Implement `src/frontend/screens/main_screen_sort_filter.py`**
Move logic for filtering (search text, selected only) and sorting (name, track count, date) into pure functions.

- [ ] **Step 3: Delegate from `MainScreen`**
Update `_get_filtered_playlists` and `_sort_playlists` to call the new functions.

---

### Task 2: Fix Export Cancellation Bug and Stabilize State

**Files:**
- Create: `src/frontend/tests/test_main_screen_state.py`
- Modify: `src/frontend/state.py`
- Modify: `src/frontend/screens/main_screen.py`
- Modify: `src/frontend/app/backend_app.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Implement job-state functions in `src/frontend/state.py`**
Add `set_current_export_job`, `get_current_export_job`, `mark_current_export_cancelled`, and `clear_current_export_job`.

- [ ] **Step 2: Update `MainScreen.cleanup_after_export`**
Add `clear_current_export_job()` to the end of `cleanup_after_export`. This ensures state is cleared on all terminal paths (success, failure, cancellation).

- [ ] **Step 3: Fix cancellation polling in `backend_export_worker`**
Add checks for `job.get("cancelled")` at these critical points in `main_screen.py`:
1. Before `generate_batch_export_chunked` (L1353)
2. Before `_backend_export_fallback_sequential` (L1364)
3. Before `download_batch_export` (L1502)
4. Before recovery/redownload pass (L1523)
5. Before second `download_batch_export` (L1537)
6. Before final sequential fallback (L1548)
7. Inside `_backend_export_fallback_sequential` loop (L1626)

If cancelled, call `Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)` and return.

- [ ] **Step 4: Fix `cancel_export` and `on_stop`**
Replace vestigial `if current_export_job:` guards with `mark_current_export_cancelled()`.
Ensure `cancel_export` button re-enables via `cleanup_after_export`.

- [ ] **Step 5: Update CHANGELOG**
Record the fix for export cancellation state.

---

### Task 3: Route Playlist Widget Construction via Factory Hook

**Files:**
- Modify: `src/frontend/screens/main_screen.py`
- Modify: `src/frontend/screens/backend_main_screen.py`

- [ ] **Step 1: Add `_make_playlist_widget` stub to `MainScreen`**
- [ ] **Step 2: Replace `BackendPlaylistCard` literals in `backend_main_screen.py`**
Replace direct calls with `self._make_playlist_widget(playlist)`.
- [ ] **Step 3: Commit**
Use message: `refactor: route BackendMainScreen card construction through factory hook`

---

### Task 4: Extract Cache and Logout Flows

**Files:**
- Create: `src/frontend/screens/main_screen_cache.py`
- Create: `src/frontend/screens/main_screen_logout.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Implement `main_screen_cache.py`**
**CRITICAL:** `open_cache_explorer` must call `create_cache_explorer()` with **zero arguments**. Drop the `cache_manager` argument from the plan's previous draft.

- [ ] **Step 2: Implement `main_screen_logout.py`**
Move logout flow logic unchanged.

- [ ] **Step 3: Delegate from `MainScreen`**

---

### Task 5: Extract Backend Error Popup

**Files:**
- Create: `src/frontend/screens/main_screen_error_popup.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Move popup logic**
Move `_show_backend_error_popup` and `_get_recoverable_backend_export_context` to the new module.

---

### Task 6: Extract Export Orchestration

**Files:**
- Create: `src/frontend/tests/test_main_screen_export.py`
- Create: `src/frontend/screens/main_screen_scheduler.py`
- Create: `src/frontend/screens/main_screen_export.py`
- Modify: `src/frontend/screens/main_screen.py`

- [ ] **Step 1: Implement `KivyScheduler`**
Drop `set_attr_soon` as it is currently unused.

- [ ] **Step 2: Move helper methods FIRST**
Move these methods to `MainScreenExportOrchestrator` (with `MainScreen` wrappers) before moving the worker body:
`_start_backend_export`, `_show_backend_overwrite_confirmation`, `_handle_backend_overwrite_confirmed`, `cancel_export`, `cleanup_after_export`, `handle_export_cancelled`, `_build_backend_output_path`.

- [ ] **Step 3: Move worker and fallback bodies**
Now that helper wrappers/delegates exist, move `backend_export_worker` and `_backend_export_fallback_sequential` bodies.

- [ ] **Step 4: Add Orchestrator Tests**
Create `src/frontend/tests/test_main_screen_export.py`. Test the orchestrator using a fake scheduler to verify threading and delegation without Kivy.

---

## Final Verification

- [ ] Run `./scripts/verify-all.sh`.
- [ ] Manually verify: Login, Refresh, Search/Sort/Select, Export (single/multi), Cancel, Error Popup, Resume, Cache, Logout.
- [ ] Confirm no bare `except:` blocks or dead code remains.
