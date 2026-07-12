"""Playlist composition fingerprinting for offline completeness and change detection.

Inputs: playlist track items (Spotify playlist item dicts), optional snapshot_id.
Outputs: unique track ID sets, stable hashes, composition fingerprints for cache gates.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple


def extract_spotify_track_id(item: Dict[str, Any]) -> Optional[str]:
    """Return the Spotify track id from a playlist item or bare track dict."""
    track = item.get("track") or item.get("item") or item
    if isinstance(track, dict):
        track_id = track.get("id")
        if isinstance(track_id, str) and track_id:
            return track_id
    return None


def unique_track_ids_from_items(items: List[Dict[str, Any]]) -> List[str]:
    """Unique Spotify track IDs preserving first-seen order."""
    seen: Set[str] = set()
    ordered: List[str] = []
    for item in items:
        track_id = extract_spotify_track_id(item)
        if track_id and track_id not in seen:
            seen.add(track_id)
            ordered.append(track_id)
    return ordered


def compute_track_id_hash(track_ids: List[str]) -> str:
    """Stable hash of the playlist's unique Spotify track ID set."""
    unique_sorted = sorted(set(filter(None, track_ids)))
    payload = ",".join(unique_sorted)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_composition_fingerprint(
    *,
    snapshot_id: Optional[str] = None,
    track_id_hash: Optional[str] = None,
) -> str:
    """Single string key for session retry ledger and cache comparison."""
    snap = snapshot_id or ""
    track_hash = track_id_hash or ""
    return f"snap:{snap}|hash:{track_hash}"


def fingerprints_match(
    cached: Dict[str, Any],
    *,
    snapshot_id: Optional[str],
    track_id_hash: str,
) -> bool:
    """Return True when cached fingerprint matches current playlist composition."""
    cached_snap = cached.get("snapshot_id")
    cached_hash = cached.get("track_id_hash")
    if isinstance(cached_snap, str) and cached_snap and isinstance(snapshot_id, str) and snapshot_id:
        return cached_snap == snapshot_id
    if isinstance(cached_hash, str) and cached_hash:
        return cached_hash == track_id_hash
    return False


def build_tracks_cache_metadata(
    items: List[Dict[str, Any]],
    *,
    snapshot_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Metadata stored alongside cached playlist track items."""
    unique_ids = unique_track_ids_from_items(items)
    return {
        "tracks": items,
        "snapshot_id": snapshot_id,
        "track_id_hash": compute_track_id_hash(unique_ids),
        "unique_track_count": len(unique_ids),
    }


def composition_delta_track_ids(
    cached_items: List[Dict[str, Any]],
    current_items: List[Dict[str, Any]],
) -> List[str]:
    """Track IDs present in current composition but not in the cached set."""
    cached_ids = set(unique_track_ids_from_items(cached_items))
    return [
        track_id
        for track_id in unique_track_ids_from_items(current_items)
        if track_id not in cached_ids
    ]


def resolve_snapshot_id_from_playlists(
    playlists: Optional[List[Dict[str, Any]]],
    playlist_id: str,
) -> Optional[str]:
    """Read snapshot_id from a cached playlists list response."""
    if not playlists:
        return None
    for playlist in playlists:
        if playlist.get("id") == playlist_id:
            snapshot_id = playlist.get("snapshot_id")
            if isinstance(snapshot_id, str) and snapshot_id:
                return snapshot_id
    return None


def normalize_tracks_cache_entry(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalize legacy list-only cache payloads to the metadata-aware shape."""
    if raw is None:
        return None
    if isinstance(raw, list):
        metadata = build_tracks_cache_metadata(raw)
        return metadata
    if isinstance(raw, dict) and isinstance(raw.get("tracks"), list):
        return raw
    return None


__all__ = [
    "build_composition_fingerprint",
    "build_tracks_cache_metadata",
    "composition_delta_track_ids",
    "compute_track_id_hash",
    "extract_spotify_track_id",
    "fingerprints_match",
    "normalize_tracks_cache_entry",
    "resolve_snapshot_id_from_playlists",
    "unique_track_ids_from_items",
]
