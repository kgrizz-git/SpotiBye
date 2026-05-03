"""Performance testing for backend integration."""

from __future__ import annotations

import logging
import time
from typing import Dict, Any

from ..services.backend_client import BackendClient
from ..services.reccobeats_backend import ReccoBeatsBackendService
from .test_framework import BackendTestFramework

logger = logging.getLogger(__name__)


class TestPerformance:
    """Test performance with large datasets."""

    def __init__(self, framework: BackendTestFramework):
        """
        Initialize performance tests.

        Args:
            framework: Test framework instance
        """
        self.framework = framework
        self.backend_client: Optional[BackendClient] = None
        self.recco_service: Optional[ReccoBeatsBackendService] = None

    def setup(self) -> bool:
        """Setup performance test environment."""
        try:
            if self.framework.mock_server:
                backend_url = self.framework.mock_server.get_base_url()
                self.backend_client = BackendClient(backend_url)
                self.recco_service = ReccoBeatsBackendService(self.backend_client)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to setup performance tests: {e}")
            return False

    def test_large_playlist_loading(self) -> bool:
        """Test loading large playlists (>1000 tracks)."""
        self.framework.start_test("Large Playlist Loading")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Find large playlist
            playlists = self.backend_client.get_playlists()
            large_playlist = None

            for playlist in playlists:
                if playlist.get("tracks", {}).get("total", 0) > 1000:
                    large_playlist = playlist
                    break

            if not large_playlist:
                self.framework.end_test(False, "No large playlist found")
                return False

            playlist_id = large_playlist["id"]

            # Measure loading time
            start_time = time.time()
            tracks = self.backend_client.get_playlist_tracks(playlist_id)
            load_time = time.time() - start_time

            if not tracks:
                self.framework.end_test(False, "Failed to load large playlist tracks")
                return False

            # Verify we have many tracks
            if len(tracks) <= 1000:
                self.framework.end_test(
                    False, f"Playlist not large enough: {len(tracks)} tracks"
                )
                return False

            # Performance check (should load within reasonable time)
            if load_time > 10.0:  # 10 seconds
                self.framework.end_test(False, f"Loading too slow: {load_time:.2f}s")
                return False

            self.framework.end_test(
                True, f"Loaded {len(tracks)} tracks in {load_time:.2f}s"
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Large playlist test failed: {e}")
            return False

    def test_analysis_performance(self) -> bool:
        """Test analysis performance with large datasets."""
        self.framework.start_test("Analysis Performance")

        try:
            if not self.recco_service:
                self.framework.end_test(False, "ReccoBeats service not initialized")
                return False

            # Find large playlist
            playlists = self.backend_client.get_playlists()
            large_playlist = None

            for playlist in playlists:
                if playlist.get("tracks", {}).get("total", 0) > 1000:
                    large_playlist = playlist
                    break

            if not large_playlist:
                self.framework.end_test(False, "No large playlist found")
                return False

            playlist_id = large_playlist["id"]

            # Measure analysis time
            start_time = time.time()
            analysis_results = self.recco_service.analyze_playlist(playlist_id)
            analysis_time = time.time() - start_time

            if not analysis_results:
                self.framework.end_test(False, "Analysis failed for large playlist")
                return False

            # Performance check (should complete within reasonable time)
            if analysis_time > 60.0:  # 60 seconds
                self.framework.end_test(
                    False, f"Analysis too slow: {analysis_time:.2f}s"
                )
                return False

            self.framework.end_test(True, f"Analysis completed in {analysis_time:.2f}s")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Analysis performance test failed: {e}")
            return False

    def test_concurrent_requests(self) -> bool:
        """Test handling concurrent requests."""
        self.framework.start_test("Concurrent Requests")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            import threading
            import queue

            # Test concurrent playlist loading
            playlists = self.backend_client.get_playlists()

            results = queue.Queue()

            def load_playlist(playlist_id):
                try:
                    start_time = time.time()
                    tracks = self.backend_client.get_playlist_tracks(playlist_id)
                    load_time = time.time() - start_time
                    results.put(
                        {"success": True, "tracks": len(tracks), "time": load_time}
                    )
                except Exception as e:
                    results.put({"success": False, "error": str(e)})

            # Start multiple threads
            threads = []
            for playlist in playlists[:3]:  # Test with first 3 playlists
                thread = threading.Thread(target=load_playlist, args=(playlist["id"],))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=30)

            # Check results
            success_count = 0
            while not results.empty():
                result = results.get()
                if result["success"]:
                    success_count += 1

            if success_count < len(playlists[:3]):
                self.framework.end_test(
                    False,
                    f"Only {success_count}/{len(playlists[:3])} requests succeeded",
                )
                return False

            self.framework.end_test(
                True, f"All {success_count} concurrent requests succeeded"
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Concurrent requests test failed: {e}")
            return False

    def test_memory_usage(self) -> bool:
        """Test memory usage with large datasets."""
        self.framework.start_test("Memory Usage")

        try:
            import psutil
            import os

            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Get initial memory usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Load large playlist
            playlists = self.backend_client.get_playlists()
            large_playlist = None

            for playlist in playlists:
                if playlist.get("tracks", {}).get("total", 0) > 1000:
                    large_playlist = playlist
                    break

            if not large_playlist:
                self.framework.end_test(False, "No large playlist found")
                return False

            playlist_id = large_playlist["id"]
            tracks = self.backend_client.get_playlist_tracks(playlist_id)

            # Check memory after loading
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Memory should not increase excessively
            if memory_increase > 500:  # 500 MB increase
                self.framework.end_test(
                    False, f"Memory usage too high: {memory_increase:.1f}MB increase"
                )
                return False

            self.framework.end_test(
                True, f"Memory usage acceptable: {memory_increase:.1f}MB increase"
            )
            return True

        except ImportError:
            self.framework.end_test(False, "psutil not available for memory testing")
            return False
        except Exception as e:
            self.framework.end_test(False, f"Memory usage test failed: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance tests."""
        logger.info("Starting performance tests")

        if not self.setup():
            return {"success": False, "message": "Failed to setup test environment"}

        # Run individual tests
        tests = [
            self.test_large_playlist_loading,
            self.test_analysis_performance,
            self.test_concurrent_requests,
            self.test_memory_usage,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            time.sleep(0.5)  # Delay between performance tests

        logger.info(f"Performance tests completed: {passed}/{total} passed")

        return {
            "success": True,
            "passed": passed,
            "total": total,
            "results": self.framework.get_test_results(),
        }
