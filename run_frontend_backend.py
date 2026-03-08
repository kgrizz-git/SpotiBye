"""Launcher for backend-integrated SpotiBye frontend."""

from __future__ import annotations

from src.frontend.app import SpotifyExporterApp


def main() -> None:
    """Launch the backend-integrated frontend app."""
    SpotifyExporterApp().run()


if __name__ == "__main__":
    main()
