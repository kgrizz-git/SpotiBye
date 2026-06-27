"""Playlist selection state and UI helpers for MainScreen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Set

from ...shared.logging_config import logger

if TYPE_CHECKING:
    from .main_screen import MainScreen


class SelectionManager:
    """Tracks selected playlist IDs and updates selection-related widgets."""

    def __init__(self, screen: "MainScreen") -> None:
        self.screen = screen
        self.selected_playlist_ids: Set[str] = set()

    def toggle_select_all(self, _instance) -> None:
        """Toggle selection for currently visible (filtered) playlists only."""
        playlist_widgets = getattr(self.screen, "playlist_widgets", None)
        if not playlist_widgets:
            return

        all_selected = all(w.checkbox.active for w in playlist_widgets)
        for widget in playlist_widgets:
            widget.checkbox.active = not all_selected

        self.update_selection_counter()

    def update_selection_counter(self) -> None:
        """Update the selection counter label."""
        try:
            selected = len(self.selected_playlist_ids)
            total = len(self.screen.playlists)
            self.screen.selection_label.text = f"Selected: {selected} of {total}"
            self._update_select_all_button_label()
        except Exception as exc:
            logger.warning("Error updating selection counter: %s", exc)

    def _update_select_all_button_label(self) -> None:
        """Update visible-toggle button text based on currently filtered cards."""
        select_all_btn = getattr(self.screen, "select_all_btn", None)
        if select_all_btn is None:
            return

        playlist_widgets = getattr(self.screen, "playlist_widgets", [])
        visible_cards = len(playlist_widgets)
        if visible_cards == 0:
            select_all_btn.text = "Select Visible"
            return

        visible_selected = sum(1 for w in playlist_widgets if w.checkbox.active)
        if visible_selected == visible_cards:
            select_all_btn.text = "Unselect Visible"
        else:
            select_all_btn.text = "Select Visible"

    def _on_playlist_checkbox_changed(self, playlist_id: str, is_active: bool) -> None:
        """Keep playlist selection persistent even when filtering hides cards."""
        if not playlist_id:
            return
        if is_active:
            self.selected_playlist_ids.add(playlist_id)
        else:
            self.selected_playlist_ids.discard(playlist_id)
        self.update_selection_counter()

    def deselect_all(self, *_args) -> None:
        """Clear all selections and uncheck visible playlist checkboxes."""
        self.selected_playlist_ids.clear()
        for widget in getattr(self.screen, "playlist_widgets", []):
            widget.checkbox.active = False
        self.update_selection_counter()
