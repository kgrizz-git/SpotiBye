"""Export job persistence mixin for BackendMainScreenAdapter."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ...services.backend_client import BackendAPIError


class ExportJobsMixin:
    """Resumable export job state persistence and loading."""

    def get_active_export_job(self) -> Optional[Dict[str, Any]]:
        """Return cached resumable export job metadata, if any."""
        return self.cache_manager.get_active_export_job()

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
