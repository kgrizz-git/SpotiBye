"""Touch-interaction mixin for BackendPlaylistCard.

Defines PlaylistCardInteractionMixin — click/hold/long-press handling,
single-vs-double click discrimination, and touch state management.
Touch state variables are class-level defaults; initialized per-instance
in the main BackendPlaylistCard.__init__ and mutated by touch events.
Depends on kivy, time, math.

Thread-safety: on_touch_* methods run on the Kivy main thread. No
background-thread access to touch state variables.
"""

from __future__ import annotations

import time
from math import sqrt
from typing import TYPE_CHECKING, Any, Optional

from kivy.clock import Clock
from kivy.metrics import dp

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

    _TouchBase = Widget
else:
    _TouchBase = object


class PlaylistCardInteractionMixin(_TouchBase):
    """Interaction mixin for BackendPlaylistCard — touch + click logic.

    Provides on_touch_down/move/up, long-press trigger, and
    double-click-vs-single-click discrimination. Calls through
    to self.show_detailed_playlist_window() (AnalysisPopupMixin)
    and self.checkbox (UIMixin) via self.* — no direct imports needed.
    """

    DOUBLE_CLICK_THRESHOLD: float = 0.4
    LONG_PRESS_DURATION: float = 0.8
    MOVEMENT_THRESHOLD: float = dp(12)

    _is_touch_down: bool = False
    _touch_start_time: float = 0.0
    _touch_start_pos: Optional[tuple[float, float]] = None
    _last_click_time: float = 0.0
    _long_press_event: Optional[Any] = None
    _pending_single_click: Optional[Any] = None
    _detailed_popup: Optional[Any] = None
    checkbox: Optional[Any] = None

    def _setup_interactions(self) -> None:
        pass  # handled by on_touch_down / on_touch_up overrides

    def on_touch_down(self, touch) -> bool | None:
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        touch.grab(self)
        self._is_touch_down = True
        self._touch_start_time = time.time()
        self._touch_start_pos = touch.pos

        if self._long_press_event:
            self._long_press_event.cancel()
        self._long_press_event = Clock.schedule_once(
            lambda _dt: self._trigger_long_press(),
            self.LONG_PRESS_DURATION,
        )
        return True

    def on_touch_move(self, touch) -> bool | None:
        if touch.grab_current is self and self._is_touch_down and self._touch_start_pos:
            dx = touch.pos[0] - self._touch_start_pos[0]
            dy = touch.pos[1] - self._touch_start_pos[1]
            if sqrt(dx * dx + dy * dy) > self.MOVEMENT_THRESHOLD:
                self._is_touch_down = False
                if self._long_press_event:
                    self._long_press_event.cancel()
        return super().on_touch_move(touch)

    def _trigger_long_press(self) -> None:
        if self._is_touch_down:
            self._is_touch_down = False
            self.show_detailed_playlist_window()

    def on_touch_up(self, touch) -> bool | None:
        if touch.grab_current is not self:
            return super().on_touch_up(touch)

        touch.ungrab(self)
        self._is_touch_down = False

        if self._long_press_event:
            self._long_press_event.cancel()

        if self._touch_start_pos:
            dx = touch.pos[0] - self._touch_start_pos[0]
            dy = touch.pos[1] - self._touch_start_pos[1]
            if sqrt(dx * dx + dy * dy) > self.MOVEMENT_THRESHOLD:
                return True

        touch_duration = time.time() - self._touch_start_time
        if touch_duration >= self.LONG_PRESS_DURATION:
            return True

        now = time.time()
        time_since_last = now - self._last_click_time

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            if self._pending_single_click:
                self._pending_single_click.cancel()
                self._pending_single_click = None
            self._last_click_time = 0.0
            self.show_detailed_playlist_window()
        else:
            self._last_click_time = now
            if self._pending_single_click:
                self._pending_single_click.cancel()
            self._pending_single_click = Clock.schedule_once(
                self._handle_delayed_single_click,
                self.DOUBLE_CLICK_THRESHOLD + 0.05,
            )

        return True

    def _handle_delayed_single_click(self, _dt) -> None:
        self._pending_single_click = None
        if not (self._detailed_popup and self._detailed_popup.parent):
            self.checkbox.active = not self.checkbox.active


__all__ = ["PlaylistCardInteractionMixin"]