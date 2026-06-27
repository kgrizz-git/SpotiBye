"""BackendMainScreen — MainScreen subclass that uses frontend-native components only."""

from __future__ import annotations

from typing import Any

from .main_screen import MainScreen
from ..ui.backend_playlist_card import BackendPlaylistCard
from ...shared.logging_config import logger


class BackendMainScreen(MainScreen):
    """MainScreen for backend mode.

    Overrides the three methods that instantiate PlaylistCard (a v2 widget with
    direct disk-cache and ReccoBeats dependencies) so that BackendPlaylistCard is
    used instead.  Also overrides update_status_with_cache_info to avoid the
    persistent_cache call that is meaningless in backend mode.
    """

    # ------------------------------------------------------------------
    # Widget factory
    # ------------------------------------------------------------------

    def _make_playlist_widget(self, playlist: dict[str, Any]) -> BackendPlaylistCard:
        return BackendPlaylistCard(playlist)

    # ------------------------------------------------------------------
    # display_playlists_with_cache — uses BackendPlaylistCard
    # ------------------------------------------------------------------

    def display_playlists_with_cache(self) -> None:
        try:
            scroll_y = getattr(self.playlist_layout.parent, "scroll_y", 1.0)

            self.status_label.text = (
                "Searching..." if self.search_query else "Loading..."
            )

            playlists_to_display = self._get_filtered_playlists()
            if self.current_sort_key != "default" or self.current_sort_reverse:
                playlists_to_display = self._sort_playlists(playlists_to_display)

            self.filtered_playlists = playlists_to_display
            self.playlist_layout.clear_widgets()
            self.playlist_widgets = []

            for playlist in playlists_to_display:
                try:
                    playlist_id = playlist.get("id", "")
                    widget = self._make_playlist_widget(playlist)
                    widget.checkbox.active = playlist_id in self.selected_playlist_ids
                    widget.checkbox.bind(
                        active=lambda _cb,
                        active,
                        pid=playlist_id: self._on_playlist_checkbox_changed(pid, active)
                    )
                    self.playlist_widgets.append(widget)
                except Exception as exc:
                    logger.warning("Error creating playlist widget: %s", exc)

            for widget in self.playlist_widgets:
                self.playlist_layout.add_widget(widget)

            if hasattr(self.playlist_layout.parent, "scroll_y"):
                self.playlist_layout.parent.scroll_y = scroll_y

            self.update_status_with_cache_info()
            self.update_selection_counter()

        except Exception as exc:
            logger.error("Error displaying playlists: %s", exc, exc_info=True)
            self.status_label.text = f"Error displaying playlists: {exc}"

    # ------------------------------------------------------------------
    # _perform_sort — uses BackendPlaylistCard
    # ------------------------------------------------------------------

    def _perform_sort(self) -> None:
        try:
            if not self.playlist_widgets:
                return

            for widget in self.playlist_widgets:
                playlist_id = widget.playlist_data.get("id", "")
                if not playlist_id:
                    continue
                if widget.checkbox.active:
                    self.selected_playlist_ids.add(playlist_id)
                else:
                    self.selected_playlist_ids.discard(playlist_id)

            scroll_y = getattr(self.playlist_layout.parent, "scroll_y", 1.0)
            self.playlist_layout.clear_widgets()
            self.playlist_widgets = []

            sorted_playlists = self._sort_playlists(self._get_filtered_playlists())

            for playlist in sorted_playlists:
                try:
                    playlist_id = playlist.get("id", "")
                    widget = self._make_playlist_widget(playlist)
                    widget.checkbox.active = playlist_id in self.selected_playlist_ids
                    widget.checkbox.bind(
                        active=lambda _cb,
                        active,
                        pid=playlist_id: self._on_playlist_checkbox_changed(pid, active)
                    )
                    self.playlist_widgets.append(widget)
                    self.playlist_layout.add_widget(widget)
                except Exception as exc:
                    logger.warning(
                        "Error creating playlist widget during sort: %s", exc
                    )

            if hasattr(self.playlist_layout.parent, "scroll_y"):
                self.playlist_layout.parent.scroll_y = scroll_y

            self.update_selection_counter()
            self.update_status_with_cache_info()

        except Exception as exc:
            logger.error("Error sorting playlists: %s", exc, exc_info=True)
            self.status_label.text = f"Error sorting playlists: {exc}"

    # ------------------------------------------------------------------
    # update_status_with_cache_info — no persistent_cache call
    # ------------------------------------------------------------------

    def update_status_with_cache_info(self) -> None:
        try:
            total = len(self.playlists)
            if self.search_query:
                shown = len(self.filtered_playlists)
                if shown == 0:
                    self.status_label.text = f'No matches for "{self.search_query}"'
                else:
                    self.status_label.text = f"Showing {shown} of {total}"
            else:
                self.status_label.text = f"Loaded {total} playlists"
        except Exception as exc:
            logger.warning("Error updating status: %s", exc)
            self.status_label.text = "Error updating status"
