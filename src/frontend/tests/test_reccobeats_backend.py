"""Tests for ReccoBeatsBackendService (FE-CRIT-1)."""

from __future__ import annotations

import pytest

from src.frontend.services.reccobeats_backend import ReccoBeatsBackendService


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
