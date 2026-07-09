"""Playlist analysis mixin for BackendMainScreenAdapter."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ....shared.logging_config import logger

# Kept in sync manually with `ANALYSIS_SCHEMA_VERSION` in
# `src/backend/utils/constants.ts`. A single frontend build only ever talks to
# one backend schema, so an exact-match comparison (not numeric `>=`) is
# sufficient and avoids needing a shared config module.
EXPECTED_ANALYSIS_SCHEMA_VERSION = "1.0"


class AnalysisMixin:
    """Backend playlist analysis orchestration."""

    def analyze_playlist(
        self, playlist_id: str, progress_callback: Optional[Callable[..., Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a playlist using backend.

        Args:
            playlist_id: Spotify playlist ID
            progress_callback: Optional progress callback

        Returns:
            Analysis results or None if error
        """
        try:
            # Check cache first
            if self.cache_manager.is_analysis_cache_valid(playlist_id):
                cached_analysis = self.cache_manager.get_cached_analysis(playlist_id)
                if cached_analysis:
                    if (
                        cached_analysis.get("schema_version")
                        == EXPECTED_ANALYSIS_SCHEMA_VERSION
                    ):
                        logger.info(f"Loading analysis for {playlist_id} from cache")
                        return cached_analysis
                    logger.info(
                        f"Cached analysis for {playlist_id} has a stale or missing "
                        "schema_version; discarding cache and re-analyzing"
                    )
                    self.cache_manager.clear_file(f"analysis_{playlist_id}.json")

            # Start analysis
            if progress_callback:
                progress_callback("Starting playlist analysis...")

            # Use the ReccoBeats backend service
            analysis_results = self.reccobeats_service.analyze_playlist(playlist_id)

            if analysis_results:
                # Cache the results
                self.cache_manager.cache_analysis(playlist_id, analysis_results)
                return analysis_results
            else:
                return None

        except Exception as e:
            logger.error(f"Error analyzing playlist: {e}")
            error_msg = f"Analysis failed: {str(e)}"
            if self.error_callback:
                self.error_callback(error_msg)
            return None

    def get_analysis_status(self, playlist_id: str) -> Dict[str, Any]:
        """
        Get analysis status for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Analysis status dictionary
        """
        try:
            return self.backend_client.get_analysis_status(playlist_id)
        except Exception as e:
            logger.error(f"Error getting analysis status: {e}")
            return {"status": "error", "error": str(e)}
