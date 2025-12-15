"""Analysis task helpers and ReccoBeats cache coordination."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from ..logging_config import logger
from ..state import AnalysisTask, active_analysis_tasks
from .persistent_cache import persistent_cache


def get_cached_playlist_analysis(playlist_id: str) -> Optional[Dict[str, Any]]:
    """Get cached analysis data for a playlist."""
    return persistent_cache.get_cached_analysis_data(playlist_id, 'combined')


def cache_playlist_analysis(
    playlist_id: str,
    spotify_data: Optional[Dict[str, Any]] = None,
    reccobeats_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Cache analysis data for a playlist with persistent storage."""
    try:
        existing_data = persistent_cache.get_cached_analysis_data(playlist_id, 'combined') or {
            'spotify': None,
            'reccobeats': None,
            'timestamp': time.time(),
        }

        if spotify_data is not None:
            existing_data['spotify'] = spotify_data
            existing_data['timestamp'] = time.time()

        if reccobeats_data is not None:
            existing_data['reccobeats'] = reccobeats_data
            existing_data['timestamp'] = time.time()

        persistent_cache.cache_analysis_data(playlist_id, existing_data, 'combined')

        sources = []
        if spotify_data is not None:
            sources.append('spotify')
        if reccobeats_data is not None:
            sources.append('reccobeats')
        if not sources:
            for key in ('spotify', 'reccobeats'):
                if existing_data.get(key):
                    sources.append(key)
        if not sources:
            sources.append('unknown')

        logger.info(
            "Cached analysis data for playlist: %s (sources: %s)",
            playlist_id,
            ", ".join(sources),
        )

    except Exception as exc:
        logger.error("Error caching analysis data: %s", exc)


def cleanup_analysis_task(playlist_id: str) -> None:
    if playlist_id in active_analysis_tasks:
        del active_analysis_tasks[playlist_id]


__all__ = [
    "get_cached_playlist_analysis",
    "cache_playlist_analysis", 
    "cleanup_analysis_task",
]
