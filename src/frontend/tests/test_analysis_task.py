"""Tests for the playlist analysis progress task helper."""

from __future__ import annotations

from unittest.mock import patch

from src.frontend.utils.analysis_task import AnalysisTask


class _Widget:
    def __init__(self) -> None:
        self.value = 0
        self.text = ""


def _run_scheduled(callback, *_args, **_kwargs):
    callback(0)


def test_update_progress_clamps_and_updates_widgets_on_clock() -> None:
    progress_bar = _Widget()
    status_label = _Widget()
    task = AnalysisTask(progress_bar, status_label)

    with patch(
        "src.frontend.utils.analysis_task.Clock.schedule_once",
        side_effect=_run_scheduled,
    ):
        task.update_progress(125, "Almost done")

    assert progress_bar.value == 100
    assert status_label.text == "Almost done"


def test_synthetic_progress_rises_caps_below_completion_and_never_moves_backward() -> None:
    progress_bar = _Widget()
    status_label = _Widget()
    task = AnalysisTask(progress_bar, status_label)

    with patch(
        "src.frontend.utils.analysis_task.Clock.schedule_once",
        side_effect=_run_scheduled,
    ):
        task.update_synthetic_progress(15, "Analyzing playlist...")
        assert progress_bar.value == 30
        assert status_label.text == "Analyzing playlist..."

        task.update_synthetic_progress(120, "Still analyzing...")
        assert progress_bar.value == 90
        assert status_label.text == "Still analyzing..."

        task.update_progress(40, "Backend caught up")
        assert progress_bar.value == 90
        assert status_label.text == "Backend caught up"

        task.update_progress(100, "Analysis complete")
        assert progress_bar.value == 100
        assert status_label.text == "Analysis complete"
