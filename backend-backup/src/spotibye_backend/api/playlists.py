"""Playlist API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth.middleware import get_spotify_token_info
from ..auth.oauth_handler import create_spotify_client_with_refresh
from ..config import get_settings
from ..logging_config import logger

router = APIRouter()
settings = get_settings()


# Pydantic models for request/response
class PlaylistResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    public: bool
    collaborative: bool
    owner: dict[str, Any]
    tracks: dict[str, Any]
    images: list[dict[str, Any]]
    followers: dict[str, Any]


class TrackResponse(BaseModel):
    id: str
    name: str
    artists: list[dict[str, Any]]
    album: dict[str, Any]
    duration_ms: int
    explicit: bool
    external_urls: dict[str, str]
    uri: str


def get_spotify_client(token_info: dict[str, Any] | None = None) -> Any:
    """Get authenticated Spotify client."""
    if not token_info:
        raise HTTPException(status_code=401, detail="Authentication required")

    sp = create_spotify_client_with_refresh(token_info)
    if not sp:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return sp


@router.get("/playlists", response_model=list[PlaylistResponse])
async def get_user_playlists(
    token_info: dict[str, Any] | None = Depends(get_spotify_token_info),
) -> list[PlaylistResponse]:
    """Get current user's playlists."""
    try:
        sp = get_spotify_client(token_info)

        playlists = []
        results = sp.current_user_playlists()

        while results:
            for item in results["items"]:
                playlists.append(PlaylistResponse(**item))
            if results["next"]:
                results = sp.next(results)
            else:
                results = None

        logger.info(f"Retrieved {len(playlists)} playlists for user")
        return playlists

    except Exception as exc:
        logger.error(f"Error getting playlists: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve playlists: {exc!s}"
        )


@router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: str,
    token_info: dict[str, Any] | None = Depends(get_spotify_token_info),
) -> PlaylistResponse:
    """Get specific playlist by ID."""
    try:
        sp = get_spotify_client(token_info)

        playlist = sp.playlist(playlist_id)
        logger.info(f"Retrieved playlist: {playlist_id}")
        return PlaylistResponse(**playlist)

    except Exception as exc:
        logger.error(f"Error getting playlist {playlist_id}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve playlist: {exc!s}"
        )


@router.get("/playlists/{playlist_id}/tracks", response_model=list[TrackResponse])
async def get_playlist_tracks(
    playlist_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    token_info: dict[str, Any] | None = Depends(get_spotify_token_info),
) -> list[TrackResponse]:
    """Get tracks from a specific playlist."""
    try:
        sp = get_spotify_client(token_info)

        tracks = []
        results = sp.playlist_items(playlist_id, offset=offset, limit=limit)

        for item in results["items"]:
            if item["track"]:
                tracks.append(TrackResponse(**item["track"]))

        logger.info(f"Retrieved {len(tracks)} tracks from playlist {playlist_id}")
        return tracks

    except Exception as exc:
        logger.error(f"Error getting tracks from playlist {playlist_id}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve tracks: {exc!s}"
        )


@router.get("/user/profile")
async def get_user_profile(
    token_info: dict[str, Any] | None = Depends(get_spotify_token_info),
) -> dict[str, Any]:
    """Get current user's profile information."""
    try:
        sp = get_spotify_client(token_info)

        user = sp.current_user()
        logger.info(f"Retrieved user profile: {user.get('id', 'unknown')}")
        return user

    except Exception as exc:
        logger.error(f"Error getting user profile: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve user profile: {exc!s}"
        )


__all__ = ["router"]
