"""ReccoBeats service updated to use Cloudflare Worker backend API."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .backend_client import BackendClient, BackendAPIError
from ..utils.network_utils import retry_on_network_error, handle_network_errors

logger = logging.getLogger(__name__)


class ReccoBeatsBackendService:
    """ReccoBeats service using Cloudflare Worker backend."""

    def __init__(self, backend_client: Optional[BackendClient] = None):
        """
        Initialize ReccoBeats backend service.

        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client or BackendClient()

    @handle_network_errors
    @retry_on_network_error(max_retries=3, backoff_factor=1.0)
    def analyze_playlist(
        self, playlist_id: str, analysis_task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze a playlist using backend API.

        Args:
            playlist_id: Spotify playlist ID
            analysis_task: Optional analysis task for cancellation tracking

        Returns:
            Analysis job information
        """
        try:
            if analysis_task and analysis_task.is_cancelled():
                return {}

            logger.info(f"Starting playlist analysis for {playlist_id}")

            # Start analysis job
            response = self.backend_client.analyze_playlist(playlist_id)
            job_id = response.get("job_id")

            if not job_id:
                raise BackendAPIError("No job ID received from backend")

            logger.info(f"Analysis job started: {job_id}")

            # Poll for completion
            return self._poll_analysis_completion(job_id, playlist_id, analysis_task)

        except Exception as e:
            logger.error(f"Playlist analysis failed: {e}")
            raise

    def _poll_analysis_completion(
        self,
        job_id: str,
        playlist_id: str,
        analysis_task: Optional[Any] = None,
        max_wait_time: int = 300,
    ) -> Dict[str, Any]:
        """
        Poll for analysis job completion.

        Args:
            job_id: Analysis job ID
            playlist_id: Spotify playlist ID
            analysis_task: Optional analysis task for cancellation tracking
            max_wait_time: Maximum time to wait in seconds

        Returns:
            Analysis results when complete
        """
        start_time = time.time()
        poll_interval = 2.0  # Start with 2 seconds
        max_poll_interval = 10.0  # Max 10 seconds between polls

        while time.time() - start_time < max_wait_time:
            if analysis_task and analysis_task.is_cancelled():
                logger.info("Analysis cancelled by user")
                return {}

            # Fetch current status; only catch transient request-level errors here.
            # Terminal states (completed / failed) must not be swallowed by this handler.
            try:
                status_response = self.backend_client.get_analysis_status(playlist_id)
            except BackendAPIError as e:
                logger.error(f"Error checking analysis status: {e}")
                time.sleep(poll_interval)
                continue

            status = status_response.get("status", "unknown")
            progress = status_response.get("progress", 0)

            logger.debug(f"Analysis status: {status}, progress: {progress}%")

            if status == "completed":
                logger.info("Analysis completed successfully")
                return self.backend_client.get_analysis_results(playlist_id)
            elif status == "failed":
                # Terminal failure — stop polling immediately and propagate.
                error_msg = status_response.get("error", "Analysis failed")
                raise BackendAPIError(f"Analysis failed: {error_msg}")
            elif status in ["pending", "processing", "running", "queued"]:
                if analysis_task:
                    analysis_task.update_progress(
                        progress, f"Analyzing playlist... {progress}%"
                    )
                # Exponential backoff for polling
                time.sleep(min(poll_interval, max_poll_interval))
                poll_interval *= 1.5
            else:
                logger.warning(f"Unknown analysis status: {status}")
                time.sleep(poll_interval)

        raise NetworkTimeoutError(f"Analysis timed out after {max_wait_time} seconds")

    @handle_network_errors
    def get_playlist_for_analysis(
        self, playlist_id: str, analysis_task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Get playlist details for analysis.

        Args:
            playlist_id: Spotify playlist ID
            analysis_task: Optional analysis task for cancellation tracking

        Returns:
            Playlist details with tracks
        """
        if analysis_task and analysis_task.is_cancelled():
            return {}

        try:
            # Get playlist details
            playlist_details = self.backend_client.get_playlist_details(playlist_id)

            # Get playlist tracks
            tracks = self.backend_client.get_playlist_tracks(playlist_id)

            # Combine details and tracks
            playlist_data = {**playlist_details, "tracks": tracks}

            logger.info(f"Retrieved playlist {playlist_id} with {len(tracks)} tracks")
            return playlist_data

        except Exception as e:
            logger.error(f"Failed to get playlist for analysis: {e}")
            raise

    # Legacy compatibility methods - these maintain the same interface as the original ReccoBeatsAPI
    def get_multiple_track_audio_features(
        self,
        spotify_track_ids: List[str],
        max_concurrent: int = 2,
        analysis_task: Optional[Any] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get audio features for multiple tracks using backend analysis.

        This method provides compatibility with the original interface but uses
        the backend analysis system instead of direct ReccoBeats API calls.
        """
        return self.get_multiple_track_audio_features_safe(
            spotify_track_ids, max_concurrent, analysis_task
        )

    def get_multiple_track_audio_features_safe(
        self,
        spotify_track_ids: List[str],
        max_concurrent: int = 2,
        analysis_task: Optional[Any] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get audio features for multiple tracks with caching.

        Args:
            spotify_track_ids: List of Spotify track IDs
            max_concurrent: Maximum concurrent requests (not used in backend version)
            analysis_task: Optional analysis task for cancellation tracking

        Returns:
            Dictionary mapping track IDs to audio features
        """
        results: Dict[str, Dict[str, Any]] = {}

        if analysis_task and analysis_task.is_cancelled():
            return results

        # Per-track cache lookup is not implemented. The previous version of
        # this method silently returned fabricated `danceability: 0.8,
        # energy: 0.9` data for two hardcoded "cached" track IDs, which
        # made the audio-feature UI look functional in development but
        # corrupted all production analysis output.
        raise NotImplementedError(
            "ReccoBeats per-track cache lookup not implemented; "
            "see docs/exec-plans/active/2026-06-21-reccobeats-wiring.md"
        )

    def get_reccobeats_id_from_spotify_id(
        self,
        spotify_track_id: str,
        analysis_task: Optional[Any] = None,
    ) -> str:
        """
        Get ReccoBeats ID for a Spotify track ID.

        Note: This method is not fully supported in backend mode as it requires
        playlist-level analysis. Returns empty string.
        """
        logger.debug("get_reccobeats_id_from_spotify_id not supported in backend mode")
        return ""

    def get_audio_features_by_reccobeats_id(
        self,
        reccobeats_id: str,
        analysis_task: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Get audio features by ReccoBeats ID.

        Note: This method is not fully supported in backend mode as it requires
        playlist-level analysis. Returns empty dict.
        """
        logger.debug(
            "get_audio_features_by_reccobeats_id not supported in backend mode"
        )
        return {}

    # Batch processing methods (legacy compatibility)
    def get_multiple_reccobeats_ids(
        self,
        spotify_track_ids: List[str],
        max_batch_size: int = 10,
        analysis_task: Optional[Any] = None,
    ) -> Dict[str, str]:
        """
        Get multiple ReccoBeats IDs for Spotify track IDs.

        Note: This method is not supported in backend mode.
        """
        logger.debug("get_multiple_reccobeats_ids not supported in backend mode")
        return {}

    def is_backend_available(self) -> bool:
        """Check if backend is available."""
        try:
            health = self.backend_client.health_check()
            return health.get("status") == "healthy"
        except Exception:
            return False

    def get_backend_status(self) -> Dict[str, Any]:
        """Get backend status information."""
        try:
            return self.backend_client.health_check()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Factory function for backward compatibility
def get_reccobeats_service() -> ReccoBeatsBackendService:
    """Get ReccoBeats backend service instance."""
    return ReccoBeatsBackendService()


# Legacy compatibility
class ReccoBeatsAPI(ReccoBeatsBackendService):
    """Legacy compatibility class for existing code."""

    pass


def get_reccobeats_api() -> ReccoBeatsAPI:
    """Get ReccoBeats API instance (legacy compatibility)."""
    return ReccoBeatsAPI()


__all__ = [
    "ReccoBeatsBackendService",
    "ReccoBeatsAPI",
    "get_reccobeats_service",
    "get_reccobeats_api",
]
