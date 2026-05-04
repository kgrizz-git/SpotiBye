"""UI responsiveness testing for network operations."""

from __future__ import annotations

import logging
import time
import threading
from typing import Dict, Any, List, Optional
from unittest.mock import patch

from ..services.backend_client import BackendClient
from ..utils.network_utils import ProgressTracker
from .test_framework import BackendTestFramework

logger = logging.getLogger(__name__)


class TestUIResponsiveness:
    """Test UI responsiveness during network operations."""

    def __init__(self, framework: BackendTestFramework):
        """
        Initialize UI responsiveness tests.

        Args:
            framework: Test framework instance
        """
        self.framework = framework
        self.backend_client: Optional[BackendClient] = None
        self.ui_events: List[Dict[str, Any]] = []

    def setup(self) -> bool:
        """Setup UI responsiveness test environment."""
        try:
            if self.framework.mock_server:
                backend_url = self.framework.mock_server.get_base_url()
                self.backend_client = BackendClient(backend_url)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to setup UI responsiveness tests: {e}")
            return False

    def mock_ui_update(self, event_type: str, data: Dict[str, Any] = None):
        """Mock UI update function to track responsiveness."""
        self.ui_events.append(
            {"timestamp": time.time(), "event_type": event_type, "data": data or {}}
        )

    def test_loading_indicators_during_requests(self) -> bool:
        """Test that loading indicators work properly during network requests."""
        self.framework.start_test("Loading Indicators During Requests")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Clear UI events
            self.ui_events.clear()

            # Mock UI update functions
            with patch("time.sleep", return_value=0.01):  # Speed up test
                # Simulate UI loading indicator
                self.mock_ui_update("loading_started", {"operation": "get_playlists"})

                # Make network request
                playlists = self.backend_client.get_playlists()

                # Simulate UI loading complete
                self.mock_ui_update(
                    "loading_completed",
                    {"operation": "get_playlists", "result_count": len(playlists)},
                )

            # Verify loading indicators were shown
            loading_events = [
                e
                for e in self.ui_events
                if e["event_type"] in ["loading_started", "loading_completed"]
            ]

            if len(loading_events) < 2:
                self.framework.end_test(
                    False,
                    f"Expected at least 2 loading events, got {len(loading_events)}",
                )
                return False

            # Verify proper sequence: start -> complete
            start_event = next(
                (e for e in loading_events if e["event_type"] == "loading_started"),
                None,
            )
            complete_event = next(
                (e for e in loading_events if e["event_type"] == "loading_completed"),
                None,
            )

            if not start_event or not complete_event:
                self.framework.end_test(
                    False, "Missing loading start or complete events"
                )
                return False

            if start_event["timestamp"] > complete_event["timestamp"]:
                self.framework.end_test(
                    False, "Loading start event after complete event"
                )
                return False

            self.framework.end_test(
                True,
                f"Loading indicators working properly, events: {len(loading_events)}",
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Loading indicators test failed: {e}")
            return False

    def test_ui_freezing_prevention(self) -> bool:
        """Test that UI doesn't freeze during long-running operations."""
        self.framework.start_test("UI Freezing Prevention")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Clear UI events
            self.ui_events.clear()

            # Simulate UI responsiveness during long operation
            ui_responsive = True
            last_ui_update = time.time()

            def simulate_ui_updates():
                """Simulate periodic UI updates during network operation."""
                nonlocal ui_responsive, last_ui_update
                for i in range(10):  # 10 UI update cycles
                    if time.time() - last_ui_update > 0.1:  # 100ms threshold
                        ui_responsive = False
                        break

                    self.mock_ui_update("ui_update", {"frame": i})
                    last_ui_update = time.time()
                    time.sleep(0.02)  # 20ms between updates

            # Start UI update simulation in background
            ui_thread = threading.Thread(target=simulate_ui_updates)
            ui_thread.start()

            # Perform network operation
            start_time = time.time()
            self.backend_client.get_playlists()
            operation_time = time.time() - start_time

            # Wait for UI thread to complete
            ui_thread.join(timeout=1.0)

            if not ui_responsive:
                self.framework.end_test(
                    False, "UI became unresponsive during operation"
                )
                return False

            # Verify UI updates occurred during operation
            ui_events = [e for e in self.ui_events if e["event_type"] == "ui_update"]

            if len(ui_events) < 5:  # Should have at least 5 UI updates
                self.framework.end_test(
                    False, f"Insufficient UI updates: {len(ui_events)}"
                )
                return False

            self.framework.end_test(
                True,
                f"UI remained responsive, updates: {len(ui_events)}, operation_time: {operation_time:.3f}s",
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"UI freezing prevention test failed: {e}")
            return False

    def test_progress_indicators(self) -> bool:
        """Test progress indicators for long-running operations."""
        self.framework.start_test("Progress Indicators")

        try:
            # Clear UI events
            self.ui_events.clear()

            # Create progress tracker
            progress_tracker = ProgressTracker(
                total_steps=5, description="Test Operation"
            )

            # Mock progress callback
            def progress_callback(current_step: int, total_steps: int, message: str):
                progress_data = {
                    "current_step": current_step,
                    "total_steps": total_steps,
                    "progress": current_step / total_steps,
                    "message": message,
                }
                self.mock_ui_update("progress_update", progress_data)

            progress_tracker.add_callback(progress_callback)

            # Simulate progress updates
            for step in range(5):
                progress_tracker.update(step=1, message=f"Processing step {step + 1}")
                time.sleep(0.01)  # Small delay

            # Verify progress events
            progress_events = [
                e for e in self.ui_events if e["event_type"] == "progress_update"
            ]

            if len(progress_events) != 5:
                self.framework.end_test(
                    False, f"Expected 5 progress events, got {len(progress_events)}"
                )
                return False

            # Verify progress values
            for i, event in enumerate(progress_events):
                progress = event["data"]
                expected_step = i + 1
                expected_progress = expected_step / 5.0

                if progress.get("current_step", 0) != expected_step:
                    self.framework.end_test(
                        False,
                        f"Current step incorrect at event {i}: expected {expected_step}, got {progress.get('current_step', 0)}",
                    )
                    return False

                if abs(progress.get("progress", 0) - expected_progress) > 0.01:
                    self.framework.end_test(
                        False,
                        f"Progress value incorrect at event {i}: expected {expected_progress}, got {progress.get('progress', 0)}",
                    )
                    return False

            self.framework.end_test(
                True, f"Progress indicators working, events: {len(progress_events)}"
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Progress indicators test failed: {e}")
            return False

    def test_error_handling_ui_feedback(self) -> bool:
        """Test UI feedback for error conditions."""
        self.framework.start_test("Error Handling UI Feedback")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Clear UI events
            self.ui_events.clear()

            # Mock error handling
            def handle_network_error(error: Exception):
                self.mock_ui_update(
                    "error_occurred",
                    {
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "retry_available": True,
                    },
                )

            # Test with invalid endpoint to trigger error
            try:
                # This should trigger a 404 error
                self.backend_client._make_request("GET", "/invalid/endpoint")
            except Exception as e:
                handle_network_error(e)

            # Verify error event was created
            error_events = [
                e for e in self.ui_events if e["event_type"] == "error_occurred"
            ]

            if len(error_events) != 1:
                self.framework.end_test(
                    False, f"Expected 1 error event, got {len(error_events)}"
                )
                return False

            error_event = error_events[0]
            error_data = error_event["data"]

            # Verify error data structure
            required_fields = ["error_type", "error_message", "retry_available"]
            for field in required_fields:
                if field not in error_data:
                    self.framework.end_test(False, f"Missing error field: {field}")
                    return False

            if not error_data["retry_available"]:
                self.framework.end_test(
                    False, "Retry should be available for network errors"
                )
                return False

            self.framework.end_test(
                True,
                f"Error handling UI feedback working, error_type: {error_data['error_type']}",
            )
            return True

        except Exception as e:
            self.framework.end_test(
                False, f"Error handling UI feedback test failed: {e}"
            )
            return False

    def test_concurrent_ui_operations(self) -> bool:
        """Test UI responsiveness during concurrent network operations."""
        self.framework.start_test("Concurrent UI Operations")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Clear UI events
            self.ui_events.clear()

            # Track UI responsiveness
            ui_responsive = True
            ui_update_count = 0

            def simulate_ui_responsiveness():
                """Simulate UI updates during concurrent operations."""
                nonlocal ui_responsive, ui_update_count
                for i in range(20):  # 20 UI update cycles
                    if time.time() - start_time > 2.0:  # 2 second timeout
                        break

                    self.mock_ui_update("ui_responsive", {"frame": i})
                    ui_update_count += 1
                    time.sleep(0.05)  # 50ms between updates

            # Start UI responsiveness monitoring
            start_time = time.time()
            ui_thread = threading.Thread(target=simulate_ui_responsiveness)
            ui_thread.start()

            # Perform concurrent network operations
            def network_operation(operation_id: int):
                """Perform network operation and track UI events."""
                try:
                    self.mock_ui_update("operation_started", {"id": operation_id})

                    # Make network request
                    playlists = self.backend_client.get_playlists()

                    self.mock_ui_update(
                        "operation_completed",
                        {"id": operation_id, "result_count": len(playlists)},
                    )
                except Exception as e:
                    self.mock_ui_update(
                        "operation_failed", {"id": operation_id, "error": str(e)}
                    )

            # Start multiple concurrent operations
            operation_threads = []
            for i in range(3):
                thread = threading.Thread(target=network_operation, args=(i,))
                operation_threads.append(thread)
                thread.start()

            # Wait for all operations to complete
            for thread in operation_threads:
                thread.join(timeout=3.0)

            # Wait for UI thread
            ui_thread.join(timeout=1.0)

            # Verify UI remained responsive
            if ui_update_count < 10:  # Should have at least 10 UI updates
                self.framework.end_test(
                    False,
                    f"Insufficient UI updates during concurrent operations: {ui_update_count}",
                )
                return False

            # Verify operation events
            operation_events = [
                e for e in self.ui_events if "operation" in e["event_type"]
            ]

            if (
                len(operation_events) < 6
            ):  # Should have at least 6 operation events (3 started + 3 completed)
                self.framework.end_test(
                    False, f"Insufficient operation events: {len(operation_events)}"
                )
                return False

            self.framework.end_test(
                True,
                f"Concurrent operations working, ui_updates: {ui_update_count}, operation_events: {len(operation_events)}",
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Concurrent UI operations test failed: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all UI responsiveness tests."""
        logger.info("Starting UI responsiveness tests")

        if not self.setup():
            return {"success": False, "message": "Failed to setup test environment"}

        # Run individual tests
        tests = [
            self.test_loading_indicators_during_requests,
            self.test_ui_freezing_prevention,
            self.test_progress_indicators,
            self.test_error_handling_ui_feedback,
            self.test_concurrent_ui_operations,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            time.sleep(0.1)  # Small delay between tests

        logger.info(f"UI responsiveness tests completed: {passed}/{total} passed")

        return {
            "success": True,
            "passed": passed,
            "total": total,
            "results": self.framework.get_test_results(),
        }
