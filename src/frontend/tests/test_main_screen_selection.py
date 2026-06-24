"""Unit tests for MainScreen SelectionManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.frontend.screens.main_screen_selection import SelectionManager


@pytest.fixture
def mock_screen():
    screen = MagicMock()
    screen.playlists = [{"id": "p1"}, {"id": "p2"}]
    screen.selection_label = MagicMock()
    screen.select_all_btn = MagicMock()
    return screen


@pytest.fixture
def manager(mock_screen):
    return SelectionManager(mock_screen)


def _make_widget(playlist_id: str, active: bool = False):
    widget = MagicMock()
    widget.checkbox.active = active
    widget.playlist_data = {"id": playlist_id}
    return widget


def test_toggle_select_all_selects_visible(mock_screen, manager):
    w1 = _make_widget("p1", active=False)
    w2 = _make_widget("p2", active=False)
    mock_screen.playlist_widgets = [w1, w2]

    manager.toggle_select_all(None)

    assert w1.checkbox.active is True
    assert w2.checkbox.active is True


def test_toggle_select_all_unselects_when_all_active(mock_screen, manager):
    w1 = _make_widget("p1", active=True)
    w2 = _make_widget("p2", active=True)
    mock_screen.playlist_widgets = [w1, w2]

    manager.toggle_select_all(None)

    assert w1.checkbox.active is False
    assert w2.checkbox.active is False


def test_checkbox_changed_mutates_live_set(manager):
    manager._on_playlist_checkbox_changed("p1", True)
    assert "p1" in manager.selected_playlist_ids

    manager._on_playlist_checkbox_changed("p1", False)
    assert "p1" not in manager.selected_playlist_ids


def test_update_selection_counter_updates_label(mock_screen, manager):
    manager.selected_playlist_ids.add("p1")
    manager.update_selection_counter()
    assert mock_screen.selection_label.text == "Selected: 1 of 2"


def test_deselect_all_clears_set_and_checkboxes(mock_screen, manager):
    w1 = _make_widget("p1", active=True)
    mock_screen.playlist_widgets = [w1]
    manager.selected_playlist_ids.update({"p1", "p2"})

    manager.deselect_all()

    assert manager.selected_playlist_ids == set()
    assert w1.checkbox.active is False
