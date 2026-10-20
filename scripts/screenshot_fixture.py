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

import io
import random
from datetime import datetime, timezone
from typing import Any

from PIL import Image, ImageDraw

DEMO_USER = {"id": "demo-user", "display_name": "demo-user"}

# (playlist name, description, track count, hue 0-360)
PLAYLISTS: list[tuple[str, str, int, int]] = [
    ("Late Night Drive", "Synthetic highways after midnight", 32, 250),
    ("Sunday Coffee", "Slow mornings and warm mugs", 24, 30),
    ("Rainy Window", "Grey skies, soft piano", 28, 205),
    ("Focus Hour", "Steady beats for deep work", 41, 160),
    ("Neon Gym", "High tempo, high energy", 36, 320),
    ("Campfire Stories", "Acoustic and unhurried", 19, 20),
    ("Golden Hour Walk", "Warm light, easy tempo", 27, 45),
    ("Road Trip Mix", "Windows down, volume up", 44, 190),
    ("Cozy Cabin", "Wool socks and fireplaces", 22, 10),
    ("Deep Space Study", "Ambient drift for long sessions", 38, 275),
    ("Weekend Cleanup", "Upbeat chores soundtrack", 30, 120),
    ("Moonlit Piano", "Quiet keys before sleep", 17, 230),
    ("Summer Block Party", "Sunny, loud, and danceable", 46, 55),
    ("Lo-Fi Library", "Dusty loops for reading", 35, 290),
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


def make_cover_png(hue: int, seed: int, size: int = 300) -> bytes:
    """Return a generated gradient PNG with a few soft shapes (no real art)."""
    rng = random.Random(seed)
    img = Image.new("RGB", (size, size))
    top = _hsv(hue, 0.55, 0.85)
    bottom = _hsv((hue + 40) % 360, 0.75, 0.35)
    px = img.load()
    assert px is not None
    for y in range(size):
        t = y / (size - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(size):
            px[x, y] = row
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(4):
        r = rng.randint(size // 10, size // 3)
        cx, cy = rng.randint(0, size), rng.randint(0, size)
        alpha = rng.randint(30, 80)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, alpha))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _hsv(h: int, s: float, v: float) -> tuple[int, int, int]:
    import colorsys

    r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def _make_tracks(rng: random.Random, pid: str, count: int) -> list[dict[str, Any]]:
    artists = [
        f"{rng.choice(_ARTIST_FIRST)} {rng.choice(_ARTIST_SECOND)}"
        for _ in range(max(4, count // 4))
    ]
    albums = [
        f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}"
        for _ in range(max(3, count // 5))
    ]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    while len(items) < count:
        title = f"{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}"
        if title in seen:
            continue
        seen.add(title)
        i = len(items)
        items.append(
            {
                "added_at": "2026-01-01T00:00:00Z",
                "track": {
                    "id": f"demo_trk_{pid[-2:]}{i:02d}",
                    "name": title,
                    "artists": [{"name": rng.choice(artists)}],
                    "album": {"name": rng.choice(albums)},
                    "duration_ms": rng.randint(150_000, 290_000),
                    "preview_url": None,
                    "track_number": i + 1,
                },
            }
        )
    return items


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

    key_pcts = {p: 0.0 for p in _PITCHES}
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
    rng = random.Random(20261019)
    now_iso = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    playlists: list[dict[str, Any]] = []
    tracks: dict[str, list[dict[str, Any]]] = {}
    analysis: dict[str, dict[str, Any]] = {}
    static: dict[str, tuple[str, bytes]] = {}
    for idx, (name, desc, count, hue) in enumerate(PLAYLISTS, start=1):
        pid = f"demo_playlist_{idx:02d}"
        cover_path = f"/covers/{pid}.png"
        static[cover_path] = ("image/png", make_cover_png(hue, seed=idx))
        tracks[pid] = _make_tracks(rng, pid, count)
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
    }
