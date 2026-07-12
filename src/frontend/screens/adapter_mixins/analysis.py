"""Playlist analysis mixin for BackendMainScreenAdapter."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ....shared.logging_config import logger
from ...services.enrichment_completeness import (
    enrichment_incompleteness_endpoints,
    is_offline_enrichment_complete,
    miss_fill_ledger_key,
)
from ...services.enrichment_errors import has_retriable_reccobeats_errors
from ...services.enrichment_retry_ledger import get_enrichment_retry_ledger
from ...services.playlist_composition import (
    build_composition_fingerprint,
    compute_track_id_hash,
    fingerprints_match,
    resolve_snapshot_id_from_playlists,
    unique_track_ids_from_items,
)

# Kept in sync manually with `ANALYSIS_SCHEMA_VERSION` in
# `src/backend/utils/constants.ts`. A single frontend build only ever talks to
# one backend schema, so an exact-match comparison (not numeric `>=`) is
# sufficient and avoids needing a shared config module.
EXPECTED_ANALYSIS_SCHEMA_VERSION = "1.1"


class AnalysisMixin:
    """Backend playlist analysis orchestration."""

    def _cached_analysis_if_valid(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        if not self.cache_manager.is_analysis_cache_valid(playlist_id):
            return None
        cached = self.cache_manager.get_cached_analysis(playlist_id)
        if not cached:
            return None
        if cached.get("schema_version") != EXPECTED_ANALYSIS_SCHEMA_VERSION:
            return None
        return cached

    def _composition_fingerprint_for_playlist(self, playlist_id: str) -> str:
        entry = self.cache_manager.get_cached_tracks_entry(playlist_id)
        if entry:
            return build_composition_fingerprint(
                snapshot_id=entry.get("snapshot_id")
                if isinstance(entry.get("snapshot_id"), str)
                else None,
                track_id_hash=entry.get("track_id_hash")
                if isinstance(entry.get("track_id_hash"), str)
                else None,
            )
        return build_composition_fingerprint()

    def _playlist_composition_changed(self, playlist_id: str) -> bool:
        """Online-only check: snapshot_id or track-id hash differs from cache."""
        cached_entry = self.cache_manager.get_cached_tracks_entry(playlist_id)
        if not cached_entry:
            return False

        if not self.network_monitor.is_connected():
            return False

        try:
            snapshot_id = resolve_snapshot_id_from_playlists(
                self.cache_manager.get_cached_playlists(),
                playlist_id,
            )
            if not snapshot_id:
                details = self.get_playlist_details(playlist_id)
                if isinstance(details, dict):
                    snap = details.get("snapshot_id")
                    if isinstance(snap, str) and snap:
                        snapshot_id = snap

            if snapshot_id and fingerprints_match(
                cached_entry,
                snapshot_id=snapshot_id,
                track_id_hash="",
            ):
                return False

            current_tracks = self.backend_client.get_playlist_tracks(playlist_id)
            current_hash = compute_track_id_hash(
                unique_track_ids_from_items(current_tracks)
            )
            return not fingerprints_match(
                cached_entry,
                snapshot_id=snapshot_id,
                track_id_hash=current_hash,
            )
        except Exception as exc:
            logger.warning(
                "Composition check failed for %s; using offline completeness gate: %s",
                playlist_id,
                exc,
            )
            return False

    def _should_auto_miss_fill(self, cached_analysis: Dict[str, Any], playlist_id: str) -> bool:
        incomplete_endpoints = enrichment_incompleteness_endpoints(cached_analysis)
        if not incomplete_endpoints:
            return False

        unique_count = cached_analysis.get("unique_track_count")
        audio_resolved = cached_analysis.get("audio_features_resolved_count")
        metadata_resolved = cached_analysis.get("track_metadata_resolved_count")
        if not isinstance(unique_count, int):
            return False
        if not isinstance(audio_resolved, int) or not isinstance(metadata_resolved, int):
            return False

        composition_fp = self._composition_fingerprint_for_playlist(playlist_id)
        ledger = get_enrichment_retry_ledger()
        for endpoint in incomplete_endpoints:
            key = miss_fill_ledger_key(
                playlist_id=playlist_id,
                composition_fingerprint=composition_fp,
                endpoint=endpoint,
                audio_resolved_count=audio_resolved,
                metadata_resolved_count=metadata_resolved,
                unique_track_count=unique_count,
            )
            if not ledger.has_attempted(key):
                return True
        return False

    def _record_miss_fill_attempt(self, cached_analysis: Dict[str, Any], playlist_id: str) -> None:
        incomplete_endpoints = enrichment_incompleteness_endpoints(cached_analysis)
        unique_count = cached_analysis.get("unique_track_count")
        audio_resolved = cached_analysis.get("audio_features_resolved_count")
        metadata_resolved = cached_analysis.get("track_metadata_resolved_count")
        if not isinstance(unique_count, int):
            return
        if not isinstance(audio_resolved, int) or not isinstance(metadata_resolved, int):
            return

        composition_fp = self._composition_fingerprint_for_playlist(playlist_id)
        ledger = get_enrichment_retry_ledger()
        for endpoint in incomplete_endpoints:
            key = miss_fill_ledger_key(
                playlist_id=playlist_id,
                composition_fingerprint=composition_fp,
                endpoint=endpoint,
                audio_resolved_count=audio_resolved,
                metadata_resolved_count=metadata_resolved,
                unique_track_count=unique_count,
            )
            ledger.record_attempt(key)

    def _run_backend_analysis(
        self,
        playlist_id: str,
        progress_callback: Optional[Callable[..., Any]] = None,
        analysis_task: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        if progress_callback:
            progress_callback("Starting playlist analysis...")

        if analysis_task is not None:
            analysis_results = self.reccobeats_service.analyze_playlist(
                playlist_id, analysis_task
            )
        else:
            analysis_results = self.reccobeats_service.analyze_playlist(playlist_id)

        if analysis_results:
            self.cache_manager.cache_analysis(playlist_id, analysis_results)
            return analysis_results
        return None

    def analyze_playlist(
        self,
        playlist_id: str,
        progress_callback: Optional[Callable[..., Any]] = None,
        analysis_task: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a playlist using backend.

        Args:
            playlist_id: Spotify playlist ID
            progress_callback: Optional progress callback
            analysis_task: Optional analysis task for backend polling progress

        Returns:
            Analysis results or None if error
        """
        try:
            cached_analysis = self._cached_analysis_if_valid(playlist_id)

            if cached_analysis:
                if has_retriable_reccobeats_errors(cached_analysis):
                    logger.info(
                        f"Cached analysis for {playlist_id} has "
                        "ReccoBeats errors; forcing re-analysis"
                    )
                    self.cache_manager.clear_file(f"analysis_{playlist_id}.json")
                    if analysis_task is not None:
                        return self.reccobeats_service.force_reanalyze_playlist(
                            playlist_id, analysis_task
                        )
                    return self.reccobeats_service.force_reanalyze_playlist(playlist_id)

                has_completeness_fields = (
                    isinstance(cached_analysis.get("unique_track_count"), int)
                    and isinstance(
                        cached_analysis.get("audio_features_resolved_count"), int
                    )
                    and isinstance(
                        cached_analysis.get("track_metadata_resolved_count"), int
                    )
                )

                if not has_completeness_fields:
                    logger.info(f"Loading analysis for {playlist_id} from cache")
                    return cached_analysis

                if is_offline_enrichment_complete(
                    cached_analysis,
                    expected_schema_version=EXPECTED_ANALYSIS_SCHEMA_VERSION,
                ):
                    if self._playlist_composition_changed(playlist_id):
                        logger.info(
                            f"Playlist {playlist_id} composition changed; re-analyzing"
                        )
                        self.cache_manager.clear_file(f"analysis_{playlist_id}.json")
                        self.get_playlist_tracks(playlist_id, force_refresh=True)
                        return self._run_backend_analysis(
                            playlist_id, progress_callback, analysis_task
                        )

                    logger.info(f"Loading analysis for {playlist_id} from cache (offline complete)")
                    return cached_analysis

                if self._should_auto_miss_fill(cached_analysis, playlist_id):
                    logger.info(
                        f"Cached analysis for {playlist_id} is enrichment-incomplete; "
                        "running targeted backend miss-fill once this session"
                    )
                    self._record_miss_fill_attempt(cached_analysis, playlist_id)
                    if analysis_task is not None:
                        result = self.reccobeats_service.run_enrichment_miss_fill(
                            playlist_id, analysis_task
                        )
                    else:
                        result = self.reccobeats_service.run_enrichment_miss_fill(
                            playlist_id
                        )
                    if result:
                        self.cache_manager.cache_analysis(playlist_id, result)
                    return result

                logger.info(
                    f"Returning cached analysis for {playlist_id} with incomplete "
                    "enrichment (auto miss-fill already attempted this session)"
                )
                return cached_analysis

            if self.cache_manager.is_analysis_cache_valid(playlist_id):
                logger.info(
                    f"Cached analysis for {playlist_id} has a stale or missing "
                    "schema_version; discarding cache and re-analyzing"
                )
                self.cache_manager.clear_file(f"analysis_{playlist_id}.json")

            return self._run_backend_analysis(
                playlist_id, progress_callback, analysis_task
            )

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

    def force_reanalyze_playlist(
        self,
        playlist_id: str,
        analysis_task: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Force backend/local analysis invalidation before re-running analysis."""
        try:
            from ...services.enrichment_retry_ledger import reset_enrichment_retry_ledger

            reset_enrichment_retry_ledger()
            if analysis_task is not None:
                result = self.reccobeats_service.force_reanalyze_playlist(
                    playlist_id, analysis_task
                )
            else:
                result = self.reccobeats_service.force_reanalyze_playlist(playlist_id)
            if result:
                self.cache_manager.cache_analysis(playlist_id, result)
            return result
        except Exception as e:
            logger.error(f"Error force re-analyzing playlist: {e}")
            if self.error_callback:
                self.error_callback(f"Analysis retry failed: {str(e)}")
            return None
