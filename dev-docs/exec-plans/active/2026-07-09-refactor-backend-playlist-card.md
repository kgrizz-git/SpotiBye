# NEEDS REVIEW

# Refactor BackendPlaylistCard to Split Under 600 Lines

**Status:** Active  
**Created:** 2026-07-09  
**Related to:** [dev-docs/backlog/TO_DO.md](../../backlog/TO_DO.md) — Code Quality / Tech Debt  
**Assessment:** Incorporates [tmp/2026-07-09T093000Z](../../../../tmp/2026-07-09T093000Z-backend-playlist-card-split-plan-assessment.md), [tmp/2026-07-09T090603Z](../../../../tmp/2026-07-09T090603Z-backend-playlist-card-split-plan-assessment.md), [tmp/2026-07-09T105313Z](../../../../tmp/2026-07-09T105313Z-backend-playlist-card-refactor-assessment.md), [tmp/2026-07-09T131607Z pass2](../../../../tmp/2026-07-09T131607Z-backend-playlist-card-split-plan-assessment-pass2.md), [tmp/2026-07-09T132805Z pass3](../../../../tmp/2026-07-09T132805Z-backend-playlist-card-split-plan-assessment-pass3.md), and [tmp/2026-07-09T150000Z](../../../../tmp/2026-07-09T150000Z-backend-playlist-card-refactor-assessment.md) assessments.

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
| Selection state | `_on_checkbox_change()` (inline in `on_touch_up()`) | ~30 |
| Analysis popup | `show_detailed_playlist_window()`, `_build_analysis_popup_content()`, `_update_analysis_ui()` | ~470 |
| Tracks popup | `_open_tracks_window()`, `_build_tracks_popup_content()`, `_make_track_row()`, `_populate_tracks()`, `_set_tracks_error()` | ~230 |
| API workers | `_load_analysis_worker()`, `_load_tracks_worker()` | ~42 |
| Class constants | `DOUBLE_CLICK_THRESHOLD`, `LONG_PRESS_DURATION`, `MOVEMENT_THRESHOLD`, `MIN_CLICK_DURATION` | ~4 |
| Track layout constants | `_COL_NUM`, `_COL_TRACK`, `_COL_ART`, `_COL_ALB` | ~4 |

**Key insights:**
- The analysis popup module alone is ~470 lines (close to 600 limit)
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

### 4. `backend_playlist_card_analysis_popup.py` (~520-560 lines)
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

### 6. `backend_playlist_card.py` (~60-90 lines)
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
| `backend_playlist_card_ui.py` | `from __future__ import annotations`, `from typing import Any`, kivy |
| `backend_playlist_card_interaction.py` | `from __future__ import annotations`, `from typing import Any, Optional`, kivy, `time`, `math` |
| `backend_playlist_card_analysis_popup.py` | `from __future__ import annotations`, `from typing import Any, Optional`, kivy (`App` from `kivy.app`, `Clock, mainthread` from `kivy.clock`), `threading`, `from ...shared.logging_config import logger`, `from .backend_playlist_card_utils import _mood_label, _describe_error_source`, `from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION` |
| `backend_playlist_card_tracks_popup.py` | `from __future__ import annotations`, `from typing import Any`, kivy (`App` from `kivy.app`, `Clock` from `kivy.clock`), `threading`, `from ...shared.logging_config import logger` |
| `backend_playlist_card.py` | `from __future__ import annotations`, `from typing import Any`, all new mixin/helper modules, kivy |

**Import-path note:** the moved helpers live in `backend_playlist_card_utils.py` in the *same* `ui/` package, so the correct import is `from .backend_playlist_card_utils import ...` — **not** `..utils` (which resolves to the unrelated `src/frontend/utils` package). Mixin methods that need a method from another mixin (e.g. analysis popup calling `self._get_playlist_image_url()`) must call it via `self.`, never import `..ui`.

## Rollback Plan

If extraction introduces regressions or line counts exceed limits mid-way:
1. **Branch strategy:** Work on `feature/split-backend-playlist-card` branch
2. **Point of no return:** After the main class is rewired to inherit the mixins (Step 6) but before the test suite is run (Steps 7–8). Before this point, the original file still defines everything and the new modules are dead code — a safe state to abandon. After Step 6 succeeds, the split is committed and rollback requires restoring the original file + deleting the 5 new modules.
3. **Rollback procedure:** `git checkout main -- src/frontend/ui/backend_playlist_card.py` and `git clean -fd src/frontend/ui/backend_playlist_card_*.py`
4. **Verification gate:** All existing tests must pass before removing exemption (Step 10)

## Implementation Steps

- [ ] **Step 1:** Create `backend_playlist_card_utils.py` with module-level utilities
  - [ ] Extract `_MOOD_BANDS`, `_ERROR_SOURCE_LABELS` constants
  - [ ] Extract `_mood_label()`, `_describe_error_source()` functions
  - [ ] Add `from __future__ import annotations` at top
  - [ ] Add module docstring and type hints
  - [ ] No dependencies (pure Python)

- [ ] **Step 2:** Create `backend_playlist_card_ui.py` defining `PlaylistCardUIMixin`
  - [ ] Define `class PlaylistCardUIMixin:` and move these methods into it:
  - [ ] Extract `_build_card_ui()` method
  - [ ] Extract `_get_playlist_image_url()` method
  - [ ] Extract `_create_text_section()` method
  - [ ] Extract graphics methods: `_schedule_graphics_update()`, `_update_info_bg()`, `_update_card_bg()`
  - [ ] Extract selection method: `_on_checkbox_change()`
  - [ ] Add `from __future__ import annotations` and `from typing import Any` at top
  - [ ] Add imports: kivy
  - [ ] Declare dynamic canvas attributes as class-level `Any` defaults: `card_bg: Any = None`, `info_bg: Any = None`, `_bg_color: Any = None` (G5/G6)
  - [ ] Add `__all__ = ["PlaylistCardUIMixin"]`

- [ ] **Step 3:** Create `backend_playlist_card_interaction.py` defining `PlaylistCardInteractionMixin`
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
  - [ ] Move these methods into the class:
  - [ ] Extract `on_touch_down()` method
  - [ ] Extract `on_touch_move()` method
  - [ ] Extract `on_touch_up()` method
  - [ ] Extract `_trigger_long_press()` method
  - [ ] Extract `_handle_delayed_single_click()` method
  - [ ] Extract `_setup_interactions()` no-op (source lines 205-206) — assign it here as the interaction mixin's setup method (G4)
  - [ ] Move class constants: `DOUBLE_CLICK_THRESHOLD`, `LONG_PRESS_DURATION`, `MOVEMENT_THRESHOLD` and **drop `MIN_CLICK_DURATION`** (dead code — never referenced in the source; removing it is scheduled, not optional) (M1)
  - [ ] Declare touch state variables as **class-level annotations with defaults** on `PlaylistCardInteractionMixin` (they are NOT re-assigned in the main `__init__`; instance reassignment happens on touch events) (G2):
    `_is_touch_down: bool = False`, `_touch_start_time: float = 0.0`, `_touch_start_pos: Optional[tuple[float, float]] = None`, `_last_click_time: float = 0.0`, `_long_press_event: Optional[Any] = None`, `_pending_single_click: Optional[Any] = None` (source lines 83-88)
  - [ ] Add `from __future__ import annotations` and `from typing import Any, Optional` at top
  - [ ] Add imports: kivy, time, math
  - [ ] Design: Kivy dispatches `on_touch_down/move/up` on the widget instance, so these must remain methods on `BackendPlaylistCard` (via inheritance), not a separate composed handler. Touch state vars (`_is_touch_down`, etc.) stay instance attributes accessed via `self.`
  - [ ] Add `__all__ = ["PlaylistCardInteractionMixin"]`

- [ ] **Step 4:** Create `backend_playlist_card_analysis_popup.py` defining `PlaylistCardAnalysisPopupMixin`
  - [ ] Define `class PlaylistCardAnalysisPopupMixin:` and move these methods into it:
  - [ ] Extract `show_detailed_playlist_window()` method
  - [ ] Extract `_build_analysis_popup_content()` method
  - [ ] Extract `_update_analysis_ui()` method (complex ~220-line method)
  - [ ] Extract `_load_analysis_worker()` method
  - [ ] Add `from __future__ import annotations` and `from typing import Any, Optional` at top
  - [ ] Add imports: kivy (`from kivy.app import App`, `from kivy.clock import Clock, mainthread`), `threading`, `from ...shared.logging_config import logger`, `from .backend_playlist_card_utils import _mood_label, _describe_error_source`, `from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION`
  - [ ] Preserve popup content attributes: `content._analysis_container`, `content._duration_label`
  - [ ] Calls `self._get_playlist_image_url()` from the UI mixin — no import needed
  - [ ] Thread-safety note: `_load_analysis_worker` already marshals its UI update via the `@mainthread`-decorated `_update_analysis_ui` (source line 571). Keep this decorator — do NOT add a second one. The popup content attributes exist before the worker runs because they are passed as arguments to the thread (not re-read off `content` at runtime). Document this assumption in the mixin docstring.
  - [ ] Add `__all__ = ["PlaylistCardAnalysisPopupMixin"]`

- [ ] **Step 5:** Create `backend_playlist_card_tracks_popup.py` defining `PlaylistCardTracksPopupMixin`
  - [ ] Define `class PlaylistCardTracksPopupMixin:` and move these methods into it:
  - [ ] Extract `_open_tracks_window()` method
  - [ ] Extract `_build_tracks_popup_content()` method
  - [ ] Extract `_make_track_row()` method
  - [ ] Extract `_populate_tracks()` method
  - [ ] Extract `_set_tracks_error()` method
  - [ ] Extract `_load_tracks_worker()` method
  - [ ] Add `from __future__ import annotations` and `from typing import Any` at top (no `Optional` — tracks methods use no `Optional` types; the `Optional[Popup]` handles live in the main class)
  - [ ] Add imports: kivy (`from kivy.app import App`, `from kivy.clock import Clock`), `threading`, `from ...shared.logging_config import logger`
  - [ ] Preserve the four `# pyright: ignore[reportArgumentType]` comments inside `_make_track_row`'s inner `cell` helper (source lines 939, 941, 945, 946) — they must move with the method or the errors reappear (M2)
  - [ ] Preserve popup content attribute: `content._tracks_layout`
  - [ ] Move track layout constants `_COL_NUM`, `_COL_TRACK`, `_COL_ART`, `_COL_ALB` as class constants on the mixin (source lines 901-904, present in code)
  - [ ] Thread-safety note: `_load_tracks_worker` already marshals its UI updates via `Clock.schedule_once` (source lines 965/974/979), and `_open_tracks_window` already guards with `hasattr(content, "_tracks_layout")` (source line 816) before spawning the thread. Keep both — the worker receives `content._tracks_layout` as an argument, so it is never re-read off `content` at runtime. Document this in the mixin docstring.
  - [ ] Add `__all__ = ["PlaylistCardTracksPopupMixin"]`

- [ ] **Step 6:** Refactor main `BackendPlaylistCard` class in `backend_playlist_card.py`
  - [ ] Add `from __future__ import annotations` and `from typing import Any` at top
  - [ ] Import all mixins and state: `from .backend_playlist_card_ui import PlaylistCardUIMixin`, `from .backend_playlist_card_interaction import PlaylistCardInteractionMixin`, `from .backend_playlist_card_analysis_popup import PlaylistCardAnalysisPopupMixin`, `from .backend_playlist_card_tracks_popup import PlaylistCardTracksPopupMixin`, `from .backend_playlist_card_utils import _mood_label, _describe_error_source`
  - [ ] Declare the class with the explicit MRO (see Module 6): `class BackendPlaylistCard(PlaylistCardInteractionMixin, PlaylistCardUIMixin, PlaylistCardAnalysisPopupMixin, PlaylistCardTracksPopupMixin, BoxLayout):` — `BoxLayout` last
  - [ ] `__init__()` calls `super().__init__(**kwargs)` then sets `playlist_data`, `_graphics_update_scheduled`, `_detailed_popup`, `_tracks_popup`, and invokes `self._setup_interactions()`
  - [ ] Keep popup handles: `_detailed_popup`, `_tracks_popup`
  - [ ] Keep graphics state: `_graphics_update_scheduled`
  - [ ] Keep playlist data: `playlist_data`
  - [ ] Preserve all public methods and attributes for compatibility
  - [ ] Add `__all__ = ["BackendPlaylistCard", "_mood_label", "_describe_error_source"]` to re-export the public API and the utilities moved to `backend_playlist_card_utils`, so existing test import at `test_backend_playlist_card_analysis.py:78` (`from ..ui.backend_playlist_card import BackendPlaylistCard, _mood_label`) continues to resolve without edit
  - [ ] Re-export `BackendPlaylistCard` and the utility helpers from the main module (class/helpers are defined in their own modules and imported + re-exported here)

- [ ] **Step 7:** Update imports across all files
  - [ ] Verify test import `test_backend_playlist_card_analysis.py:78` still resolves via the Step 6 re-export (no edit needed); only update it to `from ..ui.backend_playlist_card_utils import _mood_label` if re-export is dropped
  - [ ] Verify consumer imports: `backend_main_screen.py:8` (resolves via main module path, no `__init__.py` change needed since `ui/__init__.py` does not facade `backend_playlist_card`)
  - [ ] Verify `ui/__init__.py` lazy-loading pattern is unaffected (only `BackendSelectorPopup` is exposed there today)
  - [ ] Resolve any circular import issues; smoke-test every import pair:
    ```bash
    .venv/bin/python -c "import src.frontend.ui.backend_playlist_card_utils, src.frontend.ui.backend_playlist_card_ui, src.frontend.ui.backend_playlist_card_interaction, src.frontend.ui.backend_playlist_card_analysis_popup, src.frontend.ui.backend_playlist_card_tracks_popup, src.frontend.ui.backend_playlist_card"
    ```
  - [ ] **Run this smoke test after creating EACH new module** (not only at the end) to catch circular imports early — especially the relative import to `..screens.adapter_mixins.analysis` in the analysis-popup module. Stop and fix if any module fails to import.

- [ ] **Step 8:** Run tests and verify behavior (split into automated vs manual)
  - [ ] **Automated (pytest, headless):** `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
    - The headless suite stubs kivy and constructs cards via `BackendPlaylistCard.__new__()`, so it exercises `_mood_label` rendering, popup-content attribute wiring, and worker error paths — NOT real touch/graphics/popup-open behavior.
    - **Gate:** All automated tests must pass before proceeding to Step 10.
  - [ ] **Manual (real GUI, on a display):** the following are NOT covered by the headless suite and must be verified by hand before claiming success:
    - [ ] Card selection toggles checkbox + blue highlight on single click
    - [ ] Analysis popup opens on double-click / long-press
    - [ ] Tracks popup opens from the analysis popup's "Show Tracks" button
    - [ ] Graphics backgrounds (`card_bg`, `info_bg`, `_bg_color`) render and resize correctly
    - [ ] Error handling paths for failed API calls (manual or via worker-error tests)

- [ ] **Step 9:** Verify all modules are under 600 lines
  - [ ] After creating EACH module (Steps 1-5), run `pre-commit run file-length-check --all-files` to catch overages early, before the final Step 11 pass (Gap 8)
  - [ ] Check line counts for all new modules
  - [ ] If any module exceeds 600 lines, further split that module (e.g. break `_update_analysis_ui` into smaller rendering helpers) — fallback only; the analysis module is estimated ~520-560 and is not preemptively split
  - [ ] **Deadline:** Complete before 2026-10-07 (exemption expiry)

- [ ] **Step 10:** Remove `src/frontend/ui/backend_playlist_card.py` from exemption list
  - [ ] Update `scripts/file-length-exemptions.json`
  - [ ] Remove the exemption entry for `backend_playlist_card.py` (note: the entry's `reason` currently says "940 lines" while the file is 1056 — cosmetic, corrected by removal)

- [ ] **Step 11:** Run pre-commit hooks to verify file length check passes
  - [ ] Hook id is `file-length-check` (`.pre-commit-config.yaml:114`, entry `scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json --warn`); enforces a 700-line code limit
  - [ ] Run `pre-commit run file-length-check --all-files`
  - [ ] Verify no warnings for the new modules

- [ ] **Step 12:** Update type checking (basedpyright) and resolve cross-mixin attribute typing (G5)
  - [ ] Run `.venv/bin/basedpyright src/frontend src/shared --level error`
  - [ ] `super().on_touch_down/move/up` in the interaction mixin type-checks via the typing-only `Widget` base set up in Step 3 (pass-3 E1). If the fallback `# pyright: ignore[reportAttributeAccessIssue]` approach was used instead, confirm those suppressions are present.
  - [ ] Cross-mixin attribute access: every mixin method that reads an attribute it does not define must resolve. Approach (chosen): declare each cross-mixin attribute as a class-level annotation with a default on the mixin that first needs it:
    - `PlaylistCardInteractionMixin`: `_is_touch_down`, `_touch_start_time`, `_touch_start_pos`, `_last_click_time`, `_long_press_event`, `_pending_single_click`, `_detailed_popup`, `checkbox` (reads both in `_handle_delayed_single_click`)
    - `PlaylistCardUIMixin`: `card_bg`, `info_bg`, `_bg_color`, `checkbox`, `_graphics_update_scheduled` (writes `_graphics_update_scheduled` in `_schedule_graphics_update`)
    - `PlaylistCardAnalysisPopupMixin` / `PlaylistCardTracksPopupMixin`: `playlist_data`, `_detailed_popup` / `_tracks_popup`
    - Main class: `playlist_data`, `_graphics_update_scheduled`, `_detailed_popup`, `_tracks_popup`
    - Use `Any` defaults (e.g. `playlist_data: Any = None`) so basedpyright does not flag `self.<attr>` access. If any residual `reportAttributeAccessIssue` remains, add a targeted `# pyright: ignore[reportAttributeAccessIssue]`.
  - [ ] Add type annotations for cross-module method signatures where needed
  - [ ] Use `if TYPE_CHECKING:` blocks to avoid circular imports for type hints

- [ ] **Step 13:** Update developer docs for the new files (G7)
  - [ ] Update `dev-docs/code-map.md` to index each new `backend_playlist_card_*.py` file and its role
  - [ ] Update `dev-docs/ARCHITECTURE.md` to document the mixin-based `BackendPlaylistCard` architecture (the split into utils/ui/interaction/analysis-popup/tracks-popup mixins + the `BoxLayout`-last MRO)
  - [ ] Update `dev-docs/dependency-graph.json` with the new import edges (utils ← ui/interaction/analysis/tracks; main ← all)
  - [ ] Grep docs for stale references to the original `1056`-line count or the `backend_playlist_card.py` exemption `reason` and refresh them (e.g. `dev-docs/backlog/TO_DO.md`, any plan/index that cites the exemption) so documentation stays consistent (claim #8)
  - [ ] No CHANGELOG entry needed (internal refactor, no user-visible behavior change)
  - [ ] Before committing, run `git diff --stat` (and `git status`) to confirm only the intended files changed (new `backend_playlist_card_*.py` modules, the slimmed main module, and doc/exemption edits)

## Testing Strategy

- [ ] **Automated:** `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v` (headless suite stubs kivy; covers `_mood_label`, popup-content wiring, worker error paths)
- [ ] **Manual (real GUI):** single-click selection, analysis popup open, tracks popup open, graphics rendering/resize, API error handling
- [ ] Verify popup content attributes are preserved (`_analysis_container`, `_duration_label`, `_tracks_layout`) for worker thread access
- [ ] Run basedpyright to ensure type safety is maintained
- [ ] Test import paths: verify `from ..ui.backend_playlist_card import BackendPlaylistCard` still works (and `_mood_label` via re-export)

## Dependencies

- Must maintain compatibility with existing screens that use `BackendPlaylistCard` (`backend_main_screen.py:8`)
- Must not break existing frontend tests (`test_backend_playlist_card_analysis.py:78`)
- Must follow existing code conventions (Kivy/KivyMD patterns)
- Must preserve popup content attributes used by worker threads
- Must consider `ui/__init__.py` lazy-loading pattern for new modules

## Success Criteria

- [ ] All new module files are under 600 lines
- [ ] All existing tests pass
- [ ] File is removed from `scripts/file-length-exemptions.json`
- [ ] Pre-commit file length hook passes without exemption
- [ ] No regressions in card functionality
- [ ] Type checking passes (basedpyright)
- [ ] Import paths work for both consumers and tests
- [ ] Popup content attributes are preserved for worker thread access

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
- The analysis popup module (~520-560 lines) is within the 700-line hook limit and the 600-line soft goal; split `_update_analysis_ui()` only if it grows past 600
- Graphics and selection logic are too small for separate modules; merged into UI module
- Hook reality: `file-length-check` enforces a 700-line limit for code (with `--warn`); the 600-line target is a self-imposed safety margin
