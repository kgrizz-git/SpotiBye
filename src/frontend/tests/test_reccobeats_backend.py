"""Tests for ReccoBeatsBackendService (FE-CRIT-1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.frontend.services.backend_client import BackendAPIError
from src.frontend.services.reccobeats_backend import (
    ReccoBeatsBackendService,
    analysis_phase_label,
)
from src.frontend.utils.network_utils import NetworkError, ServerError

# ---------------------------------------------------------------------------
# Shared constants and builder helpers
# ---------------------------------------------------------------------------

COMPLETED_RESULTS: dict[str, Any] = {
    "schema_version": "1.1",
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
    with patch("src.frontend.services.reccobeats_backend.get_cache_manager") as get_cm:
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
    backend_client.get_analysis_status.side_effect = list(
        STALE_THEN_COMPLETE_SIDE_EFFECT
    )

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


class TestStaleResultsRecovery:
    """Poll-loop recovery when the backend reports completed-but-stale results.

    The backend's GET /results purges both KV keys and returns
    ANALYSIS_RESULTS_NOT_FOUND when cached results predate the current
    schema_version, so a "completed" status followed by that error code
    means the analysis needs to be re-run, not treated as a hard failure.
    """

    def _service(self, backend_client: MagicMock) -> ReccoBeatsBackendService:
        return ReccoBeatsBackendService(backend_client=backend_client)

    def test_transient_not_found_recovers_without_reposting(
        self, patched_cache_manager: MagicMock, analysis_task: MagicMock
    ) -> None:
        """A 404 right after completed is usually KV lag, not staleness."""
        backend_client = make_backend_client()
        fresh_results = {"schema_version": "1.1", "status": "completed"}
        backend_client.get_analysis_results.side_effect = [
            BackendAPIError(
                "Analysis results not found",
                status_code=404,
                error_code="ANALYSIS_RESULTS_NOT_FOUND",
            ),
            fresh_results,
        ]

        service = self._service(backend_client)
        with patch(
            "src.frontend.services.reccobeats_backend.time.sleep"
        ) as sleep_mock:
            result = service.analyze_playlist(
                "playlist-1", analysis_task=analysis_task
            )

        assert result == fresh_results
        assert backend_client.analyze_playlist.call_count == 1
        assert backend_client.get_analysis_results.call_count == 2
        sleep_mock.assert_called_once()
        patched_cache_manager.clear_file.assert_not_called()
        analysis_task.update_progress.assert_any_call(100, "Waiting for results...")

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
            "schema_version": "1.1",
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
            "schema_version": "1.1",
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
        backend_client.analyze_playlist.assert_called_once_with(
            "playlist-1", refresh=False
        )
        backend_client.get_analysis_results.assert_called_once()

    def test_force_reanalyze_uses_force_enrichment_without_delete(
        self, patched_cache_manager: MagicMock
    ) -> None:
        backend_client = make_backend_client()
        backend_client.analyze_playlist.return_value = {"job_id": "job-new"}

        service = self._service(backend_client)
        result = service.force_reanalyze_playlist("playlist-1")

        assert result == COMPLETED_RESULTS
        backend_client.delete_analysis.assert_not_called()
        patched_cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
        backend_client.analyze_playlist.assert_called_once_with(
            "playlist-1", force_enrichment=True
        )

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
        analysis_task.update_progress.assert_any_call(0, "Starting analysis... 0%")
        analysis_task.update_progress.assert_any_call(
            20, "Fetching Spotify tracks & artists... 20%"
        )
        analysis_task.update_progress.assert_any_call(
            65, "Enriching audio features (ReccoBeats)... 65%"
        )
        analysis_task.update_progress.assert_called_with(100, "Analysis complete")
        analysis_task.update_synthetic_progress.assert_not_called()

    def test_uses_synthetic_progress_after_status_progress_stays_stale(
        self, analysis_task: MagicMock
    ) -> None:
        result, _ = _run_stale_progress_scenario(analysis_task)

        assert result["status"] == "completed"
        analysis_task.update_synthetic_progress.assert_any_call(
            5.0, "Starting analysis..."
        )
        synthetic_elapsed_values = [
            c.args[0] for c in analysis_task.update_synthetic_progress.call_args_list
        ]
        assert synthetic_elapsed_values
        assert min(synthetic_elapsed_values) >= 5.0
        analysis_task.update_progress.assert_called_with(100, "Analysis complete")

    def test_logs_synthetic_progress_after_status_progress_stays_stale(
        self, analysis_task: MagicMock
    ) -> None:
        _, logger_mock = _run_stale_progress_scenario(analysis_task)

        debug_messages = [c.args[0] for c in logger_mock.debug.call_args_list if c.args]
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
        # Persistent 404s: every fetch attempt misses (e.g. a poisoned KV
        # negative cache), so each completed poll exhausts the retry budget
        # (14 attempts) before the repost decision.
        backend_client.get_analysis_results.side_effect = [stale_error] * 28

        service = self._service(backend_client)
        # `analyze_playlist` is wrapped in `@handle_network_errors`, which
        # converts a non-5xx/429/0 `BackendAPIError` into a generic
        # `NetworkError` by the time it reaches the caller.
        with (
            patch("src.frontend.services.reccobeats_backend.time.sleep"),
            pytest.raises(NetworkError),
        ):
            service.analyze_playlist("playlist-1")

        # First persistent 404 triggers exactly one re-post; the second
        # persistent 404 (from the re-posted job) is not retried again.
        assert backend_client.analyze_playlist.call_count == 2
        assert backend_client.get_analysis_results.call_count == 28

    def test_cancelled_retry_wait_returns_empty_without_reposting(
        self, patched_cache_manager: MagicMock, analysis_task: MagicMock
    ) -> None:
        backend_client = make_backend_client()
        backend_client.get_analysis_results.side_effect = BackendAPIError(
            "Analysis results not found",
            status_code=404,
            error_code="ANALYSIS_RESULTS_NOT_FOUND",
        )
        # Cancellation is checked in analyze_playlist, at the top of the
        # poll loop, before the fetch, and once more per retry.
        analysis_task.is_cancelled.side_effect = [False, False, False, True]

        service = self._service(backend_client)
        with patch("src.frontend.services.reccobeats_backend.time.sleep"):
            result = service.analyze_playlist("playlist-1", analysis_task=analysis_task)

        assert result == {}
        assert backend_client.analyze_playlist.call_count == 1
        assert backend_client.get_analysis_results.call_count == 1

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
        # Non-404 errors skip the retry loop entirely.
        assert backend_client.get_analysis_results.call_count == 1

    def test_retry_sleep_is_bounded_by_remaining_wait_budget(
        self, patched_cache_manager: MagicMock
    ) -> None:
        backend_client = make_backend_client()
        backend_client.get_analysis_results.side_effect = BackendAPIError(
            "Analysis results not found",
            status_code=404,
            error_code="ANALYSIS_RESULTS_NOT_FOUND",
        )

        # NOTE: time.time is patched on the global time module, which the
        # logging package also calls when emitting records. Script by call
        # count (not a fixed list) so captured log records cannot exhaust it.
        calls = []

        def fake_time() -> float:
            calls.append(1)
            return 299.5 if len(calls) == 1 else 300.5

        service = self._service(backend_client)
        with (
            patch(
                "src.frontend.services.reccobeats_backend.time.time",
                side_effect=fake_time,
            ),
            patch("src.frontend.services.reccobeats_backend.time.sleep") as sleep_mock,
        ):
            result = service._fetch_analysis_results_with_retry(
                "playlist-1", None, 300, 0.0
            )

        assert result is None
        assert backend_client.get_analysis_results.call_count == 2
        sleep_mock.assert_called_once_with(0.5)


class TestAnalysisPhaseLabel:
    """Progress bands mirror the backend's emission points (see helper docstring)."""

    def test_phase_boundaries(self) -> None:
        assert analysis_phase_label(0) == "Starting analysis"
        assert analysis_phase_label(10) == "Starting analysis"
        assert analysis_phase_label(20) == "Fetching Spotify tracks & artists"
        assert analysis_phase_label(64) == "Fetching Spotify tracks & artists"
        assert analysis_phase_label(65) == "Enriching audio features (ReccoBeats)"
        assert analysis_phase_label(85) == "Enriching audio features (ReccoBeats)"
        assert analysis_phase_label(86) == "Finalizing insights"
        assert analysis_phase_label(100) == "Finalizing insights"


class TestRefreshMode:
    def _service(self, backend_client: MagicMock) -> ReccoBeatsBackendService:
        return ReccoBeatsBackendService(backend_client=backend_client)

    def test_miss_fill_posts_refresh_without_force(
        self, patched_cache_manager: MagicMock
    ) -> None:
        backend_client = make_backend_client()

        service = self._service(backend_client)
        result = service.run_enrichment_miss_fill("playlist-1")

        assert result == COMPLETED_RESULTS
        backend_client.analyze_playlist.assert_called_once_with(
            "playlist-1", refresh=True
        )
        patched_cache_manager.clear_file.assert_called_once_with(
            "analysis_playlist-1.json"
        )
