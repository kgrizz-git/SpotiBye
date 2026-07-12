"""Tests for enrichment status formatting (B3.1)."""

from __future__ import annotations

from typing import Any

from src.frontend.screens.adapter_mixins.analysis import (
    EXPECTED_ANALYSIS_SCHEMA_VERSION,
)
from src.frontend.services.enrichment_status import (
    format_enrichment_status_line,
    format_last_refreshed_line,
)


def _analysis(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": EXPECTED_ANALYSIS_SCHEMA_VERSION,
        "unique_track_count": 3,
        "audio_features_resolved_count": 3,
        "track_metadata_resolved_count": 3,
        "enrichment_resolved_track_count": 3,
        "completed_at": "2026-07-12T18:30:00.000Z",
        "audio_features": {"track_count": 3},
        "errors": [],
    }
    base.update(overrides)
    return base


class TestEnrichmentStatusFormatting:
    def test_complete_shows_n_over_m(self) -> None:
        line = format_enrichment_status_line(
            _analysis(),
            expected_schema_version=EXPECTED_ANALYSIS_SCHEMA_VERSION,
        )
        assert line == "Enrichment: 3/3 tracks"

    def test_running_incomplete_shows_progress_copy(self) -> None:
        line = format_enrichment_status_line(
            _analysis(
                audio_features_resolved_count=1,
                track_metadata_resolved_count=2,
                enrichment_resolved_track_count=1,
            ),
            expected_schema_version=EXPECTED_ANALYSIS_SCHEMA_VERSION,
            is_running=True,
        )
        assert line == "Enriching tracks… (1/3)"

    def test_complete_with_omissions_is_informational(self) -> None:
        line = format_enrichment_status_line(
            _analysis(audio_features={"track_count": 2}),
            expected_schema_version=EXPECTED_ANALYSIS_SCHEMA_VERSION,
        )
        assert "complete" in line
        assert "omitted" in line

    def test_last_refreshed_formats_timestamp(self) -> None:
        line = format_last_refreshed_line(_analysis())
        assert line.startswith("Last refreshed:")
