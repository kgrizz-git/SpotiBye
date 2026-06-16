"""Shared mutable state for the backend-integrated frontend."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

current_export_job: Optional[Dict[str, Any]] = None


def set_current_export_job(
    *,
    job_id: str,
    playlist_ids: List[str],
    export_format: str,
    output_path: str,
) -> Dict[str, Any]:
    """Initialize the current export job state."""
    global current_export_job
    current_export_job = {
        "job_id": job_id,
        "playlist_ids": list(playlist_ids),
        "format": export_format,
        "output_path": output_path,
        "cancelled": False,
    }
    return current_export_job


def get_current_export_job() -> Optional[Dict[str, Any]]:
    """Return the current export job state if any."""
    return current_export_job


def mark_current_export_cancelled() -> bool:
    """Mark the current job as cancelled. Returns True if a job was marked."""
    global current_export_job
    if not current_export_job:
        return False
    current_export_job["cancelled"] = True
    return True


def clear_current_export_job() -> None:
    """Clear the current export job state."""
    global current_export_job
    current_export_job = None
