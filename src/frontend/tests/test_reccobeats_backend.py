"""Tests for ReccoBeatsBackendService (FE-CRIT-1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from src.frontend.services.backend_client import BackendAPIError
from src.frontend.services.reccobeats_backend import ReccoBeatsBackendService
from src.frontend.utils.network_utils import NetworkError, ServerError

# ---------------------------------------------------------------------------
# Shared constants and builder helpers
# ---------------------------------------------------------------------------

COMPLETED_RESULTS: dict[str, Any] = {
    "schema_version": "1.0",
    "status": "completed",
    "errors": [],
}


def make_backend_client(**overrides) -> MagicMock:
    """Return a backend client mock whose default status is completed/100%."""
    client = MagicMock()
    client.analyze_playlist.return_value = {"job_id": "job-1"}
    client.get_analysis_status.return_value = {"status": "completed", "progress": 100}
    client.get_analysis_results.return_value = COMPLETED_RESULTS
    for attr, value in overrides.items():
        getattr(client, attr).return_value = value
    return client


@pytest.fixture
def analysis_task() -> MagicMock:
    task = MagicMock()
    task.is_cancelled.return_value = False
    return task


@pytest.fixture
def patched_cache_manager():
    with patch(
        "src.frontend.services.reccobeats_backend.get_cache_manager"
    ) as get_cm:
        cache_manager = MagicMock()
        get_cm.return_value = cache_manager
        yield cache_manager


# ---------------------------------------------------------------------------
# Shared helper for the synthetic-progress scenario
# ---------------------------------------------------------------------------

STALE_THEN_COMPLETE_SIDE_EFFECT = [
    {"status": "queued", "progress": 0},
    {"status": "queued", "progress": 0},
    {"status": "queued", "progress": 0},
    {"status": "queued", "progress": 0},
    {"status": "completed", "progress": 100},
]


def _run_stale_progress_scenario(analysis_task: MagicMock):
    """Arrange and act the stale-progress scenario; return (result, logger_mock)."""
    backend_client = make_backend_client()
    backend_client.get_analysis_status.side_effect = list(STALE_THEN_COMPLETE_SIDE_EFFECT)

    current_time = [0.0]

    with (
        patch(
            "src.frontend.services.reccobeats_backend.time.time",
            side_effect=lambda: current_time[0],
        ),
        patch(
            "src.frontend.services.reccobeats_backend.time.sleep",
            side_effect=lambda s: current_time.__setitem__(0, current_time[0] + s),
        ),
        patch("src.frontend.services.reccobeats_backend.logger") as logger_mock,
    ):
        service = ReccoBeatsBackendService(backend_client=backend_client)
        result = service.analyze_playlist("playlist-1", analysis_task=analysis_task)

    return result, logger_mock


# ---------------------------------------------------------------------------


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

    def test_reposts_once_and_returns_fresh_results_on_stale_completion(
        self, patched_cache_manager: MagicMock
    ) -> None:
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

        service = self._service(backend_client)
        result = service.analyze_playlist("playlist-1")

        assert result == fresh_results
        patched_cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
        assert backend_client.analyze_playlist.call_count == 2
        assert backend_client.get_analysis_results.call_count == 2

    def test_deletes_and_reposts_once_when_completed_results_have_reccobeats_errors(
        self, patched_cache_manager: MagicMock
    ) -> None:
        backend_client = MagicMock()
        backend_client.analyze_playlist.side_effect = [
            {"job_id": "job-old"},
            {"job_id": "job-new"},
        ]
        backend_client.get_analysis_status.return_value = {
            "status": "completed",
            "progress": 100,
        }
        stale_results = {
            "schema_version": "1.0",
            "status": "completed",
            "errors": [
                {
                    "source": "reccobeats:audio-features",
                    "message": "HTTP 400",
                }
            ],
        }
        fresh_results = COMPLETED_RESULTS
        backend_client.get_analysis_results.side_effect = [stale_results, fresh_results]

        service = self._service(backend_client)
        result = service.analyze_playlist("playlist-1")

        assert result == fresh_results
        backend_client.delete_analysis.assert_called_once_with("playlist-1")
        patched_cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
        assert backend_client.analyze_playlist.call_count == 2
        assert backend_client.get_analysis_results.call_count == 2

    def test_does_not_repost_when_completed_results_only_have_coverage_warning(
        self, patched_cache_manager: MagicMock
    ) -> None:
        backend_client = make_backend_client()
        backend_client.get_analysis_results.return_value = {
            "schema_version": "1.0",
            "status": "completed",
            "errors": [
                {
                    "source": "reccobeats:coverage",
                    "message": "Audio features available for 1 of 2 tracks.",
                }
            ],
        }

        service = self._service(backend_client)
        result = service.analyze_playlist("playlist-1")

        assert result["errors"][0]["source"] == "reccobeats:coverage"
        backend_client.delete_analysis.assert_not_called()
        patched_cache_manager.clear_file.assert_not_called()
        backend_client.analyze_playlist.assert_called_once_with("playlist-1")
        backend_client.get_analysis_results.assert_called_once()

    def test_force_reanalyze_deletes_backend_and_local_cache_before_analyzing(
        self, patched_cache_manager: MagicMock
    ) -> None:
        backend_client = make_backend_client()
        backend_client.analyze_playlist.return_value = {"job_id": "job-new"}

        service = self._service(backend_client)
        result = service.force_reanalyze_playlist("playlist-1")

        assert result == COMPLETED_RESULTS
        backend_client.delete_analysis.assert_called_once_with("playlist-1")
        patched_cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
        backend_client.analyze_playlist.assert_called_once_with("playlist-1")

    def test_updates_analysis_task_to_complete_before_returning_results(
        self, analysis_task: MagicMock
    ) -> None:
        backend_client = make_backend_client()

        service = self._service(backend_client)
        result = service.analyze_playlist("playlist-1", analysis_task=analysis_task)

        assert result == COMPLETED_RESULTS
        analysis_task.update_progress.assert_called_with(100, "Analysis complete")

    def test_real_advancing_status_updates_analysis_task_without_synthetic_progress(
        self, analysis_task: MagicMock
    ) -> None:
        backend_client = make_backend_client()
        backend_client.get_analysis_status.side_effect = [
            {"status": "queued", "progress": 0},
            {"status": "processing", "progress": 20},
            {"status": "processing", "progress": 65},
            {"status": "completed", "progress": 100},
        ]

        with patch("src.frontend.services.reccobeats_backend.time.sleep"):
            service = self._service(backend_client)
            result = service.analyze_playlist("playlist-1", analysis_task=analysis_task)

        assert result["status"] == "completed"
        analysis_task.update_progress.assert_any_call(0, "Analyzing playlist... 0%")
        analysis_task.update_progress.assert_any_call(20, "Analyzing playlist... 20%")
        analysis_task.update_progress.assert_any_call(65, "Analyzing playlist... 65%")
        analysis_task.update_progress.assert_called_with(100, "Analysis complete")
        analysis_task.update_synthetic_progress.assert_not_called()

    def test_uses_synthetic_progress_after_status_progress_stays_stale(
        self, analysis_task: MagicMock
    ) -> None:
        result, _ = _run_stale_progress_scenario(analysis_task)

        assert result["status"] == "completed"
        analysis_task.update_synthetic_progress.assert_any_call(
            5.0, "Analyzing playlist..."
        )
        synthetic_elapsed_values = [
            c.args[0]
            for c in analysis_task.update_synthetic_progress.call_args_list
        ]
        assert synthetic_elapsed_values
        assert min(synthetic_elapsed_values) >= 5.0
        analysis_task.update_progress.assert_called_with(100, "Analysis complete")

    def test_logs_synthetic_progress_after_status_progress_stays_stale(
        self, analysis_task: MagicMock
    ) -> None:
        _, logger_mock = _run_stale_progress_scenario(analysis_task)

        debug_messages = [
            c.args[0] for c in logger_mock.debug.call_args_list if c.args
        ]
        assert any("Synthetic analysis progress" in msg for msg in debug_messages)

    def test_does_not_repost_more_than_once_per_analyze_call(
        self, patched_cache_manager: MagicMock
    ) -> None:
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
        backend_client = make_backend_client()
        backend_client.get_analysis_results.side_effect = BackendAPIError(
            "Internal error", status_code=500, error_code="ANALYSIS_RESULTS_FAILED"
        )

        service = self._service(backend_client)
        # `handle_network_errors` converts a 5xx `BackendAPIError` into `ServerError`.
        with pytest.raises(ServerError):
            service.analyze_playlist("playlist-1")

        assert backend_client.analyze_playlist.call_count == 1
