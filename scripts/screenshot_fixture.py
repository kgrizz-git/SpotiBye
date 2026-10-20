"""Fictional fixture data for ``scripts/capture_screenshots.py``.

Everything here is invented: playlist names, the ``demo-user`` owner, artist,
album and track names, audio-feature values, and the generated cover art. No
real Spotify data is used, so screenshots built from it contain no personal
information. Names are assembled from small word lists and may rarely collide
with a real title by chance, but none is taken from a real catalogue.

``build_test_data(base_url)`` returns the ``test_data`` dict understood by
``src/frontend/tests/mock_backend.py``.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_covers() -> Any:
    """Load the sibling covers module by path (works however this file is loaded)."""
    path = Path(__file__).with_name("screenshot_covers.py")
    spec = importlib.util.spec_from_file_location("screenshot_covers", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_covers"] = module
    spec.loader.exec_module(module)
    return module


covers = _load_covers()

DEMO_USER = {"id": "demo-user", "display_name": "demo-user"}

# (playlist name, description, track count)
PLAYLISTS: list[tuple[str, str, int]] = [
    ("Late Night Drive", "Synthetic highways after midnight", 32),
    ("Sunday Coffee", "Slow mornings and warm mugs", 24),
    ("Rainy Window", "Grey skies, soft piano", 28),
    ("Focus Hour", "Steady beats for deep work", 41),
    ("Neon Gym", "High tempo, high energy", 36),
    ("Campfire Stories", "Acoustic and unhurried", 19),
    ("Golden Hour Walk", "Warm light, easy tempo", 27),
    ("Road Trip Mix", "Windows down, volume up", 44),
    ("Cozy Cabin", "Wool socks and fireplaces", 22),
    ("Deep Space Study", "Ambient drift for long sessions", 38),
    ("Weekend Cleanup", "Upbeat chores soundtrack", 30),
    ("Moonlit Piano", "Quiet keys before sleep", 17),
    ("Summer Block Party", "Sunny, loud, and danceable", 46),
    ("Lo-Fi Library", "Dusty loops for reading", 35),
]

_ADJECTIVES = [
    "Neon",
    "Paper",
    "Velvet",
    "Quiet",
    "Golden",
    "Hollow",
    "Silver",
    "Lazy",
    "Electric",
    "Faded",
    "Wild",
    "Gentle",
    "Midnight",
    "Amber",
    "Distant",
    "Crimson",
    "Frozen",
    "Hidden",
    "Slow",
    "Bright",
]
_NOUNS = [
    "Orchard",
    "Tides",
    "Lanterns",
    "Harbor",
    "Meadow",
    "Skyline",
    "Echoes",
    "Compass",
    "Garden",
    "Satellite",
    "Postcards",
    "Rooftops",
    "Embers",
    "Valley",
    "Carousel",
    "Horizon",
    "Static",
    "Blossom",
    "Lighthouse",
    "Rivers",
]
_ARTIST_FIRST = [
    "Lumora",
    "Kestrel",
    "Orbit",
    "Quillon",
    "Marlow",
    "Tamsin",
    "Brindle",
    "Calloway",
    "Fennick",
    "Ostara",
    "Pelham",
    "Rowan",
    "Sundial",
    "Wren",
    "Alder",
    "Juniper",
    "Corvid",
    "Maple",
]
_ARTIST_SECOND = [
    "Vale",
    "Bloom",
    "Parade",
    "Fields",
    "Union",
    "Collective",
    "Hollow",
    "Atlas",
    "Signal",
    "House",
    "Choir",
    "Garden",
    "Radio",
    "Club",
]
_GENRES = [
    ("synth pop", 0.26),
    ("indie folk", 0.19),
    ("lo-fi", 0.17),
    ("ambient", 0.12),
    ("dream pop", 0.10),
    ("electronic", 0.09),
    ("acoustic", 0.07),
]
_PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


ALBUM_COUNT = 22
ALBUMS_PER_PLAYLIST = 6
# 1-based playlist numbers that use one full-bleed album cover, not a mosaic.
SINGLE_COVER = {3, 8, 12}


def _make_albums(rng: random.Random) -> list[dict[str, Any]]:
    """Invent the album pool: name, artist, and the generated cover image."""
    albums: list[dict[str, Any]] = []
    names: set[str] = set()
    while len(albums) < ALBUM_COUNT:
        title = f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}"
        if title in names:
            continue
        names.add(title)
        artist = f"{rng.choice(_ARTIST_FIRST)} {rng.choice(_ARTIST_SECOND)}"
        cover = covers.make_album_cover(rng, len(albums), title, artist)
        albums.append({"title": title, "artist": artist, "cover": cover})
    return albums


def _make_tracks(
    rng: random.Random, pid: str, count: int, albums: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    while len(items) < count:
        title = f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}"
        if title in seen:
            continue
        seen.add(title)
        i = len(items)
        album = rng.choice(albums)
        items.append(
            {
                "added_at": "2026-01-01T00:00:00Z",
                "track": {
                    "id": f"demo_trk_{pid[-2:]}{i:02d}",
                    "name": title,
                    "artists": [{"name": album["artist"]}],
                    "album": {"name": album["title"]},
                    "duration_ms": rng.randint(150_000, 290_000),
                    "preview_url": None,
                    "track_number": i + 1,
                },
            }
        )
    return items


def _make_explorer_data(
    rng: random.Random, tracks: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Legacy-shaped data the cache explorer reads from ``cache_data``.

    The backend explorer never fills ``tracks_by_playlist`` or
    ``features_by_track`` itself, so the capture script injects these.
    """
    by_playlist: dict[str, list[dict[str, Any]]] = {}
    features: dict[str, dict[str, Any]] = {}
    for pid, items in tracks.items():
        rows = []
        for it in items:
            t = it["track"]
            rows.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "artists": [a["name"] for a in t["artists"]],
                    "album": t["album"],
                    "duration_ms": t["duration_ms"],
                    "spotify_cached": True,
                    "reccobeats_cached": True,
                }
            )
            features[t["id"]] = {
                "danceability": rng.uniform(0.4, 0.85),
                "energy": rng.uniform(0.35, 0.9),
                "valence": rng.uniform(0.2, 0.8),
                "tempo": rng.uniform(80, 135),
                "acousticness": rng.uniform(0.05, 0.7),
                "instrumentalness": rng.uniform(0.0, 0.5),
                "liveness": rng.uniform(0.05, 0.3),
                "speechiness": rng.uniform(0.03, 0.12),
                "key": rng.randint(0, 11),
                "mode": rng.randint(0, 1),
                "loudness": rng.uniform(-13.0, -5.0),
            }
        by_playlist[pid] = rows
    return {"tracks_by_playlist": by_playlist, "features_by_track": features}


def _fmt_duration(ms: int) -> str:
    hrs, rem = divmod(ms // 1000, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs}h {mins}m {secs}s" if hrs else f"{mins}m {secs}s"


def _make_analysis(
    rng: random.Random, pid: str, items: list[dict[str, Any]], now_iso: str
) -> dict[str, Any]:
    tracks = [it["track"] for it in items]
    total_ms = sum(t["duration_ms"] for t in tracks)
    counts: dict[str, int] = {}
    for t in tracks:
        name = t["artists"][0]["name"]
        counts[name] = counts.get(name, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    n = len(tracks)
    genres = {
        g: {"count": max(1, round(n * share)), "percentage": round(share * 100)}
        for g, share in _GENRES
    }

    def avg(lo: float, hi: float) -> float:
        return round(rng.uniform(lo, hi), 3)

    key_pcts = dict.fromkeys(_PITCHES, 0.0)
    dominant = rng.choice(_PITCHES)
    key_pcts[dominant] = 24.0
    return {
        "job_id": f"demo_job_{pid}",
        "playlist_id": pid,
        "user_id": DEMO_USER["id"],
        "status": "completed",
        "computed_at": now_iso,
        "completed_at": now_iso,
        "overview": {
            "total_tracks": n,
            "total_duration_ms": total_ms,
            "average_duration_ms": total_ms // n,
            "formatted_duration": _fmt_duration(total_ms),
        },
        "artists": {
            "unique_artists": len(counts),
            "top_artists": [{"artist": a, "count": c} for a, c in top],
            "diversity": round(len(counts) / n, 2),
        },
        "genre_distribution": genres,
        "audio_features": {
            "track_count": n,
            "averages": {
                "acousticness": avg(0.1, 0.6),
                "danceability": avg(0.45, 0.8),
                "energy": avg(0.4, 0.85),
                "instrumentalness": avg(0.05, 0.4),
                "liveness": avg(0.08, 0.25),
                "loudness": round(rng.uniform(-12.0, -6.0), 1),
                "speechiness": avg(0.03, 0.12),
                "tempo": round(rng.uniform(92, 128), 1),
                "valence": avg(0.35, 0.75),
            },
            "key_mode_distribution": {
                "key_percentages": key_pcts,
                "dominant_key": dominant,
                "dominant_key_percentage": 24.0,
                "mode_percentages": {"major": 62.0, "minor": 38.0},
                "dominant_mode": "major",
            },
        },
        "insights": [],
        "reccobeats_metadata": {
            "isrc_available": n,
            "popularity_min": 12,
            "popularity_max": 78,
            "retrieved_at": now_iso,
        },
        "unique_track_count": n,
        "audio_features_resolved_count": n,
        "track_metadata_resolved_count": n,
        "enrichment_resolved_track_count": n,
        "errors": [],
        "schema_version": "1.1",
    }


def build_test_data(base_url: str) -> dict[str, Any]:
    """Build the mock backend ``test_data`` dict; covers are served at ``base_url``."""
    rng = covers.make_rng(20261019)
    now_iso = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    albums = _make_albums(rng)
    playlists: list[dict[str, Any]] = []
    tracks: dict[str, list[dict[str, Any]]] = {}
    analysis: dict[str, dict[str, Any]] = {}
    static: dict[str, tuple[str, bytes]] = {}
    for idx, (name, desc, count) in enumerate(PLAYLISTS, start=1):
        pid = f"demo_playlist_{idx:02d}"
        cover_path = f"/covers/{pid}.png"
        # Stride 4 over the pool: each album lands in ~2-3 mosaics, none in all.
        subset = [
            albums[(idx * 4 + k) % ALBUM_COUNT] for k in range(ALBUMS_PER_PLAYLIST)
        ]
        art = [a["cover"] for a in subset]
        image = art[0] if idx in SINGLE_COVER else covers.mosaic(art)
        static[cover_path] = ("image/png", covers.to_png(image))
        tracks[pid] = _make_tracks(rng, pid, count, subset)
        analysis[pid] = _make_analysis(rng, pid, tracks[pid], now_iso)
        playlists.append(
            {
                "id": pid,
                "name": name,
                "description": desc,
                "public": idx % 3 != 0,
                "snapshot_id": f"demo-snapshot-{idx:04d}",
                "tracks": {"total": count},
                "images": [{"url": base_url + cover_path, "width": 300, "height": 300}],
                "owner": dict(DEMO_USER),
            }
        )
    return {
        "auth_user": dict(DEMO_USER),
        "playlists": playlists,
        "playlist_tracks": tracks,
        "analysis_results": analysis,
        "static_files": static,
        "explorer": _make_explorer_data(rng, tracks),
    }
