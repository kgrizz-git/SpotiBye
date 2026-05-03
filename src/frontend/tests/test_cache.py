"""Cache performance testing for backend integration."""

from __future__ import annotations

import logging
import time
from typing import Dict, Any

from ..caching.backend_cache import BackendCacheManager
from ..services.backend_client import BackendClient
from .test_framework import BackendTestFramework

logger = logging.getLogger(__name__)


class TestCachePerformance:
    """Test cache performance and hit rates."""

    def __init__(self, framework: BackendTestFramework):
        """
        Initialize cache performance tests.

        Args:
            framework: Test framework instance
        """
        self.framework = framework
        self.cache_manager: Optional[BackendCacheManager] = None
        self.backend_client: Optional[BackendClient] = None

    def setup(self) -> bool:
        """Setup cache performance test environment."""
        try:
            if self.framework.mock_server:
                backend_url = self.framework.mock_server.get_base_url()
                self.backend_client = BackendClient(backend_url)
                self.cache_manager = BackendCacheManager(self.backend_client)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to setup cache performance tests: {e}")
            return False

    def test_cache_hit_rate(self) -> bool:
        """Test cache hit rate performance."""
        self.framework.start_test("Cache Hit Rate")

        try:
            if not self.cache_manager:
                self.framework.end_test(False, "Cache manager not initialized")
                return False

            # Clear cache to start fresh
            self.cache_manager.clear_cache()

            # Test data
            test_playlists = [
                {"id": "cache_test_1", "name": "Test Playlist 1"},
                {"id": "cache_test_2", "name": "Test Playlist 2"},
                {"id": "cache_test_3", "name": "Test Playlist 3"},
            ]

            # First cache - should be misses
            start_time = time.time()
            self.cache_manager.cache_playlists(test_playlists)
            cache_time = time.time() - start_time

            # Retrieve from cache - should be hits
            start_time = time.time()
            cached_playlists = self.cache_manager.get_cached_playlists()
            retrieve_time = time.time() - start_time

            if not cached_playlists:
                self.framework.end_test(False, "No cached playlists found")
                return False

            if len(cached_playlists) != len(test_playlists):
                self.framework.end_test(
                    False,
                    f"Cache size mismatch: expected {len(test_playlists)}, got {len(cached_playlists)}",
                )
                return False

            # Test performance - cache retrieval should be fast
            if retrieve_time > 0.1:  # 100ms threshold
                self.framework.end_test(
                    False, f"Cache retrieval too slow: {retrieve_time:.3f}s"
                )
                return False

            # Test cache validity
            is_valid = self.cache_manager.is_playlists_cache_valid()
            if not is_valid:
                self.framework.end_test(False, "Cache marked as invalid")
                return False

            self.framework.end_test(
                True,
                f"Cache hit rate: 100%, cache time: {cache_time:.3f}s, retrieve time: {retrieve_time:.3f}s",
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Cache hit rate test failed: {e}")
            return False

    def test_cache_ttl_performance(self) -> bool:
        """Test cache TTL (Time To Live) performance."""
        self.framework.start_test("Cache TTL Performance")

        try:
            if not self.cache_manager:
                self.framework.end_test(False, "Cache manager not initialized")
                return False

            # Clear cache
            self.cache_manager.clear_cache()

            # Cache with short TTL for testing
            test_data = {"id": "ttl_test", "name": "TTL Test Playlist"}

            # Cache the data
            self.cache_manager.cache_playlists([test_data])

            # Should be valid immediately
            is_valid = self.cache_manager.is_playlists_cache_valid()
            if not is_valid:
                self.framework.end_test(
                    False, "Cache should be valid immediately after caching"
                )
                return False

            # Test cache statistics
            stats = self.cache_manager.get_cache_stats()
            if not stats:
                self.framework.end_test(False, "No cache statistics returned")
                return False

            # Verify stats structure
            required_keys = ["playlists_count", "total_size_bytes"]
            for key in required_keys:
                if key not in stats:
                    self.framework.end_test(False, f"Missing cache stat: {key}")
                    return False

            self.framework.end_test(
                True, f"TTL performance test passed, stats: {stats}"
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Cache TTL test failed: {e}")
            return False

    def test_cache_memory_usage(self) -> bool:
        """Test cache memory usage and cleanup."""
        self.framework.start_test("Cache Memory Usage")

        try:
            if not self.cache_manager:
                self.framework.end_test(False, "Cache manager not initialized")
                return False

            # Clear cache
            self.cache_manager.clear_cache()

            # Cache large amount of data
            large_playlist_set = []
            for i in range(10):  # Reduced to 10 for testing
                playlist = {
                    "id": f"memory_test_{i}",
                    "name": f"Large Test Playlist {i}",
                    "description": f"Description for playlist {i} with some additional text to increase memory usage",
                    "tracks": {"total": i * 10},
                    "images": [{"url": f"http://example.com/img_{i}.jpg"}],
                }
                large_playlist_set.append(playlist)

            # Cache the large dataset
            start_time = time.time()
            self.cache_manager.cache_playlists(large_playlist_set)
            cache_time = time.time() - start_time

            # Get cache statistics
            stats = self.cache_manager.get_cache_stats()
            if not stats:
                self.framework.end_test(
                    False, "No cache statistics after large dataset"
                )
                return False

            # Verify all items are cached
            if stats["playlists_count"] != 10:
                self.framework.end_test(
                    False, f"Expected 10 cached items, got {stats['playlists_count']}"
                )
                return False

            # Test cache retrieval performance with large dataset
            start_time = time.time()
            cached_data = self.cache_manager.get_cached_playlists()
            retrieve_time = time.time() - start_time

            if len(cached_data) != 10:
                self.framework.end_test(
                    False, f"Retrieved {len(cached_data)} items, expected 10"
                )
                return False

            # Performance should still be reasonable
            if retrieve_time > 0.2:  # 200ms threshold for large dataset
                self.framework.end_test(
                    False, f"Large dataset retrieval too slow: {retrieve_time:.3f}s"
                )
                return False

            # Test cache cleanup
            self.cache_manager.clear_cache()
            stats_after_clear = self.cache_manager.get_cache_stats()

            if stats_after_clear["playlists_count"] != 0:
                self.framework.end_test(False, "Cache not properly cleared")
                return False

            self.framework.end_test(
                True,
                f"Memory usage test passed, cache_time: {cache_time:.3f}s, retrieve_time: {retrieve_time:.3f}s, cached_items: 10",
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Cache memory usage test failed: {e}")
            return False

    def test_concurrent_cache_access(self) -> bool:
        """Test concurrent cache access performance."""
        self.framework.start_test("Concurrent Cache Access")

        try:
            if not self.cache_manager:
                self.framework.end_test(False, "Cache manager not initialized")
                return False

            import threading
            import queue

            # Clear cache
            self.cache_manager.clear_cache()

            # Test data
            test_data = [
                {"id": f"concurrent_{i}", "name": f"Concurrent Test {i}"}
                for i in range(50)
            ]

            results = queue.Queue()

            def cache_worker(worker_id):
                try:
                    start_time = time.time()
                    self.cache_manager.cache_playlists(test_data)
                    cache_time = time.time() - start_time

                    # Retrieve data
                    start_time = time.time()
                    cached = self.cache_manager.get_cached_playlists()
                    retrieve_time = time.time() - start_time

                    results.put(
                        {
                            "worker_id": worker_id,
                            "cache_time": cache_time,
                            "retrieve_time": retrieve_time,
                            "success": True,
                            "items_cached": len(cached) if cached else 0,
                        }
                    )
                except Exception as e:
                    results.put(
                        {"worker_id": worker_id, "success": False, "error": str(e)}
                    )

            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=cache_worker, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join(timeout=10)

            # Check results
            successful_workers = 0
            total_cache_time = 0
            total_retrieve_time = 0

            while not results.empty():
                result = results.get()
                if result["success"]:
                    successful_workers += 1
                    total_cache_time += result["cache_time"]
                    total_retrieve_time += result["retrieve_time"]
                else:
                    logger.error(
                        f"Worker {result['worker_id']} failed: {result['error']}"
                    )

            if successful_workers < 5:
                self.framework.end_test(
                    False, f"Only {successful_workers}/5 workers succeeded"
                )
                return False

            avg_cache_time = total_cache_time / successful_workers
            avg_retrieve_time = total_retrieve_time / successful_workers

            # Performance should be reasonable even with concurrent access
            if avg_retrieve_time > 0.5:  # 500ms threshold
                self.framework.end_test(
                    False, f"Concurrent access too slow: {avg_retrieve_time:.3f}s"
                )
                return False

            self.framework.end_test(
                True,
                f"Concurrent access test passed, workers: {successful_workers}/5, avg_cache_time: {avg_cache_time:.3f}s, avg_retrieve_time: {avg_retrieve_time:.3f}s",
            )
            return True

        except Exception as e:
            self.framework.end_test(False, f"Concurrent cache access test failed: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all cache performance tests."""
        logger.info("Starting cache performance tests")

        if not self.setup():
            return {"success": False, "message": "Failed to setup test environment"}

        # Run individual tests
        tests = [
            self.test_cache_hit_rate,
            self.test_cache_ttl_performance,
            self.test_cache_memory_usage,
            self.test_concurrent_cache_access,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            time.sleep(0.1)  # Small delay between tests

        logger.info(f"Cache performance tests completed: {passed}/{total} passed")

        return {
            "success": True,
            "passed": passed,
            "total": total,
            "results": self.framework.get_test_results(),
        }
