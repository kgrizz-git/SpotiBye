"""B3 adapter tests: refresh buttons and force_enrichment wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.frontend.screens.adapter_mixins.analysis import AnalysisMixin
from src.frontend.services.enrichment_retry_ledger import (
    get_enrichment_retry_ledger,
    reset_enrichment_retry_ledger,
)


class _Harness(AnalysisMixin):
    def __init__(self) -> None:
        self.backend_client = MagicMock()
        self.cache_manager = MagicMock()
        self.reccobeats_service = MagicMock()
        self.network_monitor = MagicMock()
        self.network_monitor.is_connected.return_value = True
        self.error_callback = None
        self.progress_callback = None


@pytest.fixture(autouse=True)
def _reset_ledger() -> None:
    reset_enrichment_retry_ledger()


class TestB3RefreshAdapter:
    def test_refresh_playlist_tracks_force_refreshes_and_reanalyzes(self) -> None:
        harness = _Harness()
        harness.get_playlist_tracks = MagicMock(return_value=[{"track": {"id": "t1"}}])
        harness.cache_manager.is_tracks_cache_valid.return_value = False
        harness.reccobeats_service.analyze_playlist.return_value = {
            "status": "completed"
        }

        result = harness.refresh_playlist_tracks("playlist-1")

        harness.get_playlist_tracks.assert_called_once_with(
            "playlist-1", force_refresh=True
        )
        harness.backend_client.delete_export.assert_called_once_with("playlist-1")
        harness.cache_manager.clear_file.assert_called_once_with("analysis_playlist-1.json")
        # Refresh bypasses the completed short-circuit so new track IDs are
        # delta-enriched (see backend `refresh` mode).
        harness.reccobeats_service.analyze_playlist.assert_called_once_with(
            "playlist-1", refresh=True
        )
        assert result == {"status": "completed"}

    def test_force_reanalyze_resets_session_ledger(self) -> None:
        harness = _Harness()
        ledger = get_enrichment_retry_ledger()
        ledger.record_attempt("test-key")
        harness.reccobeats_service.force_reanalyze_playlist.return_value = {
            "status": "completed"
        }

        harness.force_reanalyze_playlist("playlist-1")

        assert not ledger.has_attempted("test-key")
        harness.reccobeats_service.force_reanalyze_playlist.assert_called_once_with(
            "playlist-1"
        )
