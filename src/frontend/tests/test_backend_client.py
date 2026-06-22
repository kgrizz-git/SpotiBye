"""Tests for BackendClient.get_playlist_tracks response shape handling (FE-HIGH-1)."""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from src.frontend.services.backend_client import BackendClient


def _track(track_id: str) -> Dict[str, Any]:
    return {"id": track_id, "name": f"Track {track_id}", "uri": f"spotify:track:{track_id}"}


class TestGetPlaylistTracksResponseShape:
    """The method must tolerate the three legitimate `_make_request` return
    shapes and degrade gracefully on anything else."""

    def _client(self) -> BackendClient:
        return BackendClient("http://localhost:8787")

    def test_returns_bare_list_unchanged(self) -> None:
        items = [_track("a"), _track("b")]
        with patch.object(BackendClient, "_make_request", return_value=items):
            assert self._client().get_playlist_tracks("playlist-1") == items

    def test_returns_items_from_dict(self) -> None:
        items = [_track("a"), _track("b")]
        with patch.object(
            BackendClient,
            "_make_request",
            return_value={"items": items, "total": 2, "rawCount": 2, "href": "x"},
        ):
            assert self._client().get_playlist_tracks("playlist-1") == items

    def test_falls_back_to_tracks_key(self) -> None:
        items = [_track("a"), _track("b")]
        with patch.object(
            BackendClient, "_make_request", return_value={"tracks": items}
        ):
            assert self._client().get_playlist_tracks("playlist-1") == items

    def test_returns_empty_list_for_dict_without_items_or_tracks(self) -> None:
        with patch.object(
            BackendClient, "_make_request", return_value={"unexpected": "shape"}
        ):
            assert self._client().get_playlist_tracks("playlist-1") == []

    def test_returns_empty_list_for_none_response(self) -> None:
        with patch.object(BackendClient, "_make_request", return_value=None):
            assert self._client().get_playlist_tracks("playlist-1") == []

    def test_returns_empty_list_for_unexpected_type(self) -> None:
        with patch.object(BackendClient, "_make_request", return_value=42):
            assert self._client().get_playlist_tracks("playlist-1") == []
