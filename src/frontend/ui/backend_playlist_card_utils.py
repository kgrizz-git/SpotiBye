"""Module-level utility helpers for BackendPlaylistCard — no kivy or project dependencies."""

from __future__ import annotations

_MOOD_BANDS: tuple[tuple[float, str], ...] = (
    (0.20, "Melancholic"),
    (0.40, "Somber"),
    (0.60, "Neutral"),
    (0.80, "Cheerful"),
)

_ERROR_SOURCE_LABELS: dict[str, str] = {
    "spotify:artists": "artist genres unavailable",
    "reccobeats:audio-features": "audio features unavailable",
    "reccobeats:track-metadata": "track metadata unavailable",
}


def _mood_label(valence: float) -> str:
    """Map a 0.0-1.0 valence score to a human-readable mood band.

    Upper bound exclusive except the last band ([0.80, 1.00]), which is
    inclusive since valence is normalized to a 0.0-1.0 range.
    """
    for upper_bound, label in _MOOD_BANDS:
        if valence < upper_bound:
            return label
    return "Euphoric"


def _describe_error_source(source: str) -> str:
    return _ERROR_SOURCE_LABELS.get(source, source)