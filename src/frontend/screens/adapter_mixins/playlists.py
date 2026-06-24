"""Playlist loading mixin for BackendMainScreenAdapter."""

from __future__ import annotations

import threading
from typing import Any, Dict, List

from kivy.clock import Clock, mainthread

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError
from ...utils.network_utils import format_error_message


class PlaylistsMixin:
    """Playlist loading with cache/threading support."""

    def load_playlists(self, force_refresh: bool = False) -> None:
        """
        Load user playlists from backend.

        Args:
            force_refresh: Force refresh from backend, ignore cache
        """

        def load_worker():
            try:
                # Check cache first (unless force refresh)
                if not force_refresh and self.cache_manager.is_playlists_cache_valid():
                    logger.info("Playlists cache is valid; attempting cache load")
                    cached_playlists = self.cache_manager.get_cached_playlists()
                    if cached_playlists:
                        cached_count = len(cached_playlists)
                        logger.info(f"Loaded {cached_count} playlists from local cache")

                        # A very common stale state is an old single-page (50-item) cache.
                        # Prefer a fresh backend pull in this case to confirm full pagination.
                        if cached_count == 50:
                            logger.warning(
                                "Cached playlist count is exactly 50; forcing backend refresh to verify pagination"
                            )
                        else:
                            Clock.schedule_once(
                                lambda dt: self._on_playlists_loaded(cached_playlists),
                                0,
                            )
                            return

                # Check network connection
                if not self.network_monitor.is_connected():
                    error_msg = format_error_message(ConnectionError())
                    Clock.schedule_once(lambda dt: self._on_error(error_msg), 0)
                    return

                # Load from backend
                if self.progress_callback:
                    Clock.schedule_once(
                        lambda dt: self.progress_callback(
                            "Loading playlists from backend..."
                        ),
                        0,
                    )

                playlists = self.backend_client.get_playlists()
                logger.info(f"Loaded {len(playlists)} playlists from backend API")

                # Cache the results
                self.cache_manager.cache_playlists(playlists)
                logger.info(f"Cached {len(playlists)} playlists from backend response")

                Clock.schedule_once(lambda dt: self._on_playlists_loaded(playlists), 0)

            except BackendAPIError as e:
                error_msg = self._format_backend_api_error(
                    e, "Failed to load playlists"
                )
                Clock.schedule_once(lambda dt: self._on_error(error_msg), 0)
            except Exception as e:
                logger.error(f"Error loading playlists: {e}")
                error_msg = f"Failed to load playlists: {str(e)}"
                Clock.schedule_once(lambda dt: self._on_error(error_msg), 0)

        threading.Thread(target=load_worker, daemon=True).start()

    @mainthread
    def _on_playlists_loaded(self, playlists: List[Dict[str, Any]]) -> None:
        """Handle playlists loaded successfully."""
        if self.playlists_loaded_callback:
            self.playlists_loaded_callback(playlists)

    @mainthread
    def _on_error(self, error_msg: str) -> None:
        """Handle error."""
        if self.error_callback:
            self.error_callback(error_msg)
