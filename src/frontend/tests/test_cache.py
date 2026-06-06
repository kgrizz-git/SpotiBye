"""Cache performance testing for backend integration."""

from __future__ import annotations

import logging
import queue
import threading
import time

import pytest

from ..caching.backend_cache import BackendCacheManager
from ..services.backend_client import BackendClient

logger = logging.getLogger(__name__)


class TestCachePerformance:
    @pytest.fixture(autouse=True)
    def setup_clients(self, mock_backend_server):
        backend_url = mock_backend_server.get_base_url()
        self.backend_client = BackendClient(backend_url)
        self.cache_manager = BackendCacheManager(self.backend_client)

    def test_cache_hit_rate(self):
        self.cache_manager.clear_cache()
        test_playlists = [
            {"id": "cache_test_1", "name": "Test Playlist 1"},
            {"id": "cache_test_2", "name": "Test Playlist 2"},
            {"id": "cache_test_3", "name": "Test Playlist 3"},
        ]
        self.cache_manager.cache_playlists(test_playlists)

        start_time = time.time()
        cached_playlists = self.cache_manager.get_cached_playlists()
        retrieve_time = time.time() - start_time

        assert cached_playlists, "No cached playlists found"
        assert (
            len(cached_playlists) == len(test_playlists)
        ), f"Cache size mismatch: expected {len(test_playlists)}, got {len(cached_playlists)}"
        assert retrieve_time <= 0.1, f"Cache retrieval too slow: {retrieve_time:.3f}s"
        assert self.cache_manager.is_playlists_cache_valid(), "Cache marked as invalid"

    def test_cache_ttl_performance(self):
        self.cache_manager.clear_cache()
        self.cache_manager.cache_playlists(
            [{"id": "ttl_test", "name": "TTL Test Playlist"}]
        )
        assert (
            self.cache_manager.is_playlists_cache_valid()
        ), "Cache should be valid immediately after caching"

        stats = self.cache_manager.get_cache_stats()
        assert stats, "No cache statistics returned"
        for key in ["playlists_count", "total_size_bytes"]:
            assert key in stats, f"Missing cache stat: {key}"

    def test_cache_memory_usage(self):
        self.cache_manager.clear_cache()
        large_playlist_set = [
            {
                "id": f"memory_test_{i}",
                "name": f"Large Test Playlist {i}",
                "description": f"Description for playlist {i} with some additional text",
                "tracks": {"total": i * 10},
                "images": [{"url": f"http://example.com/img_{i}.jpg"}],
            }
            for i in range(10)
        ]
        self.cache_manager.cache_playlists(large_playlist_set)

        stats = self.cache_manager.get_cache_stats()
        assert stats, "No cache statistics after large dataset"
        assert (
            stats["playlists_count"] == 10
        ), f"Expected 10 cached items, got {stats['playlists_count']}"

        start_time = time.time()
        cached_data = self.cache_manager.get_cached_playlists()
        retrieve_time = time.time() - start_time

        assert (
            len(cached_data) == 10
        ), f"Retrieved {len(cached_data)} items, expected 10"
        assert (
            retrieve_time <= 0.2
        ), f"Large dataset retrieval too slow: {retrieve_time:.3f}s"

        self.cache_manager.clear_cache()
        stats_after_clear = self.cache_manager.get_cache_stats()
        assert stats_after_clear["playlists_count"] == 0, "Cache not properly cleared"

    def test_concurrent_cache_access(self):
        self.cache_manager.clear_cache()
        test_data = [
            {"id": f"concurrent_{i}", "name": f"Concurrent Test {i}"} for i in range(50)
        ]
        results: queue.Queue = queue.Queue()

        def cache_worker(worker_id: int) -> None:
            try:
                self.cache_manager.cache_playlists(test_data)
                cached = self.cache_manager.get_cached_playlists()
                results.put(
                    {
                        "worker_id": worker_id,
                        "success": True,
                        "count": len(cached) if cached else 0,
                    }
                )
            except Exception as e:
                results.put({"worker_id": worker_id, "success": False, "error": str(e)})

        threads = [threading.Thread(target=cache_worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        successful = 0
        while not results.empty():
            r = results.get_nowait()
            if r["success"]:
                successful += 1
            else:
                logger.error(f"Worker {r['worker_id']} failed: {r.get('error')}")
        assert successful >= 5, f"Only {successful}/5 cache workers succeeded"
