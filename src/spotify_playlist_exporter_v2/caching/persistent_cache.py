"""Persistent caching layer for playlists, images, and analysis data."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
import threading
import time
from pathlib import Path

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from typing import Any, Dict, List, Optional

from ..config import DEFAULT_CACHE_DIR
from ..logging_config import logger


class PersistentCache:
    """Manages persistent caching of playlist data, images, and analysis results."""

    _metadata_lock = threading.RLock()

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        cache_dir = cache_dir or DEFAULT_CACHE_DIR

        self.cache_dir = Path(cache_dir)
        self.data_cache_dir = self.cache_dir / "data"
        self.image_cache_dir = self.cache_dir / "images"
        self.analysis_cache_dir = self.cache_dir / "analysis"
        self.track_cache_dir = self.analysis_cache_dir / "tracks"

        for directory in [
            self.cache_dir,
            self.data_cache_dir,
            self.image_cache_dir,
            self.analysis_cache_dir,
            self.track_cache_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()
        self._migrate_webp_cache()

        self.max_cache_age_days = 30
        self.max_cache_size_mb = 100

        logger.info("Initialized persistent cache at: %s", self.cache_dir)

    # ------------------------------------------------------------------
    # Migration helpers
    # ------------------------------------------------------------------
    def _migrate_webp_cache(self) -> None:
        """Remove .webp image cache entries left by old builds.

        Kivy's image providers in packaged macOS/Windows builds cannot decode
        WebP, so any cached .webp files from earlier versions of the app must
        be purged so that fresh JPEG/PNG downloads are triggered.
        """
        changed = False
        for url_hash in list(self.metadata.get("images", {}).keys()):
            entry = self.metadata["images"][url_hash]
            file_path = entry.get("file_path", "")
            if file_path.endswith(".webp"):
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                del self.metadata["images"][url_hash]
                changed = True

        # Also sweep for orphaned .webp files not tracked in metadata.
        for webp_file in self.image_cache_dir.glob("*.webp"):
            try:
                webp_file.unlink()
            except Exception:
                pass

        if changed:
            self._save_metadata()
            logger.info("Purged legacy WebP image cache entries")

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def _default_metadata(self) -> Dict[str, Any]:
        return {
            "playlists": {},
            "images": {},
            "analysis": {},
            "tracks": {},
            "created_at": time.time(),
        }

    def _load_metadata(self) -> Dict[str, Any]:
        backup_file = self.metadata_file.with_suffix(".bak")

        with self._metadata_lock:
            try:
                if self.metadata_file.exists():
                    with open(self.metadata_file, "r", encoding="utf-8") as file:
                        return json.load(file)
            except json.JSONDecodeError as exc:
                logger.warning("Error loading cache metadata: %s", exc)
                corrupt_file = self.metadata_file.with_name(
                    f"{self.metadata_file.stem}.corrupt-{int(time.time())}.json"
                )
                try:
                    self.metadata_file.replace(corrupt_file)
                    logger.warning("Moved corrupted cache metadata to %s", corrupt_file)
                except Exception as move_exc:
                    logger.warning(
                        "Failed to move corrupted cache metadata: %s", move_exc
                    )

                if backup_file.exists():
                    try:
                        with open(backup_file, "r", encoding="utf-8") as file:
                            return json.load(file)
                    except Exception as backup_exc:
                        logger.warning(
                            "Error loading backup cache metadata: %s", backup_exc
                        )
            except Exception as exc:
                logger.warning("Error loading cache metadata: %s", exc)

        return self._default_metadata()

    def _save_metadata(self) -> None:
        backup_file = self.metadata_file.with_suffix(".bak")
        temp_file = self.metadata_file.with_suffix(".tmp")

        with self._metadata_lock:
            try:
                with open(temp_file, "w", encoding="utf-8") as file:
                    json.dump(self.metadata, file, indent=2)
                    file.flush()
                    os.fsync(file.fileno())

                temp_file.replace(self.metadata_file)
                shutil.copy2(self.metadata_file, backup_file)
            except Exception as exc:
                logger.warning("Error saving cache metadata: %s", exc)
                try:
                    temp_file.unlink(missing_ok=True)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_cache_key(self, playlist_id: str, user_id: Optional[str] = None) -> str:
        key_string = f"{playlist_id}_{user_id}" if user_id else playlist_id
        return hashlib.md5(key_string.encode()).hexdigest()

    def _is_cache_valid(self, timestamp: float) -> bool:
        max_age_seconds = self.max_cache_age_days * 24 * 3600
        return (time.time() - timestamp) < max_age_seconds

    # ------------------------------------------------------------------
    # Playlist cache
    # ------------------------------------------------------------------
    def cache_playlist_data(
        self,
        playlist_id: str,
        playlist_data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        try:
            cache_key = self._get_cache_key(playlist_id, user_id)
            cache_file = self.data_cache_dir / f"{cache_key}.pkl"

            with open(cache_file, "wb") as file:
                # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                pickle.dump(playlist_data, file)

            self.metadata["playlists"][cache_key] = {
                "playlist_id": playlist_id,
                "user_id": user_id,
                "cached_at": time.time(),
                "file_path": str(cache_file),
            }

            self._save_metadata()
            logger.debug("Cached playlist data for %s", playlist_id)

        except Exception as exc:
            logger.warning("Error caching playlist data: %s", exc)

    def get_cached_playlist_data(
        self, playlist_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            cache_key = self._get_cache_key(playlist_id, user_id)
            if cache_key not in self.metadata["playlists"]:
                return None

            cache_info = self.metadata["playlists"][cache_key]
            if not self._is_cache_valid(cache_info["cached_at"]):
                logger.debug("Cache expired for playlist %s", playlist_id)
                self._remove_playlist_cache(cache_key)
                return None

            cache_file = Path(cache_info["file_path"])
            if cache_file.exists():
                with open(cache_file, "rb") as file:
                    # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                    return pickle.load(file)

            self._remove_playlist_cache(cache_key)
            return None

        except Exception as exc:
            logger.warning("Error retrieving cached playlist data: %s", exc)
            return None

    def _remove_playlist_cache(self, cache_key: str) -> None:
        try:
            if cache_key in self.metadata["playlists"]:
                cache_info = self.metadata["playlists"][cache_key]
                cache_file = Path(cache_info["file_path"])
                if cache_file.exists():
                    cache_file.unlink()
                del self.metadata["playlists"][cache_key]
                self._save_metadata()
        except Exception as exc:
            logger.warning("Error removing playlist cache: %s", exc)

    # ------------------------------------------------------------------
    # Image cache
    # ------------------------------------------------------------------
    def cache_image(self, image_url: str, image_data: bytes) -> Optional[str]:
        try:
            url_hash = hashlib.md5(image_url.encode()).hexdigest()

            # Try to compress and optimize the image
            optimized_data = self._optimize_image(image_data, image_url)
            if optimized_data:
                image_data = optimized_data

            # Keep broadly supported formats for packaged desktop builds.
            file_ext = ".jpg"
            lowered = image_url.lower()
            if ".png" in lowered:
                file_ext = ".png"
            elif ".jpeg" in lowered or ".jpg" in lowered:
                file_ext = ".jpg"

            cache_file = self.image_cache_dir / f"{url_hash}{file_ext}"
            with open(cache_file, "wb") as file:
                file.write(image_data)

            self.metadata["images"][url_hash] = {
                "url": image_url,
                "cached_at": time.time(),
                "file_path": str(cache_file),
                "file_size": len(image_data),
                "format": file_ext[1:],  # Store format without dot
            }
            self._save_metadata()
            logger.debug(
                "Cached optimized image: %s (%d bytes)", image_url, len(image_data)
            )
            return str(cache_file)

        except Exception as exc:
            logger.warning("Error caching image: %s", exc)
            return None

    def _optimize_image(self, image_data: bytes, image_url: str) -> Optional[bytes]:
        """Optimize image data while preserving a widely supported output format."""
        if not PIL_AVAILABLE:
            return None

        try:
            # Load image from bytes
            import io

            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB when writing JPEG. Preserve alpha for PNG where possible.
            if image.mode in ("RGBA", "LA", "P"):
                if ".png" in image_url.lower():
                    if image.mode == "P":
                        image = image.convert("RGBA")
                else:
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    background.paste(
                        image, mask=image.split()[-1] if image.mode == "RGBA" else None
                    )
                    image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # Resize if too large (optimize for UI display)
            max_size = (400, 400)  # Max 400x400 for playlist covers
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Encode using JPEG/PNG for compatibility with Kivy providers in packaged apps.
            output = io.BytesIO()
            lowered = image_url.lower()
            if ".png" in lowered:
                image.save(output, "PNG", optimize=True)
            else:
                image.save(output, "JPEG", quality=85, optimize=True)
            optimized_data = output.getvalue()

            # Only use optimized version if it's smaller
            if len(optimized_data) < len(image_data) * 0.9:  # At least 10% reduction
                logger.debug(
                    "Optimized image: %d -> %d bytes (%.1f%% reduction)",
                    len(image_data),
                    len(optimized_data),
                    (1 - len(optimized_data) / len(image_data)) * 100,
                )
                return optimized_data

        except Exception as exc:
            logger.debug("Image optimization failed for %s: %s", image_url, exc)

        return None

    def get_cached_image_path(self, image_url: str) -> Optional[str]:
        try:
            url_hash = hashlib.md5(image_url.encode()).hexdigest()
            if url_hash not in self.metadata["images"]:
                return None

            cache_info = self.metadata["images"][url_hash]
            # Legacy builds wrote WebP files that packaged Kivy providers may not decode.
            # Drop the entry here to force a clean re-download in JPEG/PNG.
            legacy_path = str(cache_info.get("file_path", ""))
            if legacy_path.endswith(".webp"):
                self._remove_image_cache(url_hash)
                return None

            if not self._is_cache_valid(cache_info["cached_at"]):
                logger.debug("Image cache expired for %s", image_url)
                self._remove_image_cache(url_hash)
                return None

            cache_file = Path(cache_info["file_path"])
            if cache_file.exists():
                return str(cache_file)

            self._remove_image_cache(url_hash)
            return None

        except Exception as exc:
            logger.warning("Error retrieving cached image: %s", exc)
            return None

    def _remove_image_cache(self, url_hash: str) -> None:
        try:
            if url_hash in self.metadata["images"]:
                cache_info = self.metadata["images"][url_hash]
                cache_file = Path(cache_info["file_path"])
                if cache_file.exists():
                    cache_file.unlink()
                del self.metadata["images"][url_hash]
                self._save_metadata()
        except Exception as exc:
            logger.warning("Error removing image cache: %s", exc)

    # ------------------------------------------------------------------
    # Analysis cache
    # ------------------------------------------------------------------
    def cache_analysis_data(
        self,
        playlist_id: str,
        analysis_data: Dict[str, Any],
        analysis_type: str = "combined",
    ) -> None:
        try:
            cache_key = f"{playlist_id}_{analysis_type}"
            cache_file = self.analysis_cache_dir / f"{cache_key}.pkl"

            with open(cache_file, "wb") as file:
                # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                pickle.dump(analysis_data, file)

            self.metadata["analysis"][cache_key] = {
                "playlist_id": playlist_id,
                "analysis_type": analysis_type,
                "cached_at": time.time(),
                "file_path": str(cache_file),
            }
            self._save_metadata()
            logger.debug("Cached analysis data for %s (%s)", playlist_id, analysis_type)

        except Exception as exc:
            logger.warning("Error caching analysis data: %s", exc)

    def get_cached_analysis_data(
        self, playlist_id: str, analysis_type: str = "combined"
    ) -> Optional[Dict[str, Any]]:
        try:
            cache_key = f"{playlist_id}_{analysis_type}"
            if cache_key not in self.metadata["analysis"]:
                return None

            cache_info = self.metadata["analysis"][cache_key]
            if not self._is_cache_valid(cache_info["cached_at"]):
                logger.debug("Analysis cache expired for playlist %s", playlist_id)
                self._remove_analysis_cache(cache_key)
                return None

            cache_file = Path(cache_info["file_path"])
            if cache_file.exists():
                with open(cache_file, "rb") as file:
                    # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
                    return pickle.load(file)

            self._remove_analysis_cache(cache_key)
            return None

        except Exception as exc:
            logger.warning("Error retrieving cached analysis data: %s", exc)
            return None

    def _remove_analysis_cache(self, cache_key: str) -> None:
        try:
            if cache_key in self.metadata["analysis"]:
                cache_info = self.metadata["analysis"][cache_key]
                cache_file = Path(cache_info["file_path"])
                if cache_file.exists():
                    cache_file.unlink()
                del self.metadata["analysis"][cache_key]
                self._save_metadata()
        except Exception as exc:
            logger.warning("Error removing analysis cache: %s", exc)

    # ------------------------------------------------------------------
    # Track-level cache
    # ------------------------------------------------------------------
    def _get_track_cache_file(self, spotify_id: str) -> Path:
        return self.track_cache_dir / f"{spotify_id}.json"

    def _load_track_cache(self, spotify_id: str, cache_file: Path) -> Dict[str, Any]:
        if not cache_file.exists():
            return {
                "spotify_id": spotify_id,
                "sources": {},
            }

        try:
            with open(cache_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if isinstance(data, dict) and "sources" in data:
                return data

            # Legacy format with raw ReccoBeats payload
            logger.debug("Migrating legacy track cache for %s", spotify_id)
            return {
                "spotify_id": spotify_id,
                "sources": {
                    "reccobeats": {
                        "fetched_at": time.time(),
                        "payload": data,
                    }
                },
            }
        except Exception as exc:
            logger.warning("Error loading track cache for %s: %s", spotify_id, exc)
            return {
                "spotify_id": spotify_id,
                "sources": {},
            }

    def _persist_track_cache(
        self, spotify_id: str, cache_payload: Dict[str, Any]
    ) -> None:
        cache_file = self._get_track_cache_file(spotify_id)
        with open(cache_file, "w", encoding="utf-8") as file:
            json.dump(cache_payload, file, indent=2)

        cache_key = f"track_{spotify_id}"
        self.metadata.setdefault("tracks", {})
        self.metadata["tracks"][cache_key] = {
            "spotify_id": spotify_id,
            "file_path": str(cache_file),
            "cached_at": time.time(),
            "size": cache_file.stat().st_size,
        }
        self._save_metadata()

    def cache_track_data(
        self,
        spotify_id: str,
        source: str,
        payload: Dict[str, Any],
        normalized: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            cache_file = self._get_track_cache_file(spotify_id)
            cache_payload = self._load_track_cache(spotify_id, cache_file)
            sources = cache_payload.setdefault("sources", {})
            sources[source] = {
                "fetched_at": time.time(),
                "payload": payload,
            }
            if normalized is not None:
                sources[source]["normalized"] = normalized

            self._persist_track_cache(spotify_id, cache_payload)
            # logger.debug("Cached %s data for track: %s", source, spotify_id)

        except Exception as exc:
            logger.warning(
                "Error caching %s data for track %s: %s", source, spotify_id, exc
            )

    def get_cached_track_data(
        self, spotify_id: str, source: str
    ) -> Optional[Dict[str, Any]]:
        try:
            tracks = self.metadata.get("tracks", {})
            cache_key = f"track_{spotify_id}"
            if cache_key not in tracks:
                return None

            cache_info = tracks[cache_key]
            cache_file = Path(cache_info["file_path"])
            if not cache_file.exists():
                self._remove_track_cache(cache_key)
                return None

            cache_payload = self._load_track_cache(spotify_id, cache_file)
            source_entry = cache_payload.get("sources", {}).get(source)
            if not source_entry:
                return None

            fetched_at = source_entry.get("fetched_at") or cache_info.get("cached_at")
            if not fetched_at or not self._is_cache_valid(fetched_at):
                self._remove_track_source(spotify_id, source, cache_payload, cache_file)
                return None

            return source_entry

        except Exception as exc:
            logger.warning(
                "Error retrieving cached %s data for %s: %s", source, spotify_id, exc
            )
            return None

    def _remove_track_source(
        self,
        spotify_id: str,
        source: str,
        cache_payload: Optional[Dict[str, Any]] = None,
        cache_file: Optional[Path] = None,
    ) -> None:
        try:
            cache_file = cache_file or self._get_track_cache_file(spotify_id)
            cache_payload = cache_payload or self._load_track_cache(
                spotify_id, cache_file
            )
            sources = cache_payload.get("sources", {})
            if source in sources:
                del sources[source]
                if sources:
                    self._persist_track_cache(spotify_id, cache_payload)
                else:
                    cache_key = f"track_{spotify_id}"
                    self._remove_track_cache(cache_key)
        except Exception as exc:
            logger.warning(
                "Error removing cached %s data for %s: %s", source, spotify_id, exc
            )

    def cache_track_reccobeats(
        self, spotify_id: str, reccobeats_data: Dict[str, Any]
    ) -> None:
        payload = dict(reccobeats_data)
        payload.setdefault("spotify_id", spotify_id)
        payload.setdefault("source", "reccobeats")
        self.cache_track_data(spotify_id, "reccobeats", payload)

    def get_cached_track_reccobeats(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        cached = self.get_cached_track_data(spotify_id, "reccobeats")
        if cached:
            return cached.get("payload")
        return None

    def cache_playlist_tracks(
        self, playlist_id: str, user_id: str, tracks: List[Dict[str, Any]]
    ) -> None:
        """Cache the track list for a playlist with cache status for each track."""
        try:
            cache_key = f"playlist_tracks_{playlist_id}_{user_id}"

            # Process tracks with cache status
            processed_tracks = []
            for track in tracks:
                track_id = track.get("id")
                if not track_id:
                    continue

                # Check cache status for this track
                spotify_cached = (
                    self.get_cached_track_data(track_id, "spotify") is not None
                )
                reccobeats_cached = (
                    self.get_cached_track_reccobeats(track_id) is not None
                )

                processed_track = {
                    "id": track_id,
                    "name": track.get("name", ""),
                    "artists": [
                        artist.get("name", "") for artist in track.get("artists", [])
                    ],
                    "album": track.get("album", {}).get("name", ""),
                    "added_at": track.get("added_at"),
                    "spotify_cached": spotify_cached,
                    "reccobeats_cached": reccobeats_cached,
                    "position": track.get("position", len(processed_tracks)),
                }
                processed_tracks.append(processed_track)

            cache_data = {
                "tracks": processed_tracks,
                "total_tracks": len(processed_tracks),
                "spotify_cached_count": sum(
                    1 for t in processed_tracks if t["spotify_cached"]
                ),
                "reccobeats_cached_count": sum(
                    1 for t in processed_tracks if t["reccobeats_cached"]
                ),
                "last_updated": time.time(),
            }

            cache_file = self.data_cache_dir / f"{cache_key}.json"
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            # Update metadata
            playlists_cache = self.metadata.setdefault("playlist_tracks", {})
            playlists_cache[cache_key] = {
                "file_path": str(cache_file),
                "cached_at": time.time(),
                "track_count": len(processed_tracks),
            }
            self._save_metadata()

            logger.info(
                "Cached %d tracks for playlist %s (%d Spotify cached, %d ReccoBeats cached)",
                len(processed_tracks),
                playlist_id,
                cache_data["spotify_cached_count"],
                cache_data["reccobeats_cached_count"],
            )

        except Exception as exc:
            logger.error("Error caching playlist tracks: %s", exc)

    def get_cached_playlist_tracks(
        self, playlist_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached track list with cache status for a playlist."""
        try:
            cache_key = f"playlist_tracks_{playlist_id}_{user_id}"
            playlists_cache = self.metadata.get("playlist_tracks", {})

            if cache_key not in playlists_cache:
                return None

            cache_file = Path(playlists_cache[cache_key]["file_path"])
            if not cache_file.exists():
                del playlists_cache[cache_key]
                self._save_metadata()
                return None

            with open(cache_file, "r") as f:
                return json.load(f)

        except Exception as exc:
            logger.warning("Error getting cached playlist tracks: %s", exc)
            return None

    def update_playlist_track_cache_status(
        self, playlist_id: str, user_id: str, track_id: str
    ) -> None:
        """Update cache status for a specific track in a playlist."""
        try:
            cached_data = self.get_cached_playlist_tracks(playlist_id, user_id)
            if not cached_data:
                return

            # Find and update the track
            for track in cached_data["tracks"]:
                if track["id"] == track_id:
                    track["spotify_cached"] = (
                        self.get_cached_track_data(track_id, "spotify") is not None
                    )
                    track["reccobeats_cached"] = (
                        self.get_cached_track_reccobeats(track_id) is not None
                    )
                    break

            # Update counts and save
            cached_data["spotify_cached_count"] = sum(
                1 for t in cached_data["tracks"] if t["spotify_cached"]
            )
            cached_data["reccobeats_cached_count"] = sum(
                1 for t in cached_data["tracks"] if t["reccobeats_cached"]
            )
            cached_data["last_updated"] = time.time()

            cache_key = f"playlist_tracks_{playlist_id}_{user_id}"
            cache_file = self.data_cache_dir / f"{cache_key}.json"
            with open(cache_file, "w") as f:
                json.dump(cached_data, f, indent=2)

        except Exception as exc:
            logger.warning("Error updating playlist track cache status: %s", exc)

    def _remove_track_cache(self, cache_key: str) -> None:
        try:
            tracks = self.metadata.get("tracks", {})
            if cache_key in tracks:
                cache_info = tracks[cache_key]
                cache_file = Path(cache_info["file_path"])
                if cache_file.exists():
                    cache_file.unlink()
                del tracks[cache_key]
                self._save_metadata()
        except Exception as exc:
            logger.warning("Error removing track cache: %s", exc)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def cleanup_old_cache(self) -> None:
        try:
            cleaned_count = 0

            for cache_key in list(self.metadata["playlists"].keys()):
                cache_info = self.metadata["playlists"][cache_key]
                if not self._is_cache_valid(cache_info["cached_at"]):
                    self._remove_playlist_cache(cache_key)
                    cleaned_count += 1

            for url_hash in list(self.metadata["images"].keys()):
                cache_info = self.metadata["images"][url_hash]
                if not self._is_cache_valid(cache_info["cached_at"]):
                    self._remove_image_cache(url_hash)
                    cleaned_count += 1

            for cache_key in list(self.metadata["analysis"].keys()):
                cache_info = self.metadata["analysis"][cache_key]
                if not self._is_cache_valid(cache_info["cached_at"]):
                    self._remove_analysis_cache(cache_key)
                    cleaned_count += 1

            tracks = self.metadata.get("tracks", {})
            for cache_key in list(tracks.keys()):
                cache_info = tracks[cache_key]
                cache_file = Path(cache_info["file_path"])
                spotify_id = cache_info.get("spotify_id") or cache_key.replace(
                    "track_", ""
                )
                cache_payload = self._load_track_cache(spotify_id, cache_file)
                sources = cache_payload.get("sources", {})
                for source_name in list(sources.keys()):
                    fetched_at = sources[source_name].get(
                        "fetched_at", cache_info.get("cached_at", 0)
                    )
                    if not fetched_at or not self._is_cache_valid(fetched_at):
                        self._remove_track_source(
                            spotify_id, source_name, cache_payload, cache_file
                        )
                        cleaned_count += 1
                        cache_payload = self._load_track_cache(spotify_id, cache_file)
                        sources = cache_payload.get("sources", {})

                if not sources:
                    self._remove_track_cache(cache_key)

            if cleaned_count > 0:
                logger.info("Cleaned up %s expired cache entries", cleaned_count)

        except Exception as exc:
            logger.warning("Error during cache cleanup: %s", exc)

    def get_cache_stats(self) -> Dict[str, Any]:
        try:
            total_size = 0
            file_count = 0

            for directory in [
                self.data_cache_dir,
                self.image_cache_dir,
                self.analysis_cache_dir,
            ]:
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                        file_count += 1

            return {
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
                "playlists_cached": len(self.metadata["playlists"]),
                "images_cached": len(self.metadata["images"]),
                "analysis_cached": len(self.metadata["analysis"]),
            }

        except Exception as exc:
            logger.warning("Error getting cache stats: %s", exc)
            return {}

    def clear_all_cache(self) -> None:
        try:
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)

            for directory in [
                self.cache_dir,
                self.data_cache_dir,
                self.image_cache_dir,
                self.analysis_cache_dir,
            ]:
                directory.mkdir(parents=True, exist_ok=True)

            self.metadata = {
                "playlists": {},
                "images": {},
                "analysis": {},
                "tracks": {},
                "created_at": time.time(),
            }
            self._save_metadata()
            logger.info("Cleared all cache data")

        except Exception as exc:
            logger.error("Error clearing cache: %s", exc)

    def get_detailed_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information for exploration."""
        try:
            detailed_info = {
                "summary": self.get_cache_stats(),
                "playlists": [],
                "tracks": [],
                "images": [],
                "analysis": [],
            }
            expired_playlists = 0

            # Get detailed playlist info with actual names
            for cache_key, cache_info in list(self.metadata["playlists"].items()):
                playlist_id = cache_info.get("playlist_id", "")
                if not self._is_cache_valid(cache_info.get("cached_at", 0)):
                    expired_playlists += 1
                    self._remove_playlist_cache(cache_key)
                    continue

                try:
                    playlist_data = self.get_cached_playlist_data(
                        playlist_id, cache_info.get("user_id")
                    )
                    if not playlist_data:
                        continue
                    name = playlist_data.get(
                        "name", f"Playlist {playlist_id or 'Unknown'}"
                    )
                    tracks_count = playlist_data.get("tracks", {}).get("total", 0)
                except Exception:
                    # Fallback to basic info if cache read fails
                    name = f"Playlist {playlist_id or 'Unknown'}"
                    tracks_count = 0

                detailed_info["playlists"].append(
                    {
                        "cache_key": cache_key,
                        "playlist_id": cache_info.get("playlist_id", ""),
                        "user_id": cache_info.get("user_id", ""),
                        "name": name,
                        "tracks_count": tracks_count,
                        "cached_at": cache_info.get("cached_at", 0),
                        "size_mb": round(
                            self._get_file_size_mb(cache_info.get("file_path", "")), 2
                        ),
                    }
                )

            if expired_playlists:
                logger.info(
                    "Removed %s expired playlist cache entr%s while loading cache explorer",
                    expired_playlists,
                    "y" if expired_playlists == 1 else "ies",
                )

            # Get detailed track info with actual track names (sample first 30 for performance)
            tracks_sample = list(self.metadata.get("tracks", {}).items())[:30]
            for cache_key, cache_info in tracks_sample:
                try:
                    spotify_id = cache_info.get(
                        "spotify_id", cache_key.replace("track_", "")
                    )
                    track_file = Path(cache_info.get("file_path", ""))

                    # Try to get actual track data
                    track_name = f"Track {spotify_id}"
                    artists = []
                    album = ""
                    sources = ["cached"]

                    if track_file.exists():
                        try:
                            with open(track_file, "r", encoding="utf-8") as f:
                                track_data = json.load(f)

                            # Extract Spotify track info if available
                            spotify_data = track_data.get("sources", {}).get(
                                "spotify", {}
                            )
                            if spotify_data and "normalized" in spotify_data:
                                normalized = spotify_data["normalized"]
                                track_name = normalized.get("name", track_name)
                                artists = normalized.get("artists", [])
                                album = normalized.get("album", "")

                            # Get available sources
                            sources = list(track_data.get("sources", {}).keys())

                        except Exception as exc:
                            logger.debug(
                                "Error reading track cache %s: %s", cache_key, exc
                            )

                    detailed_info["tracks"].append(
                        {
                            "cache_key": cache_key,
                            "spotify_id": spotify_id,
                            "name": track_name,
                            "artists": artists,
                            "album": album,
                            "sources": sources,
                            "cached_at": cache_info.get("cached_at", 0),
                            "size_mb": round(
                                self._get_file_size_mb(cache_info.get("file_path", "")),
                                2,
                            ),
                        }
                    )
                except Exception as exc:
                    logger.debug("Error processing track %s: %s", cache_key, exc)
                    continue

            # Get image info from metadata (sample first 15 for performance)
            images_sample = list(self.metadata["images"].items())[:15]
            for url_hash, cache_info in images_sample:
                detailed_info["images"].append(
                    {
                        "cache_key": url_hash,
                        "url": cache_info.get("url", ""),
                        "cached_at": cache_info.get("cached_at", 0),
                        "file_size_kb": round(cache_info.get("file_size", 0) / 1024, 1),
                        "file_path": cache_info.get("file_path", ""),
                    }
                )

            # Get analysis info from metadata
            for cache_key, cache_info in list(self.metadata["analysis"].items()):
                detailed_info["analysis"].append(
                    {
                        "cache_key": cache_key,
                        "playlist_id": cache_info.get("playlist_id", ""),
                        "analysis_type": cache_info.get("analysis_type", ""),
                        "cached_at": cache_info.get("cached_at", 0),
                        "size_mb": round(
                            self._get_file_size_mb(cache_info.get("file_path", "")), 2
                        ),
                    }
                )

            return detailed_info

        except Exception as exc:
            logger.error("Error getting detailed cache info: %s", exc)
            return {"error": str(exc)}

    def _get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB."""
        try:
            path = Path(file_path)
            if path.exists():
                return path.stat().st_size / (1024 * 1024)
        except Exception:
            pass
        return 0.0


persistent_cache = PersistentCache()

__all__ = ["PersistentCache", "persistent_cache"]
