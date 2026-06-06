"""Shared pytest fixtures for frontend integration tests."""

from __future__ import annotations

import pytest

from .mock_backend import MockBackendServer, DEFAULT_TEST_DATA


@pytest.fixture(scope="session")
def mock_backend_server():
    server = MockBackendServer(port=0)
    server.set_test_data(DEFAULT_TEST_DATA)
    server.start()
    yield server
    server.stop()
