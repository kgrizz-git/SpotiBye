"""Resumable export state machine mixin for BackendMainScreenAdapter."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError


class ExportsResumableMixin:
    """Resumable batch export job orchestration."""

    def _validate_resumable_job_fields(
        self, job: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract and validate required fields from resumable job response."""
        job_id = str(job.get("job_id") or "")
        cursor = str(job.get("current_cursor") or "")
        resume_token = str(job.get("current_resume_token") or "")
        if not job_id or not cursor or not resume_token:
            logger.warning("Resumable export job response missing required fields")
            return None, None, None
        return job_id, cursor, resume_token

    def _is_job_complete(self, status: Dict[str, Any]) -> bool:
        """Check if the resumable job has completed."""
        status_name = str(status.get("status", ""))
        return status_name == "completed" or not bool(
            status.get("continuation_required", True)
        )

    def _attempt_transient_error_recovery(
        self,
        job_id: str,
        cursor: str,
        resume_token: str,
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """Attempt to recover from transient errors by polling job status."""
        try:
            latest_status = self.backend_client.get_export_job_status(job_id)
            if isinstance(latest_status, dict):
                new_cursor = str(latest_status.get("current_cursor") or cursor)
                new_token = str(
                    latest_status.get("current_resume_token") or resume_token
                )
                self._persist_active_export_job(
                    latest_status, playlist_ids, format, resume_context
                )

                if self._is_job_complete(latest_status):
                    self._emit_progress(
                        "Resumable export completed after backend status recovery"
                    )
                    return latest_status, new_cursor, new_token
        except BackendAPIError:
            pass
        return None, cursor, resume_token

    def _handle_conflict_error(
        self,
        e: BackendAPIError,
        job_id: str,
        cursor: str,
        resume_token: str,
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Handle 409 conflict errors by syncing to latest cursor/token."""
        if isinstance(e.response_data, dict):
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
                return str(latest_cursor), str(latest_token)
            else:
                status = self.backend_client.get_export_job_status(job_id)
                new_cursor = str(status.get("current_cursor") or cursor)
                new_token = str(status.get("current_resume_token") or resume_token)
                self._persist_active_export_job(
                    status, playlist_ids, format, resume_context
                )
                return new_cursor, new_token
        return cursor, resume_token

    def _execute_export_step(
        self,
        job_id: str,
        cursor: str,
        resume_token: str,
        chunk_size: int,
    ) -> Dict[str, Any]:
        """Execute a single export job step with retry logic."""
        return self._run_with_transient_retry(
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

    def _update_export_progress(
        self, status: Dict[str, Any], playlist_ids: List[str]
    ) -> None:
        """Update progress display based on current job status."""
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

    def _update_cursor_and_token(
        self, status: Dict[str, Any], cursor: str, resume_token: str
    ) -> Tuple[str, str]:
        """Update cursor and resume token from status response."""
        new_cursor = str(status.get("current_cursor") or cursor)
        new_token = str(status.get("current_resume_token") or resume_token)
        return new_cursor, new_token

    def _persist_completed_job(
        self,
        status: Dict[str, Any],
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Persist and return a completed status, or signal that work remains."""
        if not self._is_job_complete(status):
            return None
        self._persist_active_export_job(status, playlist_ids, format, resume_context)
        return status

    def _recover_from_step_error(
        self,
        error: BackendAPIError,
        job_id: str,
        cursor: str,
        resume_token: str,
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], str, str]:
        """Recover from retryable or conflict errors raised by an export step."""
        if error.status_code in {500, 502, 503, 504, None}:
            recovered_status, new_cursor, new_token = (
                self._attempt_transient_error_recovery(
                    job_id,
                    cursor,
                    resume_token,
                    playlist_ids,
                    format,
                    resume_context,
                )
            )
            if recovered_status:
                return recovered_status, new_cursor or cursor, new_token or resume_token
            raise error

        if error.status_code == 409:
            new_cursor, new_token = self._handle_conflict_error(
                error,
                job_id,
                cursor,
                resume_token,
                playlist_ids,
                format,
                resume_context,
            )
            time.sleep(0.2)
            return None, new_cursor or cursor, new_token or resume_token

        raise error

    def _run_export_step_or_recover(
        self,
        job_id: str,
        cursor: str,
        resume_token: str,
        playlist_ids: List[str],
        format: str,
        chunk_size: int,
        resume_context: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], str, str]:
        """Run one export step, returning recovered state when necessary."""
        try:
            status = self._execute_export_step(job_id, cursor, resume_token, chunk_size)
        except BackendAPIError as error:
            return self._recover_from_step_error(
                error,
                job_id,
                cursor,
                resume_token,
                playlist_ids,
                format,
                resume_context,
            )
        return status, cursor, resume_token

    def _record_step_progress(
        self,
        status: Dict[str, Any],
        cursor: str,
        resume_token: str,
        playlist_ids: List[str],
        format: str,
        resume_context: Optional[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """Update UI and persist the cursor state after a successful step."""
        self._update_export_progress(status, playlist_ids)
        cursor, resume_token = self._update_cursor_and_token(
            status, cursor, resume_token
        )
        self._persist_active_export_job(status, playlist_ids, format, resume_context)
        return cursor, resume_token

    def _poll_job_completion(
        self,
        job_id: str,
        cursor: str,
        resume_token: str,
        playlist_ids: List[str],
        format: str,
        chunk_size: int,
        max_steps: int,
        resume_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Poll the job until completion or max steps reached."""
        status = {
            "job_id": job_id,
            "current_cursor": cursor,
            "current_resume_token": resume_token,
        }

        for _ in range(max_steps):
            if not isinstance(status, dict):
                return None
            completed_status = self._persist_completed_job(
                status, playlist_ids, format, resume_context
            )
            if completed_status:
                return completed_status

            status, cursor, resume_token = self._run_export_step_or_recover(
                job_id,
                cursor,
                resume_token,
                playlist_ids,
                format,
                chunk_size,
                resume_context,
            )
            if status is None:
                continue

            if not isinstance(status, dict):
                return None

            cursor, resume_token = self._record_step_progress(
                status,
                cursor,
                resume_token,
                playlist_ids,
                format,
                resume_context,
            )
            time.sleep(0.35)

        logger.error("Resumable export reached max steps without completion")
        return status

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

            job_id, cursor, resume_token = self._validate_resumable_job_fields(job)
            if not job_id:
                return None

            self._persist_active_export_job(job, playlist_ids, format, resume_context)

            status = self._poll_job_completion(
                job_id,
                cursor if cursor else "",
                resume_token if resume_token else "",
                playlist_ids,
                format,
                chunk_size,
                max_steps,
                resume_context,
            )

            if status and self._is_job_complete(status):
                return status

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
            logger.error("Error generating resumable batch export: %s", e)
            if report_errors and self.error_callback:
                self.error_callback(f"Resumable export failed: {str(e)}")
            return None
