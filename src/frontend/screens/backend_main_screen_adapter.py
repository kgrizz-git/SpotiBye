"""Backend integration adapter for existing MainScreen to use backend services."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from kivy.clock import Clock, mainthread

from ..services.backend_client import BackendClient, BackendAPIError
from ..services.reccobeats_backend import ReccoBeatsBackendService
from ..caching.backend_cache import BackendCacheManager, get_cache_manager
from ..utils.network_utils import NetworkStatusMonitor, format_error_message, NetworkError
from ...spotify_playlist_exporter_v2.logging_config import logger

logger = logging.getLogger(__name__)


class BackendMainScreenAdapter:
    """Adapter to integrate backend services with existing MainScreen."""
    
    def __init__(self, backend_client: Optional[BackendClient] = None):
        """
        Initialize backend adapter.
        
        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client or BackendClient()
        self.reccobeats_service = ReccoBeatsBackendService(self.backend_client)
        self.cache_manager = get_cache_manager()
        self.network_monitor = NetworkStatusMonitor(self.backend_client)
        
        # Callbacks for UI updates
        self.playlists_loaded_callback: Optional[callable] = None
        self.error_callback: Optional[callable] = None
        self.progress_callback: Optional[callable] = None
        
    def set_callbacks(self, playlists_loaded: Optional[callable] = None,
                     error: Optional[callable] = None,
                     progress: Optional[callable] = None) -> None:
        """
        Set UI update callbacks.
        
        Args:
            playlists_loaded: Callback for when playlists are loaded
            error: Callback for error messages
            progress: Callback for progress updates
        """
        self.playlists_loaded_callback = playlists_loaded
        self.error_callback = error
        self.progress_callback = progress

    def _format_backend_api_error(self, error: BackendAPIError, fallback_prefix: str) -> str:
        """Build a user-visible message with backend error code/message/request id when available."""
        status = f"HTTP {error.status_code}" if error.status_code is not None else "HTTP error"
        message = str(error)

        error_payload = {}
        if isinstance(error.response_data, dict):
            maybe_error = error.response_data.get('error')
            if isinstance(maybe_error, dict):
                error_payload = maybe_error

        code = error_payload.get('code')
        request_id = error_payload.get('request_id')

        parts = [fallback_prefix, status]
        if code:
            parts.append(f"code={code}")
        parts.append(message)
        if request_id:
            parts.append(f"request_id={request_id}")

        return " | ".join(parts)

    def _run_with_transient_retry(self, operation_name: str, func: callable,
                                  max_attempts: int = 4, base_delay: float = 1.0):
        """Run an operation with retry/backoff for transient backend failures."""
        retryable_statuses = {429, 500, 502, 503, 504}
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except BackendAPIError as e:
                last_error = e
                status = e.status_code
                is_retryable = status in retryable_statuses

                if not is_retryable or attempt >= max_attempts:
                    raise

                delay = base_delay * attempt
                logger.warning(
                    "%s failed with transient backend error (status=%s). Retrying in %.1fs (%s/%s)",
                    operation_name,
                    status,
                    delay,
                    attempt,
                    max_attempts,
                )
                if self.progress_callback:
                    self.progress_callback(
                        f"{operation_name} temporary backend error (HTTP {status}), retrying ({attempt}/{max_attempts})..."
                    )
                time.sleep(delay)
            except Exception as e:
                last_error = e
                if attempt >= max_attempts:
                    raise
                delay = base_delay * attempt
                logger.warning(
                    "%s failed with transient error. Retrying in %.1fs (%s/%s): %s",
                    operation_name,
                    delay,
                    attempt,
                    max_attempts,
                    e,
                )
                time.sleep(delay)

        if last_error:
            raise last_error
    
    # Playlist management
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
                            logger.warning("Cached playlist count is exactly 50; forcing backend refresh to verify pagination")
                        else:
                            Clock.schedule_once(
                                lambda dt: self._on_playlists_loaded(cached_playlists),
                                0
                            )
                            return

                        
                
                # Check network connection
                if not self.network_monitor.is_connected():
                    error_msg = format_error_message(ConnectionError())
                    Clock.schedule_once(
                        lambda dt: self._on_error(error_msg),
                        0
                    )
                    return
                
                # Load from backend
                if self.progress_callback:
                    Clock.schedule_once(
                        lambda dt: self.progress_callback("Loading playlists from backend..."),
                        0
                    )
                
                playlists = self.backend_client.get_playlists()
                logger.info(f"Loaded {len(playlists)} playlists from backend API")
                
                # Cache the results
                self.cache_manager.cache_playlists(playlists)
                logger.info(f"Cached {len(playlists)} playlists from backend response")
                
                Clock.schedule_once(
                    lambda dt: self._on_playlists_loaded(playlists),
                    0
                )
                
            except BackendAPIError as e:
                error_msg = self._format_backend_api_error(e, 'Failed to load playlists')
                Clock.schedule_once(
                    lambda dt: self._on_error(error_msg),
                    0
                )
            except Exception as e:
                logger.error(f"Error loading playlists: {e}")
                error_msg = f"Failed to load playlists: {str(e)}"
                Clock.schedule_once(
                    lambda dt: self._on_error(error_msg),
                    0
                )
        
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
    
    # Track management
    def get_playlist_tracks(self, playlist_id: str, force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
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
            if not force_refresh and self.cache_manager.is_tracks_cache_valid(playlist_id):
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
            error_msg = self._format_backend_api_error(e, 'Export generation failed')
            if self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error getting playlist tracks: {e}")
            if self.error_callback:
                self.error_callback(f"Failed to load tracks: {str(e)}")
            return None
    
    # Analysis management
    def analyze_playlist(self, playlist_id: str, progress_callback: Optional[callable] = None) -> Optional[Dict[str, Any]]:
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
                logger.info(f"Loading analysis for {playlist_id} from cache")
                cached_analysis = self.cache_manager.get_cached_analysis(playlist_id)
                if cached_analysis:
                    return cached_analysis
            
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
            return {'status': 'error', 'error': str(e)}
    
    # Export management
    def generate_export(self, playlist_id: str, format: str = 'xlsx', report_errors: bool = True) -> Optional[Dict[str, Any]]:
        """
        Generate export for a playlist.
        
        Args:
            playlist_id: Spotify playlist ID
            format: Export format
            
        Returns:
            Export information or None if error
        """
        try:
            if self.progress_callback:
                self.progress_callback("Generating export...")
            
            export_info = self._run_with_transient_retry(
                "Generating export",
                lambda: self.backend_client.generate_export(playlist_id, format),
                max_attempts=6,
                base_delay=1.5,
            )
            
            # Cache export info
            self.cache_manager.cache_export_info(playlist_id, export_info)
            
            return export_info
            
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, 'Export generation failed')
            if report_errors and self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error generating export: {e}")
            if report_errors and self.error_callback:
                self.error_callback(f"Export failed: {str(e)}")
            return None
    
    def download_export(self, playlist_id: str, export_id: str, save_path: str) -> bool:
        """
        Download export file.
        
        Args:
            playlist_id: Spotify playlist ID
            export_id: Export ID
            save_path: Path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.progress_callback:
                self.progress_callback("Downloading export...")
            
            export_data = self._run_with_transient_retry(
                "Downloading export",
                lambda: self.backend_client.download_export(playlist_id, export_id),
            )
            
            # Save to file
            with open(save_path, 'wb') as f:
                f.write(export_data)
            
            logger.info(f"Export saved to {save_path}")
            return True
            
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, 'Export download failed')
            if self.error_callback:
                self.error_callback(error_msg)
            return False
        except Exception as e:
            logger.error(f"Error downloading export: {e}")
            if self.error_callback:
                self.error_callback(f"Download failed: {str(e)}")
            return False

    def generate_batch_export(self, playlist_ids: List[str], format: str = 'xlsx') -> Optional[Dict[str, Any]]:
        """Generate a combined export for multiple playlists."""
        try:
            if self.progress_callback:
                self.progress_callback("Generating combined export...")

            export_info = self._run_with_transient_retry(
                "Generating combined export",
                lambda: self.backend_client.generate_batch_export(playlist_ids, format),
            )
            return export_info
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, 'Chunked export generation failed')
            if self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error generating batch export: {e}")
            if self.error_callback:
                self.error_callback(f"Combined export failed: {str(e)}")
            return None

    def generate_batch_export_chunked(
        self,
        playlist_ids: List[str],
        format: str = 'xlsx',
        chunk_size: int = 1,
        max_steps: int = 200,
        report_errors: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Generate combined export via multiple chunked backend invocations."""
        try:
            if self.progress_callback:
                self.progress_callback("Generating combined export (chunked)...")

            cursor = 0
            job_id: Optional[str] = None
            last_status: Optional[Dict[str, Any]] = None

            for step in range(max_steps):
                status = self._run_with_transient_retry(
                    "Generating combined export chunk",
                    lambda: self.backend_client.generate_batch_export_chunk(
                        playlist_ids=playlist_ids,
                        format=format,
                        job_id=job_id,
                        cursor=cursor,
                        chunk_size=chunk_size,
                    ),
                    max_attempts=5,
                    base_delay=1.0,
                )
                if not isinstance(status, dict):
                    return None

                last_status = status
                job_id = str(status.get('job_id') or job_id or '')
                cursor = int(status.get('next_cursor', cursor))
                processed = int(status.get('processed_count', 0))
                total = int(status.get('playlist_count', len(playlist_ids)))

                if self.progress_callback:
                    self.progress_callback(f"Chunked export progress: {processed}/{total} playlists")

                if status.get('status') == 'completed' or not status.get('continuation_required', False):
                    return status

                # Small delay to avoid sustained pressure on backend/upstream during large runs.
                time.sleep(0.5)

            logger.error("Chunked batch export reached max steps without completion")
            if report_errors and self.error_callback:
                self.error_callback("Chunked export timed out before completion")
            return last_status
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, 'Combined export generation failed')
            if report_errors and self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error generating chunked batch export: {e}")
            if report_errors and self.error_callback:
                self.error_callback(f"Chunked export failed: {str(e)}")
            return None

    def download_batch_export(self, export_id: str, save_path: str) -> bool:
        """Download combined export file."""
        try:
            if self.progress_callback:
                self.progress_callback("Downloading combined export...")

            export_data = self._run_with_transient_retry(
                "Downloading combined export",
                lambda: self.backend_client.download_batch_export(export_id),
            )
            with open(save_path, 'wb') as f:
                f.write(export_data)

            logger.info(f"Combined export saved to {save_path}")
            return True
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, 'Combined export download failed')
            if self.error_callback:
                self.error_callback(error_msg)
            return False
        except Exception as e:
            logger.error(f"Error downloading combined export: {e}")
            if self.error_callback:
                self.error_callback(f"Combined download failed: {str(e)}")
            return False
    
    # Utility methods
    def get_network_status(self) -> Dict[str, Any]:
        """Get current network status."""
        return {
            'connected': self.network_monitor.is_connected(),
            'message': self.network_monitor.get_status_message()
        }
    
    def refresh_connection(self) -> None:
        """Refresh network connection status."""
        self.network_monitor.force_check()
    
    def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """
        Clear cache.
        
        Args:
            cache_type: Type of cache to clear ('playlists', 'tracks', 'analysis', 'export', or None for all)
        """
        try:
            if cache_type == 'playlists':
                self.cache_manager.clear_cache('playlists.json')
            elif cache_type == 'tracks':
                self.cache_manager.clear_cache('tracks_*.json')
            elif cache_type == 'analysis':
                self.cache_manager.clear_cache('analysis_*.json')
            elif cache_type == 'export':
                self.cache_manager.clear_cache('export_*.json')
            else:
                self.cache_manager.clear_cache()
            
            logger.info(f"Cleared {cache_type or 'all'} cache")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_cache_stats()
    
    # Authentication helpers
    def is_authenticated(self) -> bool:
        """Check if authenticated with backend."""
        return self.backend_client.is_authenticated()
    
    def logout(self) -> None:
        """Logout and clear authentication state."""
        try:
            # Clear backend client token
            self.backend_client.clear_auth_token()
            
            # Clear auth token cache
            self.cache_manager.clear_auth_token()
            
            # Clear all data cache
            self.cache_manager.clear_cache()
            
            logger.info("Backend logout completed")
            
        except Exception as e:
            logger.error(f"Error during logout: {e}")


# Factory function
def create_backend_adapter(backend_client: Optional[BackendClient] = None) -> BackendMainScreenAdapter:
    """
    Create backend adapter instance.
    
    Args:
        backend_client: Optional backend client
        
    Returns:
        Backend adapter instance
    """
    return BackendMainScreenAdapter(backend_client)


# Legacy compatibility functions
def get_reccobeats_api():
    """Legacy compatibility function - returns backend service."""
    return ReccoBeatsBackendService()


def create_spotify_client_with_refresh(token_info: dict | None):
    """Legacy compatibility function - not used in backend mode."""
    return None


__all__ = [
    "BackendMainScreenAdapter",
    "create_backend_adapter",
    "get_reccobeats_api",
    "create_spotify_client_with_refresh",
]
