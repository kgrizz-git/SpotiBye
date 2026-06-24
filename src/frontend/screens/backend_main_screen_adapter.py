"""Backend integration adapter for existing MainScreen to use backend services."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from kivy.clock import Clock, mainthread

from ..services.backend_client import BackendClient, BackendAPIError
from ..services.reccobeats_backend import ReccoBeatsBackendService
from ..caching.backend_cache import get_cache_manager
from ..utils.network_utils import NetworkStatusMonitor, format_error_message
from ...shared.logging_config import logger


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
        self.playlists_loaded_callback: Optional[Callable[..., Any]] = None
        self.error_callback: Optional[Callable[..., Any]] = None
        self.progress_callback: Optional[Callable[..., Any]] = None
        self._export_circuit_open_until: float = 0.0
        self._export_circuit_reason: str = ""

    def set_callbacks(
        self,
        playlists_loaded: Optional[Callable[..., Any]] = None,
        error: Optional[Callable[..., Any]] = None,
        progress: Optional[Callable[..., Any]] = None,
    ) -> None:
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

    def set_trace_id(self, trace_id: Optional[str]) -> None:
        """Set per-export trace ID propagated by backend client."""
        self.backend_client.set_trace_id(trace_id)

    def _emit_progress(self, message: str) -> None:
        """Send progress to UI and terminal logs."""
        # MainScreen logs progress with trace context; avoid duplicate adapter-side logs.
        if self.progress_callback:
            self.progress_callback(message)

    def _format_backend_api_error(
        self, error: BackendAPIError, fallback_prefix: str
    ) -> str:
        """Build a user-visible message with backend error code/message/request id when available."""
        status = (
            f"HTTP {error.status_code}"
            if error.status_code is not None
            else "HTTP error"
        )
        message = str(error)

        error_payload = {}
        if isinstance(error.response_data, dict):
            maybe_error = error.response_data.get("error")
            if isinstance(maybe_error, dict):
                error_payload = maybe_error

        code = error_payload.get("code")
        request_id = error_payload.get("request_id")
        details_payload = (
            error_payload.get("details")
            if isinstance(error_payload.get("details"), dict)
            else {}
        )

        source = "backend" if error.status_code is not None else "transport"
        if isinstance(error.response_data, dict):
            source = str(error.response_data.get("origin", source))

        upstream = details_payload.get("upstream")
        upstream_status = details_payload.get("upstream_status")

        parts = [fallback_prefix, status]
        parts.append(f"source={source}")
        if code:
            parts.append(f"code={code}")
        if upstream:
            parts.append(f"upstream={upstream}")
        if upstream_status:
            parts.append(f"upstream_status={upstream_status}")
        parts.append(message)
        if request_id:
            parts.append(f"request_id={request_id}")

        return " | ".join(parts)

    def _run_with_transient_retry(
        self,
        operation_name: str,
        func: callable,
        max_attempts: int = 4,
        base_delay: float = 1.0,
    ):
        """Run an operation with retry/backoff for transient backend failures."""
        retryable_statuses = {429, 500, 502, 503, 504}
        last_error: Optional[Exception] = None
        consecutive_503 = 0

        is_export_operation = (
            "export" in operation_name.lower() or "download" in operation_name.lower()
        )

        now = time.time()
        if is_export_operation and now < self._export_circuit_open_until:
            wait_secs = int(self._export_circuit_open_until - now)
            msg = f"Backend export temporarily cooling down ({wait_secs}s remaining): {self._export_circuit_reason}"
            raise BackendAPIError(msg, 503)

        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except BackendAPIError as e:
                last_error = e
                status = e.status_code
                is_retryable = status in retryable_statuses

                if status == 503:
                    consecutive_503 += 1
                else:
                    consecutive_503 = 0

                if is_export_operation and consecutive_503 >= 3:
                    self._export_circuit_open_until = time.time() + 25.0
                    self._export_circuit_reason = "repeated HTTP 503 responses"
                    raise BackendAPIError(
                        "Backend export service is unstable (repeated 503). Cooling down for 25s before next attempt.",
                        503,
                        e.response_data,
                    )

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

    # Track management
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
            error_msg = self._format_backend_api_error(e, "Export generation failed")
            if self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error getting playlist tracks: {e}")
            if self.error_callback:
                self.error_callback(f"Failed to load tracks: {str(e)}")
            return None

    # Analysis management
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
            return {"status": "error", "error": str(e)}

    # Export management
    def generate_export(
        self,
        playlist_id: str,
        format: str = "xlsx",
        report_errors: bool = True,
        retry_attempts: int = 6,
        retry_base_delay: float = 1.5,
    ) -> Optional[Dict[str, Any]]:
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
                self._emit_progress("Generating export...")

            export_info = self._run_with_transient_retry(
                "Generating export",
                lambda: self.backend_client.generate_export(playlist_id, format),
                max_attempts=max(1, retry_attempts),
                base_delay=max(0.1, retry_base_delay),
            )

            # Cache export info
            self.cache_manager.cache_export_info(playlist_id, export_info)

            return export_info

        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, "Export generation failed")
            if report_errors and self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error generating export: {e}")
            if report_errors and self.error_callback:
                self.error_callback(f"Export failed: {str(e)}")
            return None

    def download_export(self, playlist_id: str, save_path: str) -> bool:
        """
        Download export file.

        Args:
            playlist_id: Spotify playlist ID
            save_path: Path to save the file

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.progress_callback:
                self._emit_progress("Downloading export...")

            export_data = self._run_with_transient_retry(
                "Downloading export",
                lambda: self.backend_client.download_export(playlist_id),
            )

            # Save to file
            with open(save_path, "wb") as f:
                f.write(export_data)

            logger.info(f"Export saved to {save_path}")
            return True

        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(e, "Export download failed")
            if self.error_callback:
                self.error_callback(error_msg)
            return False
        except Exception as e:
            logger.error(f"Error downloading export: {e}")
            if self.error_callback:
                self.error_callback(f"Download failed: {str(e)}")
            return False

    def generate_batch_export(
        self, playlist_ids: List[str], format: str = "xlsx"
    ) -> Optional[Dict[str, Any]]:
        """Generate a combined export for multiple playlists."""
        try:
            if self.progress_callback:
                self._emit_progress("Generating combined export...")

            export_info = self._run_with_transient_retry(
                "Generating combined export",
                lambda: self.backend_client.generate_batch_export(playlist_ids, format),
            )
            return export_info
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(
                e, "Chunked export generation failed"
            )
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
        format: str = "xlsx",
        chunk_size: int = 1,
        max_steps: int = 600,
        report_errors: bool = True,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate combined export via resumable jobs, with legacy chunk fallback."""
        resumable_result = self._generate_batch_export_resumable(
            playlist_ids=playlist_ids,
            format=format,
            chunk_size=chunk_size,
            max_steps=max_steps,
            report_errors=False,
            resume_context=resume_context,
        )
        if resumable_result:
            return resumable_result

        logger.info(
            "Resumable export unavailable or failed; falling back to legacy chunked endpoint"
        )

        try:
            if self.progress_callback:
                self._emit_progress("Generating combined export (chunked)...")

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
                job_id = str(status.get("job_id") or job_id or "")
                cursor = int(status.get("next_cursor", cursor))
                processed = int(status.get("processed_count", 0))
                total = int(status.get("playlist_count", len(playlist_ids)))

                self._emit_progress(
                    f"Chunked export progress: {processed}/{total} playlists"
                )

                if status.get("status") == "completed" or not status.get(
                    "continuation_required", False
                ):
                    return status

                # Small delay to avoid sustained pressure on backend/upstream during large runs.
                time.sleep(0.5)

            logger.error("Chunked batch export reached max steps without completion")
            if report_errors and self.error_callback:
                self.error_callback("Chunked export timed out before completion")
            return last_status
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(
                e, "Combined export generation failed"
            )
            if report_errors and self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error generating chunked batch export: {e}")
            if report_errors and self.error_callback:
                self.error_callback(f"Chunked export failed: {str(e)}")
            return None

    def _generate_batch_export_resumable(
        self,
        playlist_ids: List[str],
        format: str = "xlsx",
        chunk_size: int = 1,
        max_steps: int = 600,
        report_errors: bool = True,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate combined export through resumable job endpoints."""
        try:
            if self.progress_callback:
                self._emit_progress("Generating combined export (resumable)...")

            job = self._load_or_create_resumable_job(
                playlist_ids, format, resume_context
            )
            if not isinstance(job, dict):
                return None

            job_id = str(job.get("job_id") or "")
            cursor = str(job.get("current_cursor") or "")
            resume_token = str(job.get("current_resume_token") or "")
            if not job_id or not cursor or not resume_token:
                logger.warning("Resumable export job response missing required fields")
                return None

            self._persist_active_export_job(job, playlist_ids, format, resume_context)

            status = job
            for _ in range(max_steps):
                status_name = str(status.get("status", ""))
                if status_name == "completed" or not bool(
                    status.get("continuation_required", True)
                ):
                    self._persist_active_export_job(
                        status, playlist_ids, format, resume_context
                    )
                    return status

                try:
                    status = self._run_with_transient_retry(
                        "Processing export job step",
                        lambda: self.backend_client.step_export_job(
                            job_id=job_id,
                            cursor=cursor,
                            resume_token=resume_token,
                            max_playlists_per_step=chunk_size,
                        ),
                        max_attempts=4,
                        base_delay=1.0,
                    )
                except BackendAPIError as e:
                    # The backend persists resumable job state before some finalization work.
                    # A timeout/503 here can still mean the job actually completed server-side,
                    # so poll status once before abandoning the resumable path.
                    if e.status_code in {500, 502, 503, 504, None}:
                        try:
                            latest_status = self.backend_client.get_export_job_status(
                                job_id
                            )
                            if isinstance(latest_status, dict):
                                status = latest_status
                                cursor = str(status.get("current_cursor") or cursor)
                                resume_token = str(
                                    status.get("current_resume_token") or resume_token
                                )
                                self._persist_active_export_job(
                                    status, playlist_ids, format, resume_context
                                )

                                if str(
                                    status.get("status", "")
                                ) == "completed" or not bool(
                                    status.get("continuation_required", True)
                                ):
                                    self._emit_progress(
                                        "Resumable export completed after backend status recovery"
                                    )
                                    return status
                        except BackendAPIError:
                            pass

                    if e.status_code == 409 and isinstance(e.response_data, dict):
                        details = (
                            e.response_data.get("error", {}).get("details", {})
                            if isinstance(e.response_data.get("error"), dict)
                            else {}
                        )
                        latest_cursor = details.get("latest_cursor")
                        latest_token = details.get("latest_resume_token")
                        logger.warning(
                            "Resumable export conflict encountered; syncing to latest cursor/token"
                        )

                        if latest_cursor and latest_token:
                            cursor = str(latest_cursor)
                            resume_token = str(latest_token)
                        else:
                            status = self.backend_client.get_export_job_status(job_id)
                            cursor = str(status.get("current_cursor") or cursor)
                            resume_token = str(
                                status.get("current_resume_token") or resume_token
                            )
                            self._persist_active_export_job(
                                status, playlist_ids, format, resume_context
                            )

                        time.sleep(0.2)
                        continue
                    raise

                if not isinstance(status, dict):
                    return None

                processed = int(status.get("processed_count", 0))
                total = int(status.get("playlist_count", len(playlist_ids)))
                phase = str(status.get("phase", "collect"))
                current_track_offset = int(status.get("current_track_offset", 0) or 0)
                if phase == "assemble":
                    assembled = int(status.get("assemble_index", 0) or 0)
                    self._emit_progress(
                        f"Resumable export progress ({phase}): assembled {assembled}/{total} playlists"
                    )
                else:
                    self._emit_progress(
                        f"Resumable export progress ({phase}): {processed}/{total} playlists, current track offset {current_track_offset}"
                    )

                cursor = str(status.get("current_cursor") or cursor)
                resume_token = str(status.get("current_resume_token") or resume_token)
                self._persist_active_export_job(
                    status, playlist_ids, format, resume_context
                )

                time.sleep(0.35)

            logger.error("Resumable export reached max steps without completion")
            if report_errors and self.error_callback:
                self.error_callback("Resumable export timed out before completion")
            return status
        except BackendAPIError as e:
            if e.status_code == 404:
                logger.info("Resumable export endpoints not available on backend")
                return None

            if e.status_code == 409 and isinstance(e.response_data, dict):
                details = (
                    e.response_data.get("error", {}).get("details", {})
                    if isinstance(e.response_data.get("error"), dict)
                    else {}
                )
                latest_cursor = details.get("latest_cursor")
                latest_token = details.get("latest_resume_token")
                if latest_cursor and latest_token:
                    logger.warning(
                        "Resumable export conflict encountered; retry will resume with backend-provided cursor/token"
                    )

            error_msg = self._format_backend_api_error(
                e, "Resumable export generation failed"
            )
            if report_errors and self.error_callback:
                self.error_callback(error_msg)
            return None
        except Exception as e:
            logger.error(f"Error generating resumable batch export: {e}")
            if report_errors and self.error_callback:
                self.error_callback(f"Resumable export failed: {str(e)}")
            return None

    def download_batch_export(
        self, export_id: str, save_path: str, report_errors: bool = True
    ) -> bool:
        """Download combined export file."""
        try:
            if self.progress_callback:
                self._emit_progress("Downloading combined export...")

            preferred_mode = "auto"
            try:
                status = self.backend_client.get_export_job_status(export_id)
                hint = (
                    str(status.get("render_mode_hint", "auto"))
                    if isinstance(status, dict)
                    else "auto"
                )
                if hint in {"rich", "lite"}:
                    preferred_mode = hint
                    if hint == "lite":
                        self._emit_progress(
                            "Large export reliability mode detected; downloading lite-rendered combined file..."
                        )
            except BackendAPIError:
                # Status endpoint may be temporarily unavailable; continue with default auto mode.
                pass

            for recovery_pass in range(2):
                try:
                    export_data = self._run_with_transient_retry(
                        "Downloading combined export",
                        lambda mode=preferred_mode: self._download_batch_export_any(
                            export_id, mode=mode
                        ),
                        max_attempts=6,
                        base_delay=2.0,
                    )
                    with open(save_path, "wb") as f:
                        f.write(export_data)

                    logger.info(f"Combined export saved to {save_path}")
                    self.clear_active_export_job(export_id)
                    return True
                except BackendAPIError as e:
                    can_recover = e.status_code in {409, 500, 502, 503, 504, None}
                    if not can_recover or recovery_pass >= 1:
                        raise

                    self._emit_progress(
                        "Combined download not ready yet; checking job status and retrying..."
                    )
                    try:
                        status = self.backend_client.get_export_job_status(export_id)
                        if isinstance(status, dict):
                            playlist_ids = [
                                str(pid)
                                for pid in list(status.get("playlist_ids") or [])
                                if isinstance(pid, str) and pid
                            ]
                            export_format = str(status.get("file_format") or "xlsx")
                            self._persist_active_export_job(
                                status, playlist_ids, export_format
                            )

                            status_name = str(status.get("status", ""))
                            continuation_required = bool(
                                status.get("continuation_required", True)
                            )
                            render_hint = str(
                                status.get("render_mode_hint", preferred_mode)
                            )
                            if render_hint in {"rich", "lite"}:
                                preferred_mode = render_hint
                            if (
                                status_name != "completed"
                                and continuation_required
                                and playlist_ids
                            ):
                                self._emit_progress(
                                    "Resuming combined export job before download retry..."
                                )
                                resumed_status = self._generate_batch_export_resumable(
                                    playlist_ids=playlist_ids,
                                    format=export_format,
                                    chunk_size=1,
                                    max_steps=240,
                                    report_errors=False,
                                    resume_context={"allow_resume": True},
                                )
                                if isinstance(resumed_status, dict):
                                    self._persist_active_export_job(
                                        resumed_status, playlist_ids, export_format
                                    )
                                    resumed_hint = str(
                                        resumed_status.get(
                                            "render_mode_hint", preferred_mode
                                        )
                                    )
                                    if resumed_hint in {"rich", "lite"}:
                                        preferred_mode = resumed_hint
                    except BackendAPIError as status_err:
                        logger.warning(
                            "Combined download recovery status check failed: %s",
                            status_err,
                        )

                    # Last-chance deterministic downgrade for large exports: explicit lite mode.
                    if recovery_pass == 0 and preferred_mode != "lite":
                        preferred_mode = "lite"
                        self._emit_progress(
                            "Retrying combined download in lightweight render mode..."
                        )

                    time.sleep(3.0)

            return False
        except BackendAPIError as e:
            error_msg = self._format_backend_api_error(
                e, "Combined export download failed"
            )
            if report_errors and self.error_callback:
                self.error_callback(error_msg)
            return False
        except Exception as e:
            logger.error(f"Error downloading combined export: {e}")
            if report_errors and self.error_callback:
                self.error_callback(f"Combined download failed: {str(e)}")
            return False

    def get_active_export_job(self) -> Optional[Dict[str, Any]]:
        """Return cached resumable export job metadata, if any."""
        return self.cache_manager.get_active_export_job()

    def _download_batch_export_any(self, export_id: str, mode: str = "auto") -> bytes:
        """Download from resumable job endpoint first, then legacy batch endpoint."""
        try:
            return self.backend_client.download_export_job(export_id, mode=mode)
        except BackendAPIError as e:
            if e.status_code == 404:
                return self.backend_client.download_batch_export(export_id)
            raise

    def _load_or_create_resumable_job(
        self,
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load matching cached resumable job from local cache or create a new one."""
        allow_resume = bool((resume_context or {}).get("allow_resume"))
        cached_job = (
            self._get_matching_active_export_job(playlist_ids, format, resume_context)
            if allow_resume
            else None
        )
        if cached_job:
            self._emit_progress("Resuming previous export job...")
            try:
                return self.backend_client.get_export_job_status(
                    str(cached_job.get("job_id") or "")
                )
            except BackendAPIError as e:
                if e.status_code != 404:
                    raise
                self.clear_active_export_job()

        return self._run_with_transient_retry(
            "Creating export job",
            lambda: self.backend_client.create_export_job(playlist_ids, format),
            max_attempts=3,
            base_delay=1.0,
        )

    def _persist_active_export_job(
        self,
        status: Dict[str, Any],
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist active resumable export job metadata for restart recovery."""
        if not isinstance(status, dict):
            return

        payload: Dict[str, Any] = {
            "job_id": status.get("job_id"),
            "playlist_ids": list(playlist_ids),
            "format": format,
            "current_cursor": status.get("current_cursor"),
            "current_resume_token": status.get("current_resume_token"),
            "status": status.get("status"),
            "phase": status.get("phase"),
            "continuation_required": status.get("continuation_required", True),
            "current_track_offset": status.get("current_track_offset", 0),
            "processed_count": status.get("processed_count", 0),
            "playlist_count": status.get("playlist_count", len(playlist_ids)),
            "trace_id": self.backend_client.trace_id,
            "updated_at": time.time(),
        }
        if isinstance(resume_context, dict):
            payload["output_path"] = resume_context.get("output_path")
            payload["playlist_names"] = resume_context.get("playlist_names")

        self.cache_manager.cache_active_export_job(payload)

    def _get_matching_active_export_job(
        self,
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return cached active export job when it matches the current export request."""
        cached_job = self.cache_manager.get_active_export_job()
        if not isinstance(cached_job, dict):
            return None

        if str(cached_job.get("format") or "") != format:
            return None

        if list(cached_job.get("playlist_ids") or []) != list(playlist_ids):
            return None

        if isinstance(resume_context, dict):
            cached_output_path = cached_job.get("output_path")
            current_output_path = resume_context.get("output_path")
            if (
                cached_output_path
                and current_output_path
                and str(cached_output_path) != str(current_output_path)
            ):
                return None

        cached_job_id = str(cached_job.get("job_id") or "")
        cached_cursor = str(cached_job.get("current_cursor") or "")
        cached_token = str(cached_job.get("current_resume_token") or "")
        if not cached_job_id or not cached_cursor or not cached_token:
            return None

        return cached_job

    def clear_active_export_job(self, export_id: Optional[str] = None) -> None:
        """Clear persisted active resumable export job metadata."""
        cached_job = self.cache_manager.get_active_export_job()
        if export_id and isinstance(cached_job, dict):
            cached_job_id = str(cached_job.get("job_id") or "")
            if cached_job_id and cached_job_id != export_id:
                return
        self.cache_manager.clear_active_export_job()

    # Utility methods
    def get_network_status(self) -> Dict[str, Any]:
        """Get current network status."""
        return {
            "connected": self.network_monitor.is_connected(),
            "message": self.network_monitor.get_status_message(),
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
            if cache_type == "playlists":
                self.cache_manager.clear_cache("playlists.json")
            elif cache_type == "tracks":
                self.cache_manager.clear_cache("tracks_*.json")
            elif cache_type == "analysis":
                self.cache_manager.clear_cache("analysis_*.json")
            elif cache_type == "export":
                self.cache_manager.clear_cache("export_*.json")
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
def create_backend_adapter(
    backend_client: Optional[BackendClient] = None,
) -> BackendMainScreenAdapter:
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
