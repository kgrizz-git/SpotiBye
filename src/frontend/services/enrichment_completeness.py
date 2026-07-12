"""Offline enrichment completeness checks for cached analysis results."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .enrichment_errors import has_retriable_reccobeats_errors

REQUIRED_ANALYSIS_ENDPOINTS = ("audio-features", "track-metadata")


def is_offline_enrichment_complete(
    analysis: Dict[str, Any],
    *,
    expected_schema_version: str,
) -> bool:
    """True when all required endpoints resolved every unique playlist track ID."""
    if analysis.get("schema_version") != expected_schema_version:
        return False
    if has_retriable_reccobeats_errors(analysis):
        return False

    unique_count = analysis.get("unique_track_count")
    if not isinstance(unique_count, int) or unique_count <= 0:
        return False

    audio_resolved = analysis.get("audio_features_resolved_count")
    metadata_resolved = analysis.get("track_metadata_resolved_count")
    if not isinstance(audio_resolved, int) or not isinstance(metadata_resolved, int):
        return False

    return audio_resolved >= unique_count and metadata_resolved >= unique_count


def enrichment_incompleteness_endpoints(
    analysis: Dict[str, Any],
) -> Tuple[str, ...]:
    """Endpoint names still missing resolved coverage (hits + absents)."""
    unique_count = analysis.get("unique_track_count")
    if not isinstance(unique_count, int) or unique_count <= 0:
        return REQUIRED_ANALYSIS_ENDPOINTS

    incomplete: list[str] = []
    audio_resolved = analysis.get("audio_features_resolved_count")
    metadata_resolved = analysis.get("track_metadata_resolved_count")
    if not isinstance(audio_resolved, int) or audio_resolved < unique_count:
        incomplete.append("audio-features")
    if not isinstance(metadata_resolved, int) or metadata_resolved < unique_count:
        incomplete.append("track-metadata")
    return tuple(incomplete)


def miss_fill_ledger_key(
    *,
    playlist_id: str,
    composition_fingerprint: str,
    endpoint: str,
    audio_resolved_count: int,
    metadata_resolved_count: int,
    unique_track_count: int,
) -> str:
    """Session ledger key for one automatic coverage miss-fill attempt."""
    return (
        f"{playlist_id}|{composition_fingerprint}|{endpoint}|"
        f"af:{audio_resolved_count}|tm:{metadata_resolved_count}|u:{unique_track_count}"
    )


__all__ = [
    "REQUIRED_ANALYSIS_ENDPOINTS",
    "enrichment_incompleteness_endpoints",
    "is_offline_enrichment_complete",
    "miss_fill_ledger_key",
]
