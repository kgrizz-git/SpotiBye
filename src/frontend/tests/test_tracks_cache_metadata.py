"""Tests for tracks cache metadata (B2.2)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.frontend.caching.backend_cache import (
    DEFAULT_TRACKS_CACHE_TTL_SECONDS,
    BackendCacheManager,
)
from src.frontend.services.backend_client import BackendClient


class TestTracksCacheMetadata:
    def _manager(self, tmp_path: Path) -> BackendCacheManager:
        manager = BackendCacheManager(BackendClient("http://localhost:8787"))
        manager.cache_dir = tmp_path
        return manager

    def test_cache_tracks_stores_metadata_and_legacy_getter_returns_list(
        self, tmp_path: Path
    ) -> None:
        manager = self._manager(tmp_path)
        items = [{"track": {"id": "t1", "name": "One"}}]
        metadata = {
            "tracks": items,
            "snapshot_id": "snap-1",
            "track_id_hash": "hash-1",
            "unique_track_count": 1,
        }
        manager.cache_tracks("pl-1", items, metadata=metadata)

        entry = manager.get_cached_tracks_entry("pl-1")
        assert entry is not None
        assert entry["snapshot_id"] == "snap-1"
        assert entry["unique_track_count"] == 1
        assert manager.get_cached_tracks("pl-1") == items

    def test_default_tracks_ttl_is_24_hours(self) -> None:
        assert DEFAULT_TRACKS_CACHE_TTL_SECONDS == 86_400

    def test_legacy_list_payload_normalizes_on_read(self, tmp_path: Path) -> None:
        manager = self._manager(tmp_path)
        legacy_items = [{"track": {"id": "t2", "name": "Two"}}]
        cache_path = manager._cache_file_path("tracks_pl-2.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "data": legacy_items,
                    "timestamp": time.time(),
                    "ttl": DEFAULT_TRACKS_CACHE_TTL_SECONDS,
                },
                handle,
            )

        entry = manager.get_cached_tracks_entry("pl-2")
        assert entry is not None
        assert entry["tracks"] == legacy_items
        assert entry["unique_track_count"] == 1
