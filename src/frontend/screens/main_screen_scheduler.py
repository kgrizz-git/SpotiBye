"""Kivy scheduling adapter for MainScreen background workers."""

from __future__ import annotations

from typing import Callable
from kivy.clock import Clock


class KivyScheduler:
    """Interface to Kivy Clock for background threads."""

    def call_soon(self, callback: Callable[[], None]) -> None:
        """Schedule a callback for the next frame on the main thread."""
        Clock.schedule_once(lambda _dt: callback(), 0)

    def call_later(self, delay: float, callback: Callable[[], None]) -> None:
        """Schedule a callback after a delay on the main thread."""
        Clock.schedule_once(lambda _dt: callback(), delay)
