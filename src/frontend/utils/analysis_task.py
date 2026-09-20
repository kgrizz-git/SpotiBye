"""UI-safe progress helper for backend playlist analysis."""

from __future__ import annotations

from typing import Any

from kivy.clock import Clock


class AnalysisTask:
    """Tracks cancellation and marshals analysis progress updates onto Kivy."""

    def __init__(self, progress_bar: Any, status_label: Any) -> None:
        self._progress_bar = progress_bar
        self._status_label = status_label
        self._cancelled = False
        self._displayed_progress = 0

    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def update_progress(self, progress: int, message: str) -> None:
        clamped = self._clamp(progress)
        if clamped < self._displayed_progress and clamped < 100:
            clamped = self._displayed_progress
        self._set_progress(clamped, message)

    def update_synthetic_progress(
        self,
        elapsed_seconds: float,
        message: str,
        cap: int = 90,
    ) -> None:
        synthetic = min(self._clamp(cap), int(max(0.0, elapsed_seconds) * 2))
        if synthetic <= self._displayed_progress:
            synthetic = self._displayed_progress
        self._set_progress(synthetic, message)

    def _set_progress(self, progress: int, message: str) -> None:
        self._displayed_progress = self._clamp(progress)

        def apply_update(_dt: float) -> None:
            # Execution-time guard: a callback queued before dismiss/refresh
            # must not touch detached or reassigned widgets. Runs on the main
            # thread, same thread as cancel(), so the check is race-free.
            if self._cancelled:
                return
            if self._progress_bar is not None:
                self._progress_bar.value = self._displayed_progress
            if self._status_label is not None:
                self._status_label.text = message

        Clock.schedule_once(apply_update, 0)

    @staticmethod
    def _clamp(progress: int) -> int:
        return max(0, min(100, int(progress)))
