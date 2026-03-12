import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.frontend.caching.backend_cache import BackendCacheManager


class TestResumableExportCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_patch = patch('os.path.expanduser', return_value=self.temp_dir.name)
        self.home_patch.start()

        self.cache_manager = BackendCacheManager()

    def tearDown(self):
        self.home_patch.stop()
        self.temp_dir.cleanup()

    def test_cache_and_clear_active_export_job(self):
        payload = {
            'job_id': 'job-123',
            'playlist_ids': ['p1', 'p2'],
            'format': 'xlsx',
            'current_cursor': '{"next_playlist_index":1,"next_track_offset":0,"phase":"collect"}',
            'current_resume_token': 'token-abc',
            'status': 'running',
            'continuation_required': True,
            'output_path': '/tmp/out.xlsx',
        }

        self.cache_manager.cache_active_export_job(payload, ttl=120)

        loaded = self.cache_manager.get_active_export_job()
        self.assertIsNotNone(loaded)
        loaded_dict = loaded or {}
        self.assertEqual(loaded_dict.get('job_id'), 'job-123')
        self.assertEqual(loaded_dict.get('playlist_ids'), ['p1', 'p2'])
        self.assertEqual(loaded_dict.get('output_path'), '/tmp/out.xlsx')

        self.cache_manager.clear_active_export_job()
        self.assertIsNone(self.cache_manager.get_active_export_job())

        cache_file = Path(self.temp_dir.name) / '.spotibye_cache' / 'active_export_job.json'
        self.assertFalse(cache_file.exists())


if __name__ == '__main__':
    unittest.main()
