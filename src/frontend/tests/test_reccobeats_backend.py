"""Tests for ReccoBeatsBackendService (FE-CRIT-1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.frontend.services.backend_client import BackendAPIError
from src.frontend.services.reccobeats_backend import ReccoBeatsBackendService
from src.frontend.utils.network_utils import NetworkError, ServerError


class TestGetMultipleTrackAudioFeaturesSafe:
    """Verify the hardcoded `cached_track_1`/`cached_track_2` stub is gone."""

    def _service(self) -> ReccoBeatsBackendService:
        return ReccoBeatsBackendService()

    def test_raises_not_implemented_for_real_track_ids(self) -> None:
        with pytest.raises(NotImplementedError):
            self._service().get_multiple_track_audio_features_safe(
                ["real_track_abc123"]
            )

    def test_raises_not_implemented_for_legacy_cached_track_id(self) -> None:
        # The previous implementation returned fabricated
        # `{"danceability": 0.8, "energy": 0.9}` for this ID. Verify the
        # behavior is gone.
        with pytest.raises(NotImplementedError):
            self._service().get_multiple_track_audio_features_safe(["cached_track_1"])

    def test_raises_not_implemented_for_legacy_cached_track_id_2(self) -> None:
        with pytest.raises(NotImplementedError):
            self._service().get_multiple_track_audio_features_safe(["cached_track_2"])

    def test_does_not_return_fabricated_audio_features(self) -> None:
        with pytest.raises(NotImplementedError):
            self._service().get_multiple_track_audio_features_safe(["any_track_id"])

    def test_returns_empty_dict_for_cancelled_analysis(self) -> None:
        class _CancelledTask:
            def is_cancelled(self) -> bool:
                return True

        # Cancellation is checked before the NotImplementedError, so a
        # cancelled task returns an empty dict (early return) without
        # raising.
        result = self._service().get_multiple_track_audio_features_safe(
            ["track_a", "track_b"],
            analysis_task=_CancelledTask(),
        )
        assert result == {}

    def test_wrapper_propagates_not_implemented(self) -> None:
        # The legacy wrapper delegates to the safe variant and must
        # propagate the same error.
        with pytest.raises(NotImplementedError):
            self._service().get_multiple_track_audio_features(["track_x"])


class TestStaleResultsRecovery:
    """Poll-loop recovery when the backend reports completed-but-stale results.

    The backend's GET /results purges both KV keys and returns
    ANALYSIS_RESULTS_NOT_FOUND when cached results predate the current
    schema_version, so a "completed" status followed by that error code
    means the analysis needs to be re-run, not treated as a hard failure.
    """

    def _service(self, backend_client: MagicMock) -> ReccoBeatsBackendService:
        return ReccoBeatsBackendService(backend_client=backend_client)

    def test_reposts_once_and_returns_fresh_results_on_stale_completion(self) -> None:
        backend_client = MagicMock()
        backend_client.analyze_playlist.side_effect = [
            {"job_id": "job-old"},
            {"job_id": "job-new"},
        ]
        backend_client.get_analysis_status.return_value = {
            "status": "completed",
            "progress": 100,
        }
        fresh_results = {"schema_version": "1.0", "status": "completed"}
        backend_client.get_analysis_results.side_effect = [
            BackendAPIError(
                "Analysis results not found",
                status_code=404,
                error_code="ANALYSIS_RESULTS_NOT_FOUND",
            ),
            fresh_results,
        ]

        with patch(
            "src.frontend.services.reccobeats_backend.get_cache_manager"
        ) as get_cm:
            cache_manager = MagicMock()
            get_cm.return_value = cache_manager

            service = self._service(backend_client)
            result = service.analyze_playlist("playlist-1")

        assert result == fresh_results
        cache_manager.clear_file.assert_called_once_with("analysis_playlist-1.json")
        assert backend_client.analyze_playlist.call_count == 2
        assert backend_client.get_analysis_results.call_count == 2

    def test_does_not_repost_more_than_once_per_analyze_call(self) -> None:
        backend_client = MagicMock()
        backend_client.analyze_playlist.side_effect = [
            {"job_id": "job-old"},
            {"job_id": "job-new"},
        ]
        backend_client.get_analysis_status.return_value = {
            "status": "completed",
            "progress": 100,
        }
        stale_error = BackendAPIError(
            "Analysis results not found",
            status_code=404,
            error_code="ANALYSIS_RESULTS_NOT_FOUND",
        )
        backend_client.get_analysis_results.side_effect = [stale_error, stale_error]

        with patch(
            "src.frontend.services.reccobeats_backend.get_cache_manager"
        ) as get_cm:
            get_cm.return_value = MagicMock()

            service = self._service(backend_client)
            # `analyze_playlist` is wrapped in `@handle_network_errors`, which
            # converts a non-5xx/429/0 `BackendAPIError` into a generic
            # `NetworkError` by the time it reaches the caller.
            with pytest.raises(NetworkError):
                service.analyze_playlist("playlist-1")

        # First stale result triggers exactly one re-post; the second stale
        # result (from the re-posted job) is not retried again.
        assert backend_client.analyze_playlist.call_count == 2
        assert backend_client.get_analysis_results.call_count == 2

    def test_non_stale_error_propagates_without_reposting(self) -> None:
        backend_client = MagicMock()
        backend_client.analyze_playlist.return_value = {"job_id": "job-1"}
        backend_client.get_analysis_status.return_value = {
            "status": "completed",
            "progress": 100,
        }
        backend_client.get_analysis_results.side_effect = BackendAPIError(
            "Internal error", status_code=500, error_code="ANALYSIS_RESULTS_FAILED"
        )

        service = self._service(backend_client)
        # `handle_network_errors` converts a 5xx `BackendAPIError` into `ServerError`.
        with pytest.raises(ServerError):
            service.analyze_playlist("playlist-1")

        assert backend_client.analyze_playlist.call_count == 1
