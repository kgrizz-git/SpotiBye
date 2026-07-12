"""User-facing enrichment status copy for analysis popups."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .enrichment_completeness import is_offline_enrichment_complete


def _resolved_track_count(analysis: Dict[str, Any]) -> Optional[int]:
    resolved = analysis.get("enrichment_resolved_track_count")
    if isinstance(resolved, int):
        return resolved
    audio = analysis.get("audio_features_resolved_count")
    metadata = analysis.get("track_metadata_resolved_count")
    if isinstance(audio, int) and isinstance(metadata, int):
        return min(audio, metadata)
    return None


def format_enrichment_status_line(
    analysis: Dict[str, Any],
    *,
    expected_schema_version: str,
    is_running: bool = False,
) -> str:
    """
    Build the informational "Enrichment: N/M tracks" status line.

    Uses endpoint-specific resolved counts (hits + verified absents), not
    audio_features.track_count alone.
    """
    unique = analysis.get("unique_track_count")
    if not isinstance(unique, int) or unique <= 0:
        return ""

    resolved = _resolved_track_count(analysis)
    if resolved is None:
        return ""

    if is_running and resolved < unique:
        return f"Enriching tracks… ({resolved}/{unique})"

    if is_offline_enrichment_complete(
        analysis, expected_schema_version=expected_schema_version
    ):
        audio_hits = (analysis.get("audio_features") or {}).get("track_count")
        if isinstance(audio_hits, int) and audio_hits < unique:
            return (
                f"Enrichment: {unique}/{unique} tracks "
                "(complete; some tracks omitted by ReccoBeats)"
            )
        return f"Enrichment: {unique}/{unique} tracks"

    if resolved < unique:
        return f"Enrichment: {resolved}/{unique} tracks (fetching missing data…)"

    return f"Enrichment: {resolved}/{unique} tracks"


def format_last_refreshed_line(analysis: Dict[str, Any]) -> str:
    """Human-readable last-refreshed timestamp from analysis metadata."""
    raw = analysis.get("completed_at") or analysis.get("computed_at")
    if not isinstance(raw, str) or not raw.strip():
        return ""

    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return f"Last refreshed: {dt.strftime('%Y-%m-%d %H:%M UTC')}"
    except ValueError:
        return f"Last refreshed: {raw}"


__all__ = ["format_enrichment_status_line", "format_last_refreshed_line"]
