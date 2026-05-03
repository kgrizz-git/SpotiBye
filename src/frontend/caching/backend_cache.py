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
    def get_cached_tracks(self, playlist_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached tracks for a playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            List of tracks or None if not cached
        """
        return self._load_cache_file(f"tracks_{playlist_id}.json")

    def cache_tracks(
        self, playlist_id: str, tracks: List[Dict[str, Any]], ttl: int = 7200
    ) -> None:
        """
        Cache tracks for a playlist with TTL.

        Args:
            playlist_id: Spotify playlist ID
            tracks: List of tracks to cache
            ttl: Time to live in seconds
        """
        cache_data = {"data": tracks, "timestamp": time.time(), "ttl": ttl}
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
        # Add environment hash to filename for environment-specific caching
        env_hash = self._hash_backend_url(self._get_backend_url_safe())
        env_filename = f"{env_hash}_active_export_job.json"
        cache_path = self.cache_dir / env_filename
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
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
                raise

    def _load_cache_file(self, filename: str) -> Optional[Any]:
        """
        Load data from cache file with thread-safe access.

        Args:
            filename: Cache filename

        Returns:
            Cached data or None if not found/invalid
        """
        # Add environment hash to filename for environment-specific caching
        env_hash = self._hash_backend_url(self._get_backend_url_safe())
        env_filename = f"{env_hash}_{filename}"
        cache_path = self.cache_dir / env_filename

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
        # Add environment hash to filename for environment-specific caching
        env_hash = self._hash_backend_url(self._get_backend_url_safe())
        env_filename = f"{env_hash}_{filename}"
        cache_path = self.cache_dir / env_filename
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
            # Add environment hash to filename for environment-specific caching
            env_hash = self._hash_backend_url(self._get_backend_url_safe())
            env_filename = f"{env_hash}_{filename}"
            cache_path = self.cache_dir / env_filename
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

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            stats = {
                "total_cached_items": 0,
                "cache_size_bytes": 0,
                "last_updated": None,
            }

            # Check playlists cache
            playlists_cache = self.cache_dir / "playlists.json"
            if playlists_cache.exists():
                try:
                    with open(playlists_cache, "r") as f:
                        cached_data = json.load(f)
                        if isinstance(cached_data, list):
                            stats["total_cached_items"] += len(cached_data)
                        stats["cache_size_bytes"] += playlists_cache.stat().st_size
                        stats["last_updated"] = playlists_cache.stat().st_mtime
                except (json.JSONDecodeError, IOError):
                    pass

            # Check token cache
            if self.token_cache_path.exists():
                stats["cache_size_bytes"] += self.token_cache_path.stat().st_size
                if (
                    not stats["last_updated"]
                    or self.token_cache_path.stat().st_mtime > stats["last_updated"]
                ):
                    stats["last_updated"] = self.token_cache_path.stat().st_mtime

            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "total_cached_items": 0,
                "cache_size_bytes": 0,
                "last_updated": None,
            }

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
                cache_files = list(self.cache_dir.glob("*.json"))

            for cache_file in cache_files:
                cache_file.unlink()
                logger.debug(f"Removed cache file: {cache_file}")

            logger.info(f"Cleared {len(cache_files)} cache files")

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)

            # Count by type
            # Count actual playlists in the playlists cache
            playlists_count = 0
            playlists_cache = self.cache_dir / "playlists.json"
            if playlists_cache.exists():
                try:
                    with open(playlists_cache, "r") as f:
                        cached_data = json.load(f)
                        if isinstance(cached_data, dict) and "data" in cached_data:
                            playlists_count = len(cached_data["data"])
                except (json.JSONDecodeError, IOError):
                    pass

            tracks_count = len(list(self.cache_dir.glob("tracks_*.json")))
            analysis_count = len(list(self.cache_dir.glob("analysis_*.json")))
            export_count = len(list(self.cache_dir.glob("export_*.json")))

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
        cache_manager = get_cache_manager()
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
