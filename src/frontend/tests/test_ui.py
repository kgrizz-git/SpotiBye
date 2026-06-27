"""UI functionality testing for backend integration."""

from __future__ import annotations

import logging

import pytest

from ..services.backend_client import BackendClient
from ..services.reccobeats_backend import ReccoBeatsBackendService
from ..caching.backend_cache import BackendCacheManager

logger = logging.getLogger(__name__)


class TestUIFunctionality:
    backend_client: BackendClient | None = None
    recco_service: ReccoBeatsBackendService | None = None
    cache_manager: BackendCacheManager | None = None

    @pytest.fixture(autouse=True)
    def setup_clients(self, mock_backend_server):
        backend_url = mock_backend_server.get_base_url()
        self.backend_client = BackendClient(backend_url)
        self.recco_service = ReccoBeatsBackendService(self.backend_client)
        self.cache_manager = BackendCacheManager(self.backend_client)

    def test_playlist_loading(self):
        playlists = self.backend_client.get_playlists()
        assert playlists, "No playlists returned"
        assert len(playlists) > 0, "Empty playlists list"
        first_playlist = playlists[0]
        for field in ["id", "name", "tracks"]:
            assert field in first_playlist, f"Missing required field: {field}"

    def test_playlist_details(self):
        playlists = self.backend_client.get_playlists()
        assert playlists, "No playlists available"
        playlist_id = playlists[0]["id"]
        details = self.backend_client.get_playlist_details(playlist_id)
        assert details, "No playlist details returned"
        assert details.get("id") == playlist_id, "Playlist ID mismatch"

    def test_track_loading(self):
        playlists = self.backend_client.get_playlists()
        assert playlists, "No playlists available"
        playlist_id = playlists[0]["id"]
        tracks = self.backend_client.get_playlist_tracks(playlist_id)
        assert tracks, "No tracks returned"
        if len(tracks) > 0:
            first_track = tracks[0]
            for field in ["id", "name", "artists"]:
                assert field in first_track, f"Missing track field: {field}"

    def test_analysis_functionality(self):
        playlists = self.backend_client.get_playlists()
        assert playlists, "No playlists available"
        playlist_id = playlists[0]["id"]
        analysis_results = self.recco_service.analyze_playlist(playlist_id)
        assert analysis_results, "No analysis results returned"
        assert "results" in analysis_results, "Missing analysis results key"

    def test_export_functionality(self):
        playlists = self.backend_client.get_playlists()
        assert playlists, "No playlists available"
        playlist_id = playlists[0]["id"]
        export_response = self.backend_client.generate_export(playlist_id, "xlsx")
        assert export_response, "No export response returned"
        assert export_response.get("export_id"), "No export ID in response"

    def test_caching_functionality(self):
        test_playlists = [{"id": "test_1", "name": "Test Playlist"}]
        self.cache_manager.cache_playlists(test_playlists)
        cached_playlists = self.cache_manager.get_cached_playlists()
        assert cached_playlists, "No cached playlists found"
        assert len(cached_playlists) > 0, "Empty cached playlists"
        assert self.cache_manager.is_playlists_cache_valid(), "Cache marked as invalid"

    def test_error_handling(self):
        with pytest.raises(Exception):
            self.backend_client.get_playlist_details("invalid_id_12345")
        with pytest.raises(Exception):
            self.backend_client.get_track_details("invalid_track_12345")
