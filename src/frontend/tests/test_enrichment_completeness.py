"""Tests for offline enrichment completeness helpers."""

from __future__ import annotations

from src.frontend.services.enrichment_completeness import (
    enrichment_incompleteness_endpoints,
    is_offline_enrichment_complete,
)


class TestEnrichmentCompleteness:
    def test_complete_when_both_endpoints_resolve_unique_set(self) -> None:
        analysis = {
            "schema_version": "1.1",
            "unique_track_count": 3,
            "audio_features_resolved_count": 3,
            "track_metadata_resolved_count": 3,
            "errors": [],
        }
        assert is_offline_enrichment_complete(analysis, expected_schema_version="1.1")

    def test_complete_with_duplicates_when_unique_set_resolved(self) -> None:
        analysis = {
            "schema_version": "1.1",
            "unique_track_count": 2,
            "audio_features_resolved_count": 2,
            "track_metadata_resolved_count": 2,
            "errors": [],
        }
        assert is_offline_enrichment_complete(analysis, expected_schema_version="1.1")

    def test_incomplete_when_metadata_unresolved(self) -> None:
        analysis = {
            "schema_version": "1.1",
            "unique_track_count": 2,
            "audio_features_resolved_count": 2,
            "track_metadata_resolved_count": 1,
            "errors": [],
        }
        assert not is_offline_enrichment_complete(analysis, expected_schema_version="1.1")
        assert enrichment_incompleteness_endpoints(analysis) == ("track-metadata",)

    def test_not_complete_on_hard_reccobeats_error(self) -> None:
        analysis = {
            "schema_version": "1.1",
            "unique_track_count": 1,
            "audio_features_resolved_count": 1,
            "track_metadata_resolved_count": 1,
            "errors": [{"source": "reccobeats:audio-features", "message": "HTTP 500"}],
        }
        assert not is_offline_enrichment_complete(analysis, expected_schema_version="1.1")

    def test_coverage_warning_does_not_block_offline_complete(self) -> None:
        analysis = {
            "schema_version": "1.1",
            "unique_track_count": 2,
            "audio_features_resolved_count": 2,
            "track_metadata_resolved_count": 2,
            "errors": [{"source": "reccobeats:coverage", "message": "partial"}],
        }
        assert is_offline_enrichment_complete(analysis, expected_schema_version="1.1")
