"""Pytest configuration and fixtures for testing."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.spotibye_backend.api.main import app
from src.spotibye_backend.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
)
from src.spotibye_backend.config import Settings


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with temporary directories."""
    # Create temporary directories for testing
    temp_dir = tempfile.mkdtemp(prefix="spotibye_test_")

    # Set test environment variables
    os.environ["SPOTIPY_CLIENT_ID"] = "test_client_id"
    os.environ["SPOTIPY_CLIENT_SECRET"] = "test_client_secret"
    os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only"
    os.environ["DEBUG"] = "true"
    os.environ["CACHE_PATH"] = os.path.join(temp_dir, "test_token")
    os.environ["SAVE_DIR"] = os.path.join(temp_dir, "downloads")
    os.environ["TMP_DIR"] = os.path.join(temp_dir, "exports")
    os.environ["DEFAULT_CACHE_DIR"] = os.path.join(temp_dir, "cache")

    yield Settings()

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture()
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Create test client with test settings."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Create authentication headers with valid JWT token."""
    user_data = {
        "sub": "test_user",
        "username": "testuser",
        "display_name": "Test User",
    }
    access_token = create_access_token(user_data)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture()
def auth_headers_with_spotify() -> dict[str, str]:
    """Create authentication headers with JWT token and Spotify token info."""
    user_data = {
        "sub": "test_user",
        "username": "testuser",
        "display_name": "Test User",
        "token_info": {
            "access_token": "test_spotify_token",
            "refresh_token": "test_spotify_refresh",
            "expires_at": 1765305000,  # Future timestamp
        },
    }
    access_token = create_access_token(user_data)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture()
def refresh_token() -> str:
    """Create a valid refresh token for testing."""
    return create_refresh_token("test_user")


@pytest.fixture()
def temp_file() -> Generator[Path, None, None]:
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_text("test content")
        yield temp_path
        temp_path.unlink(missing_ok=True)


@pytest.fixture()
def mock_spotify_data() -> dict[str, any]:
    """Mock Spotify API response data."""
    return {
        "playlists": {
            "items": [
                {
                    "id": "test_playlist_1",
                    "name": "Test Playlist 1",
                    "description": "A test playlist",
                    "tracks": {"total": 10},
                    "external_urls": {
                        "spotify": "https://open.spotify.com/playlist/test_playlist_1"
                    },
                    "images": [
                        {
                            "url": "https://example.com/image.jpg",
                            "height": 300,
                            "width": 300,
                        }
                    ],
                }
            ]
        },
        "user": {
            "id": "test_user_id",
            "display_name": "Test User",
            "email": "test@example.com",
            "country": "US",
            "product": "premium",
        },
        "tracks": {
            "items": [
                {
                    "track": {
                        "id": "test_track_1",
                        "name": "Test Track",
                        "artists": [{"name": "Test Artist"}],
                        "album": {"name": "Test Album"},
                        "duration_ms": 180000,
                        "external_urls": {
                            "spotify": "https://open.spotify.com/track/test_track_1"
                        },
                    }
                }
            ]
        },
    }


@pytest.fixture()
def mock_analysis_data() -> dict[str, any]:
    """Mock analysis response data."""
    return {
        "playlist_id": "test_playlist_1",
        "status": "completed",
        "results": {
            "total_tracks": 10,
            "analyzed_tracks": 10,
            "audio_features": {
                "danceability": 0.7,
                "energy": 0.8,
                "valence": 0.6,
                "acousticness": 0.3,
                "instrumentalness": 0.1,
                "liveness": 0.2,
                "speechiness": 0.4,
            },
            "reccobeats_analysis": {
                "recommendations": [{"track_id": "rec_track_1", "score": 0.9}]
            },
        },
        "created_at": "2025-12-09T12:00:00Z",
        "completed_at": "2025-12-09T12:05:00Z",
    }


# Performance testing utilities
@pytest.fixture()
def performance_monitor():
    """Utility for monitoring performance during tests."""
    import threading
    import time

    import psutil

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.memory_usage = []
            self.monitoring = False
            self.monitor_thread = None

        def start_monitoring(self):
            """Start performance monitoring."""
            self.start_time = time.time()
            self.monitoring = True
            self.memory_usage = []

            def monitor():
                process = psutil.Process()
                while self.monitoring:
                    self.memory_usage.append(process.memory_info().rss)
                    time.sleep(0.1)

            self.monitor_thread = threading.Thread(target=monitor)
            self.monitor_thread.start()

        def stop_monitoring(self):
            """Stop performance monitoring and return results."""
            self.end_time = time.time()
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join()

            return {
                "duration": self.end_time - self.start_time,
                "peak_memory": max(self.memory_usage) if self.memory_usage else 0,
                "avg_memory": sum(self.memory_usage) / len(self.memory_usage)
                if self.memory_usage
                else 0,
            }

    return PerformanceMonitor()


# Test database/cache setup
@pytest.fixture(scope="session")
def test_cache_dir() -> Generator[Path, None, None]:
    """Create a temporary cache directory for testing."""
    cache_dir = Path(tempfile.mkdtemp(prefix="spotibye_cache_test_"))
    yield cache_dir
    import shutil

    shutil.rmtree(cache_dir, ignore_errors=True)


@pytest.fixture()
def mock_redis():
    """Mock Redis for testing (if Redis is available)."""
    try:
        import redis

        # Try to connect to Redis
        client = redis.Redis(host="localhost", port=6379, db=15, decode_responses=True)
        client.ping()  # Test connection
        yield client
        # Clean up test database
        client.flushdb()
    except (ImportError, redis.ConnectionError):
        # Redis not available, skip Redis tests
        pytest.skip("Redis not available for testing")


# Mock external services
@pytest.fixture()
def mock_spotify_client():
    """Mock Spotify client for testing."""

    class MockSpotifyClient:
        def __init__(self, token_info=None):
            self.token_info = token_info or {}

        def current_user(self):
            return {
                "id": "test_user_id",
                "display_name": "Test User",
                "email": "test@example.com",
            }

        def current_user_playlists(self):
            return {
                "items": [
                    {
                        "id": "test_playlist_1",
                        "name": "Test Playlist",
                        "description": "A test playlist",
                    }
                ]
            }

        def playlist(self, playlist_id):
            return {
                "id": playlist_id,
                "name": "Test Playlist",
                "description": "A test playlist",
            }

        def playlist_items(self, playlist_id, offset=0, limit=50):
            return {
                "items": [
                    {
                        "track": {
                            "id": "test_track_1",
                            "name": "Test Track",
                            "artists": [{"name": "Test Artist"}],
                        }
                    }
                ]
            }

    return MockSpotifyClient


# Async testing utilities
@pytest.fixture()
def event_loop():
    """Create an event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Rate limiting test utilities
@pytest.fixture()
def rate_limiter():
    """Mock rate limiter for testing."""
    import time
    from collections import defaultdict

    class MockRateLimiter:
        def __init__(self, max_requests=100, window_seconds=60):
            self.max_requests = max_requests
            self.window_seconds = window_seconds
            self.requests = defaultdict(list)

        def is_allowed(self, key: str) -> bool:
            now = time.time()
            # Remove old requests
            self.requests[key] = [
                req_time
                for req_time in self.requests[key]
                if now - req_time < self.window_seconds
            ]

            if len(self.requests[key]) < self.max_requests:
                self.requests[key].append(now)
                return True

            return False

        def reset(self, key: str):
            """Reset rate limit for a specific key."""
            self.requests[key].clear()

    return MockRateLimiter()


# Error simulation utilities
@pytest.fixture()
def error_simulator():
    """Utility for simulating various error conditions."""

    class ErrorSimulator:
        def __init__(self):
            self.error_conditions = {}

        def set_error(self, endpoint: str, error: Exception):
            """Set an error to be raised for a specific endpoint."""
            self.error_conditions[endpoint] = error

        def should_error(self, endpoint: str):
            """Check if an error should be raised for the endpoint."""
            error = self.error_conditions.get(endpoint)
            if error:
                raise error
            return False

        def clear_errors(self):
            """Clear all error conditions."""
            self.error_conditions.clear()

    return ErrorSimulator()
