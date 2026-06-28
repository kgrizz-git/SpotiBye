"""Combined export download mixin for BackendMainScreenAdapter."""

from __future__ import annotations

import time

from ....shared.logging_config import logger
from ...services.backend_client import BackendAPIError


class ExportsDownloadMixin:
    """Combined/batch export download with recovery logic."""

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

    def _download_batch_export_any(self, export_id: str, mode: str = "auto") -> bytes:
        """Download from resumable job endpoint first, then legacy batch endpoint."""
        try:
            return self.backend_client.download_export_job(export_id, mode=mode)
        except BackendAPIError as e:
            if e.status_code == 404:
                return self.backend_client.download_batch_export(export_id)
            raise
