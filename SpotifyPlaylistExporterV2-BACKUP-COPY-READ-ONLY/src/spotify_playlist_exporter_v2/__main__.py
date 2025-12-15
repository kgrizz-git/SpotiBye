"""CLI entry point for spotify_playlist_exporter_v2."""

from .app import SpotifyExporterApp


def main() -> None:
    SpotifyExporterApp().run()


if __name__ == "__main__":  # pragma: no cover
    main()
