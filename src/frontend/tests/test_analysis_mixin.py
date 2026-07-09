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
