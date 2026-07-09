# Refactor BackendPlaylistCard to Split Under 600 Lines

**Status:** Completed  
**Created:** 2026-07-09  
**Completed:** 2026-07-09  
**Related to:** [dev-docs/backlog/TO_DO.md](../../backlog/TO_DO.md) — Code Quality / Tech Debt  
**Assessment:** Incorporates [tmp/2026-07-09T093000Z](../../../../tmp/2026-07-09T093000Z-backend-playlist-card-split-plan-assessment.md), [tmp/2026-07-09T090603Z](../../../../tmp/2026-07-09T090603Z-backend-playlist-card-split-plan-assessment.md), [tmp/2026-07-09T105313Z](../../../../tmp/2026-07-09T105313Z-backend-playlist-card-refactor-assessment.md), [tmp/2026-07-09T131607Z pass2](../../../../tmp/2026-07-09T131607Z-backend-playlist-card-split-plan-assessment-pass2.md), [tmp/2026-07-09T132805Z pass3](../../../../tmp/2026-07-09T132805Z-backend-playlist-card-split-plan-assessment-pass3.md), [tmp/2026-07-09T150000Z](../../../../tmp/2026-07-09T150000Z-backend-playlist-card-refactor-assessment.md), [tmp/2026-07-09T200000Z](../../../../tmp/2026-07-09T200000Z-backend-playlist-card-plan-assessment.md), and [tmp/2026-07-09T220000Z](../../../../tmp/2026-07-09T220000Z-refactor-backend-playlist-card-assessment.md), and [tmp/2026-07-09T192456Z](../../../../tmp/2026-07-09T192456Z-refactor-backend-playlist-card-assessment.md) assessments.

## Objective

Refactor `src/frontend/ui/backend_playlist_card.py` (currently 1056 lines) into multiple focused modules, each under 600 lines, so it can be removed from the file length exemption list in `scripts/file-length-exemptions.json`.

## Current State

- **File:** `src/frontend/ui/backend_playlist_card.py` — 1056 lines
- **Exemption:** Currently exempted in `scripts/file-length-exemptions.json` (expires 2026-10-07)
- **Hook limit:** 700 lines for code files (goal: under 600 lines for safety margin)

## Code Analysis

The `BackendPlaylistCard` class currently handles multiple concerns. Based on actual code inspection:

| Concern | Methods | Approx Lines |
|---------|---------|--------------|
| Module-level utilities | `_mood_label()`, `_describe_error_source()` | ~15 |
| UI construction | `_build_card_ui()`, `_get_playlist_image_url()`, `_create_text_section()` | ~100 |
| Touch interaction | `on_touch_down()`, `on_touch_move()`, `on_touch_up()`, `_trigger_long_press()`, `_handle_delayed_single_click()` | ~85 |
| Graphics updates | `_schedule_graphics_update()`, `_update_info_bg()`, `_update_card_bg()` | ~10 |
| Selection state | `_on_checkbox_change()` (source lines 289-293, ~5 lines) | ~5 |
| Analysis popup | `show_detailed_playlist_window()`, `_build_analysis_popup_content()`, `_update_analysis_ui()` | ~490 |
| Tracks popup | `_open_tracks_window()`, `_build_tracks_popup_content()`, `_make_track_row()`, `_populate_tracks()`, `_set_tracks_error()` | ~230 |
| API workers | `_load_analysis_worker()`, `_load_tracks_worker()` | ~42 |
| Class constants | `DOUBLE_CLICK_THRESHOLD`, `LONG_PRESS_DURATION`, `MOVEMENT_THRESHOLD`, `MIN_CLICK_DURATION` | ~4 |
| Track layout constants | `_COL_NUM`, `_COL_TRACK`, `_COL_ART`, `_COL_ALB` | ~4 |

**Key insights:**
- The analysis popup module alone is ~490 lines (close to 600 limit)
- `_update_analysis_ui()` is the largest single method (~220 lines) and handles multiple rendering concerns
- Graphics and selection are too small for separate modules (~10-30 lines each)
- API workers are minimal (~42 lines total)
- Cross-cutting concerns: popup methods call UI methods, interaction calls popup methods
- `_handle_delayed_single_click()` (line 280) is called by `on_touch_up()` and must be extracted with interaction module
- Track column constants `_COL_NUM`, `_COL_TRACK`, `_COL_ART`, `_COL_ALB` (lines 901-904) are used by `_make_track_row()` and must move with tracks popup module

## Revised Split Structure

### 1. `backend_playlist_card_utils.py` (~50-80 lines)
**Purpose:** Module-level utility functions (no dependencies)
**Contents:**
- `_MOOD_BANDS` constant
- `_ERROR_SOURCE_LABELS` constant
- `_mood_label()` function
- `_describe_error_source()` function

### 2. `backend_playlist_card_ui.py` (~120-150 lines)
**Purpose:** UI construction and layout (defines `PlaylistCardUIMixin`)
**Contents:**
- `class PlaylistCardUIMixin:` with methods:
  - `_build_card_ui()`
  - `_get_playlist_image_url()`
  - `_create_text_section()`
  - Graphics setup (canvas.before, Rectangle initialization)
  - Graphics update methods: `_schedule_graphics_update()`, `_update_info_bg()`, `_update_card_bg()`
  - Selection method: `_on_checkbox_change()`
- **Dependencies:** kivy, `.backend_playlist_card_utils`
- **Note:** `card_bg`, `info_bg`, `_bg_color` are created dynamically inside the `with self.canvas.before:` block in `_build_card_ui` (not declared in `__init__`); they remain dynamic on the mixin instance. Annotate them as class-level `Any` defaults (see basedpyright plan, G5).

### 3. `backend_playlist_card_interaction.py` (~100-120 lines)
**Purpose:** Touch interaction handling
**Contents:**
- `on_touch_down()` method
- `on_touch_move()` method
- `on_touch_up()` method
- `_trigger_long_press()` method
- `_handle_delayed_single_click()` method
- Touch state management constants: `DOUBLE_CLICK_THRESHOLD`, `LONG_PRESS_DURATION`, `MOVEMENT_THRESHOLD`, `MIN_CLICK_DURATION`
- Touch state variables: `_is_touch_down`, `_touch_start_time`, `_touch_start_pos`, `_last_click_time`, `_long_press_event`, `_pending_single_click`
- **Dependencies:** kivy, time, math

### 4. `backend_playlist_card_analysis_popup.py` (~530-540 lines)
**Purpose:** Analysis popup management (defines `PlaylistCardAnalysisPopupMixin`, largest concern)
**Contents:**
- `class PlaylistCardAnalysisPopupMixin:` with methods:
  - `show_detailed_playlist_window()`
  - `_build_analysis_popup_content()`
  - `_update_analysis_ui()`
  - Analysis worker: `_load_analysis_worker()`
- **Dependencies:** kivy (`App`, `Clock`, `mainthread`), threading, `.backend_playlist_card_utils`, `..screens.adapter_mixins.analysis`
- **Note:** calls `self._get_playlist_image_url()` (defined on `PlaylistCardUIMixin`) — no import needed, resolves via `self`.

### 5. `backend_playlist_card_tracks_popup.py` (~200-250 lines)
**Purpose:** Tracks popup management (defines `PlaylistCardTracksPopupMixin`)
**Contents:**
- `class PlaylistCardTracksPopupMixin:` with methods:
  - `_open_tracks_window()`
  - `_build_tracks_popup_content()`
  - `_make_track_row()`
  - `_populate_tracks()`
  - `_set_tracks_error()`
  - Tracks worker: `_load_tracks_worker()`
- Track layout constants: `_COL_NUM`, `_COL_TRACK`, `_COL_ART`, `_COL_ALB` (class constants on the mixin, source lines 901-904)
- **Dependencies:** kivy (`App`, `Clock`), threading

### 6. `backend_playlist_card.py` (~35-90 lines; actual body ~40 after extraction)
**Purpose:** Main card class orchestration
**Contents:**
- `BackendPlaylistCard` class declaration with explicit MRO:
  ```python
  class BackendPlaylistCard(
      PlaylistCardInteractionMixin,
      PlaylistCardUIMixin,
      PlaylistCardAnalysisPopupMixin,
      PlaylistCardTracksPopupMixin,
      BoxLayout,
  ):
  ```
  `BoxLayout` (Kivy `EventDispatcher` metaclass) MUST be last to avoid metaclass conflicts. Mixins do **NOT** define `__init__`; all instance state is set in the main class `__init__` and via class-level attribute defaults (Step 12). `super().__init__(**kwargs)` in the main class resolves through the mixin MRO to `BoxLayout` precisely *because* the mixins define no `__init__`.
- `__init__()` method (coordinates module imports and setup)
- Popup handles: `_detailed_popup`, `_tracks_popup`
- Graphics state: `_graphics_update_scheduled`
- Playlist data: `playlist_data`
- Cross-mixin attribute declarations (see G5 plan): declare all shared instance attributes with `Any` defaults on the mixins (or a shared base)
- Integration of split modules via mixin inheritance (not composition)
- **Dependencies:** All modules

## Dependency Hierarchy

```
backend_playlist_card_utils.py               (no deps — pure constants + helpers)
backend_playlist_card_ui.py                  → kivy, .backend_playlist_card_utils
backend_playlist_card_interaction.py         → kivy, time, math
backend_playlist_card_analysis_popup.py      → kivy, threading, .backend_playlist_card_utils, ..screens.adapter_mixins.analysis
backend_playlist_card_tracks_popup.py        → kivy, threading
backend_playlist_card.py                     → ALL modules (mixin inheritance)
```

## Import Distribution Plan

Each new module must include `from __future__ import annotations` at the top (project convention) and a module-level docstring plus a docstring on its mixin class describing its purpose and dependencies (e.g. `"""UI mixin for BackendPlaylistCard. Depends on kivy and .backend_playlist_card_utils."""`). Imports distributed as follows:

| Module | Imports |
|--------|---------|
| `backend_playlist_card_utils.py` | `from __future__ import annotations` (stdlib only) |
| `backend_playlist_card_ui.py` | `from __future__ import annotations`, `from typing import Any`, kivy, `from kivy.metrics import dp` |
| `backend_playlist_card_interaction.py` | `from __future__ import annotations`, `from typing import Any, Optional`, kivy, `time`, `math`, `from kivy.clock import Clock`, `from kivy.metrics import dp` |
| `backend_playlist_card_analysis_popup.py` | `from __future__ import annotations`, `from typing import Any, Optional`, kivy (`App` from `kivy.app`, `Clock, mainthread` from `kivy.clock`), `from kivy.metrics import dp`, `threading`, `from ...shared.logging_config import logger`, `from .backend_playlist_card_utils import _mood_label, _describe_error_source`, `from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION` |
| `backend_playlist_card_tracks_popup.py` | `from __future__ import annotations`, `from typing import Any`, kivy (`App` from `kivy.app`, `Clock` from `kivy.clock`), `from kivy.metrics import dp`, `threading`, `from ...shared.logging_config import logger` |
| `backend_playlist_card.py` | `from __future__ import annotations`, `from typing import Any`, all new mixin/helper modules, kivy, `from kivy.metrics import dp` |

**Import-path note:** the moved helpers live in `backend_playlist_card_utils.py` in the *same* `ui/` package, so the correct import is `from .backend_playlist_card_utils import ...` — **not** `..utils` (which resolves to the unrelated `src/frontend/utils` package). Mixin methods that need a method from another mixin (e.g. analysis popup calling `self._get_playlist_image_url()`) must call it via `self.`, never import `..ui`.

## Rollback Plan

If extraction introduces regressions or line counts exceed limits mid-way:
1. **Branch strategy:** Work on `feature/split-backend-playlist-card` branch
2. **Point of no return:** After the main class is rewired to inherit the mixins (Step 6) but before the test suite is run (Steps 7–8). Before this point, the original file still defines everything and the new modules are dead code — a safe state to abandon. After Step 6 succeeds, the split is committed and rollback requires restoring the original file + deleting the 5 new modules.
3. **Rollback procedure:** `git checkout main -- src/frontend/ui/backend_playlist_card.py` and `git clean -fd src/frontend/ui/backend_playlist_card_*.py`
4. **Verification gate:** All existing tests must pass before removing exemption (Step 10)

## Progress Note

Updated 2026-07-09 after reconciling the plan against the working tree and fresh verification:

- The code split itself is implemented: `backend_playlist_card.py` is now 66 lines and the five helper modules exist.
- Fresh verification passed for `.venv/bin/basedpyright src/frontend src/shared --level error` and the full frontend pytest suite (`162 passed, 7 skipped`) when re-run outside the sandbox with `KIVY_HOME=/private/tmp/spotibye-kivy`.
- `scripts/file-length-exemptions.json` no longer contains a `backend_playlist_card.py` exemption.
- Manual GUI verification was completed on 2026-07-09 based on direct runtime confirmation from the user. A pure import smoke test of the Kivy modules remains unreliable in this headless shell because Kivy still aborts without a usable window provider even when `KIVY_WINDOW=mock` is set.

## Implementation Steps

- [x] **Step 1:** Create `backend_playlist_card_utils.py` with module-level utilities
  - [x] Extract `_MOOD_BANDS`, `_ERROR_SOURCE_LABELS` constants
  - [x] Extract `_mood_label()`, `_describe_error_source()` functions
  - [x] Add `from __future__ import annotations` at top
  - [x] Add module docstring and type hints
  - [x] No dependencies (pure Python)

- [x] **Step 2:** Create `backend_playlist_card_ui.py` defining `PlaylistCardUIMixin`
  - [x] Define `class PlaylistCardUIMixin:` and move these methods into it:
  - [x] Extract `_build_card_ui()` method
  - [x] Extract `_get_playlist_image_url()` method
  - [x] Extract `_create_text_section()` method
  - [x] Extract graphics methods: `_schedule_graphics_update()`, `_update_info_bg()`, `_update_card_bg()`
  - [x] Extract selection method: `_on_checkbox_change()`
  - [x] Add `from __future__ import annotations` and `from typing import Any` at top
  - [x] Add imports: kivy, `from kivy.metrics import dp` (UI methods use `dp()` extensively)
  - [x] Declare dynamic canvas attributes as class-level `Any` defaults: `card_bg: Any = None`, `info_bg: Any = None`, `_bg_color: Any = None`, `cover_image: Any = None`, `checkbox: Any = None` (G5/G6; `cover_image` + `checkbox` are assigned in `_build_card_ui`, so they must be declared here for basedpyright)
  - [x] Add `__all__ = ["PlaylistCardUIMixin"]`

- [x] **Step 3:** Create `backend_playlist_card_interaction.py` defining `PlaylistCardInteractionMixin`
  - [ ] Define the mixin with a typing-only `Widget` base so `super().on_touch_down/move/up` type-checks under basedpyright `--level error` (E1):
    ```python
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from kivy.uix.widget import Widget
        _TouchBase = Widget
    else:
        _TouchBase = object

    class PlaylistCardInteractionMixin(_TouchBase):
        ...
    ```
    At runtime `super().on_touch_*` resolves via the instance MRO to `BoxLayout`/`Widget`; at type-check time it resolves to `Widget`. (Fallback: keep `class PlaylistCardInteractionMixin:` and add `# pyright: ignore[reportAttributeAccessIssue]` on the three `super().on_touch_*` calls.)
  - [x] Move these methods into the class:
  - [x] Extract `on_touch_down()` method
  - [x] Extract `on_touch_move()` method
  - [x] Extract `on_touch_up()` method
  - [x] Extract `_trigger_long_press()` method
  - [x] Extract `_handle_delayed_single_click()` method
  - [x] Extract `_setup_interactions()` no-op (source lines 205-206) — assign it here as the interaction mixin's setup method (G4)
  - [x] Move class constants: `DOUBLE_CLICK_THRESHOLD`, `LONG_PRESS_DURATION`, `MOVEMENT_THRESHOLD` and **drop `MIN_CLICK_DURATION`** (dead code — never referenced in the source; removing it is scheduled, not optional) (M1)
  - [x] Declare touch state variables as **class-level annotations with defaults** on `PlaylistCardInteractionMixin` (they are NOT re-assigned in the main `__init__`; instance reassignment happens on touch events) (G2):
    `_is_touch_down: bool = False`, `_touch_start_time: float = 0.0`, `_touch_start_pos: Optional[tuple[float, float]] = None`, `_last_click_time: float = 0.0`, `_long_press_event: Optional[Any] = None`, `_pending_single_click: Optional[Any] = None` (source lines 83-88)
  - [x] Add `from __future__ import annotations` and `from typing import Any, Optional` at top
  - [x] Add imports: kivy, time, math, `from kivy.clock import Clock` (used by `on_touch_down`/`on_touch_up` via `Clock.schedule_once`), `from kivy.metrics import dp` (used by `MOVEMENT_THRESHOLD = dp(12)` and `sqrt` comes from math)
  - [x] Design: Kivy dispatches `on_touch_down/move/up` on the widget instance, so these must remain methods on `BackendPlaylistCard` (via inheritance), not a separate composed handler. Touch state vars (`_is_touch_down`, etc.) stay instance attributes accessed via `self.`
  - [x] Add `__all__ = ["PlaylistCardInteractionMixin"]`

- [x] **Step 4:** Create `backend_playlist_card_analysis_popup.py` defining `PlaylistCardAnalysisPopupMixin`
  - [x] Define `class PlaylistCardAnalysisPopupMixin:` and move these methods into it:
  - [x] Extract `show_detailed_playlist_window()` method
  - [x] Extract `_build_analysis_popup_content()` method — it contains a local closure `info_label(...)` (source lines 444-463) used throughout the method; keep it as an inner function, do NOT extract it as a separate module-level or mixin method
  - [x] Extract `_update_analysis_ui()` method (complex ~220-line method)
  - [x] Extract `_load_analysis_worker()` method
  - [x] Add `from __future__ import annotations` and `from typing import Any, Optional` at top
  - [x] Add imports: kivy (`from kivy.app import App`, `from kivy.clock import Clock, mainthread`), `from kivy.metrics import dp`, `threading`, `from ...shared.logging_config import logger`, `from .backend_playlist_card_utils import _mood_label, _describe_error_source`, `from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION`
  - [x] Preserve popup content attributes: `content._analysis_container`, `content._duration_label`
  - [x] Calls `self._get_playlist_image_url()` from the UI mixin — no import needed
  - [x] Thread-safety note: `_load_analysis_worker` already marshals its UI update via the `@mainthread`-decorated `_update_analysis_ui` (source line 571). Keep this decorator — do NOT add a second one. The popup content attributes exist before the worker runs because they are passed as arguments to the thread (not re-read off `content` at runtime). Document this assumption in the mixin docstring.
  - [x] Add `__all__ = ["PlaylistCardAnalysisPopupMixin"]`

- [x] **Step 5:** Create `backend_playlist_card_tracks_popup.py` defining `PlaylistCardTracksPopupMixin`
  - [x] Define `class PlaylistCardTracksPopupMixin:` and move these methods into it:
  - [x] Extract `_open_tracks_window()` method
  - [x] Extract `_build_tracks_popup_content()` method
  - [x] Extract `_make_track_row()` method
  - [x] Extract `_populate_tracks()` method
  - [x] Extract `_set_tracks_error()` method
  - [x] Extract `_load_tracks_worker()` method
  - [x] Add `from __future__ import annotations` and `from typing import Any` at top (no `Optional` — tracks methods use no `Optional` types; the `Optional[Popup]` handles live in the main class)
  - [x] Add imports: kivy (`from kivy.app import App`, `from kivy.clock import Clock`), `from kivy.metrics import dp`, `threading`, `from ...shared.logging_config import logger`
  - [x] Preserve the four `# pyright: ignore[reportArgumentType]` comments inside `_make_track_row`'s inner `cell` helper (source lines 939, 941, 945, 946) — they must move with the method or the errors reappear (M2)
  - [x] Preserve popup content attribute: `content._tracks_layout`
  - [x] Move track layout constants `_COL_NUM`, `_COL_TRACK`, `_COL_ART`, `_COL_ALB` as class constants on the mixin (source lines 901-904, present in code)
  - [x] Thread-safety note: `_load_tracks_worker` already marshals its UI updates via `Clock.schedule_once` (source lines 965/974/979), and `_open_tracks_window` already guards with `hasattr(content, "_tracks_layout")` (source line 816) before spawning the thread. Keep both — the worker receives `content._tracks_layout` as an argument, so it is never re-read off `content` at runtime. Document this in the mixin docstring.
  - [x] Add `__all__ = ["PlaylistCardTracksPopupMixin"]`

- [x] **Step 6:** Refactor main `BackendPlaylistCard` class in `backend_playlist_card.py`
  - [x] Add `from __future__ import annotations` and `from typing import Any` at top, `from kivy.metrics import dp` (main `__init__` uses `dp()`)
  - [x] Import all mixins and state: `from .backend_playlist_card_ui import PlaylistCardUIMixin`, `from .backend_playlist_card_interaction import PlaylistCardInteractionMixin`, `from .backend_playlist_card_analysis_popup import PlaylistCardAnalysisPopupMixin`, `from .backend_playlist_card_tracks_popup import PlaylistCardTracksPopupMixin`, `from .backend_playlist_card_utils import _mood_label, _describe_error_source`
  - [x] Declare the class with the explicit MRO (see Module 6): `class BackendPlaylistCard(PlaylistCardInteractionMixin, PlaylistCardUIMixin, PlaylistCardAnalysisPopupMixin, PlaylistCardTracksPopupMixin, BoxLayout):` — `BoxLayout` last
  - [x] `__init__()` calls `super().__init__(**kwargs)` then sets `playlist_data`, `_graphics_update_scheduled`, `_detailed_popup`, `_tracks_popup`, and invokes `self._setup_interactions()`
  - [x] Keep popup handles: `_detailed_popup`, `_tracks_popup`
  - [x] Keep graphics state: `_graphics_update_scheduled`
  - [x] Keep playlist data: `playlist_data`
  - [x] Preserve all public methods and attributes for compatibility
  - [x] Add `__all__ = ["BackendPlaylistCard", "_mood_label", "_describe_error_source"]` to re-export the public API and the utilities moved to `backend_playlist_card_utils`, so existing test import at `test_backend_playlist_card_analysis.py:78` (`from ..ui.backend_playlist_card import BackendPlaylistCard, _mood_label`) continues to resolve without edit
  - [x] Re-export `BackendPlaylistCard` and the utility helpers from the main module (class/helpers are defined in their own modules and imported + re-exported here)

- [ ] **Step 7:** Update imports across all files
  - [x] Verify test import `test_backend_playlist_card_analysis.py:78` still resolves via the Step 6 re-export (no edit needed); only update it to `from ..ui.backend_playlist_card_utils import _mood_label` if re-export is dropped
  - [x] Verify consumer imports: `backend_main_screen.py:8` (resolves via main module path, no `__init__.py` change needed since `ui/__init__.py` does not facade `backend_playlist_card`)
  - [x] Grep for *all* importers before rewiring, to confirm none do `from src.frontend.ui import BackendPlaylistCard` or wildcard imports that would bypass the main module: `grep -rn "backend_playlist_card" src/ --include=*.py` (claim #7)
  - [x] Verify `ui/__init__.py` lazy-loading pattern is unaffected (only `BackendSelectorPopup` is exposed there today)
  - [ ] Resolve any circular import issues; smoke-test every import pair:
    ```bash
    .venv/bin/python -c "import src.frontend.ui.backend_playlist_card_utils, src.frontend.ui.backend_playlist_card_ui, src.frontend.ui.backend_playlist_card_interaction, src.frontend.ui.backend_playlist_card_analysis_popup, src.frontend.ui.backend_playlist_card_tracks_popup, src.frontend.ui.backend_playlist_card"
    ```
  - [ ] **Run this smoke test after creating EACH new module** (not only at the end) to catch circular imports early — especially the relative import to `..screens.adapter_mixins.analysis` in the analysis-popup module. Stop and fix if any module fails to import.
    Note: a late smoke-import attempt in the headless shell still aborts inside Kivy's window-provider bootstrap, so import safety is inferred from passing tests and successful basedpyright rather than a clean raw module-import run.

- [ ] **Step 8:** Run tests and verify behavior (split into automated vs manual)
  - [x] **Automated (pytest, headless):** `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
    - The headless suite stubs kivy and constructs cards via `BackendPlaylistCard.__new__()`, so it exercises `_mood_label` rendering, popup-content attribute wiring, and worker error paths — NOT real touch/graphics/popup-open behavior.
    - **Gate:** All automated tests must pass before proceeding to Step 10.
    - Verified 2026-07-09 under elevated execution with `KIVY_HOME=/private/tmp/spotibye-kivy`: `162 passed, 7 skipped`.
  - [x] **Manual (real GUI, on a display):** the following are NOT covered by the headless suite and were verified by hand before closing the plan:
    - [x] Card selection toggles checkbox + blue highlight on single click
    - [x] Double-click vs single-click vs long-press discrimination works (no false triggers)
    - [x] Analysis popup opens on double-click / long-press
    - [x] Tracks popup opens from the analysis popup's "Show Tracks" button
    - [x] Error banner renders when the analysis `errors` array is non-empty (partial-failure path)
    - [x] ReccoBeats metadata section renders (ISRC coverage / popularity range) when present
    - [x] Key/mode display renders in the audio-features section
    - [x] Tracks popup scrolls correctly with many tracks
    - [x] Popup dismisses on outside click (`auto_dismiss=True`) and checkbox state persists across open/close
    - [x] Graphics backgrounds (`card_bg`, `info_bg`, `_bg_color`) render and resize correctly
    - [x] Error handling paths for failed API calls (manual or via worker-error tests)

- [ ] **Step 9:** Verify all modules are under 600 lines
  - [ ] After creating EACH module (Steps 1-5), run `pre-commit run file-length-check --all-files` to catch overages early, before the final Step 11 pass (Gap 8)
  - [ ] **Warn-only gate (Gap 9):** the hook runs with `--warn`, so file-length overages are reported as warnings and do NOT block the commit. This Step 9 check is a soft gate for the 600-line *soft* goal only; the hard 700-line limit is enforced by the same hook but still warn-level. Do not rely on it to hard-fail.
  - [x] Check line counts for all new modules
  - [x] If any module exceeds 600 lines, further split that module (e.g. break `_update_analysis_ui` into smaller rendering helpers) — fallback only; the analysis module is estimated ~530-540 and is not preemptively split
  - [x] **Deadline:** Complete before 2026-10-07 (exemption expiry). **Contingency (Gap 7):** if the refactor cannot finish by then, extend the `expiry` date in `scripts/file-length-exemptions.json` *before* it lapses — otherwise the warn-only hook will begin flagging the still-oversized file and (combined with other blocking hooks) impede commits.

- [x] **Step 10:** Remove `src/frontend/ui/backend_playlist_card.py` from exemption list
  - [x] Update `scripts/file-length-exemptions.json`
  - [x] Remove the exemption entry for `backend_playlist_card.py` (note: the entry's `reason` currently says "940 lines" while the file is 1056 — cosmetic, corrected by removal)

- [ ] **Step 11:** Run pre-commit hooks to verify file length check passes
  - [x] Hook id is `file-length-check` (`.pre-commit-config.yaml:114`, entry `scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json --warn`); enforces a 700-line code limit
  - [x] Run `pre-commit run file-length-check --all-files`
  - [x] Verify no warnings for the new modules
    Note: `pre-commit run file-length-check --all-files` and `--files ...` both skipped the untracked new files in this working tree, so the direct hook entry command was run instead:
    `.venv/bin/python scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json --warn src/frontend/ui/backend_playlist_card.py src/frontend/ui/backend_playlist_card_utils.py src/frontend/ui/backend_playlist_card_ui.py src/frontend/ui/backend_playlist_card_interaction.py src/frontend/ui/backend_playlist_card_analysis_popup.py src/frontend/ui/backend_playlist_card_tracks_popup.py`

- [x] **Step 12:** Update type checking (basedpyright) and resolve cross-mixin attribute typing (G5)
  - [x] Run `.venv/bin/basedpyright src/frontend src/shared --level error`
  - [x] `super().on_touch_down/move/up` in the interaction mixin type-checks via the typing-only `Widget` base set up in Step 3 (pass-3 E1). If the fallback `# pyright: ignore[reportAttributeAccessIssue]` approach was used instead, confirm those suppressions are present.
  - [x] Cross-mixin attribute access: every mixin method that reads an attribute it does not define must resolve. Approach (chosen): declare each cross-mixin attribute as a class-level annotation with a default on the mixin that first needs it:
    - `PlaylistCardInteractionMixin`: `_is_touch_down`, `_touch_start_time`, `_touch_start_pos`, `_last_click_time`, `_long_press_event`, `_pending_single_click`, `_detailed_popup`, `checkbox` (reads both in `_handle_delayed_single_click`)
    - `PlaylistCardUIMixin`: `card_bg`, `info_bg`, `_bg_color`, `checkbox`, `cover_image`, `_graphics_update_scheduled` (assigns `cover_image` + `checkbox` in `_build_card_ui`; writes `_graphics_update_scheduled` in `_schedule_graphics_update`) — `checkbox` is also declared on `PlaylistCardInteractionMixin` since `_handle_delayed_single_click` reads it there
    - `PlaylistCardAnalysisPopupMixin` / `PlaylistCardTracksPopupMixin`: `playlist_data`, `_detailed_popup` / `_tracks_popup`
    - Main class: `playlist_data`, `_graphics_update_scheduled`, `_detailed_popup`, `_tracks_popup`
    - Use `Any` defaults (e.g. `playlist_data: Any = None`) so basedpyright does not flag `self.<attr>` access. If any residual `reportAttributeAccessIssue` remains, add a targeted `# pyright: ignore[reportAttributeIssue]`.
    - **`from __future__ import annotations` + class-level defaults (Gap 10):** only the *annotation* part of `attr: bool = False` is deferred to a string; the *value* (`= False`, `= None`) is still evaluated at class-definition time and works correctly at runtime. So declaring `_is_touch_down: bool = False` etc. is safe. The class-level defaults on mixins do not collide across the MRO because each mixin defines its own attributes; `BoxLayout` does not set these names.
  - [x] **MRO / pyright note (claim #2):** basedpyright resolves `self.<attr>` against the class where the *method* is defined, not the runtime MRO of the composed `BackendPlaylistCard`. Because every cross-mixin attribute is declared on the mixin that reads it (table above), the MRO order does **not** affect pyright — the current order (`InteractionMixin` → `UIMixin` → `AnalysisPopupMixin` → `TracksPopupMixin` → `BoxLayout`) is correct and need not be reordered. The order only matters for runtime `super()` calls, where it correctly reaches `BoxLayout`/`Widget`.
  - [x] Add type annotations for cross-module method signatures where needed
  - [x] Use `if TYPE_CHECKING:` blocks to avoid circular imports for type hints

- [x] **Step 13:** Update developer docs for the new files (G7)
  - [x] Update `dev-docs/code-map.md` to index each new `backend_playlist_card_*.py` file and its role
  - [x] Update `ARCHITECTURE.md` (repo **root**, not `dev-docs/` — `dev-docs/ARCHITECTURE.md` does not exist) to document the mixin-based `BackendPlaylistCard` architecture (the split into utils/ui/interaction/analysis-popup/tracks-popup mixins + the `BoxLayout`-last MRO). Note: the root `ARCHITECTURE.md` already documents the `ui/` layer contract, so add a brief subsection under the `ui/` layer rather than a large new top-level section (E1).
  - [x] **Fix the stale GUI toolkit reference in root `ARCHITECTURE.md` (N2, required):** it incorrectly names `CustomTkinter` as the Python GUI toolkit (line 13 "Python CustomTkinter GUI (src/frontend/)" and line 189 "| CustomTkinter | Python GUI toolkit |"). The frontend actually uses **Kivy/KivyMD** (every `src/frontend/ui/*.py` imports kivy). Replace both occurrences with `Kivy/KivyMD` so the doc matches the codebase.
  - [x] Update `dev-docs/dependency-graph.json` (E2) with the new import edges, and **correct the existing incomplete entry**:
    - The current `src/frontend/ui/backend_playlist_card.py` entry lists only `src/shared/logging_config.py` but is missing the real `from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION` import (source line 25). Replace this entry to reflect the split main module's actual direct imports: the four mixin modules + the utils module (e.g. `["src/frontend/ui/backend_playlist_card_ui.py", "..._interaction.py", "..._analysis_popup.py", "..._tracks_popup.py", "src/frontend/ui/backend_playlist_card_utils.py", "src/shared/logging_config.py"]`).
    - Add a new entry for `src/frontend/ui/backend_playlist_card_analysis_popup.py` that includes `"src/frontend/screens/adapter_mixins/analysis.py"` (where `EXPECTED_ANALYSIS_SCHEMA_VERSION` lives), plus `backend_playlist_card_utils.py` and `logging_config.py`.
    - Add new entries for the other three mixin modules + `utils` capturing their direct imports (`kivy`, `logging_config`, `utils`, and each other as needed).
  - [x] Grep docs for stale references to the original `1056`-line count or the `backend_playlist_card.py` exemption `reason` and refresh them (e.g. `dev-docs/backlog/TO_DO.md`, any plan/index that cites the exemption) so documentation stays consistent (claim #8)
  - [x] No CHANGELOG entry needed (internal refactor, no user-visible behavior change)
  - [x] Before committing, run `git diff --stat` (and `git status`) to confirm only the intended files changed (new `backend_playlist_card_*.py` modules, the slimmed main module, and doc/exemption edits)

## Testing Strategy

- [x] **Automated:** `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v` (headless suite stubs kivy; covers `_mood_label`, popup-content wiring, worker error paths)
- [x] **Manual (real GUI):** single-click selection, analysis popup open, tracks popup open, graphics rendering/resize, API error handling
- [x] Verify popup content attributes are preserved (`_analysis_container`, `_duration_label`, `_tracks_layout`) for worker thread access
- [x] Run basedpyright to ensure type safety is maintained
- [x] Test import paths: verify `from ..ui.backend_playlist_card import BackendPlaylistCard` still works (and `_mood_label` via re-export)

## Dependencies

- Must maintain compatibility with existing screens that use `BackendPlaylistCard` (`backend_main_screen.py:8`)
- Must not break existing frontend tests (`test_backend_playlist_card_analysis.py:78`)
- Must follow existing code conventions (Kivy/KivyMD patterns)
- Must preserve popup content attributes used by worker threads
- Must consider `ui/__init__.py` lazy-loading pattern for new modules

## Success Criteria

- [x] All new module files are under 600 lines
- [x] All existing tests pass
- [x] File is removed from `scripts/file-length-exemptions.json`
- [x] Pre-commit file length hook passes without exemption
- [x] No regressions in card functionality
- [x] Type checking passes (basedpyright)
- [x] Import paths work for both consumers and tests
- [x] Popup content attributes are preserved for worker thread access

## Risks & Mitigations

**Risk:** Circular import dependencies between new modules
**Mitigation:** Follow defined dependency hierarchy; use `self.` references for cross-module calls; avoid importing modules that depend on each other

**Risk:** Breaking existing functionality during extraction
**Mitigation:** Run tests after each extraction step; keep changes small and incremental; preserve all public methods and attributes

**Risk:** Touch interaction state management across modules
**Mitigation:** Use mixin inheritance so `on_touch_*` stay methods on `BackendPlaylistCard`; touch state variables remain instance attributes on `self` (no cross-object access breakage)

**Risk:** Popup content attributes lost during split
**Mitigation:** Explicitly preserve `content._analysis_container`, `content._duration_label`, `content._tracks_layout` in popup modules

**Risk:** Import path changes break consumers and tests
**Mitigation:** Re-export `BackendPlaylistCard` from main module; update test imports for moved utilities; verify consumer imports still resolve

**Risk:** `_update_analysis_ui()` is too complex for single module
**Mitigation:** If analysis popup module exceeds 600 lines, further split `_update_analysis_ui()` into smaller rendering methods

**Risk:** Cross-module method calls during incremental extraction
**Mitigation:** Use `self.` references to call methods that haven't been extracted yet; extract in dependency order (utils → ui → interaction → popups)

## Notes

- The main `BackendPlaylistCard` class will become a thin orchestrator that inherits UI/Interaction/Popup mixins
- Use **mixin inheritance** (not composition) for the interaction handler — Kivy dispatches `on_touch_down/move/up` on the widget instance, so they must be methods on `BackendPlaylistCard`
- Maintain existing docstrings and comments during extraction
- Keep the same public API for compatibility with calling code
- New modules do NOT need to be added to `ui/__init__.py` (it only facades `BackendSelectorPopup`; consumers import `backend_playlist_card` by path)
- The analysis popup module (~530-540 lines) is within the 700-line hook limit and the 600-line soft goal; split `_update_analysis_ui()` only if it grows past 600
- Graphics and selection logic are too small for separate modules; merged into UI module
- Hook reality: `file-length-check` enforces a 700-line limit for code (with `--warn`); the 600-line target is a self-imposed safety margin
