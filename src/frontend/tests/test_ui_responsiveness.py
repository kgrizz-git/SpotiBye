"""UI responsiveness testing for network operations."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from ..services.backend_client import BackendClient
from ..utils.network_utils import ProgressTracker

logger = logging.getLogger(__name__)


class TestUIResponsiveness:
    @pytest.fixture(autouse=True)
    def setup_clients(self, mock_backend_server):
        backend_url = mock_backend_server.get_base_url()
        self.backend_client = BackendClient(backend_url)
        self.ui_events: List[Dict[str, Any]] = []

    def _emit(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        self.ui_events.append(
            {"timestamp": time.time(), "event_type": event_type, "data": data or {}}
        )

    def test_loading_indicators_during_requests(self):
        self.ui_events.clear()
        with patch("time.sleep", return_value=0.01):
            self._emit("loading_started", {"operation": "get_playlists"})
            playlists = self.backend_client.get_playlists()
            self._emit(
                "loading_completed",
                {"operation": "get_playlists", "result_count": len(playlists)},
            )

        loading_events = [
            e
            for e in self.ui_events
            if e["event_type"] in ("loading_started", "loading_completed")
        ]
        assert (
            len(loading_events) >= 2
        ), f"Expected at least 2 loading events, got {len(loading_events)}"
        start_event = next(
            (e for e in loading_events if e["event_type"] == "loading_started"), None
        )
        complete_event = next(
            (e for e in loading_events if e["event_type"] == "loading_completed"), None
        )
        assert (
            start_event and complete_event
        ), "Missing loading start or complete events"
        assert (
            start_event["timestamp"] <= complete_event["timestamp"]
        ), "Loading start event after complete event"

    def test_ui_freezing_prevention(self):
        self.ui_events.clear()
        ui_responsive = True
        last_ui_update = time.time()

        def simulate_ui_updates() -> None:
            nonlocal ui_responsive, last_ui_update
            for i in range(10):
                if time.time() - last_ui_update > 0.1:
                    ui_responsive = False
                    break
                self._emit("ui_update", {"frame": i})
                last_ui_update = time.time()
                time.sleep(0.02)

        ui_thread = threading.Thread(target=simulate_ui_updates)
        ui_thread.start()
        self.backend_client.get_playlists()
        ui_thread.join(timeout=1.0)

        assert ui_responsive, "UI became unresponsive during operation"
        ui_update_events = [e for e in self.ui_events if e["event_type"] == "ui_update"]
        assert (
            len(ui_update_events) >= 5
        ), f"Insufficient UI updates: {len(ui_update_events)}"

    def test_progress_indicators(self):
        self.ui_events.clear()
        progress_tracker = ProgressTracker(total_steps=5, description="Test Operation")

        def progress_callback(
            current_step: int, total_steps: int, message: str
        ) -> None:
            self._emit(
                "progress_update",
                {
                    "current_step": current_step,
                    "total_steps": total_steps,
                    "progress": current_step / total_steps,
                    "message": message,
                },
            )

        progress_tracker.add_callback(progress_callback)
        for step in range(5):
            progress_tracker.update(step=1, message=f"Processing step {step + 1}")
            time.sleep(0.01)

        progress_events = [
            e for e in self.ui_events if e["event_type"] == "progress_update"
        ]
        assert (
            len(progress_events) == 5
        ), f"Expected 5 progress events, got {len(progress_events)}"

        for i, event in enumerate(progress_events):
            data = event["data"]
            expected_step = i + 1
            assert (
                data.get("current_step") == expected_step
            ), f"Current step incorrect at event {i}: expected {expected_step}, got {data.get('current_step')}"
            assert (
                abs(data.get("progress", 0) - expected_step / 5.0) <= 0.01
            ), f"Progress value incorrect at event {i}"

    def test_error_handling_ui_feedback(self):
        self.ui_events.clear()

        def handle_network_error(error: Exception) -> None:
            self._emit(
                "error_occurred",
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "retry_available": True,
                },
            )

        try:
            self.backend_client._make_request("GET", "/invalid/endpoint")
        except Exception as e:
            handle_network_error(e)

        error_events = [
            e for e in self.ui_events if e["event_type"] == "error_occurred"
        ]
        assert (
            len(error_events) == 1
        ), f"Expected 1 error event, got {len(error_events)}"
        error_data = error_events[0]["data"]
        for field in ["error_type", "error_message", "retry_available"]:
            assert field in error_data, f"Missing error field: {field}"
        assert error_data[
            "retry_available"
        ], "Retry should be available for network errors"

    def test_concurrent_ui_operations(self):
        self.ui_events.clear()
        ui_update_count = 0
        start_time = time.time()

        def simulate_ui_responsiveness() -> None:
            nonlocal ui_update_count
            for i in range(20):
                if time.time() - start_time > 2.0:
                    break
                self._emit("ui_responsive", {"frame": i})
                ui_update_count += 1
                time.sleep(0.05)

        def network_operation(operation_id: int) -> None:
            try:
                self._emit("operation_started", {"id": operation_id})
                playlists = self.backend_client.get_playlists()
                self._emit(
                    "operation_completed",
                    {"id": operation_id, "result_count": len(playlists)},
                )
            except Exception as e:
                self._emit("operation_failed", {"id": operation_id, "error": str(e)})

        ui_thread = threading.Thread(target=simulate_ui_responsiveness)
        ui_thread.start()

        op_threads = [
            threading.Thread(target=network_operation, args=(i,)) for i in range(3)
        ]
        for t in op_threads:
            t.start()
        for t in op_threads:
            t.join(timeout=3.0)
        ui_thread.join(timeout=1.0)

        assert (
            ui_update_count >= 10
        ), f"Insufficient UI updates during concurrent operations: {ui_update_count}"
        operation_events = [e for e in self.ui_events if "operation" in e["event_type"]]
        assert (
            len(operation_events) >= 6
        ), f"Insufficient operation events: {len(operation_events)}"
