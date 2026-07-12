"""ReccoBeats service updated to use Cloudflare Worker backend API."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .backend_client import BackendClient, BackendAPIError
from .enrichment_errors import has_retriable_reccobeats_errors
from ..caching.backend_cache import get_cache_manager
from ..utils.network_utils import (
    NetworkTimeoutError,
    handle_network_errors,
    retry_on_network_error,
)

logger = logging.getLogger(__name__)

SYNTHETIC_PROGRESS_STALE_AFTER_SECONDS = 5.0


class ReccoBeatsBackendService:
    """
    ReccoBeats service using Cloudflare Worker backend.

    Playlist analysis and export enrichment are served by backend analysis and
    export routes; per-track cache is global on the Worker.
    """

    def __init__(self, backend_client: Optional[BackendClient] = None):
        """
        Initialize ReccoBeats backend service.

        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client or BackendClient()
        # Guards against re-posting more than once per top-level
        # `analyze_playlist` call when polling discovers stale results.
        self._reposted_on_stale = False
        self._reposted_on_reccobeats_error = False

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

            self._reposted_on_stale = False
            self._reposted_on_reccobeats_error = False
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

    def force_reanalyze_playlist(
        self, playlist_id: str, analysis_task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Enqueue a fresh analysis job with per-track ReccoBeats force refresh."""
        get_cache_manager().clear_file(f"analysis_{playlist_id}.json")
        self._reposted_on_stale = False
        self._reposted_on_reccobeats_error = False
        logger.info(f"Force re-analyzing playlist {playlist_id} (force_enrichment)")

        response = self.backend_client.analyze_playlist(
            playlist_id, force_enrichment=True
        )
        job_id = response.get("job_id")

        if not job_id:
            raise BackendAPIError("No job ID received from backend")

        return self._poll_analysis_completion(job_id, playlist_id, analysis_task)

    def run_enrichment_miss_fill(
        self, playlist_id: str, analysis_task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Re-run analysis so the backend per-track cache miss-fills unresolved IDs only."""
        get_cache_manager().clear_file(f"analysis_{playlist_id}.json")
        return self.analyze_playlist(playlist_id, analysis_task)

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
        last_reported_progress: Optional[int] = None
        stale_progress_since: Optional[float] = None

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
                if analysis_task:
                    analysis_task.update_progress(100, "Analysis complete")
                try:
                    results = self.backend_client.get_analysis_results(playlist_id)
                    if (
                        has_retriable_reccobeats_errors(results)
                        and not self._reposted_on_reccobeats_error
                    ):
                        logger.info(
                            "Cached analysis has ReccoBeats errors; "
                            "clearing backend/local caches and re-analyzing once"
                        )
                        self._reposted_on_reccobeats_error = True
                        self.backend_client.delete_analysis(playlist_id)
                        get_cache_manager().clear_file(f"analysis_{playlist_id}.json")
                        new_response = self.backend_client.analyze_playlist(playlist_id)
                        new_job_id = new_response.get("job_id")
                        if not new_job_id:
                            raise BackendAPIError("No job ID received from backend")
                        return self._poll_analysis_completion(
                            new_job_id, playlist_id, analysis_task, max_wait_time
                        )
                    return results
                except BackendAPIError as e:
                    if (
                        e.error_code != "ANALYSIS_RESULTS_NOT_FOUND"
                        or self._reposted_on_stale
                    ):
                        raise
                    # The backend purges stale (pre-schema-bump) results on GET,
                    # so a "completed" status with no results means the cached
                    # analysis is stale. Invalidate the local cache and
                    # re-trigger analysis once — the backend's POST stale-check
                    # will enqueue a fresh job since the KV status/results were
                    # already deleted by the GET above.
                    logger.warning(
                        f"Analysis results for {playlist_id} are stale or missing; "
                        "invalidating cache and re-triggering analysis once"
                    )
                    self._reposted_on_stale = True
                    get_cache_manager().clear_file(f"analysis_{playlist_id}.json")
                    new_response = self.backend_client.analyze_playlist(playlist_id)
                    new_job_id = new_response.get("job_id")
                    if not new_job_id:
                        raise BackendAPIError("No job ID received from backend") from e
                    return self._poll_analysis_completion(
                        new_job_id, playlist_id, analysis_task, max_wait_time
                    )
            elif status == "failed":
                # Terminal failure — stop polling immediately and propagate.
                error_msg = status_response.get("error", "Analysis failed")
                raise BackendAPIError(f"Analysis failed: {error_msg}")
            elif status in ["pending", "processing", "running", "queued"]:
                if analysis_task:
                    now = time.time()
                    if (
                        last_reported_progress is not None
                        and progress <= last_reported_progress
                        and hasattr(analysis_task, "update_synthetic_progress")
                        and stale_progress_since is not None
                        and now - stale_progress_since
                        >= SYNTHETIC_PROGRESS_STALE_AFTER_SECONDS
                    ):
                        elapsed = now - start_time
                        logger.debug(
                            "Synthetic analysis progress active after "
                            f"{elapsed:.1f}s; backend status remains {status}, "
                            f"progress: {progress}%"
                        )
                        analysis_task.update_synthetic_progress(
                            elapsed, "Analyzing playlist..."
                        )
                    else:
                        if (
                            last_reported_progress is None
                            or progress > last_reported_progress
                        ):
                            analysis_task.update_progress(
                                progress, f"Analyzing playlist... {progress}%"
                            )
                            stale_progress_since = now
                        elif stale_progress_since is None:
                            stale_progress_since = now
                    if (
                        last_reported_progress is None
                        or progress > last_reported_progress
                    ):
                        last_reported_progress = progress
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
