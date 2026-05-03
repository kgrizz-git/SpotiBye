"""UI functionality testing for backend integration."""

from __future__ import annotations

import logging
import time
from typing import Dict, Any

from ..services.backend_client import BackendClient
from ..services.reccobeats_backend import ReccoBeatsBackendService
from ..caching.backend_cache import BackendCacheManager
from .test_framework import BackendTestFramework

logger = logging.getLogger(__name__)


class TestUIFunctionality:
    """Test UI functionality with backend integration."""

    def __init__(self, framework: BackendTestFramework):
        """
        Initialize UI tests.

        Args:
            framework: Test framework instance
        """
        self.framework = framework
        self.backend_client: Optional[BackendClient] = None
        self.recco_service: Optional[ReccoBeatsBackendService] = None
        self.cache_manager: Optional[BackendCacheManager] = None

    def setup(self) -> bool:
        """Setup UI test environment."""
        try:
            if self.framework.mock_server:
                backend_url = self.framework.mock_server.get_base_url()
                self.backend_client = BackendClient(backend_url)
                self.recco_service = ReccoBeatsBackendService(self.backend_client)
                self.cache_manager = BackendCacheManager(self.backend_client)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to setup UI tests: {e}")
            return False

    def test_playlist_loading(self) -> bool:
        """Test playlist loading functionality."""
        self.framework.start_test("Playlist Loading")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Test getting playlists
            playlists = self.backend_client.get_playlists()

            if not playlists:
                self.framework.end_test(False, "No playlists returned")
                return False

            if len(playlists) == 0:
                self.framework.end_test(False, "Empty playlists list")
                return False

            # Verify playlist structure
            first_playlist = playlists[0]
            required_fields = ["id", "name", "tracks"]

            for field in required_fields:
                if field not in first_playlist:
                    self.framework.end_test(False, f"Missing required field: {field}")
                    return False

            self.framework.end_test(True, f"Loaded {len(playlists)} playlists")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Playlist loading failed: {e}")
            return False

    def test_playlist_details(self) -> bool:
        """Test playlist details retrieval."""
        self.framework.start_test("Playlist Details")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Get a playlist ID from playlists list
            playlists = self.backend_client.get_playlists()
            if not playlists:
                self.framework.end_test(False, "No playlists available")
                return False

            playlist_id = playlists[0]["id"]

            # Test getting playlist details
            details = self.backend_client.get_playlist_details(playlist_id)

            if not details:
                self.framework.end_test(False, "No playlist details returned")
                return False

            # Verify details structure
            if details.get("id") != playlist_id:
                self.framework.end_test(False, "Playlist ID mismatch")
                return False

            self.framework.end_test(True, "Playlist details retrieved successfully")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Playlist details failed: {e}")
            return False

    def test_track_loading(self) -> bool:
        """Test track loading from playlist."""
        self.framework.start_test("Track Loading")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Get a playlist ID
            playlists = self.backend_client.get_playlists()
            if not playlists:
                self.framework.end_test(False, "No playlists available")
                return False

            playlist_id = playlists[0]["id"]

            # Test getting tracks
            tracks = self.backend_client.get_playlist_tracks(playlist_id)

            if not tracks:
                self.framework.end_test(False, "No tracks returned")
                return False

            # Verify track structure
            if len(tracks) > 0:
                first_track = tracks[0]
                required_fields = ["id", "name", "artists"]

                for field in required_fields:
                    if field not in first_track:
                        self.framework.end_test(False, f"Missing track field: {field}")
                        return False

            self.framework.end_test(True, f"Loaded {len(tracks)} tracks")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Track loading failed: {e}")
            return False

    def test_analysis_functionality(self) -> bool:
        """Test playlist analysis functionality."""
        self.framework.start_test("Analysis Functionality")

        try:
            if not self.recco_service:
                self.framework.end_test(False, "ReccoBeats service not initialized")
                return False

            # Get a playlist ID
            playlists = self.backend_client.get_playlists()
            if not playlists:
                self.framework.end_test(False, "No playlists available")
                return False

            playlist_id = playlists[0]["id"]

            # Test playlist analysis
            analysis_results = self.recco_service.analyze_playlist(playlist_id)

            if not analysis_results:
                self.framework.end_test(False, "No analysis results returned")
                return False

            # Verify analysis results structure
            if "results" not in analysis_results:
                self.framework.end_test(False, "Missing analysis results")
                return False

            self.framework.end_test(True, "Analysis completed successfully")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Analysis failed: {e}")
            return False

    def test_export_functionality(self) -> bool:
        """Test export functionality."""
        self.framework.start_test("Export Functionality")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Get a playlist ID
            playlists = self.backend_client.get_playlists()
            if not playlists:
                self.framework.end_test(False, "No playlists available")
                return False

            playlist_id = playlists[0]["id"]

            # Test export generation
            export_response = self.backend_client.generate_export(playlist_id, "xlsx")

            if not export_response:
                self.framework.end_test(False, "No export response returned")
                return False

            export_id = export_response.get("export_id")
            if not export_id:
                self.framework.end_test(False, "No export ID in response")
                return False

            self.framework.end_test(True, f"Export generated with ID: {export_id}")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Export failed: {e}")
            return False

    def test_caching_functionality(self) -> bool:
        """Test caching functionality."""
        self.framework.start_test("Caching Functionality")

        try:
            if not self.cache_manager:
                self.framework.end_test(False, "Cache manager not initialized")
                return False

            # Test playlist caching
            test_playlists = [{"id": "test_1", "name": "Test Playlist"}]
            self.cache_manager.cache_playlists(test_playlists)

            # Test cache retrieval
            cached_playlists = self.cache_manager.get_cached_playlists()

            if not cached_playlists:
                self.framework.end_test(False, "No cached playlists found")
                return False

            if len(cached_playlists) == 0:
                self.framework.end_test(False, "Empty cached playlists")
                return False

            # Test cache validity
            is_valid = self.cache_manager.is_playlists_cache_valid()

            if not is_valid:
                self.framework.end_test(False, "Cache marked as invalid")
                return False

            self.framework.end_test(True, "Caching functionality working")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Caching test failed: {e}")
            return False

    def test_error_handling(self) -> bool:
        """Test error handling in UI components."""
        self.framework.start_test("Error Handling")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Test invalid playlist ID
            try:
                invalid_playlist = self.backend_client.get_playlist_details(
                    "invalid_id_12345"
                )
                # Should not reach here for invalid ID
                self.framework.end_test(False, "Invalid playlist ID should raise error")
                return False
            except Exception:
                # Expected behavior
                pass

            # Test invalid track ID
            try:
                invalid_track = self.backend_client.get_track_details(
                    "invalid_track_12345"
                )
                # Should not reach here for invalid ID
                self.framework.end_test(False, "Invalid track ID should raise error")
                return False
            except Exception:
                # Expected behavior
                pass

            self.framework.end_test(True, "Error handling working correctly")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Error handling test failed: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all UI functionality tests."""
        logger.info("Starting UI functionality tests")

        if not self.setup():
            return {"success": False, "message": "Failed to setup test environment"}

        # Run individual tests
        tests = [
            self.test_playlist_loading,
            self.test_playlist_details,
            self.test_track_loading,
            self.test_analysis_functionality,
            self.test_export_functionality,
            self.test_caching_functionality,
            self.test_error_handling,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            time.sleep(0.1)  # Small delay between tests

        logger.info(f"UI functionality tests completed: {passed}/{total} passed")

        return {
            "success": True,
            "passed": passed,
            "total": total,
            "results": self.framework.get_test_results(),
        }
