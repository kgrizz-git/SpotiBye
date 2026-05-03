"""Global configuration and constants for Spotify Playlist Exporter V2."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Final

from kivy.metrics import dp

# Spotify API configuration
CLIENT_ID: Final[str] = os.environ.get("SPOTIPY_CLIENT_ID", "YOUR_CLIENT_ID_HERE")
CLIENT_SECRET: Final[str] = os.environ.get(
    "SPOTIPY_CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE"
)
SCOPE: Final[str] = "playlist-read-private playlist-read-collaborative"

# OAuth ports to try in order (fallback logic)
OAUTH_PORTS: Final[list[int]] = [8001, 8101, 8202, 8303, 8888, 5001, 5003, 5000, 5002]

# Default redirect URI (will be updated dynamically based on available port)
DEFAULT_REDIRECT_URI: Final[str] = "http://127.0.0.1:8888/callback"

# Dynamic redirect URI (set at runtime based on available port)
REDIRECT_URI: str = DEFAULT_REDIRECT_URI

# ReccoBeats API configuration
RECCOBEATS_BASE_URL: Final[str] = "https://api.reccobeats.com/v1"
RECCOBEATS_TIMEOUT: Final[int] = 10  # seconds


class UIConstants:
    """UI metrics consolidated to avoid repeated dp() calculations."""

    REDUCED_SPACING = dp(12)
    STANDARD_SPACING = dp(16)
    LARGE_SPACING = dp(18)
    HEADER_HEIGHT = dp(20)
    TECH_DETAILS_FONT = dp(13)
    POPUP_WIDTH = dp(360)


# Token cache path
CACHE_PATH: Final[str] = os.path.expanduser("~/.spotify_exporter_token")

# Directories for exports and temp data
SAVE_DIR = os.path.expanduser("~/Downloads")
if not os.path.exists(SAVE_DIR):
    SAVE_DIR = tempfile.gettempdir()

TMP_DIR = os.path.join(tempfile.gettempdir(), "spotify_exports")
os.makedirs(TMP_DIR, exist_ok=True)

# Cache directories
DEFAULT_CACHE_DIR = Path(os.path.expanduser("~")) / ".spotify_exporter_cache"
