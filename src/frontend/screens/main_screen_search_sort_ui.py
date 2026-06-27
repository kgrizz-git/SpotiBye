"""Debounced search and sort UI logic for MainScreen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from kivy.clock import Clock
from kivy.metrics import dp

from ...shared.logging_config import logger

if TYPE_CHECKING:
    from .main_screen import MainScreen


class SearchSortUIHandler:
    """Handles search/sort widget state, debouncing, and filter bookkeeping."""

    def __init__(self, screen: "MainScreen") -> None:
        self.screen = screen
        self.search_query = ""
        self.current_sort_key = "default"
        self.current_sort_reverse = False
        self.filtered_playlists: List[Dict[str, Any]] = []
        self._search_trigger: Optional[object] = None
        self._sort_trigger: Optional[object] = None
        self._search_debounce_seconds = 0.3
        self._sort_debounce_seconds = 0.5

    def configure_dropdown(self, spinner) -> None:
        try:
            dropdown = getattr(spinner, "_dropdown", None)
            if dropdown and dropdown.children:
                for option in dropdown.children[0].children:
                    if hasattr(option, "height"):
                        option.height = dp(30)
                        option.size_hint_y = None
                    if hasattr(option, "font_size"):
                        option.font_size = dp(12)
        except Exception as exc:
            logger.warning("Error configuring dropdown: %s", exc)

    def on_sort_change(self, spinner, text) -> None:
        try:
            sort_map = {
                "Default": "default",
                "Playlist Title": "name",
                "# of Tracks": "tracks",
                "Owner": "owner",
            }
            self.current_sort_key = sort_map.get(text, "default")
            Clock.schedule_once(lambda _: self.update_sort_controls_visibility(), 0.1)
            self.update_sort_direction_button()
            self.schedule_sort_refresh()
        except Exception as exc:
            logger.warning("Error changing sort: %s", exc)

    def update_sort_controls_visibility(self) -> None:
        try:
            by_label = getattr(self.screen, "by_label", None)
            sort_direction_btn = getattr(self.screen, "sort_direction_btn", None)
            if by_label is None or sort_direction_btn is None:
                return

            is_default = self.current_sort_key == "default"
            if is_default:
                by_label.opacity = 0
                by_label.width = 0
                sort_direction_btn.opacity = 0
                sort_direction_btn.width = 0
                sort_direction_btn.disabled = True
            else:
                by_label.opacity = 1
                by_label.width = dp(25)
                sort_direction_btn.opacity = 1
                sort_direction_btn.width = dp(67)
                sort_direction_btn.disabled = False
        except Exception as exc:
            logger.error("Error updating sort controls visibility: %s", exc)

    def update_sort_direction_button(self) -> None:
        try:
            btn = self.screen.sort_direction_btn
            if self.current_sort_key in ["default", "name", "owner"]:
                if self.current_sort_reverse:
                    btn.text = "Z-A"
                    btn.background_color = [0.7, 0.4, 0.4, 1]
                else:
                    btn.text = "A-Z"
                    btn.background_color = [0.55, 0.55, 0.55, 1]
            else:
                if self.current_sort_reverse:
                    btn.text = "+ -"
                    btn.background_color = [0.7, 0.4, 0.4, 1]
                else:
                    btn.text = "- +"
                    btn.background_color = [0.55, 0.55, 0.55, 1]
        except Exception as exc:
            logger.warning("Error updating sort direction button: %s", exc)

    def toggle_sort_direction(self, *_args) -> None:
        if self.screen.sort_direction_btn.disabled:
            return
        self.current_sort_reverse = not self.current_sort_reverse
        self.update_sort_direction_button()
        self.schedule_sort_refresh()

    def schedule_sort_refresh(self) -> None:
        """Schedule a debounced sort refresh via the screen's _perform_sort hook."""
        try:
            if self._sort_trigger:
                self._sort_trigger.cancel()

            self._sort_trigger = Clock.schedule_once(
                lambda _dt: self.screen._perform_sort(),
                self._sort_debounce_seconds,
            )
        except Exception as exc:
            logger.warning("Error scheduling sort: %s", exc)

    def reset_sort_ui(self) -> None:
        """Reset sort controls to default (e.g. after playlist reload)."""
        self.current_sort_key = "default"
        self.current_sort_reverse = False
        self.screen.sort_spinner.text = "Default"
        self.update_sort_direction_button()

    def on_search_text(self, _instance, value) -> None:
        if self._search_trigger:
            self._search_trigger.cancel()

        self._search_trigger = Clock.schedule_once(
            lambda _dt: self._perform_search(value),
            self._search_debounce_seconds,
        )

    def _perform_search(self, search_text: str) -> None:
        try:
            self.search_query = search_text.strip().lower()
            self.screen.display_playlists_with_cache()
        except Exception as exc:
            logger.error("Error performing search: %s", exc)
            self.screen.status_label.text = f"Search error: {str(exc)}"

    def clear_search(self, _instance) -> None:
        if self._search_trigger:
            self._search_trigger.cancel()
            self._search_trigger = None

        self.screen.search_input.text = ""
        self.search_query = ""

        playlist_parent = getattr(self.screen.playlist_layout, "parent", None)
        if playlist_parent is not None and hasattr(playlist_parent, "scroll_y"):
            playlist_parent.scroll_y = 1.0

        self.screen.display_playlists_with_cache()

    def get_filtered_playlists(self) -> List[Dict[str, Any]]:
        """Return playlists filtered by the current search query."""
        from .main_screen_sort_filter import filter_playlists

        try:
            return filter_playlists(self.screen.playlists, self.search_query)
        except Exception as exc:
            logger.warning("Error filtering playlists: %s", exc)
            return self.screen.playlists.copy()

    def sort_playlist_list(
        self, playlists: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort playlists using current sort key and direction."""
        from .main_screen_sort_filter import sort_playlists

        return sort_playlists(
            playlists, self.current_sort_key, self.current_sort_reverse
        )
