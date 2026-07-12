"""Tests for playlist composition fingerprint helpers."""

from __future__ import annotations

from typing import Any

from src.frontend.services.playlist_composition import (
    build_composition_fingerprint,
    build_tracks_cache_metadata,
    compute_track_id_hash,
    fingerprints_match,
    unique_track_ids_from_items,
)


def _item(track_id: str) -> dict[str, Any]:
    return {"track": {"id": track_id, "name": track_id}}


class TestPlaylistComposition:
    def test_unique_track_ids_deduplicates(self) -> None:
        items = [_item("a"), _item("a"), _item("b")]
        assert unique_track_ids_from_items(items) == ["a", "b"]

    def test_track_id_hash_is_order_independent(self) -> None:
        assert compute_track_id_hash(["b", "a"]) == compute_track_id_hash(["a", "b"])

    def test_fingerprints_match_on_snapshot_id(self) -> None:
        cached = {"snapshot_id": "snap-1", "track_id_hash": "hash-1"}
        assert fingerprints_match(cached, snapshot_id="snap-1", track_id_hash="other")

    def test_fingerprints_match_on_track_hash_when_no_snapshot(self) -> None:
        cached = {"track_id_hash": "abc"}
        assert fingerprints_match(cached, snapshot_id=None, track_id_hash="abc")

    def test_build_tracks_cache_metadata_counts_unique_ids(self) -> None:
        metadata = build_tracks_cache_metadata(
            [_item("a"), _item("a"), _item("b")],
            snapshot_id="snap-2",
        )
        assert metadata["unique_track_count"] == 2
        assert metadata["snapshot_id"] == "snap-2"
        assert build_composition_fingerprint(
            snapshot_id=metadata["snapshot_id"],
            track_id_hash=metadata["track_id_hash"],
        ).startswith("snap:snap-2|")
