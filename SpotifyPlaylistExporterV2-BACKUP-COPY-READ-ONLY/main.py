"""Convenience entry point to launch the Spotify Playlist Exporter app."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the src/ directory (where the package lives) is on sys.path when running this file directly.
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from spotify_playlist_exporter_v2.app import SpotifyExporterApp  # noqa: E402


def main() -> None:
    """Launch the Kivy application."""
    SpotifyExporterApp().run()


if __name__ == "__main__":
    main()
