from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from src.frontend.screens.main_screen_export import MainScreenExportOrchestrator

class FakeScheduler:
    def call_soon(self, callback):
        callback()
    def call_later(self, delay, callback):
        callback()

@pytest.fixture
def mock_screen():
    screen = MagicMock()
    screen.backend_adapter = MagicMock()
    screen.status_label = MagicMock()
    screen.progress_bar = MagicMock()
    screen.export_btn = MagicMock()
    screen.cancel_btn = MagicMock()
    screen.filename_input = MagicMock()
    screen.trace_mode_enabled = False
    screen._current_trace_id = ""
    screen._backend_error_phase = "idle"
    screen._backend_error_step = ""
    return screen

@pytest.fixture
def orchestrator(mock_screen):
    return MainScreenExportOrchestrator(mock_screen, FakeScheduler())

def test_orchestrator_initialization(orchestrator, mock_screen):
    assert orchestrator.screen == mock_screen
    assert isinstance(orchestrator.scheduler, FakeScheduler)

def test_build_backend_output_path_single(orchestrator):
    path = orchestrator._build_backend_output_path({"id": "1"}, "/tmp/file.xlsx", False)
    assert path == "/tmp/file.xlsx"

def test_cancel_export(orchestrator, mock_screen):
    with patch("src.frontend.screens.main_screen_export.mark_current_export_cancelled", return_value=True):
        orchestrator.cancel_export()
        assert mock_screen.cancel_btn.disabled is True
        assert mock_screen.status_label.text == "Cancelling export..."

def test_cleanup_after_export(orchestrator, mock_screen):
    with patch("src.frontend.screens.main_screen_export.clear_current_export_job") as mock_clear:
        orchestrator.cleanup_after_export()
        assert mock_screen.export_btn.disabled is False
        assert mock_screen.progress_bar.value == 0
        mock_clear.assert_called_once()

def test_handle_export_cancelled(orchestrator, mock_screen):
    orchestrator.handle_export_cancelled()
    assert mock_screen.status_label.text == "Export cancelled"
