from __future__ import annotations
from datetime import datetime
from src.frontend.screens.main_screen_filenames import (
    get_file_extension,
    selected_export_format,
    generate_default_filename,
    increment_filename_suffix,
    logged_in_as_text,
    normalize_display_username,
    sanitize_export_filename_component,
)


def test_get_file_extension():
    assert get_file_extension("xlsx") == ".xlsx"
    assert get_file_extension("XLSX") == ".xlsx"
    assert get_file_extension("csv") == ".csv"
    assert get_file_extension("json") == ".json"
    assert get_file_extension("unknown") == ".xlsx"


def test_selected_export_format():
    assert selected_export_format("XLSX") == "xlsx"
    assert selected_export_format(" csv ") == "csv"
    assert selected_export_format("JSON") == "json"
    assert selected_export_format("") == "xlsx"
    assert selected_export_format(None) == "xlsx"


def test_logged_in_as_text_never_shows_literal_none():
    assert logged_in_as_text("Ada") == "Logged in as: Ada"
    assert logged_in_as_text(None) == "Logged in as: Unknown User"
    assert logged_in_as_text("None") == "Logged in as: Unknown User"
    assert normalize_display_username(None, fallback="user") == "user"


def test_generate_default_filename():
    now = datetime(2026, 6, 16, 9, 30, 0)
    # Expected format: Spotify_Playlists_{user}_{YYYY-MM-DD_HH-MM-SSAM/PM}.xlsx
    expected = "Spotify_Playlists_Ada_2026-06-16_09-30-00AM.csv"
    assert generate_default_filename("Ada", "csv", now=now) == expected

    # Test fallback username
    assert "Spotify_Playlists_user_" in generate_default_filename(None, "xlsx", now=now)
    assert "Spotify_Playlists_user_" in generate_default_filename(
        "None", "xlsx", now=now
    )


def test_increment_filename_suffix():
    # Test .xlsx (existing behavior)
    assert increment_filename_suffix("file.xlsx") == "file_2.xlsx"
    assert increment_filename_suffix("file_2.xlsx") == "file_3.xlsx"
    assert increment_filename_suffix("file_3.xlsx") == "file_4.xlsx"
    assert increment_filename_suffix("file_4.xlsx") == "file_5.xlsx"
    assert increment_filename_suffix("file_5.xlsx") == "file_5.xlsx"

    # Test .csv (bug fix: extension agnostic)
    assert increment_filename_suffix("data.csv") == "data_2.csv"
    assert increment_filename_suffix("data_2.csv") == "data_3.csv"

    # Test .json
    assert increment_filename_suffix("export.json") == "export_2.json"

    # FE-HIGH-2: digit-ending basenames must not be silently corrupted
    # (`song_14.xlsx` previously became `song_1_5.xlsx`).
    assert increment_filename_suffix("song_14.xlsx") == "song_14_2.xlsx"
    assert increment_filename_suffix("song_35.xlsx") == "song_35_2.xlsx"
    assert (
        increment_filename_suffix("My_Playlist_2026.xlsx") == "My_Playlist_2026_2.xlsx"
    )
    # After appending _2, a subsequent call increments _2 -> _3.
    assert increment_filename_suffix("song_14_2.xlsx") == "song_14_3.xlsx"


def test_sanitize_export_filename_component():
    assert sanitize_export_filename_component("My Playlist/Name") == "My Playlist_Name"
    assert sanitize_export_filename_component("Invalid:*?<>|") == "Invalid_"
    assert sanitize_export_filename_component("") == "playlist"
    assert sanitize_export_filename_component(None) == "playlist"
    # Test length limit
    long_name = "a" * 100
    assert len(sanitize_export_filename_component(long_name)) == 80
