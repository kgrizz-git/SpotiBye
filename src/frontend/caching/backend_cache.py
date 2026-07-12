"""Backend-compatible caching system for frontend integration."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
import os

from ..config.backend_config import CACHE_DIR, FeatureFlags
from ..services.backend_client import BackendClient
from ..services.playlist_composition import normalize_tracks_cache_entry

# Default playlist tracks cache TTL — 24h (B2); refresh buttons bypass earlier.
DEFAULT_TRACKS_CACHE_TTL_SECONDS = 86_400

logger = logging.getLogger(__name__)


class BackendCacheManager:
    """Cache manager that works with backend and local caching."""

    def __init__(self, backend_client: Optional[BackendClient] = None):
        """
        Initialize backend cache manager.

        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client
        self.cache_dir = CACHE_DIR

        # Create environment-specific cache paths
        backend_url = self._get_backend_url_safe()
        env_hash = self._hash_backend_url(backend_url)
        self.token_cache_path = self.cache_dir / f"backend_token_{env_hash}.json"

        self._file_locks = {}  # Dictionary to store file locks
        self._lock = threading.Lock()  # Global lock for managing file locks

        # Ensure cache directory exists
        self.cache_dir.mkdir(exist_ok=True)

    def _get_backend_url_safe(self) -> str:
        """Get backend URL safely, fallback to default if not available."""
        if self.backend_client:
            return self.backend_client.base_url
        return "default"

    def _hash_backend_url(self, backend_url: str) -> str:
        """Create a safe hash of backend URL for cache filenames."""
        import hashlib

        # Create a short, safe hash for filename
        hash_obj = hashlib.sha256(backend_url.encode())
        return hash_obj.hexdigest()[:12]

    # Token management
    def save_auth_token(self, token_data: Dict[str, Any]) -> None:
        """
        Save authentication token to local cache.

        Args:
            token_data: Token data to cache
        """
        try:
            with open(self.token_cache_path, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.debug("Authentication token saved to cache")
        except Exception as e:
            logger.error(f"Failed to save auth token: {e}")

    def load_auth_token(self) -> Optional[Dict[str, Any]]:
        """
        Load authentication token from local cache.

        Returns:
            Token data or None if not found
        """
        try:
            if not self.token_cache_path.exists():
                return None

            with open(self.token_cache_path, "r") as f:
                token_data = json.load(f)

            logger.debug("Authentication token loaded from cache")
            return token_data

        except Exception as e:
            logger.error(f"Failed to load auth token: {e}")
            return None

    def clear_auth_token(self) -> None:
        """Clear authentication token from local cache."""
        try:
            if self.token_cache_path.exists():
                self.token_cache_path.unlink()
                logger.debug("Authentication token cleared from cache")
        except Exception as e:
            logger.error(f"Failed to clear auth token: {e}")

    # Playlist caching
    def get_cached_playlists(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached playlists.

        Returns:
            List of playlists or None if not cached
        """
        return self._load_cache_file("playlists.json")

    def cache_playlists(self, playlists: List[Dict[str, Any]], ttl: int = 3600) -> None:
        """
        Cache playlists with TTL.

        Args:
            playlists: List of playlists to cache
            ttl: Time to live in seconds
        """
        # Playlists endpoint returns a full snapshot; replace cache to avoid stale/missing data.
        all_playlists = playlists

        cache_data = {"data": all_playlists, "timestamp": time.time(), "ttl": ttl}
        self._save_cache_file("playlists.json", cache_data)
        logger.info(
            f"Saved playlists cache snapshot with {len(all_playlists)} items (ttl={ttl}s)"
        )

    def is_playlists_cache_valid(self) -> bool:
        """
        Check if playlists cache is valid.

        Returns:
            True if cache is valid, False otherwise
        """
        return self._is_cache_valid("playlists.json")

    # Track caching
    def get_cached_tracks_entry(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached tracks entry including composition fingerprint metadata.

        Returns:
            Dict with keys `tracks`, `snapshot_id`, `track_id_hash`,
            `unique_track_count`, or None if not cached.
        """
        raw = self._load_cache_file(f"tracks_{playlist_id}.json")
        return normalize_tracks_cache_entry(raw)

    def get_cached_tracks(self, playlist_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached tracks for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            List of tracks or None if not cached
        """
        entry = self.get_cached_tracks_entry(playlist_id)
        if entry is None:
            return None
        tracks = entry.get("tracks")
        return tracks if isinstance(tracks, list) else None

    def cache_tracks(
        self,
        playlist_id: str,
        tracks: List[Dict[str, Any]],
        ttl: int = DEFAULT_TRACKS_CACHE_TTL_SECONDS,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Cache tracks for a playlist with TTL and optional composition metadata.

        Args:
            playlist_id: Spotify playlist ID
            tracks: List of playlist track items to cache
            ttl: Time to live in seconds (default 24 hours)
            metadata: Optional pre-built metadata dict from build_tracks_cache_metadata
        """
        if metadata is not None:
            payload = {**metadata, "tracks": tracks}
        else:
            from ..services.playlist_composition import build_tracks_cache_metadata

            payload = build_tracks_cache_metadata(tracks)
        cache_data = {"data": payload, "timestamp": time.time(), "ttl": ttl}
        self._save_cache_file(f"tracks_{playlist_id}.json", cache_data)

    def is_tracks_cache_valid(self, playlist_id: str) -> bool:
        """
        Check if tracks cache is valid for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            True if cache is valid, False otherwise
        """
        return self._is_cache_valid(f"tracks_{playlist_id}.json")

    # Analysis caching
    def get_cached_analysis(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis results for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Analysis results or None if not cached
        """
        return self._load_cache_file(f"analysis_{playlist_id}.json")

    def cache_analysis(
        self, playlist_id: str, analysis: Dict[str, Any], ttl: int = 86400
    ) -> None:
        """
        Cache analysis results for a playlist with TTL.

        Args:
            playlist_id: Spotify playlist ID
            analysis: Analysis results to cache
            ttl: Time to live in seconds (default 24 hours)
        """
        cache_data = {"data": analysis, "timestamp": time.time(), "ttl": ttl}
        self._save_cache_file(f"analysis_{playlist_id}.json", cache_data)

    def is_analysis_cache_valid(self, playlist_id: str) -> bool:
        """
        Check if analysis cache is valid for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            True if cache is valid, False otherwise
        """
        return self._is_cache_valid(f"analysis_{playlist_id}.json")

    # Export caching
    def get_cached_export_info(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached export information for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Export information or None if not cached
        """
        return self._load_cache_file(f"export_{playlist_id}.json")

    def cache_export_info(
        self, playlist_id: str, export_info: Dict[str, Any], ttl: int = 3600
    ) -> None:
        """
        Cache export information for a playlist with TTL.

        Args:
            playlist_id: Spotify playlist ID
            export_info: Export information to cache
            ttl: Time to live in seconds
        """
        cache_data = {"data": export_info, "timestamp": time.time(), "ttl": ttl}
        self._save_cache_file(f"export_{playlist_id}.json", cache_data)

    def get_active_export_job(self) -> Optional[Dict[str, Any]]:
        """Get cached resumable export job metadata for restart recovery."""
        return self._load_cache_file("active_export_job.json")

    def cache_active_export_job(
        self, export_job: Dict[str, Any], ttl: int = 86400
    ) -> None:
        """Persist active resumable export job metadata."""
        cache_data = {
            "data": export_job,
            "timestamp": time.time(),
            "ttl": ttl,
        }
        self._save_cache_file("active_export_job.json", cache_data)

    def clear_active_export_job(self) -> None:
        """Remove cached active resumable export job metadata."""
        cache_path = self._cache_file_path("active_export_job.json")
        file_lock = self._get_file_lock(cache_path)

        with file_lock:
            try:
                if cache_path.exists():
                    cache_path.unlink()
                    logger.debug("Cleared active export job cache")
            except Exception as e:
                logger.error(f"Failed to clear active export job cache: {e}")

    # Cache utility methods
    def _get_file_lock(self, cache_path: Path):
        """Get or create a file lock for the given cache path."""
        with self._lock:
            if cache_path not in self._file_locks:
                self._file_locks[cache_path] = threading.Lock()
            return self._file_locks[cache_path]

    def _atomic_write_cache_file(self, cache_path: Path, data: Dict[str, Any]) -> None:
        """
        Atomically write cache file to prevent corruption during concurrent access.

        Args:
            cache_path: Path to cache file
            data: Data to write
        """
        file_lock = self._get_file_lock(cache_path)

        with file_lock:
            temp_file: Path | None = None
            try:
                # Write to temporary file first
                temp_file = cache_path.with_suffix(".tmp")
                with open(temp_file, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()  # Ensure data is written to disk
                    os.fsync(f.fileno())  # Force write to disk

                # Atomic move - this is thread-safe on Unix systems
                temp_file.replace(cache_path)

            except Exception as e:
                logger.error(f"Failed to atomically write cache file {cache_path}: {e}")
                # Clean up temp file if it exists
                if temp_file is not None and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass
                raise

    def _cache_file_path(self, filename: str) -> Path:
        """
        Compute the on-disk path for a given cache filename, prefixing the
        env-scoped hash so cache files are isolated per backend URL.

        All read/write/clear helpers should funnel through this so the
        hashing rule lives in exactly one place (FE-HIGH-3).
        """
        env_hash = self._hash_backend_url(self._get_backend_url_safe())
        return self.cache_dir / f"{env_hash}_{filename}"

    def _load_cache_file(self, filename: str) -> Optional[Any]:
        """
        Load data from cache file with thread-safe access.

        Args:
            filename: Cache filename

        Returns:
            Cached data or None if not found/invalid
        """
        cache_path = self._cache_file_path(filename)

        file_lock = self._get_file_lock(cache_path)

        with file_lock:
            try:
                if not cache_path.exists():
                    return None

                with open(cache_path, "r") as f:
                    cache_data = json.load(f)

                # Check if cache has expired
                if not self._is_cache_data_valid(cache_data):
                    cache_path.unlink()  # Remove expired cache
                    return None

                return cache_data.get("data")

            except Exception as e:
                logger.error(f"Failed to load cache file {filename}: {e}")
                return None

    def _save_cache_file(self, filename: str, data: Dict[str, Any]) -> None:
        """
        Save data to cache file with thread-safe atomic writes.

        Args:
            filename: Cache filename
            data: Data to cache
        """
        cache_path = self._cache_file_path(filename)
        self._atomic_write_cache_file(cache_path, data)

    def _is_cache_valid(self, filename: str) -> bool:
        """
        Check if cache file is valid and not expired.

        Args:
            filename: Cache filename

        Returns:
            True if cache is valid, False otherwise
        """
        try:
            cache_path = self._cache_file_path(filename)
            if not cache_path.exists():
                return False

            with open(cache_path, "r") as f:
                cache_data = json.load(f)

            return self._is_cache_data_valid(cache_data)

        except Exception as e:
            logger.error(f"Failed to validate cache file {filename}: {e}")
            return False

    def _is_cache_data_valid(self, cache_data: Dict[str, Any]) -> bool:
        """
        Check if cache data is valid and not expired.

        Args:
            cache_data: Cache data dictionary

        Returns:
            True if cache data is valid, False otherwise
        """
        try:
            timestamp = cache_data.get("timestamp", 0)
            ttl = cache_data.get("ttl", 0)

            if not timestamp or not ttl:
                return False

            current_time = time.time()
            return (current_time - timestamp) < ttl

        except Exception:
            return False

    def clear_cache(self, pattern: Optional[str] = None) -> None:
        """
        Clear cache files.

        Args:
            pattern: Optional pattern to match files (e.g., 'tracks_*.json')
        """
        try:
            if pattern:
                cache_files = list(self.cache_dir.glob(pattern))
            else:
                # Only env-hash-prefixed data files by default; preserves
                # backend_token_*.json and backend_selection.json (auth +
                # selection). Pass a glob explicitly to target those.
                env_hash = self._hash_backend_url(self._get_backend_url_safe())
                cache_files = list(self.cache_dir.glob(f"{env_hash}_*.json"))

            for cache_file in cache_files:
                cache_file.unlink()
                logger.debug(f"Removed cache file: {cache_file}")

            logger.info(f"Cleared {len(cache_files)} cache files")

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def clear_file(self, filename: str) -> None:
        """
        Clear a single cache file by its logical name (without env-hash prefix).

        Routes through _cache_file_path so the same env-scoped hashing rule
        used by _load_cache_file / _save_cache_file applies here. Missing
        files are ignored.
        """
        try:
            cache_path = self._cache_file_path(filename)
            if cache_path.exists():
                cache_path.unlink()
                logger.debug(f"Removed cache file: {cache_path}")
        except Exception as e:
            logger.error(f"Failed to clear cache file {filename}: {e}")

    def clear_cache_glob(self, pattern: str) -> None:
        """
        Clear cache files matching a glob pattern, with the env-hash prefix
        automatically applied. The pattern is a logical name (no env_hash
        prefix); e.g. 'tracks_*.json' matches '{env_hash}_tracks_*.json'.

        Missing files are ignored.
        """
        try:
            env_hash = self._hash_backend_url(self._get_backend_url_safe())
            full_pattern = f"{env_hash}_{pattern}"
            for cache_file in self.cache_dir.glob(full_pattern):
                cache_file.unlink()
                logger.debug(f"Removed cache file: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to clear cache glob {pattern}: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        try:
            env_hash = self._hash_backend_url(self._get_backend_url_safe())
            env_prefix = f"{env_hash}_"

            cache_files = [
                cache_file
                for cache_file in self.cache_dir.glob("*.json")
                if cache_file.name.startswith(env_prefix)
                or cache_file == self.token_cache_path
            ]
            total_size = sum(f.stat().st_size for f in cache_files)

            # Count by type
            # Count actual playlists in the playlists cache
            playlists_count = 0
            playlists_cache = self.cache_dir / f"{env_prefix}playlists.json"
            if playlists_cache.exists():
                try:
                    with open(playlists_cache, "r") as f:
                        cached_data = json.load(f)
                        if isinstance(cached_data, dict) and "data" in cached_data:
                            playlists_count = len(cached_data["data"])
                except (json.JSONDecodeError, IOError):
                    pass

            tracks_count = len(list(self.cache_dir.glob(f"{env_prefix}tracks_*.json")))
            analysis_count = len(
                list(self.cache_dir.glob(f"{env_prefix}analysis_*.json"))
            )
            export_count = len(list(self.cache_dir.glob(f"{env_prefix}export_*.json")))

            return {
                "total_files": len(cache_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "playlists_count": playlists_count,
                "tracks_count": tracks_count,
                "analysis_count": analysis_count,
                "export_count": export_count,
                "cache_dir": str(self.cache_dir),
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "error": str(e),
            }


# Global cache manager instance
_cache_manager: Optional[BackendCacheManager] = None


def get_cache_manager() -> BackendCacheManager:
    """Get or create global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = BackendCacheManager()
    return _cache_manager


def set_cache_manager(cache_manager: BackendCacheManager) -> None:
    """Set global cache manager instance."""
    global _cache_manager
    _cache_manager = cache_manager


# Legacy compatibility functions
def cache_spotify_track(track_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Legacy compatibility function for Spotify track caching."""
    # In backend mode, we rely on backend caching
    if FeatureFlags.ENABLE_CACHING:
        get_cache_manager()
        # Cache tracks as part of playlist caching
        return track_payload
    return None


def get_cached_spotify_track(track_id: str) -> Optional[Dict[str, Any]]:
    """Legacy compatibility function for getting cached Spotify track."""
    # In backend mode, we rely on backend caching
    return None


def cache_reccobeats_mapping(spotify_id: str, reccobeats_id: str) -> None:
    """Legacy compatibility function for ReccoBeats mapping caching."""
    # In backend mode, this is handled by the backend
    pass


def get_cached_reccobeats_mapping(spotify_id: str) -> Optional[str]:
    """Legacy compatibility function for getting cached ReccoBeats mapping."""
    # In backend mode, this is handled by the backend
    return None


__all__ = [
    "BackendCacheManager",
    "get_cache_manager",
    "set_cache_manager",
    "cache_spotify_track",
    "get_cached_spotify_track",
    "cache_reccobeats_mapping",
    "get_cached_reccobeats_mapping",
]
