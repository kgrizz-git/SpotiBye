"""Single/batch export mixin for BackendMainScreenAdapter."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError


class ExportsMixin:
    """Single-playlist and batch export orchestration."""

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
