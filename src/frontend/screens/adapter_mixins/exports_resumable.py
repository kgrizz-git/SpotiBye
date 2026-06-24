"""Resumable export state machine mixin for BackendMainScreenAdapter."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError


class ExportsResumableMixin:
    """Resumable batch export job orchestration."""

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
