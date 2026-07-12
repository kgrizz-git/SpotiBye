"""B2 analysis gate tests: offline completeness, miss-fill ledger, composition."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from src.frontend.screens.adapter_mixins.analysis import (
    EXPECTED_ANALYSIS_SCHEMA_VERSION,
    AnalysisMixin,
)
from src.frontend.services.enrichment_retry_ledger import reset_enrichment_retry_ledger


class _Harness(AnalysisMixin):
    def __init__(self) -> None:
        self.cache_manager = MagicMock()
        self.reccobeats_service = MagicMock()
        self.backend_client = MagicMock()
        self.network_monitor = MagicMock()
        self.error_callback = None

    def get_playlist_tracks(self, playlist_id: str, force_refresh: bool = False):
        return []


def _complete_analysis() -> dict[str, Any]:
    return {
        "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
        "status": "completed",
        "unique_track_count": 2,
        "audio_features_resolved_count": 2,
        "track_metadata_resolved_count": 2,
        "errors": [],
    }


def _incomplete_analysis() -> dict[str, Any]:
    return {
        "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
        "status": "completed",
        "unique_track_count": 2,
        "audio_features_resolved_count": 1,
        "track_metadata_resolved_count": 2,
        "errors": [],
    }


class TestAnalysisMixinB2Gates:
    def setup_method(self) -> None:
        reset_enrichment_retry_ledger()

    def test_offline_complete_returns_cache_without_backend_call(self) -> None:
        harness = _Harness()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = _complete_analysis()
        harness.network_monitor.is_connected.return_value = False

        result = harness.analyze_playlist("playlist-1")

        assert result == _complete_analysis()
        harness.reccobeats_service.analyze_playlist.assert_not_called()
        harness.reccobeats_service.run_enrichment_miss_fill.assert_not_called()

    def test_incomplete_triggers_miss_fill_once_per_session(self) -> None:
        harness = _Harness()
        incomplete = _incomplete_analysis()
        refreshed = {**incomplete, "audio_features_resolved_count": 2}
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = incomplete
        harness.reccobeats_service.run_enrichment_miss_fill.return_value = refreshed

        first = harness.analyze_playlist("playlist-1")
        second = harness.analyze_playlist("playlist-1")

        assert first == refreshed
        assert second == incomplete
        harness.reccobeats_service.run_enrichment_miss_fill.assert_called_once()

    def test_manual_force_reanalyze_bypasses_session_guard(self) -> None:
        harness = _Harness()
        incomplete = _incomplete_analysis()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = incomplete
        harness.analyze_playlist("playlist-1")
        harness.reccobeats_service.force_reanalyze_playlist.return_value = incomplete

        harness.force_reanalyze_playlist("playlist-1")

        harness.reccobeats_service.force_reanalyze_playlist.assert_called_once()

    def test_composition_change_invalidates_and_refreshes_tracks(self) -> None:
        harness = _Harness()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = _complete_analysis()
        harness.cache_manager.get_cached_tracks_entry.return_value = {
            "snapshot_id": "old-snap",
            "track_id_hash": "old-hash",
            "tracks": [],
            "unique_track_count": 2,
        }
        harness.network_monitor.is_connected.return_value = True
        harness.get_playlist_tracks = MagicMock(return_value=[])
        harness.get_playlist_details = MagicMock(return_value={"snapshot_id": "new-snap"})
        harness.backend_client.get_playlist_tracks.return_value = [
            {"track": {"id": "x"}},
            {"track": {"id": "y"}},
            {"track": {"id": "z"}},
        ]
        harness.reccobeats_service.analyze_playlist.return_value = _complete_analysis()

        with patch.object(
            AnalysisMixin,
            "_playlist_composition_changed",
            return_value=True,
        ):
            harness.analyze_playlist("playlist-1")

        harness.cache_manager.clear_file.assert_called_with("analysis_playlist-1.json")
        harness.get_playlist_tracks.assert_called_with("playlist-1", force_refresh=True)
        harness.reccobeats_service.analyze_playlist.assert_called_once()
