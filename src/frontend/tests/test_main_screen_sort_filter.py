from __future__ import annotations
import pytest
from src.frontend.screens.main_screen_sort_filter import (
    filter_playlists,
    sort_playlists,
)


@pytest.fixture
def playlists():
    return [
        {
            "id": "1",
            "name": "Rock Classics",
            "owner": {"display_name": "Alice"},
            "tracks": {"total": 50},
        },
        {
            "id": "2",
            "name": "Jazz Night",
            "owner": {"display_name": "Bob"},
            "tracks": {"total": 20},
        },
        {
            "id": "3",
            "name": "Classical Focus",
            "owner": {"display_name": "Alice"},
            "tracks": {"total": 100},
        },
    ]


def test_filter_playlists_by_name(playlists):
    result = filter_playlists(playlists, "rock")
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_filter_playlists_by_owner(playlists):
    result = filter_playlists(playlists, "Alice")
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[1]["id"] == "3"


def test_filter_playlists_and_logic(playlists):
    result = filter_playlists(playlists, "Alice Classical")
    assert len(result) == 1
    assert result[0]["id"] == "3"


def test_filter_playlists_no_query(playlists):
    result = filter_playlists(playlists, "")
    assert len(result) == 3


def test_sort_playlists_by_name(playlists):
    # Ascending
    result = sort_playlists(playlists, "name", False)
    assert result[0]["name"] == "Classical Focus"
    assert result[1]["name"] == "Jazz Night"
    assert result[2]["name"] == "Rock Classics"

    # Descending
    result = sort_playlists(playlists, "name", True)
    assert result[0]["name"] == "Rock Classics"


def test_sort_playlists_by_tracks(playlists):
    result = sort_playlists(playlists, "tracks", False)
    assert result[0]["tracks"]["total"] == 20
    assert result[1]["tracks"]["total"] == 50
    assert result[2]["tracks"]["total"] == 100


def test_sort_playlists_by_owner(playlists):
    result = sort_playlists(playlists, "owner", False)
    # Alice, Alice, Bob
    assert result[0]["owner"]["display_name"] == "Alice"
    assert result[1]["owner"]["display_name"] == "Alice"
    assert result[2]["owner"]["display_name"] == "Bob"


def test_sort_playlists_default(playlists):
    result = sort_playlists(playlists, "default", False)
    assert result == playlists
