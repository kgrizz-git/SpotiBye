import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from ..caching.backend_cache import BackendCacheManager


class TestResumableExportCache(unittest.TestCase):
    temp_dir: Any = None
    home_patch: Any = None
    cache_manager: BackendCacheManager | None = None

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_patch = patch("os.path.expanduser", return_value=self.temp_dir.name)
        self.home_patch.start()

        self.cache_manager = BackendCacheManager()

    def tearDown(self):
        self.home_patch.stop()
        self.temp_dir.cleanup()

    def test_cache_and_clear_active_export_job(self):
        payload = {
            "job_id": "job-123",
            "playlist_ids": ["p1", "p2"],
            "format": "xlsx",
            "current_cursor": '{"next_playlist_index":1,"next_track_offset":0,"phase":"collect"}',
            "current_resume_token": "token-abc",
            "status": "running",
            "continuation_required": True,
            "output_path": "/tmp/out.xlsx",
        }

        self.cache_manager.cache_active_export_job(payload, ttl=120)

        loaded = self.cache_manager.get_active_export_job()
        self.assertIsNotNone(loaded)
        loaded_dict = loaded or {}
        self.assertEqual(loaded_dict.get("job_id"), "job-123")
        self.assertEqual(loaded_dict.get("playlist_ids"), ["p1", "p2"])
        self.assertEqual(loaded_dict.get("output_path"), "/tmp/out.xlsx")

        # The cached file lives at the env-hashed path produced by
        # `_cache_file_path` (FE-HIGH-3). Verify the file is present at
        # that exact path before clearing.
        cached_path = self.cache_manager._cache_file_path(
            "active_export_job.json"
        )
        self.assertTrue(cached_path.exists())

        self.cache_manager.clear_active_export_job()
        self.assertIsNone(self.cache_manager.get_active_export_job())
        self.assertFalse(cached_path.exists())

    def test_cache_file_path_helpers_share_prefix(self):
        # FE-HIGH-3: every read/write/clear helper must produce the same
        # path for a given filename. This guards against drift between
        # clear_active_export_job and the save/load helpers.
        path_via_helper = self.cache_manager._cache_file_path("playlists.json")
        # Same path produced by manually composing the hash + filename.
        env_hash = self.cache_manager._hash_backend_url(
            self.cache_manager._get_backend_url_safe()
        )
        expected = self.cache_manager.cache_dir / f"{env_hash}_playlists.json"
        self.assertEqual(path_via_helper, expected)


if __name__ == "__main__":
    unittest.main()
