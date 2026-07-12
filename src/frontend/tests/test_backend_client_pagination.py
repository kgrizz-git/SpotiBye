"""Tests for BackendClient playlist track pagination and force_refresh."""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

from src.frontend.services.backend_client import BackendClient


def _track(track_id: str) -> Dict[str, Any]:
    return {"track": {"id": track_id, "name": track_id}}


class TestPlaylistTracksPagination:
    def _client(self) -> BackendClient:
        return BackendClient("http://localhost:8787")

    def test_paginates_until_raw_count_less_than_limit(self) -> None:
        pages: List[tuple[List[Dict[str, Any]], int, int]] = [
            ([_track("a"), _track("b")], 50, 75),
            ([_track("c")], 25, 75),
        ]

        def fake_page(
            playlist_id: str,
            *,
            limit: int = 50,
            offset: int = 0,
            force_refresh: bool = False,
        ) -> tuple[List[Dict[str, Any]], int, int]:
            assert playlist_id == "playlist-1"
            index = 0 if offset == 0 else 1
            return pages[index]

        with patch.object(BackendClient, "get_playlist_tracks_page", side_effect=fake_page):
            items = self._client().get_playlist_tracks("playlist-1")

        assert len(items) == 3
        assert [item["track"]["id"] for item in items] == ["a", "b", "c"]

    def test_force_refresh_passed_to_details_and_items(self) -> None:
        client = self._client()
        with patch.object(
            BackendClient, "_make_request", return_value={"items": [], "rawCount": 0, "total": 0}
        ) as mock_request:
            client.get_playlist_tracks("playlist-1", force_refresh=True)
            client.get_playlist_details("playlist-1", force_refresh=True)

        assert mock_request.call_count == 2
        tracks_call = mock_request.call_args_list[0]
        details_call = mock_request.call_args_list[1]
        assert tracks_call.kwargs["params"]["force_refresh"] == "true"
        assert details_call.kwargs["params"]["force_refresh"] == "true"
