"""Launcher for backend-integrated SpotiBye frontend."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).parent.resolve() / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from src.frontend.app import SpotifyExporterApp


def main() -> None:
    """Launch the backend-integrated frontend app."""
    SpotifyExporterApp().run()


if __name__ == "__main__":
    main()
