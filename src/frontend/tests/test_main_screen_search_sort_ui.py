"""Unit tests for MainScreen SearchSortUIHandler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.frontend.screens.main_screen_search_sort_ui import SearchSortUIHandler


class FakeTrigger:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def mock_screen():
    screen = MagicMock()
    screen.playlists = [{"id": "p1", "name": "Alpha"}]
    screen.search_input = MagicMock()
    screen.status_label = MagicMock()
    screen.sort_spinner = MagicMock()
    screen.sort_direction_btn = MagicMock()
    screen.sort_direction_btn.disabled = False
    screen.by_label = MagicMock()
    screen.playlist_layout = MagicMock()
    screen.playlist_layout.parent = MagicMock()
    screen.playlist_layout.parent.scroll_y = 0.5
    return screen


@pytest.fixture
def handler(mock_screen):
    return SearchSortUIHandler(mock_screen)


def test_on_search_text_debounces_and_cancels_prior(handler):
    first_trigger = FakeTrigger()
    second_trigger = FakeTrigger()

    with patch(
        "src.frontend.screens.main_screen_search_sort_ui.Clock.schedule_once",
        side_effect=[first_trigger, second_trigger],
    ) as schedule:
        handler.on_search_text(None, "a")
        handler.on_search_text(None, "ab")

    assert first_trigger.cancelled is True
    assert schedule.call_count == 2
    assert handler._search_trigger is second_trigger


def test_perform_search_updates_query_and_displays(handler, mock_screen):
    handler._perform_search("  Rock  ")
    assert handler.search_query == "rock"
    mock_screen.display_playlists_with_cache.assert_called_once()


def test_clear_search_resets_input_query_and_scroll(handler, mock_screen):
    handler._search_trigger = FakeTrigger()
    handler.search_query = "rock"

    handler.clear_search(None)

    assert handler._search_trigger is None
    mock_screen.search_input.text = ""
    assert handler.search_query == ""
    assert mock_screen.playlist_layout.parent.scroll_y == 1.0
    mock_screen.display_playlists_with_cache.assert_called_once()


def test_schedule_sort_refresh_calls_perform_sort_after_debounce(handler, mock_screen):
    trigger = FakeTrigger()

    with patch(
        "src.frontend.screens.main_screen_search_sort_ui.Clock.schedule_once",
        return_value=trigger,
    ) as schedule:
        handler.schedule_sort_refresh()

    assert schedule.call_count == 1
    callback = schedule.call_args[0][0]
    callback(0)
    mock_screen._perform_sort.assert_called_once()


def test_schedule_sort_refresh_cancels_existing_trigger(handler):
    old_trigger = FakeTrigger()
    handler._sort_trigger = old_trigger
    new_trigger = FakeTrigger()

    with patch(
        "src.frontend.screens.main_screen_search_sort_ui.Clock.schedule_once",
        return_value=new_trigger,
    ):
        handler.schedule_sort_refresh()

    assert old_trigger.cancelled is True
    assert handler._sort_trigger is new_trigger
