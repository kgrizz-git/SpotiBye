"""Playlist API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth.oauth_handler import create_spotify_client_with_refresh
from ..auth.middleware import get_spotify_token_info
from ..config import get_settings
from ..logging_config import logger

router = APIRouter()
settings = get_settings()


# Pydantic models for request/response
class PlaylistResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    public: bool
    collaborative: bool
    owner: Dict[str, Any]
    tracks: Dict[str, Any]
    images: List[Dict[str, Any]]
    followers: Dict[str, Any]


class TrackResponse(BaseModel):
    id: str
    name: str
    artists: List[Dict[str, Any]]
    album: Dict[str, Any]
    duration_ms: int
    explicit: bool
    external_urls: Dict[str, str]
    uri: str


def get_spotify_client(token_info: Optional[Dict[str, Any]] = None) -> Any:
    """Get authenticated Spotify client."""
    if not token_info:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    sp = create_spotify_client_with_refresh(token_info)
    if not sp:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    return sp


@router.get("/playlists", response_model=List[PlaylistResponse])
async def get_user_playlists(
    token_info: Optional[Dict[str, Any]] = Depends(get_spotify_token_info)
) -> List[PlaylistResponse]:
    """Get current user's playlists."""
    try:
        sp = get_spotify_client(token_info)
        
        playlists = []
        results = sp.current_user_playlists()
        
        while results:
            for item in results['items']:
                playlists.append(PlaylistResponse(**item))
            if results['next']:
                results = sp.next(results)
            else:
                results = None
        
        logger.info(f"Retrieved {len(playlists)} playlists for user")
        return playlists
        
    except Exception as exc:
        logger.error(f"Error getting playlists: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve playlists: {str(exc)}")


@router.get("/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: str,
    token_info: Optional[Dict[str, Any]] = Depends(get_spotify_token_info)
) -> PlaylistResponse:
    """Get specific playlist by ID."""
    try:
        sp = get_spotify_client(token_info)
        
        playlist = sp.playlist(playlist_id)
        logger.info(f"Retrieved playlist: {playlist_id}")
        return PlaylistResponse(**playlist)
        
    except Exception as exc:
        logger.error(f"Error getting playlist {playlist_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve playlist: {str(exc)}")


@router.get("/playlists/{playlist_id}/tracks", response_model=List[TrackResponse])
async def get_playlist_tracks(
    playlist_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    token_info: Optional[Dict[str, Any]] = Depends(get_spotify_token_info)
) -> List[TrackResponse]:
    """Get tracks from a specific playlist."""
    try:
        sp = get_spotify_client(token_info)
        
        tracks = []
        results = sp.playlist_items(playlist_id, offset=offset, limit=limit)
        
        for item in results['items']:
            if item['track']:
                tracks.append(TrackResponse(**item['track']))
        
        logger.info(f"Retrieved {len(tracks)} tracks from playlist {playlist_id}")
        return tracks
        
    except Exception as exc:
        logger.error(f"Error getting tracks from playlist {playlist_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve tracks: {str(exc)}")


@router.get("/user/profile")
async def get_user_profile(
    token_info: Optional[Dict[str, Any]] = Depends(get_spotify_token_info)
) -> Dict[str, Any]:
    """Get current user's profile information."""
    try:
        sp = get_spotify_client(token_info)
        
        user = sp.current_user()
        logger.info(f"Retrieved user profile: {user.get('id', 'unknown')}")
        return user
        
    except Exception as exc:
        logger.error(f"Error getting user profile: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user profile: {str(exc)}")


__all__ = ["router"]
