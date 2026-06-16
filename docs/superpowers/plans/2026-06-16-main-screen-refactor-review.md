# Main Screen Refactor — Plan Review Notes

> **Status:** Pre-implementation review of `2026-06-16-main-screen-refactor.md`.
> These notes are linked from the top of the plan and should be resolved
> before any Task 1+ code is written.
>
> **Revision history:**
> - v1 (initial): framed concern #3 as the plan adding a behavior change
>   dressed as state refactor.
> - v2: the original author confirmed in a side comment that
>   `current_export_job` is "not actually set anywhere; cancellation
>   state is likely broken/vestigial" and that Task 2 is intentionally
>   fixing the cancellation bug, not just stabilizing state. Concern #3
>   reframed. Also: actual method count is **73**, not 65.
> - v3 (this version): research items R1-R7 investigated against the
>   current codebase. Concern #2 retracted — the adapter method
>   `clear_active_export_job` does exist (see R6/Correction below).

## Summary

The plan is directionally correct: `main_screen.py` is 1,940 lines, mixes UI
construction with export orchestration, and the existing `BackendMainScreen`
factory override is the natural seam. The Assessment Accuracy Check itself is
honest about the corrections, which is good. But there are **3 critical
errors** that will break tests or runtime behavior on first execution,
**5 design gaps** that will produce dead code, regressions, or test files
with no corresponding production change, and **6 research items** that
should be confirmed before Task 1.

---

## Critical errors (block Task 1+ as written)

### 1. `create_cache_explorer` signature mismatch (Task 4)

**Plan (line 554-557):**
```python
def open_cache_explorer(screen, create_cache_explorer, backend_available: bool, *_args) -> None:
    try:
        if backend_available and screen.backend_adapter:
            popup = create_cache_explorer(screen.backend_adapter.cache_manager)
```

**Actual (`src/frontend/screens/cache_explorer_adapter.py:80`):**
```python
def create_cache_explorer() -> CacheExplorerPopup:
    """Create appropriate cache explorer popup."""
    adapter = get_cache_explorer_adapter()
    return adapter.get_cache_explorer()
```

The real function takes **zero arguments** and resolves the adapter
internally. The plan invents a `cache_manager` parameter that does not
exist. Additionally, the current `MainScreen.open_cache_explorer`
(main_screen.py:1856-1879) does not pass the cache manager — passing it is
a **behavior change**, not a mechanical move. This will raise
`TypeError: create_cache_explorer() takes 0 positional arguments` on first
open.

**Fix:** In the moved function, call `create_cache_explorer()` with no
arguments. Drop the `cache_manager` argument from the function signature
and from the `MainScreen` wrapper.

---

### 2. ~~`cancel_export` references a non-existent adapter method~~ — RETRACTED

**Plan (line 378-389):**
```python
def cancel_export(self, *_args) -> None:
    if mark_current_export_cancelled():
        if self.backend_adapter:
            self.backend_adapter.clear_active_export_job()
        ...
```

**Correction (per R6 research):** `clear_active_export_job` *does* exist on
`BackendMainScreenAdapter` at `backend_main_screen_adapter.py:1012`:
```python
def clear_active_export_job(self, export_id: Optional[str] = None) -> None:
    """Clear persisted active resumable export job metadata."""
    cached_job = self.cache_manager.get_active_export_job()
    if export_id and isinstance(cached_job, dict):
        cached_job_id = str(cached_job.get("job_id") or "")
        if cached_job_id and cached_job_id != export_id:
            return
    self.cache_manager.clear_active_export_job()
```

It is also defined on `BackendCacheManager` at `caching/backend_cache.py:258`
and is exercised by `test_resumable_export_cache.py:21`. The plan's call
`self.backend_adapter.clear_active_export_job()` (no args) is valid and
uses the existing public API. **This concern is retracted.**

---

### 3. Worker polling is a legitimate bug fix, but the plan text doesn't say so (Task 2)

**Plan (lines 358-373):** Injects cancellation checks "before each
backend generation/download step and inside the sequential loop" and
add a `clear_current_export_job()` call "at every successful terminal
path and every failed terminal path."

**Context (from the original author's side comment):** "`current_export_job`
is not actually set anywhere; cancellation state is likely
broken/vestigial, so the plan stabilizes that before export extraction."
That confirms Task 2 is fixing a known-broken cancellation path, not
adding new behavior. The CHANGELOG entry under Step 6 also frames it
as a fix. **So the polling is in scope and justified.** The concern
below is about plan-text clarity, not about whether the change should
happen.

**Problems with how it's currently specified:**

- The plan text under Step 4 reads as a state refactor, not a bug fix.
  A reviewer reading the plan in isolation cannot tell that the worker
  currently never checks `cancelled` and that this task adds the check.
  The intent is in a side comment, not in the plan.
- The polling sites are vague: "before each backend
  generation/download step and inside the sequential loop." The current
  worker has at least 6 candidate check points (main_screen.py:1305,
  1323, 1412, 1539, 1553, 1566). A vague instruction makes it easy to
  pick the wrong points and ship a partial fix.
- The terminal paths needing `clear_current_export_job()` are not
  enumerated. Missing any one leaks global state into the next export.
- The `handle_export_cancelled` referenced in the new check
  (`Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)`)
  is not defined in the plan's visible context. Need to confirm it
  exists on `MainScreen` (it is not in the Step 7 move list).

**Fix:** Reword Task 2 Step 4 to lead with "Fix the cancellation bug
introduced by vestigial state — the worker must poll the cancelled
flag and clear job state on every terminal path." Then **enumerate**
the check points and the cleanup sites by line number or by named
subroutine in the current worker. Add `handle_export_cancelled` to the
Step 4 wiring explicitly (or confirm it exists). The CHANGELOG entry
already says "Fixed" which matches the new framing — keep that.

---

### 4. `cancel_export` button never re-enables (Task 2, lines 378-389)

After cancellation the new code sets `self.cancel_btn.disabled = True`
and `text = "Cancelling..."`. Nothing in the visible path restores the
button. The current `cleanup_after_export` (main_screen.py:1699) handles
button reset, but the plan doesn't say which moved method (Task 6,
Step 7) restores it. Most likely it lives inside `cleanup_after_export`,
but Task 6 moves cleanup *after* Task 2 ships, so the button will be
permanently disabled for one release.

**Fix:** Either reorder so `cleanup_after_export` is moved before
`cancel_export` in Task 6, or add a Step 4.5 to Task 2 that
preserves the existing button-reset behavior inline.

---

### 5. Filename format silently rewritten (Task 1)

**Plan (line 134-145):** New helper emits
`spotify_playlists_Ada_Lovelace_20260616.xlsx`.

**Actual (`main_screen.py:1882-1894`):** Current code emits
`Spotify_Playlists_{user}_{YYYY-MM-DD_HH-MM-SSAM/PM}.xlsx`.

The Goal section says "without changing… file naming." Task 1 changes
it. The test asserts the new format and will pass while the user-visible
filename is different. **There is no CHANGELOG entry for this** — the
plan only requires a CHANGELOG update if cancellation or export
behavior changes.

**Fix:** Decide whether the format change is in scope. If yes, add a
CHANGELOG entry under Task 1. If no, match the existing format in
`generate_default_filename` and `generate_default_filename_uses_username_date_and_extension`
test (or change the test name/assertion to match intent).

---

## Design gaps

### 6. Task 3 factory seam is largely a no-op

`BackendMainScreen._make_playlist_widget()` already exists
(backend_main_screen.py:23). The only place the base class is *missing*
the override is the two `BackendPlaylistCard(playlist)` literal calls
in `backend_main_screen.py:49` and `backend_main_screen.py:100`. The
real work is replacing those two literals. Adding a
`NotImplementedError` stub to `MainScreen` is fine, but the Step 2 text
contradicts itself: "replace both direct `BackendPlaylistCard(playlist)`
calls with… `self._make_playlist_widget(playlist)`" and then "Keep the
existing `_make_playlist_widget()` implementation" — but the existing
implementation is already an override, not a no-op. The step is
mostly correct but the prose is confusing. The Task 3 commit message
("add main screen playlist widget factory seam") overstates the change.

**Fix:** Rename commit message to "route BackendMainScreen card
construction through factory hook" and tighten Step 2 prose.

---

### 7. `_get_filtered_playlists` and `_sort_playlists` are never extracted

`test_main_screen_sort_selection.py` is in the file list (line 41), but
no task in the plan moves `_get_filtered_playlists` (main_screen.py:946)
or `_sort_playlists` (main_screen.py:976) out of `MainScreen`. The test
file is created with no production code to exercise. The Assessment
Accuracy Check confirms they are "not dead code; `BackendMainScreen`
calls both" — so they are reachable but not testable from a non-screen
module.

**Fix:** Either add a Task 1.5 that extracts these into a screen-free
module (pure functions over the playlist list), or remove the test file
from the list. Recommend extracting — the plan's stated goal is
"smaller, testable units" and these are the easiest pure-function
candidates.

---

### 8. `main_screen_export.py` worker body cannot move before its callees (Task 6, Steps 5-7)

`backend_export_worker` calls:
- `self._show_backend_error_popup`
- `self.cleanup_after_export`
- `self._selected_export_format`
- `self._sanitize_export_filename_component`
- `self._get_file_extension`
- `self._backend_export_fallback_sequential`
- `self._handle_backend_overwrite_confirmed`

And mutates: `self.filename_input`, `self.status_label`,
`self.cancel_btn`, `self.progress_bar`.

Step 5 says "Move the body of `backend_export_worker()` into
`MainScreenExportOrchestrator.worker()`" with a thin wrapper. But the
methods the worker calls are listed in Step 7 as moves that come
*after* Step 5. If Step 5 moves the body with the original
`self.<method>()` calls, the orchestrator must either (a) also reach
into `screen.<method>()` (which works if the wrappers exist) or (b)
forward through the orchestrator.

Reading Step 5 carefully: "Replace `self.` references that refer to
screen widgets or screen helper methods with `screen.` after
assigning `screen = self.screen`." This works **only if wrappers are
in place** for every callee. Step 5 ships before the callees are moved
(Step 7), so the wrappers do exist at that point — but the orchestrator
ends up with a `worker()` that calls `screen._show_backend_error_popup`
which calls `main_screen_error_popup.show_backend_error_popup(screen, ...)`
which is a 3-hop indirection. That's fine, but it means the wrappers
are load-bearing in ways Step 5 doesn't acknowledge.

**Fix:** Reorder Task 6 to move the helper methods first, then the
worker. Or commit Step 5 as a no-op (worker still on `MainScreen`,
orchestrator just calls `screen.backend_export_worker()`) and only
commit Step 5's body move in a follow-up after Step 7 is done.

---

### 9. No test for the export orchestrator

The plan creates an orchestrator that owns threading, scheduling, and
the entire export flow, but the test plan stops at filenames and
job-state. The orchestrator's `worker()` is a passthrough on day one;
the real testable seam only materializes after Step 7. Adding at
least one orchestrator-level test (with `KivyScheduler` replaced by a
fake `RecordingScheduler`) would justify the abstraction and catch
regressions in the threading contract.

**Fix:** Add a test that constructs `MainScreenExportOrchestrator`
with a fake scheduler, calls `.begin(...)`, and asserts the worker
runs with the right arguments. Place it in `test_main_screen_export.py`.

---

### 10. `KivyScheduler.set_attr_soon` is dead on day one

The adapter defines `set_attr_soon` (line 794) but no caller uses it.
No extraction in the plan references it.

**Fix:** Drop `set_attr_soon` from the adapter, or add a docstring
noting it's a forward-looking hook for later extractions. Dead code on
day one violates the plan's "no `console.log` in non-test backend
code" / minimum-surface-area spirit.

---

## Pre-implementation research (R1-R7)

**Status: complete. All seven items checked against the current
codebase. Results below.**

### R1. Does `scripts/verify-all.sh` exist? — YES

`/scripts/verify-all.sh` exists and is executable. It calls
`./scripts/verify-backend.sh` then `./scripts/verify-frontend.sh`.

`verify-frontend.sh` (20 lines) does:
```bash
cd "$REPO_ROOT/src/frontend"
python -m pytest tests/ -q
```
Silent on success, prints failures on error. No virtualenv requirement
enforced (only a warning). Plan's Final Verification step will work
as written.

### R2. Kivy headless test setup — NOT A BLOCKER

`python -m pytest tests/ --collect-only` collects **53 tests** from 11
test files with no display required. Only 2 of 11 test files
(`test_cache_explorer_mock.py`, `test_backend_cache_explorer.py`)
import Kivy at all. The conftest fixture is just
`MockBackendServer` (a `ThreadingHTTPServer` mock). No
`SDL_VIDEODRIVER` env var is set anywhere in the test suite.

**Implication for the plan:** The repeated "expected PASS or only
existing environment-related skips" line is true in practice on a
local dev box. The "kivy display skip" escape hatch is real but
uncommon. New pure-function tests (Tasks 1, 2) will not hit Kivy at
all. New orchestrator tests (Task 6) will need either Kivy imports
or a fake scheduler — see concern #9 for the latter recommendation.

### R3. All `current_export_job` writers — NONE

`rg "current_export_job\s*=" src/frontend` returns only:
- `state.py:7` — the initial `Optional[Dict] = None` declaration
- `main_screen.py:1689` — a read (`if current_export_job:`)
- `backend_app.py:343` — a read (`if current_export_job:`)

There are **no active writers** of `current_export_job` in the
current codebase. The original author's claim is verified — the
state is vestigial. The only related mutation is
`current_export_job["cancelled"] = True` inside the read guard
(main_screen.py:1690, backend_app.py:344), but that mutates a key
on a dict that is *always `None`* at that point, so it raises
`AttributeError` if it were ever reached (it isn't, because the
guard is always False).

**Implication for the plan:** Task 2's state functions are
*introducing* the writer side of the contract. The plan needs to
also handle the fact that the existing `cancel_export` and
`on_stop` paths are dead code (the `if current_export_job:` checks
are unreachable). They can be removed in Task 2 once the new
`mark_current_export_cancelled()` flow is in place.

### R4. All `BackendPlaylistCard(...)` call sites — CONFIRMED (2 literal, 1 in factory)

`rg "BackendPlaylistCard\("` returns:
- `backend_main_screen.py:24` — inside `_make_playlist_widget()` override (keep)
- `backend_main_screen.py:49` — literal in `display_playlists_with_cache()` (replace)
- `backend_main_screen.py:100` — literal in `_perform_sort()` (replace)
- (Plus 1 class definition in `ui/backend_playlist_card.py:27` and 4 doc/historical references.)

The plan's count is correct. Task 3's two replacements are
exhaustive.

### R5. `_show_error_dialog`, `_log_error`, `_update_export_status` truly unused — YES, DEAD CODE

`rg "_show_error_dialog|_log_error|_update_export_status"` against
`src/` returns ONLY the three definitions (main_screen.py:644, 658,
665) and references in the plan/assessment docs. No tests, no
callbacks, no adapter call sites.

The only `self._show_error_dialog(...)` / `self._log_error(...)`
references outside `main_screen.py` are in
`docs/export-formats-implementation.md:363-415`, which is a
historical design doc describing old v2 behavior — the code
described there no longer exists.

**Recommendation:** Add a Task 0 to delete these three methods
before Task 1 starts. They are unreachable, untested, and the
`_show_error_dialog` method is distinct from the (used)
`_show_backend_error_popup` that Task 5 will extract. Deleting
them reduces the 1,940-line count and prevents future readers
from assuming they are part of the contract.

### R6. `app.logout()` vs `BackendMainScreenAdapter.logout()` — APP WINS, PLAN IS CORRECT

`BackendSpotifyExporterApp.logout()` exists at
`backend_app.py:274` and is the orchestrator: it calls
`self.backend_adapter.logout()`, clears `token_info` and
`username`, and returns the screen manager to the login screen.

`main_screen.py:740` already uses the right indirection:
```python
elif app and hasattr(app, "logout"):
    Clock.schedule_once(lambda _: app.logout(), 0.2)
```

The plan's `perform_logout()` mirrors this exactly. No change
needed. (See R6 correction under concern #2 above — the same
research also confirmed `clear_active_export_job` exists on the
adapter, retracting concern #2 entirely.)

### R7. `_current_trace_id` set before `backend_export_worker` — YES, ALWAYS

`begin_backend_export` (main_screen.py:1241-1267) sets
`self._current_trace_id` (lines 1247-1249), pushes it to the
adapter via `set_trace_id` (line 1252), and **then** starts the
thread targeting `self.backend_export_worker` (line 1264). The
worker runs on a daemon thread, so the trace ID is established
in the main thread before the worker can read it.

**Bonus finding:** `handle_export_cancelled` does exist at
`main_screen.py:1708`, so concern #3's reference to it is valid —
no hidden prerequisite needed.

### R7.1. (Bonus) Test count and Kivy test scope

There are 53 frontend tests across 11 files. Of those, only 2
files import Kivy. None of the new tests planned for Tasks 1, 2,
or 6 (the orchestrator test recommended in concern #9) need a
display if the orchestrator is constructed directly with a fake
scheduler — no Kivy widgets required.

---

## Suggested plan deltas (in order of priority)

1. **Fix Task 4** `open_cache_explorer` signature — drop
   `cache_manager` argument, call `create_cache_explorer()`.
2. ~~**Fix Task 2** `clear_active_export_job` call~~ — **RESOLVED.**
   The method exists on the adapter (see R6). Plan is correct.
3. **Scope Task 2 explicitly as a bug fix** — reword Step 4 to lead
   with "fix broken cancellation polling," enumerate the check points
   and terminal cleanup sites by line number, and confirm
   `handle_export_cancelled` exists on `MainScreen`. The CHANGELOG
   entry already says "Fixed" — align the plan prose with that intent.
4. **Add Task 1.5** to extract `_get_filtered_playlists` and
   `_sort_playlists` so the test file in the file list has a
   corresponding production change.
5. **Reorder Task 6** so helper methods (Step 7 list) move *before*
   the worker body (Step 5).
6. **Add `test_main_screen_export.py`** with a fake-scheduler
   orchestrator test.
7. **Decide on filename format** — if Task 1 keeps the new format, add
   a CHANGELOG entry. If not, match the existing format and rename the
   test.
8. **Drop `KivyScheduler.set_attr_soon`** or mark it explicitly as
   forward-looking.
9. **Confirm R1-R7** before writing any code.

---

## Open questions for the author

- Is the filename format change (Spotify_Playlists → spotify_playlists,
  AM/PM timestamp → YYYYMMDD) intentional, or should the new helper
  match the current format?
- ~~Is the `clear_active_export_job` adapter method a new feature, or
  was it assumed to exist?~~ **RESOLVED (R6):** the method exists, plan
  is correct.
- Should `_get_filtered_playlists` / `_sort_playlists` move as part of
  this refactor, or stay on `MainScreen` and be left out of scope?
- **R5:** Are the dead-looking helpers (`_show_error_dialog`,
  `_log_error`, `_update_export_status`) safe to delete now, or are
  they reserved for future use? Research shows zero callers in the
  current codebase.
- **R3:** Should Task 2 also remove the now-dead `if current_export_job:`
  guards in `cancel_export` (main_screen.py:1689) and `on_stop`
  (backend_app.py:343), or leave them as a transitional safety net?
