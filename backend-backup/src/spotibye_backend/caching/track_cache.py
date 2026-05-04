"""Helpers for per-track Spotify and ReccoBeats caching."""

from __future__ import annotations

from typing import Any

from ..logging_config import logger
from .persistent_cache import persistent_cache


def normalize_spotify_track(track: dict[str, Any]) -> dict[str, Any]:
    """Flatten Spotify track payload into a normalized structure."""
    track_id = track.get("id", "")
    artists = track.get("artists", []) or []
    artist_names = [artist.get("name", "") for artist in artists]
    artist_ids = [artist.get("id") for artist in artists if artist.get("id")]

    album = track.get("album", {}) or {}
    duration_ms = track.get("duration_ms", 0) or 0

    normalized = {
        "id": track_id,
        "name": track.get("name", ""),
        "title": track.get("name", ""),
        "artists": artist_names,
        "artist_ids": artist_ids,
        "album": album.get("name", ""),
        "album_id": album.get("id"),
        "duration_ms": duration_ms,
        "popularity": track.get("popularity", 0),
        "explicit": track.get("explicit", False),
        "spotify_url": track.get("external_urls", {}).get("spotify", ""),
        "spotify_uri": track.get("uri", ""),
        "source": "spotify",
    }

    added_at = track.get("added_at")
    if added_at:
        normalized["added_at"] = added_at

    return normalized


def cache_spotify_track(track_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Persist a Spotify track payload and return the normalized view."""
    track_id = track_payload.get("id")
    if not track_id:
        return None

    normalized = normalize_spotify_track(track_payload)
    persistent_cache.cache_track_data(track_id, "spotify", track_payload, normalized)
    # logger.info(
    #     "Cached Spotify track %s • title='%s' • artists=%s",
    #     track_id,
    #     normalized.get('title', ''),
    #     normalized.get('artists', []),
    # )
    return normalized


def get_cached_spotify_track(spotify_id: str) -> dict[str, Any] | None:
    """Return normalized Spotify track data from cache if present."""
    cached_entry = persistent_cache.get_cached_track_data(spotify_id, "spotify")
    if not cached_entry:
        return None

    normalized = cached_entry.get("normalized")
    payload = cached_entry.get("payload")

    if normalized:
        # logger.debug(
        #     "Retrieved Spotify cache for %s • title='%s' • artists=%s",
        #     spotify_id,
        #     normalized.get('title', ''),
        #     normalized.get('artists', []),
        # )
        return normalized

    if payload:
        normalized = normalize_spotify_track(payload)
        persistent_cache.cache_track_data(spotify_id, "spotify", payload, normalized)
        logger.info(
            "Rehydrated Spotify cache for %s from payload • title='%s'",
            spotify_id,
            normalized.get("title", ""),
        )
        return normalized

    return None


def get_or_cache_spotify_track(track_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Retrieve normalized Spotify data, updating cache with the latest payload."""
    spotify_id = track_payload.get("id") if track_payload else None
    if not spotify_id:
        return None

    try:
        normalized = normalize_spotify_track(track_payload)
        persistent_cache.cache_track_data(
            spotify_id, "spotify", track_payload, normalized
        )
        return normalized
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to cache Spotify track %s: %s", spotify_id, exc)
        return get_cached_spotify_track(spotify_id)


def cache_reccobeats_features(spotify_id: str, features: dict[str, Any]) -> None:
    """Persist ReccoBeats payload for a track with source labelling."""
    if not spotify_id or not isinstance(features, dict):
        return

    payload = dict(features)
    payload.setdefault("spotify_id", spotify_id)
    payload.setdefault("source", "reccobeats")
    persistent_cache.cache_track_reccobeats(spotify_id, payload)
    logger.info(
        "Cached ReccoBeats features for %s • keys=%s",
        spotify_id,
        sorted(payload.keys()),
    )


def get_cached_reccobeats_features(spotify_id: str) -> dict[str, Any] | None:
    payload = persistent_cache.get_cached_track_reccobeats(spotify_id)
    if payload:
        # logger.debug(
        #     "Retrieved ReccoBeats cache for %s • keys=%s",
        #     spotify_id,
        #     sorted(payload.keys()),
        # )
        payload.setdefault("spotify_id", spotify_id)
        payload.setdefault("source", "reccobeats")
    return payload


def cache_reccobeats_mapping(spotify_id: str, reccobeats_id: str) -> None:
    """Persist the Spotify -> ReccoBeats ID mapping."""
    if not spotify_id or not reccobeats_id:
        return

    try:
        payload = {
            "spotify_id": spotify_id,
            "reccobeats_id": reccobeats_id,
        }
        persistent_cache.cache_track_data(spotify_id, "reccobeats_id", payload)
        # logger.debug("Cached ReccoBeats ID %s for Spotify track %s", reccobeats_id, spotify_id)
    except Exception as exc:
        logger.warning("Failed to cache ReccoBeats ID for %s: %s", spotify_id, exc)


def get_cached_reccobeats_mapping(spotify_id: str) -> str | None:
    """Return cached ReccoBeats ID for the Spotify track if present."""
    if not spotify_id:
        return None

    entry = persistent_cache.get_cached_track_data(spotify_id, "reccobeats_id")
    if not entry:
        return None

    payload = entry.get("payload") or {}
    reccobeats_id = payload.get("reccobeats_id")
    if reccobeats_id:
        # logger.debug("Using cached ReccoBeats ID %s for Spotify track %s", reccobeats_id, spotify_id)
        pass
    return reccobeats_id


def get_or_update_playlist_tracks(sp, playlist_id: str, user_id: str) -> dict[str, Any]:
    """Get playlist tracks from Spotify API and update cache with status tracking.

    Args:
        sp: Spotify client
        playlist_id: Spotify playlist ID
        user_id: User ID for cache key

    Returns:
        Dictionary with tracks data and cache statistics
    """
    try:
        # Get current tracks from Spotify API
        results = sp.playlist_tracks(playlist_id)
        current_tracks = []

        while results:
            for item in results["items"]:
                track = item.get("track")
                if track:
                    # Add position and added_at from the playlist item
                    track_data = track.copy()
                    track_data["position"] = item.get("position", len(current_tracks))
                    track_data["added_at"] = item.get("added_at")
                    current_tracks.append(track_data)

            if results["next"]:
                results = sp.next(results)
            else:
                break

        # Cache the tracks with status
        persistent_cache.cache_playlist_tracks(playlist_id, user_id, current_tracks)

        # Get the cached data with status information
        cached_data = persistent_cache.get_cached_playlist_tracks(playlist_id, user_id)

        return {
            "tracks": current_tracks,
            "total_tracks": len(current_tracks),
            "cache_data": cached_data,
            "spotify_cached_count": cached_data.get("spotify_cached_count", 0)
            if cached_data
            else 0,
            "reccobeats_cached_count": cached_data.get("reccobeats_cached_count", 0)
            if cached_data
            else 0,
            "new_tracks": len(current_tracks)
            - (cached_data.get("total_tracks", 0) if cached_data else 0),
        }

    except Exception as exc:
        logger.error("Error getting playlist tracks: %s", exc)
        return {
            "tracks": [],
            "total_tracks": 0,
            "cache_data": None,
            "spotify_cached_count": 0,
            "reccobeats_cached_count": 0,
            "new_tracks": 0,
        }


def cache_spotify_track_with_playlist_update(
    track_payload: dict[str, Any], playlist_id: str, user_id: str
) -> dict[str, Any] | None:
    """Cache Spotify track and update playlist cache status."""
    normalized = cache_spotify_track(track_payload)
    if normalized and playlist_id and user_id:
        persistent_cache.update_playlist_track_cache_status(
            playlist_id, user_id, normalized["id"]
        )
    return normalized


def cache_reccobeats_features_with_playlist_update(
    spotify_id: str, features: dict[str, Any], playlist_id: str, user_id: str
) -> None:
    """Cache ReccoBeats features and update playlist cache status."""
    cache_reccobeats_features(spotify_id, features)
    if playlist_id and user_id:
        persistent_cache.update_playlist_track_cache_status(
            playlist_id, user_id, spotify_id
        )
