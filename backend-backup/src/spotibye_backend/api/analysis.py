"""Analysis API endpoints for track analysis and ReccoBeats integration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ..auth.oauth_handler import create_spotify_client_with_refresh
from ..caching.analysis import (
    AnalysisTask,
    cache_playlist_analysis,
    get_cached_playlist_analysis,
)
from ..config import get_settings
from ..logging_config import logger
from ..services.reccobeats import ReccoBeatsAPI

router = APIRouter()
settings = get_settings()


# Pydantic models
class AudioFeaturesResponse(BaseModel):
    danceability: float
    energy: float
    key: int
    loudness: float
    mode: int
    speechiness: float
    acousticness: float
    instrumentalness: float
    liveness: float
    valence: float
    tempo: float
    type: str
    id: str
    uri: str
    track_href: str
    analysis_url: str
    duration_ms: int
    time_signature: int


class AnalysisRequest(BaseModel):
    playlist_id: str
    include_reccobeats: bool = True


class AnalysisStatusResponse(BaseModel):
    playlist_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    progress: float | None = None
    message: str | None = None
    spotify_data: dict[str, Any] | None = None
    reccobeats_data: dict[str, Any] | None = None


def get_spotify_client(token_info: dict[str, Any] | None = None) -> Any:
    """Get authenticated Spotify client."""
    if not token_info:
        raise HTTPException(status_code=401, detail="Authentication required")

    sp = create_spotify_client_with_refresh(token_info)
    if not sp:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return sp


@router.post("/analysis/start", response_model=dict[str, str])
async def start_playlist_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    token_info: dict[str, Any] | None = Depends(lambda: None),
) -> dict[str, str]:
    """Start analysis of a playlist in the background."""
    try:
        playlist_id = request.playlist_id

        # Check if analysis is already running
        if playlist_id in AnalysisTask.active_analysis_tasks:
            raise HTTPException(
                status_code=409, detail="Analysis already in progress for this playlist"
            )

        # Start background analysis
        background_tasks.add_task(
            analyze_playlist_background,
            playlist_id,
            request.include_reccobeats,
            token_info,
        )

        logger.info(f"Started analysis for playlist: {playlist_id}")
        return {"message": "Analysis started", "playlist_id": playlist_id}

    except Exception as exc:
        logger.error(f"Error starting analysis: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start analysis: {exc!s}"
        )


@router.get("/analysis/{playlist_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(playlist_id: str) -> AnalysisStatusResponse:
    """Get status of playlist analysis."""
    try:
        # Check if analysis is active
        if playlist_id in AnalysisTask.active_analysis_tasks:
            task = AnalysisTask.active_analysis_tasks[playlist_id]
            return AnalysisStatusResponse(
                playlist_id=playlist_id,
                status="in_progress" if not task.cancelled else "cancelled",
                message="Analysis in progress",
            )

        # Check cached results
        cached_data = get_cached_playlist_analysis(playlist_id)
        if cached_data:
            return AnalysisStatusResponse(
                playlist_id=playlist_id,
                status="completed",
                spotify_data=cached_data.get("spotify"),
                reccobeats_data=cached_data.get("reccobeats"),
            )

        # No analysis found
        return AnalysisStatusResponse(
            playlist_id=playlist_id,
            status="not_found",
            message="No analysis found for this playlist",
        )

    except Exception as exc:
        logger.error(f"Error getting analysis status: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get analysis status: {exc!s}"
        )


@router.get("/analysis/{playlist_id}/results")
async def get_analysis_results(playlist_id: str) -> dict[str, Any]:
    """Get completed analysis results for a playlist."""
    try:
        cached_data = get_cached_playlist_analysis(playlist_id)
        if not cached_data:
            raise HTTPException(
                status_code=404, detail="No analysis found for this playlist"
            )

        return cached_data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error getting analysis results: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get analysis results: {exc!s}"
        )


@router.delete("/analysis/{playlist_id}")
async def cancel_analysis(playlist_id: str) -> dict[str, str]:
    """Cancel ongoing analysis for a playlist."""
    try:
        if playlist_id in AnalysisTask.active_analysis_tasks:
            task = AnalysisTask.active_analysis_tasks[playlist_id]
            task.cancel()
            logger.info(f"Cancelled analysis for playlist: {playlist_id}")
            return {"message": "Analysis cancelled", "playlist_id": playlist_id}
        else:
            raise HTTPException(
                status_code=404, detail="No active analysis found for this playlist"
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error cancelling analysis: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel analysis: {exc!s}"
        )


@router.get("/tracks/{track_id}/audio-features", response_model=AudioFeaturesResponse)
async def get_track_audio_features(
    track_id: str, token_info: dict[str, Any] | None = Depends(lambda: None)
) -> AudioFeaturesResponse:
    """Get audio features for a specific track."""
    try:
        sp = get_spotify_client(token_info)

        features = sp.audio_features([track_id])
        if not features or not features[0]:
            raise HTTPException(
                status_code=404, detail="Audio features not found for track"
            )

        logger.info(f"Retrieved audio features for track: {track_id}")
        return AudioFeaturesResponse(**features[0])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error getting audio features for track {track_id}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get audio features: {exc!s}"
        )


async def analyze_playlist_background(
    playlist_id: str, include_reccobeats: bool, token_info: dict[str, Any] | None
) -> None:
    """Background task to analyze playlist."""
    try:
        with AnalysisTask(playlist_id) as task:
            sp = get_spotify_client(token_info)

            # Get playlist tracks
            task.update_progress("Fetching playlist tracks...")
            results = sp.playlist_items(playlist_id)
            tracks = []

            while results:
                for item in results["items"]:
                    if item["track"] and not task.is_cancelled():
                        tracks.append(item["track"])

                if results["next"] and not task.is_cancelled():
                    results = sp.next(results)
                else:
                    results = None

            if task.is_cancelled():
                return

            # Get Spotify audio features
            task.update_progress("Analyzing Spotify audio features...")
            track_ids = [track["id"] for track in tracks if track["id"]]
            spotify_features = {}

            # Process in batches of 100 (Spotify API limit)
            batch_size = 100
            for i in range(0, len(track_ids), batch_size):
                if task.is_cancelled():
                    return

                batch_ids = track_ids[i : i + batch_size]
                features = sp.audio_features(batch_ids)

                for j, feature in enumerate(features):
                    if feature and batch_ids[j]:
                        spotify_features[batch_ids[j]] = feature

            # Get ReccoBeats analysis if requested
            reccobeats_features = {}
            if include_reccobeats and not task.is_cancelled():
                task.update_progress("Analyzing with ReccoBeats...")
                recco_api = ReccoBeatsAPI()
                reccobeats_features = recco_api.get_audio_features_batch(
                    track_ids, task
                )

            # Cache results
            if not task.is_cancelled():
                cache_playlist_analysis(
                    playlist_id,
                    spotify_data=spotify_features,
                    reccobeats_data=reccobeats_features,
                )
                logger.info(f"Completed analysis for playlist: {playlist_id}")

    except Exception as exc:
        logger.error(f"Error in background analysis: {exc}")
        # Cache error state
        cache_playlist_analysis(
            playlist_id,
            spotify_data={"error": str(exc)},
            reccobeats_data={"error": str(exc)},
        )


__all__ = ["router"]
