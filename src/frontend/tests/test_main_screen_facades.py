"""Unit tests for MainScreen facade properties and delegation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.frontend.screens.main_screen import MainScreen
from src.frontend.screens.main_screen_search_sort_ui import SearchSortUIHandler


@pytest.fixture
def screen():
    with (
        patch(
            "src.frontend.screens.main_screen.Screen.__init__",
            lambda self, **kwargs: None,
        ),
        patch.object(MainScreen, "build_ui"),
    ):
        return MainScreen()


def test_selected_playlist_ids_is_live_set_reference(screen):
    assert (
        screen.selected_playlist_ids is screen.selection_manager.selected_playlist_ids
    )
    screen.selected_playlist_ids.add("playlist-x")
    assert "playlist-x" in screen.selection_manager.selected_playlist_ids


def test_search_query_property_round_trip(screen):
    screen.search_query = "jazz"
    assert screen.search_sort.search_query == "jazz"
    assert screen.search_query == "jazz"


def test_filtered_playlists_property_round_trip(screen):
    playlists = [{"id": "p1"}]
    screen.filtered_playlists = playlists
    assert screen.search_sort.filtered_playlists == playlists
    assert screen.filtered_playlists == playlists


def test_sort_key_properties_round_trip(screen):
    screen.current_sort_key = "name"
    screen.current_sort_reverse = True
    assert screen.search_sort.current_sort_key == "name"
    assert screen.search_sort.current_sort_reverse is True


def test_schedule_sort_refresh_delegates_to_handler(screen):
    with patch.object(screen.search_sort, "schedule_sort_refresh") as mock_refresh:
        screen.schedule_sort_refresh()
        mock_refresh.assert_called_once()


def test_perform_sort_terminus_via_handler():
    mock_screen = MagicMock()
    handler = SearchSortUIHandler(mock_screen)

    with patch(
        "src.frontend.screens.main_screen_search_sort_ui.Clock.schedule_once",
    ) as schedule:
        schedule.return_value = MagicMock()
        handler.schedule_sort_refresh()
        callback = schedule.call_args[0][0]
        callback(0)

    mock_screen._perform_sort.assert_called_once()
