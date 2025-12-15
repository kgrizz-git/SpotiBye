import logging


def configure_logging() -> logging.Logger:
    """Configure logging similar to the original monolithic script."""
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger("spotify_playlist_exporter_v2")
    logger.setLevel(logging.DEBUG)

    # Reduce noise from third-party libraries
    logging.getLogger('spotipy').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    return logger


logger = configure_logging()
