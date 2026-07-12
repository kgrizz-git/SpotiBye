"""Helpers for deciding when ReccoBeats analysis errors are retry-worthy."""

from __future__ import annotations

from typing import Any, Dict


def has_retriable_reccobeats_errors(analysis: Dict[str, Any]) -> bool:
    """Return True for hard ReccoBeats errors, excluding coverage notes.

    `reccobeats:coverage` means enrichment was partial, not that a full
    re-analysis should be replayed. Targeted missing-track retry lands with the
    per-track cache work.
    """
    errors = analysis.get("errors")
    if not isinstance(errors, list):
        return False
    return any(
        isinstance(error, dict)
        and isinstance(error.get("source"), str)
        and error["source"].startswith("reccobeats:")
        and error["source"] != "reccobeats:coverage"
        for error in errors
    )
