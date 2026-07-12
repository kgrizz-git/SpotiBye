"""Tests for AnalysisMixin's local-cache schema_version staleness check."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.frontend.screens.adapter_mixins.analysis import (
    EXPECTED_ANALYSIS_SCHEMA_VERSION,
    AnalysisMixin,
)


class _Harness(AnalysisMixin):
    def __init__(self) -> None:
        self.cache_manager = MagicMock()
        self.reccobeats_service = MagicMock()
        self.error_callback = None


class TestAnalyzePlaylistCacheStaleness:
    def test_returns_cached_analysis_when_schema_version_matches(self) -> None:
        harness = _Harness()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
        }

        result = harness.analyze_playlist("playlist-1")

        assert result == {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
        }
        harness.reccobeats_service.analyze_playlist.assert_not_called()
        harness.cache_manager.clear_file.assert_not_called()

    def test_forwards_analysis_task_to_normal_backend_analysis(self) -> None:
        harness = _Harness()
        analysis_task = MagicMock()
        harness.cache_manager.is_analysis_cache_valid.return_value = False
        fresh = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
        }
        harness.reccobeats_service.analyze_playlist.return_value = fresh

        result = harness.analyze_playlist("playlist-1", analysis_task=analysis_task)

        assert result == fresh
        harness.reccobeats_service.analyze_playlist.assert_called_once_with(
            "playlist-1", analysis_task
        )

    def test_forwards_analysis_task_to_forced_reanalysis(self) -> None:
        harness = _Harness()
        analysis_task = MagicMock()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
            "errors": [{"source": "reccobeats:track-metadata"}],
        }
        fresh = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
            "errors": [],
        }
        harness.reccobeats_service.force_reanalyze_playlist.return_value = fresh

        result = harness.analyze_playlist("playlist-1", analysis_task=analysis_task)

        assert result == fresh
        harness.reccobeats_service.force_reanalyze_playlist.assert_called_once_with(
            "playlist-1", analysis_task
        )

    def test_forces_reanalysis_when_cached_current_schema_has_reccobeats_errors(
        self,
    ) -> None:
        harness = _Harness()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
            "errors": [
                {
                    "source": "reccobeats:audio-features",
                    "message": "HTTP 400",
                }
            ],
        }
        fresh = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
            "errors": [],
        }
        harness.reccobeats_service.force_reanalyze_playlist.return_value = fresh

        result = harness.analyze_playlist("playlist-1")

        assert result == fresh
        harness.cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
        harness.reccobeats_service.force_reanalyze_playlist.assert_called_once_with(
            "playlist-1"
        )
        harness.reccobeats_service.analyze_playlist.assert_not_called()

    def test_returns_cached_analysis_when_only_reccobeats_coverage_warning(
        self,
    ) -> None:
        harness = _Harness()
        cached = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
            "errors": [
                {
                    "source": "reccobeats:coverage",
                    "message": "Audio features available for 1 of 2 tracks.",
                }
            ],
        }
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = cached

        result = harness.analyze_playlist("playlist-1")

        assert result == cached
        harness.cache_manager.clear_file.assert_not_called()
        harness.reccobeats_service.force_reanalyze_playlist.assert_not_called()
        harness.reccobeats_service.analyze_playlist.assert_not_called()

    def test_discards_cache_and_reanalyzes_when_schema_version_missing(self) -> None:
        harness = _Harness()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = {"status": "completed"}
        fresh = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
        }
        harness.reccobeats_service.analyze_playlist.return_value = fresh

        result = harness.analyze_playlist("playlist-1")

        assert result == fresh
        harness.cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
        harness.reccobeats_service.analyze_playlist.assert_called_once_with(
            "playlist-1"
        )

    def test_discards_cache_and_reanalyzes_when_schema_version_stale(self) -> None:
        harness = _Harness()
        harness.cache_manager.is_analysis_cache_valid.return_value = True
        harness.cache_manager.get_cached_analysis.return_value = {
            "schema_version": "0.9",
            "status": "completed",
        }
        fresh = {
            "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
            "status": "completed",
        }
        harness.reccobeats_service.analyze_playlist.return_value = fresh

        result = harness.analyze_playlist("playlist-1")

        assert result == fresh
        harness.cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
