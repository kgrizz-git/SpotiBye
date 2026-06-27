"""Performance testing for backend integration."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

import pytest

from ..services.backend_client import BackendClient
from ..services.reccobeats_backend import ReccoBeatsBackendService

logger = logging.getLogger(__name__)


class TestPerformance:
    backend_client: BackendClient | None = None
    recco_service: ReccoBeatsBackendService | None = None

    @pytest.fixture(autouse=True)
    def setup_clients(self, mock_backend_server):
        backend_url = mock_backend_server.get_base_url()
        self.backend_client = BackendClient(backend_url)
        self.recco_service = ReccoBeatsBackendService(self.backend_client)

    def test_large_playlist_loading(self):
        playlists = self.backend_client.get_playlists()
        large_playlist = next(
            (p for p in playlists if p.get("tracks", {}).get("total", 0) > 1000), None
        )
        assert large_playlist, "No large playlist found in test data"
        playlist_id = large_playlist["id"]
        start_time = time.time()
        tracks = self.backend_client.get_playlist_tracks(playlist_id)
        load_time = time.time() - start_time
        assert tracks, "Failed to load large playlist tracks"
        assert len(tracks) > 1000, f"Playlist not large enough: {len(tracks)} tracks"
        assert load_time <= 10.0, f"Loading too slow: {load_time:.2f}s"

    def test_analysis_performance(self):
        playlists = self.backend_client.get_playlists()
        large_playlist = next(
            (p for p in playlists if p.get("tracks", {}).get("total", 0) > 1000), None
        )
        assert large_playlist, "No large playlist found in test data"
        playlist_id = large_playlist["id"]
        start_time = time.time()
        analysis_results = self.recco_service.analyze_playlist(playlist_id)
        analysis_time = time.time() - start_time
        assert analysis_results, "Analysis failed for large playlist"
        assert analysis_time <= 60.0, f"Analysis too slow: {analysis_time:.2f}s"

    def test_concurrent_requests(self):
        playlists = self.backend_client.get_playlists()
        target = len(playlists[:3])
        results: queue.Queue[dict[str, Any]] = queue.Queue()

        def load_playlist(playlist_id: str) -> None:
            try:
                tracks = self.backend_client.get_playlist_tracks(playlist_id)
                results.put({"success": True, "tracks": len(tracks)})
            except Exception as e:
                results.put({"success": False, "error": str(e)})

        threads = [
            threading.Thread(target=load_playlist, args=(p["id"],))
            for p in playlists[:3]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        success_count = 0
        while not results.empty():
            if results.get_nowait().get("success"):
                success_count += 1
        assert (
            success_count >= target
        ), f"Only {success_count}/{target} requests succeeded"

    def test_memory_usage(self):
        psutil = pytest.importorskip("psutil")
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024

        playlists = self.backend_client.get_playlists()
        large_playlist = next(
            (p for p in playlists if p.get("tracks", {}).get("total", 0) > 1000), None
        )
        assert large_playlist, "No large playlist found in test data"
        self.backend_client.get_playlist_tracks(large_playlist["id"])

        memory_increase = process.memory_info().rss / 1024 / 1024 - initial_memory
        assert (
            memory_increase <= 500
        ), f"Memory usage too high: {memory_increase:.1f}MB increase"
