"""State management for SpotiBye backend."""

from __future__ import annotations

# Global state for tracking active analysis tasks
active_analysis_tasks: dict[str, AnalysisTask] = {}


class AnalysisTask:
    """Track and manage playlist analysis tasks."""

    def __init__(self, playlist_id: str):
        self.playlist_id = playlist_id
        self.cancelled = False
        self.spotify_data: dict[str, any] | None = None
        self.reccobeats_data: dict[str, any] | None = None
        self.created_at = None
        self.updated_at = None

    def is_cancelled(self) -> bool:
        """Check if the task has been cancelled."""
        return self.cancelled

    def cancel(self) -> None:
        """Cancel the analysis task."""
        self.cancelled = True

    def update_progress(self, message: str) -> None:
        """Update progress message."""
        from ..logging_config import logger

        logger.info(f"Analysis task {self.playlist_id}: {message}")

    def __enter__(self):
        """Context manager entry."""
        active_analysis_tasks[self.playlist_id] = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.playlist_id in active_analysis_tasks:
            del active_analysis_tasks[self.playlist_id]


__all__ = ["AnalysisTask", "active_analysis_tasks"]
