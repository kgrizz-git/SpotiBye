"""Filename and export-format helpers for MainScreen."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Optional


def get_file_extension(format_type: str) -> str:
    """Get file extension for export format."""
    extensions = {"xlsx": ".xlsx", "csv": ".csv", "json": ".json"}
    return extensions.get(format_type.lower(), ".xlsx")


def selected_export_format(format_text: str) -> str:
    """Return the normalized export format ('xlsx', 'csv', or 'json')."""
    fmt = (format_text or "xlsx").strip().lower()
    return fmt if fmt in ("xlsx", "csv", "json") else "xlsx"


def generate_default_filename(
    username: Optional[str] = None, format_type: str = "xlsx", now: Optional[datetime] = None
) -> str:
    """Generate a default export filename based on username and current timestamp."""
    # Handle None or empty username cases
    if not username or username == "None":
        safe_username = "user"
    else:
        safe_username = str(username)

    # Format: YYYY-MM-DD_HH-MM-SSAM/PM
    current = now or datetime.now()
    timestamp = current.strftime("%Y-%m-%d_%I-%M-%S%p")

    return f"Spotify_Playlists_{safe_username}_{timestamp}.{format_type}"


def increment_filename_suffix(filename: str) -> str:
    """Increment filename suffix from _2 to _5 as needed.

    Recognizes a *trailing* `_N` suffix anchored before the extension, so
    digit-ending basenames (e.g. `song_14.xlsx`) are not corrupted.

    Args:
        filename: Base filename (e.g., 'Spotify_Playlists_user_2026-06-16_09-30-00AM.xlsx')

    Returns:
        Filename with incremented suffix, or original if already at `_5`.
    """
    base, extension = os.path.splitext(filename)

    # Match a trailing _N where N is a single digit 2..5. Anchored to the
    # end of the basename so `song_14` (a legitimate digit-ending name) is
    # not misinterpreted as `song_1` + `_4`.
    match = re.search(r"^_(?P<n>[2-5])$", base[-2:])

    if match:
        current_n = int(match.group("n"))
        if current_n >= 5:
            return filename
        new_n = current_n + 1
        return base[:-2] + f"_{new_n}" + extension

    # No recognized suffix, append _2.
    return base + "_2" + extension


def sanitize_export_filename_component(value: str) -> str:
    """Sanitize playlist/file name component for cross-platform safe filenames."""
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", value or "").strip()
    return safe[:80] if safe else "playlist"
