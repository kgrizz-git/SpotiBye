"""ReccoBeats API client extracted from the monolithic script."""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..caching.analysis import AnalysisTask
from ..caching.persistent_cache import persistent_cache
from ..caching.track_cache import cache_reccobeats_mapping, get_cached_reccobeats_mapping
from ..config import RECCOBEATS_BASE_URL, RECCOBEATS_TIMEOUT
from ..logging_config import logger


class ReccoBeatsAPI:
    """Wrapper for ReccoBeats API calls with correct two-step process and cancellation support."""

    def __init__(self) -> None:
        self.base_url = RECCOBEATS_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Spotify-Playlist-Exporter/1.0'})

    # ------------------------------------------------------------------
    # Track lookup helpers
    # ------------------------------------------------------------------
    def get_reccobeats_id_from_spotify_id(
        self,
        spotify_track_id: str,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> str:
        try:
            if analysis_task and analysis_task.is_cancelled():
                return ""

            if not spotify_track_id or len(spotify_track_id) != 22:
                logger.warning("Invalid Spotify track ID format: %s", spotify_track_id)
                return ""

            url = f"{self.base_url}/track"
            params = {'ids': spotify_track_id}
            response = self.session.get(url, params=params, timeout=RECCOBEATS_TIMEOUT)

            if analysis_task and analysis_task.is_cancelled():
                return ""

            if response.status_code == 200:
                return self._extract_reccobeats_id(spotify_track_id, response.json())

            if response.status_code == 404:
                logger.debug("Track %s not found in ReccoBeats database", spotify_track_id)
            elif response.status_code == 429:
                logger.warning("ReccoBeats API rate limit hit for track lookup %s", spotify_track_id)
            else:
                logger.warning(
                    "ReccoBeats track lookup API error %s for %s: %s",
                    response.status_code,
                    spotify_track_id,
                    response.text,
                )
            return ""

        except requests.exceptions.Timeout:
            logger.warning("ReccoBeats track lookup API timeout for %s", spotify_track_id)
            return ""
        except requests.exceptions.RequestException as exc:
            logger.warning("ReccoBeats track lookup API request error for %s: %s", spotify_track_id, exc)
            return ""
        except Exception as exc:
            logger.error("Unexpected error getting ReccoBeats ID for %s: %s", spotify_track_id, exc)
            return ""

    def _extract_reccobeats_id(self, spotify_track_id: str, data: Any) -> str:
        tracks_data = None
        if isinstance(data, dict) and 'content' in data:
            tracks_data = data['content']
        elif isinstance(data, list):
            tracks_data = data
        elif isinstance(data, dict):
            for key in ['tracks', 'data', 'items']:
                if key in data:
                    tracks_data = data[key]
                    break
            else:
                tracks_data = [data]

        if tracks_data:
            track_data = tracks_data[0]
            reccobeats_id = track_data.get('id')
            if reccobeats_id:
                logger.debug("Found ReccoBeats ID %s for Spotify ID %s", reccobeats_id, spotify_track_id)
                return reccobeats_id

        logger.debug("No tracks found in ReccoBeats for %s", spotify_track_id)
        return ""

    def get_audio_features_by_reccobeats_id(
        self,
        reccobeats_id: str,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> Dict[str, Any]:
        try:
            if analysis_task and analysis_task.is_cancelled():
                return {}

            if not reccobeats_id or len(reccobeats_id) != 36:
                logger.warning("Invalid ReccoBeats ID format: %s", reccobeats_id)
                return {}

            url = f"{self.base_url}/track/{reccobeats_id}/audio-features"
            response = self.session.get(url, timeout=RECCOBEATS_TIMEOUT)

            if analysis_task and analysis_task.is_cancelled():
                return {}

            if response.status_code == 200:
                data = response.json()
                expected_features = [
                    'danceability',
                    'energy',
                    'valence',
                    'acousticness',
                    'instrumentalness',
                    'speechiness',
                    'loudness',
                    'tempo',
                ]
                if any(feature in data for feature in expected_features):
                    return data
                logger.warning(
                    "ReccoBeats response missing expected audio features for %s", reccobeats_id
                )
                return {}

            if response.status_code == 404:
                logger.debug("Audio features not found for ReccoBeats ID %s", reccobeats_id)
            elif response.status_code == 429:
                logger.warning("ReccoBeats API rate limit hit for audio features %s", reccobeats_id)
            else:
                logger.warning(
                    "ReccoBeats audio features API error %s for %s: %s",
                    response.status_code,
                    reccobeats_id,
                    response.text,
                )
            return {}

        except requests.exceptions.Timeout:
            logger.warning("ReccoBeats audio features API timeout for %s", reccobeats_id)
            return {}
        except requests.exceptions.RequestException as exc:
            logger.warning("ReccoBeats audio features API request error for %s: %s", reccobeats_id, exc)
            return {}
        except Exception as exc:
            logger.error("Unexpected error getting audio features for %s: %s", reccobeats_id, exc)
            return {}

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------
    def get_multiple_reccobeats_ids(
        self,
        spotify_track_ids: List[str],
        max_batch_size: int = 10,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> Dict[str, str]:
        id_mapping: Dict[str, str] = {}

        try:
            total_batches = (len(spotify_track_ids) + max_batch_size - 1) // max_batch_size
            logger.info("Starting ReccoBeats ID lookup for %s tracks (%s batches)", len(spotify_track_ids), total_batches)
            
            for i in range(0, len(spotify_track_ids), max_batch_size):
                if analysis_task and analysis_task.is_cancelled():
                    logger.info("ReccoBeats batch lookup cancelled")
                    return id_mapping

                batch = spotify_track_ids[i:i + max_batch_size]
                batch_num = i // max_batch_size + 1
                
                # Log progress every 50 tracks or every 10 batches, whichever comes first
                if i % 50 == 0 or batch_num % 10 == 1:
                    logger.info("Processing ReccoBeats ID lookup batch %s/%s (tracks %s-%s)", 
                              batch_num, total_batches, i + 1, min(i + max_batch_size, len(spotify_track_ids)))

                try:
                    url = f"{self.base_url}/track"
                    params = {'ids': ','.join(batch)}
                    response = self.session.get(url, params=params, timeout=RECCOBEATS_TIMEOUT)

                    if analysis_task and analysis_task.is_cancelled():
                        logger.info("ReccoBeats batch lookup cancelled after API call")
                        return id_mapping

                    if response.status_code == 200:
                        self._process_batch_response(batch, response.json(), id_mapping)
                    elif response.status_code == 429:
                        logger.warning("ReccoBeats API rate limit hit for batch lookup")
                        time.sleep(2.0)
                    else:
                        logger.warning(
                            "ReccoBeats batch lookup API error %s: %s",
                            response.status_code,
                            response.text,
                        )

                except Exception as exc:
                    logger.warning("Error processing batch %s: %s", i // max_batch_size + 1, exc)
                    continue

                if i + max_batch_size < len(spotify_track_ids):
                    if analysis_task and analysis_task.is_cancelled():
                        return id_mapping
                    time.sleep(0.5)

            logger.info(
                "Successfully mapped %s/%s Spotify IDs to ReccoBeats IDs",
                len(id_mapping),
                len(spotify_track_ids),
            )
            return id_mapping

        except Exception as exc:
            logger.error("Error in batch ReccoBeats ID lookup: %s", exc)
            return id_mapping

    def _process_batch_response(
        self,
        batch: List[str],
        data: Any,
        id_mapping: Dict[str, str],
    ) -> None:
        tracks_data = None
        if isinstance(data, dict) and 'content' in data:
            tracks_data = data['content']
        elif isinstance(data, list):
            tracks_data = data
        elif isinstance(data, dict):
            for key in ['tracks', 'data', 'items']:
                if key in data:
                    tracks_data = data[key]
                    break
            else:
                tracks_data = [data]

        if not tracks_data:
            logger.debug("No tracks data found in batch response for batch size %s", len(batch))
            return

        for track_data in tracks_data:
            if isinstance(track_data, dict):
                spotify_url = track_data.get('href', '')
                reccobeats_id = track_data.get('id', '')

                spotify_id = None
                if spotify_url and 'spotify.com/track/' in spotify_url:
                    spotify_id = spotify_url.split('/')[-1]

                if spotify_id and reccobeats_id and spotify_id in batch:
                    id_mapping[spotify_id] = reccobeats_id
                    # logger.debug("Mapped %s -> %s", spotify_id, reccobeats_id)
                else:
                    logger.debug(
                        "Could not map track: spotify_id=%s, reccobeats_id=%s, in_batch=%s",
                        spotify_id,
                        reccobeats_id,
                        spotify_id in batch if spotify_id else False,
                    )

    # ------------------------------------------------------------------
    # Audio features (multi-track)
    # ------------------------------------------------------------------
    def get_multiple_track_audio_features(
        self,
        spotify_track_ids: List[str],
        max_concurrent: int = 2,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> Dict[str, Dict[str, Any]]:
        return self._get_multiple_track_audio_features_impl(
            spotify_track_ids,
            max_concurrent,
            analysis_task,
            use_cache=False,
        )

    def get_multiple_track_audio_features_safe(
        self,
        spotify_track_ids: List[str],
        max_concurrent: int = 2,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> Dict[str, Dict[str, Any]]:
        return self._get_multiple_track_audio_features_impl(
            spotify_track_ids,
            max_concurrent,
            analysis_task,
            use_cache=True,
        )

    def _get_multiple_track_audio_features_impl(
        self,
        spotify_track_ids: List[str],
        max_concurrent: int,
        analysis_task: Optional[AnalysisTask],
        use_cache: bool,
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}

        try:
            if analysis_task and analysis_task.is_cancelled():
                return results

            logger.info("Step 1: Getting ReccoBeats IDs for %s tracks", len(spotify_track_ids))

            cached_ids: Dict[str, str] = {}
            missing_ids: List[str] = []
            for spotify_id in spotify_track_ids:
                cached_id = get_cached_reccobeats_mapping(spotify_id)
                if cached_id:
                    cached_ids[spotify_id] = cached_id
                else:
                    missing_ids.append(spotify_id)

            id_mapping: Dict[str, str] = dict(cached_ids)
            if missing_ids:
                logger.info("Looking up ReccoBeats IDs for %s uncached tracks", len(missing_ids))
                fresh_mapping = self.get_multiple_reccobeats_ids(missing_ids, analysis_task=analysis_task)
                for spotify_id, reccobeats_id in fresh_mapping.items():
                    id_mapping[spotify_id] = reccobeats_id
                    cache_reccobeats_mapping(spotify_id, reccobeats_id)

            if analysis_task and analysis_task.is_cancelled():
                logger.info("ReccoBeats analysis cancelled after ID mapping")
                return results

            if not id_mapping:
                logger.warning("No ReccoBeats IDs found for any tracks")
                return results

            logger.info("Step 2: Getting audio features for %s mapped tracks", len(id_mapping))

            # Get the list of Spotify IDs to process
            spotify_ids = list(id_mapping.keys())
            
            # Count cached vs uncached tracks for logging
            cached_count = 0
            uncached_tracks = []
            
            if use_cache:
                for spotify_id in spotify_ids:
                    cached_data = persistent_cache.get_cached_track_reccobeats(spotify_id)
                    if cached_data:
                        cached_count += 1
                        results[spotify_id] = cached_data
                    else:
                        uncached_tracks.append(spotify_id)
                
                logger.info("Found %s cached ReccoBeats features, fetching %s uncached tracks", cached_count, len(uncached_tracks))
            
            def fetch_audio_features(spotify_id: str, reccobeats_id: str) -> Tuple[str, Dict[str, Any]]:
                if use_cache:
                    cached_data = persistent_cache.get_cached_track_reccobeats(spotify_id)
                    if cached_data:
                        logger.debug("Using cached ReccoBeats data for track: %s", spotify_id)
                        return spotify_id, cached_data

                for attempt in range(3):
                    try:
                        if analysis_task and analysis_task.is_cancelled():
                            return spotify_id, {}

                        if attempt > 0:
                            time.sleep(0.5 * attempt)

                        features = self.get_audio_features_by_reccobeats_id(reccobeats_id, analysis_task)

                        if analysis_task and analysis_task.is_cancelled():
                            return spotify_id, {}

                        if features:
                            features.update({'spotify_id': spotify_id, 'reccobeats_id': reccobeats_id})
                            if use_cache:
                                persistent_cache.cache_track_reccobeats(spotify_id, features)
                            return spotify_id, features

                    except Exception as exc:
                        if attempt == 2:
                            logger.warning("Failed to get audio features for %s after 3 attempts: %s", spotify_id, exc)
                            return spotify_id, {}
                        time.sleep(1.0)

                return spotify_id, {}

            batch_size = min(max_concurrent, 3)
            # Only process uncached tracks if using cache
            spotify_ids = uncached_tracks if use_cache else list(id_mapping.keys())
            total_batches = (len(spotify_ids) + batch_size - 1) // batch_size
            processed_count = 0

            if spotify_ids:
                logger.info("Starting audio features fetch for %s uncached tracks (%s batches)", len(spotify_ids), total_batches)
            else:
                logger.info("All %s tracks already cached, no fetching needed", cached_count)
                return results

            for i in range(0, len(spotify_ids), batch_size):
                if analysis_task and analysis_task.is_cancelled():
                    logger.info("ReccoBeats audio features cancelled during batch processing")
                    return results

                batch_spotify_ids = spotify_ids[i:i + batch_size]
                batch_num = i // batch_size + 1
                
                # Log progress every 50 tracks or every 10 batches, whichever comes first
                if i % 50 == 0 or batch_num % 10 == 1:
                    logger.info("Processing audio features batch %s/%s (tracks %s-%s, %s features found so far)", 
                              batch_num, total_batches, i + 1, min(i + batch_size, len(spotify_ids)), len(results))

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                    future_to_track = {
                        executor.submit(fetch_audio_features, spotify_id, id_mapping[spotify_id]): spotify_id
                        for spotify_id in batch_spotify_ids
                    }

                    for future in concurrent.futures.as_completed(future_to_track):
                        if analysis_task and analysis_task.is_cancelled():
                            logger.info("ReccoBeats audio features cancelled during future processing")
                            for remaining_future in future_to_track:
                                remaining_future.cancel()
                            return results

                        try:
                            spotify_id, features = future.result(timeout=RECCOBEATS_TIMEOUT * 3)
                            if features:
                                results[spotify_id] = features
                        except Exception as exc:
                            spotify_id = future_to_track[future]
                            logger.warning("Error processing audio features for %s: %s", spotify_id, exc)

                if i + batch_size < len(spotify_ids):
                    if analysis_task and analysis_task.is_cancelled():
                        return results
                    time.sleep(1.5)
                
                processed_count += len(batch_spotify_ids)
                
                # Log intermediate progress every 50 tracks processed
                if processed_count % 50 == 0 or processed_count == len(spotify_ids):
                    logger.info("Audio features progress: %s/%s tracks processed (%s features found)", 
                              processed_count, len(spotify_ids), len(results))

            success_rate = len(results) / len(spotify_track_ids) * 100 if spotify_track_ids else 0
            logger.info(
                "Successfully fetched audio features for %s/%s tracks from ReccoBeats (%s%%)",
                len(results),
                len(spotify_track_ids),
                int(success_rate),
            )
            return results

        except Exception as exc:
            logger.error("Error in multiple track audio features: %s", exc)
            return results


def get_reccobeats_api() -> ReccoBeatsAPI:
    return ReccoBeatsAPI()


__all__ = ["ReccoBeatsAPI", "get_reccobeats_api"]
