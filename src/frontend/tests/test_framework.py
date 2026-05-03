"""Test framework for backend integration testing."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .mock_backend import MockBackendServer, DEFAULT_TEST_DATA

logger = logging.getLogger(__name__)


class BackendTestFramework:
    """Framework for testing frontend backend integration."""

    def __init__(self):
        """Initialize test framework."""
        self.mock_server: Optional[MockBackendServer] = None
        self.test_results: List[Dict[str, Any]] = []
        self.current_test: Optional[str] = None

    def setup_mock_backend(self, test_data: Optional[Dict[str, Any]] = None) -> bool:
        """Setup mock backend server."""
        test_data = test_data or DEFAULT_TEST_DATA

        self.mock_server = MockBackendServer()
        self.mock_server.set_test_data(test_data)

        return self.mock_server.start()

    def teardown_mock_backend(self) -> None:
        """Stop mock backend server."""
        if self.mock_server:
            self.mock_server.stop()
            self.mock_server = None

    def start_test(self, test_name: str) -> None:
        """Start a new test."""
        self.current_test = test_name
        logger.info(f"Starting test: {test_name}")

    def end_test(self, success: bool, message: str = "") -> None:
        """End current test and record results."""
        if not self.current_test:
            return

        result = {
            "test_name": self.current_test,
            "success": success,
            "message": message,
            "timestamp": time.time(),
        }

        self.test_results.append(result)
        logger.info(
            f"Test {self.current_test}: {'PASSED' if success else 'FAILED'} - {message}"
        )
        self.current_test = None

    def get_test_results(self) -> List[Dict[str, Any]]:
        """Get all test results."""
        return self.test_results.copy()

    def clear_results(self) -> None:
        """Clear all test results."""
        self.test_results.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests

        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests * 100)
            if total_tests > 0
            else 0,
            "results": self.test_results,
        }
