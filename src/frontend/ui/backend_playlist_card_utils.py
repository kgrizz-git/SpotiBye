"""Module-level utility helpers for BackendPlaylistCard — no kivy or project dependencies."""

from __future__ import annotations

import json
import re

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
    "reccobeats:coverage": "audio feature coverage note",
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


def _describe_error_source(source: str, message: str | None = None) -> str:
    label = _ERROR_SOURCE_LABELS.get(source, source)
    if message:
        return f"{label} ({_format_partial_error_message(message)})"
    return label


def _format_partial_error_message(message: str) -> str:
    match = re.fullmatch(r"HTTP (\d+):\s*(.*)", message.strip(), flags=re.DOTALL)
    if not match:
        return message

    status = match.group(1)
    body = match.group(2).strip()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return message

    error_payload = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_payload, dict):
        return message

    spotify_message = error_payload.get("message")
    if not isinstance(spotify_message, str) or not spotify_message:
        return message

    return f"Spotify returned {status}: {spotify_message}"
