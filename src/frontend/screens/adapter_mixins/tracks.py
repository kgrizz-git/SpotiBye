"""Track fetching mixin for BackendMainScreenAdapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError


class TracksMixin:
    """Playlist track and details loading."""

    def get_playlist_details(
        self, playlist_id: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get playlist details from backend."""
        try:
            if self.progress_callback:
                self.progress_callback("Loading playlist details...")

            details = self.backend_client.get_playlist_details(playlist_id)
            return details if isinstance(details, dict) else None
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, "Playlist details failed")
            if self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error getting playlist details: {e}")
            if self.error_callback:
                self.error_callback(f"Failed to load playlist details: {str(e)}")
            return None

    def get_playlist_tracks(
        self, playlist_id: str, force_refresh: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get tracks for a playlist.

        Args:
            playlist_id: Spotify playlist ID
            force_refresh: Force refresh from backend

        Returns:
            List of tracks or None if error
        """
        try:
            # Check cache first
            if not force_refresh and self.cache_manager.is_tracks_cache_valid(
                playlist_id
            ):
                logger.info(f"Loading tracks for {playlist_id} from cache")
                cached_tracks = self.cache_manager.get_cached_tracks(playlist_id)
                if cached_tracks:
                    return cached_tracks

            # Load from backend
            if self.progress_callback:
                self.progress_callback("Loading playlist tracks...")

            tracks = self.backend_client.get_playlist_tracks(playlist_id)

            # Cache the results
            self.cache_manager.cache_tracks(playlist_id, tracks)

            return tracks

        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, "Failed to load playlist tracks")
            if self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error getting playlist tracks: {e}")
            if self.error_callback:
                self.error_callback(f"Failed to load tracks: {str(e)}")
            return None
