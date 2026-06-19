# Main Screen Refactor Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the partially completed `MainScreen` refactor by cleaning up residual coupling, adding targeted behavioral coverage, and making the documentation tracker match the code.

**Architecture:** Keep `MainScreen` as the Kivy screen and widget owner. Keep extracted modules responsible for pure helpers, cache/logout/error popup flows, scheduling, export orchestration, and export job state. Completion work should avoid another broad rewrite and should only tighten the remaining boundaries around `main_screen.py`.

**Tech Stack:** Python 3, Kivy/KivyMD, pytest, existing frontend backend adapter, existing `src/frontend/state.py` export job state helpers.

---

## Current Audit

The refactor was already mostly implemented before this plan:

- `src/frontend/screens/main_screen.py` is now 1,053 lines, down from the 1,940-line assessment baseline.
- Extracted modules exist: `main_screen_filenames.py`, `main_screen_sort_filter.py`, `main_screen_scheduler.py`, `main_screen_cache.py`, `main_screen_logout.py`, `main_screen_error_popup.py`, and `main_screen_export.py`.
- State helpers exist in `src/frontend/state.py`.
- Focused tests exist for filenames, sort/filter, state, and export orchestration.
- Focused verification passed on June 19, 2026:

```bash
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest \
  src/frontend/tests/test_main_screen_filenames.py \
  src/frontend/tests/test_main_screen_sort_filter.py \
  src/frontend/tests/test_main_screen_state.py \
  src/frontend/tests/test_main_screen_export.py -q
```

Expected before adding cancellation coverage: `22 passed`. Current focused verification after this plan: `23 passed`.

The refactor is complete as of June 19, 2026. `main_screen.py` stale imports were removed, export orchestration cancellation coverage was added, extracted-flow boundaries were verified, and `./scripts/verify-all.sh` passed outside the sandbox.

## File Structure

- Modify: `src/frontend/screens/main_screen.py` — remove imports made obsolete by extraction; keep public wrappers used by other frontend code.
- Modify: `src/frontend/screens/main_screen_export.py` — only if tests expose cancellation or cleanup defects.
- Modify: `src/frontend/tests/test_main_screen_export.py` — add cancellation and terminal cleanup coverage using fake adapters and fake scheduler.
- Modify: `dev-docs/TO_DO.md` — keep the task status and plan link accurate.
- Modify: `dev-docs/refactor-assessments/main_screen-refactor-assessment-2026-06-15.md` — link this completion plan from the original assessment.
- Optional after completion: move `docs/superpowers/plans/2026-06-16-main-screen-refactor-V3.md` to `docs/superpowers/plans/superseded/` or replace it with a short supersession note if no active references depend on it.

---

### Task 1: Remove Stale Imports From `main_screen.py`

**Files:**
- Modify: `src/frontend/screens/main_screen.py`

- [x] **Step 1: Confirm stale imports**

Run:

```bash
rg -n "\bthreading\b|\btime\b|\buuid\b|\bdatetime\b|\bClipboard\b|clear_current_export_job|get_current_export_job|mark_current_export_cancelled|set_current_export_job|CacheExplorerPopup" src/frontend/screens/main_screen.py
```

Expected before edit: hits only in the import section.

- [x] **Step 2: Edit imports**

Remove these lines from `src/frontend/screens/main_screen.py`:

```python
import threading
import time
import uuid
from datetime import datetime
from kivy.core.clipboard import Clipboard
from ..state import (
    clear_current_export_job,
    get_current_export_job,
    mark_current_export_cancelled,
    set_current_export_job,
)
from ..ui.cache_explorer import CacheExplorerPopup
```

Keep these imports because they are still used in `main_screen.py`:

```python
import os
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle
from ..config.backend_config import EXPORT_DIR as SAVE_DIR
```

- [x] **Step 3: Verify no stale references remain**

Run:

```bash
rg -n "\bthreading\b|\btime\b|\buuid\b|\bdatetime\b|\bClipboard\b|clear_current_export_job|get_current_export_job|mark_current_export_cancelled|set_current_export_job|CacheExplorerPopup" src/frontend/screens/main_screen.py
```

Expected: no output.

- [x] **Step 4: Run focused import-sensitive tests**

Run:

```bash
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/test_main_screen_filenames.py src/frontend/tests/test_main_screen_sort_filter.py -q
```

Expected: all tests pass.

---

### Task 2: Add Export Cancellation Branch Coverage

**Files:**
- Modify: `src/frontend/tests/test_main_screen_export.py`
- Modify if needed: `src/frontend/screens/main_screen_export.py`

- [x] **Step 1: Add fake adapter helpers to `test_main_screen_export.py`**

Append these helpers below `FakeScheduler`:

```python
from src.frontend import state


class CancelDuringGenerateAdapter:
    def __init__(self):
        self.trace_id = None
        self.cleared = False

    def set_trace_id(self, trace_id):
        self.trace_id = trace_id

    def clear_active_export_job(self, *_args):
        self.cleared = True

    def generate_batch_export_chunked(self, *_args, **_kwargs):
        state.mark_current_export_cancelled()
        return {"job_id": "job-1", "track_count": 1}

    def download_batch_export(self, *_args, **_kwargs):
        raise AssertionError("download_batch_export should not run after cancellation")
```

- [x] **Step 2: Add worker cancellation test**

Append this test:

```python
def test_worker_stops_when_cancelled_after_generation(orchestrator, mock_screen):
    state.clear_current_export_job()
    mock_screen.backend_adapter = CancelDuringGenerateAdapter()
    mock_screen._get_file_extension.return_value = ".xlsx"
    mock_screen._selected_export_format.return_value = "xlsx"
    mock_screen._sanitize_export_filename_component.side_effect = lambda value: value
    state.set_current_export_job(
        job_id="job-1",
        playlist_ids=["playlist-1"],
        export_format="xlsx",
        output_path="/tmp/export.xlsx",
    )

    orchestrator.backend_export_worker(
        [{"id": "playlist-1", "name": "Playlist 1"}],
        "/tmp/export.xlsx",
    )

    assert mock_screen.status_label.text == "Export cancelled"
    assert state.get_current_export_job() is None
```

- [x] **Step 3: Run the new test**

Run:

```bash
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/test_main_screen_export.py::test_worker_stops_when_cancelled_after_generation -q
```

Expected: pass. If it fails because the worker continues to download after cancellation, add an `_check_cancelled()` call immediately after `generate_batch_export_chunked(...)` in `src/frontend/screens/main_screen_export.py`.

- [x] **Step 4: Run all export tests**

Run:

```bash
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/test_main_screen_export.py -q
```

Expected: all tests pass.

---

### Task 3: Verify Extracted Flow Boundaries

**Files:**
- Modify if needed: `src/frontend/screens/main_screen.py`
- Modify if needed: `src/frontend/screens/main_screen_export.py`
- Modify if needed: `src/frontend/screens/main_screen_cache.py`
- Modify if needed: `src/frontend/screens/main_screen_logout.py`
- Modify if needed: `src/frontend/screens/main_screen_error_popup.py`

- [x] **Step 1: Confirm old god-method bodies are gone from `main_screen.py`**

Run:

```bash
rg -n "generate_batch_export_chunked|download_batch_export|generate_export|download_export|Clipboard.copy|Confirm Cache Clear|Confirm Logout|Backend Error Details" src/frontend/screens/main_screen.py
```

Expected: no output. Any hit means a moved flow leaked back into `main_screen.py`.

- [x] **Step 2: Confirm wrappers remain for compatibility**

Run:

```bash
rg -n "def _start_backend_export|def backend_export_worker|def cancel_export|def logout|def show_clear_cache_confirmation|def _show_backend_error_popup" src/frontend/screens/main_screen.py
```

Expected: one wrapper per listed method.

- [x] **Step 3: Confirm extracted modules own the moved behavior**

Run:

```bash
rg -n "generate_batch_export_chunked|download_batch_export|generate_export|download_export|Clipboard.copy|Confirm Cache Clear|Confirm Logout|Backend Error Details" src/frontend/screens/main_screen_export.py src/frontend/screens/main_screen_cache.py src/frontend/screens/main_screen_logout.py src/frontend/screens/main_screen_error_popup.py
```

Expected: hits in the extracted modules only.

---

### Task 4: Repair Refactor Documentation

**Files:**
- Modify: `dev-docs/TO_DO.md`
- Modify: `dev-docs/refactor-assessments/main_screen-refactor-assessment-2026-06-15.md`

- [x] **Step 1: Update `dev-docs/TO_DO.md`**

The main item should be checked after final verification:

```markdown
- [x] **High Priority: Complete main screen refactor** — [completion plan](../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md). Completed after cleanup, cancellation branch coverage, and full verification.
  - [x] Task 0: Cleanup dead code (_show_error_dialog, _log_error, _update_export_status)
  - [x] Task 1: Extract filename and format helpers -> `main_screen_filenames.py` + tests
  - [x] Task 1.5: Extract sort and filter helpers -> `main_screen_sort_filter.py` + tests
  - [x] Task 2: Fix export cancellation state in `state.py` + tests
  - [x] Task 3: Make playlist widget factory hook real in `MainScreen` / `BackendMainScreen`
  - [x] Task 4: Extract cache and logout flows -> `main_screen_cache.py`, `main_screen_logout.py`
  - [x] Task 5: Extract backend error popup -> `main_screen_error_popup.py`
  - [x] Task 6: Extract export orchestration -> `main_screen_export.py`, `main_screen_scheduler.py`
  - [x] Completion Task A: Remove stale imports from `main_screen.py`
  - [x] Completion Task B: Add export cancellation branch coverage
  - [x] Completion Task C: Run full verification and update this item
```

- [x] **Step 2: Update the original assessment**

Add this block below the assessment title metadata:

```markdown
> **2026-06-19 status:** This refactor has been completed and verified. `main_screen.py` is now 1,053 lines, the planned helper modules exist, cancellation branch coverage was added, and completion details are tracked in [Main Screen Refactor Completion Implementation Plan](../../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md).
```

- [x] **Step 3: Verify links resolve from their source files**

Run:

```bash
test -f docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md
test -f "$(dirname dev-docs/TO_DO.md)/../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md"
test -f "$(dirname dev-docs/refactor-assessments/main_screen-refactor-assessment-2026-06-15.md)/../../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md"
```

Expected: all commands exit 0.

---

### Task 5: Final Verification

**Files:**
- Modify if needed: any file changed by failures found in this task.

- [x] **Step 1: Run focused main-screen tests**

Run:

```bash
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest \
  src/frontend/tests/test_main_screen_filenames.py \
  src/frontend/tests/test_main_screen_sort_filter.py \
  src/frontend/tests/test_main_screen_state.py \
  src/frontend/tests/test_main_screen_export.py -q
```

Expected: all tests pass.

- [x] **Step 2: Run frontend tests**

Run:

```bash
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v
```

Expected: all tests pass.

- [x] **Step 3: Run repository verification**

Run:

```bash
./scripts/verify-all.sh
```

Expected: silent success or a zero exit status.

- [x] **Step 4: Update tracker when complete**

After Steps 1-3 pass, change the main item in `dev-docs/TO_DO.md` to checked:

```markdown
- [x] **High Priority: Complete main screen refactor** — [completion plan](../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md). Completed after cleanup, cancellation branch coverage, and full verification.
```

Leave the completed subtask checkboxes in place as evidence.
