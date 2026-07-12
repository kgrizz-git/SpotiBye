"""Track fetching mixin for BackendMainScreenAdapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError
from ...services.playlist_composition import (
    build_tracks_cache_metadata,
    resolve_snapshot_id_from_playlists,
)


class TracksMixin:
    """Playlist track and details loading."""

    def get_playlist_details(
        self, playlist_id: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get playlist details from backend."""
        try:
            if self.progress_callback:
                self.progress_callback("Loading playlist details...")

            details = self.backend_client.get_playlist_details(
                playlist_id, force_refresh=force_refresh
            )
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

    def _resolve_snapshot_id_for_playlist(self, playlist_id: str) -> Optional[str]:
        """Prefer list snapshot_id; fall back to cached tracks metadata."""
        snapshot_id = resolve_snapshot_id_from_playlists(
            self.cache_manager.get_cached_playlists(),
            playlist_id,
        )
        if snapshot_id:
            return snapshot_id
        entry = self.cache_manager.get_cached_tracks_entry(playlist_id)
        if entry:
            cached_snap = entry.get("snapshot_id")
            if isinstance(cached_snap, str) and cached_snap:
                return cached_snap
        return None

    def get_playlist_tracks(
        self, playlist_id: str, force_refresh: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get tracks for a playlist.

        Args:
            playlist_id: Spotify playlist ID
            force_refresh: Force refresh from backend (local + backend KV)

        Returns:
            List of tracks or None if error
        """
        try:
            if not force_refresh and self.cache_manager.is_tracks_cache_valid(
                playlist_id
            ):
                logger.info(f"Loading tracks for {playlist_id} from cache")
                cached_tracks = self.cache_manager.get_cached_tracks(playlist_id)
                if cached_tracks:
                    return cached_tracks

            if self.progress_callback:
                self.progress_callback("Loading playlist tracks...")

            tracks = self.backend_client.get_playlist_tracks(
                playlist_id, force_refresh=force_refresh
            )

            snapshot_id = self._resolve_snapshot_id_for_playlist(playlist_id)
            if not snapshot_id and not force_refresh:
                details = self.get_playlist_details(playlist_id)
                if isinstance(details, dict):
                    snap = details.get("snapshot_id")
                    if isinstance(snap, str) and snap:
                        snapshot_id = snap
            if force_refresh:
                details = self.get_playlist_details(playlist_id, force_refresh=True)
                if isinstance(details, dict):
                    snap = details.get("snapshot_id")
                    if isinstance(snap, str) and snap:
                        snapshot_id = snap

            metadata = build_tracks_cache_metadata(tracks, snapshot_id=snapshot_id)
            self.cache_manager.cache_tracks(
                playlist_id,
                tracks,
                metadata=metadata,
            )

            return tracks

        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(
                e, "Failed to load playlist tracks"
            )
            if self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error getting playlist tracks: {e}")
            if self.error_callback:
                self.error_callback(f"Failed to load tracks: {str(e)}")
            return None
