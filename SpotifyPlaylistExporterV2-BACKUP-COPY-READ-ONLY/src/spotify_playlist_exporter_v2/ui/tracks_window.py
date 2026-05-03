"""TracksWindow popup implemented with KivyMD's data table."""

from __future__ import annotations

import threading
from typing import Optional

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivymd.uix.datatables import MDDataTable

from ..logging_config import logger
from ..auth.login_screen import create_spotify_client_with_refresh


class TracksWindow(Popup):
    """Window to display playlist tracks with detailed information."""

    def __init__(self, playlist_data, **kwargs):
        self.playlist_data = playlist_data
        self.tracks_popup = None
        self.column_data = [
            ("#", dp(10)),
            ("Title", dp(62)),
            ("Artist", dp(68)),
            ("Album", dp(76)),
            ("Duration", dp(45)),
        ]
        self.data_table: Optional[MDDataTable] = None

        content = self._create_tracks_content()

        super().__init__(
            title=f'Tracks: {playlist_data.get("name", "Unknown Playlist")}',
            title_size=dp(18),
            title_color=(1, 1, 1, 1),
            content=content,
            size_hint=(0.8, 0.85),
            background_color=(0.05, 0.05, 0.05, 0.95),
            auto_dismiss=True,
            overlay_color=(0, 0, 0, 0.3),
            **kwargs,
        )

        self.tracks_data = []
        self.loading = True
        self._tracks_loaded = False  # Flag to track if tracks are loaded

    def _create_tracks_content(self):
        main_layout = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))

        header_layout = self._create_header()
        main_layout.add_widget(header_layout)

        self.table_container = BoxLayout(orientation="vertical", size_hint=(1, 1))
        self.loading_label = Label(
            text="Loading tracks...",
            font_size=dp(16),
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None,
            height=dp(50),
        )
        self.table_container.add_widget(self.loading_label)
        main_layout.add_widget(self.table_container)

        close_button = Button(
            text="Close",
            size_hint_y=None,
            height=dp(45),
            font_size=dp(16),
            background_color=[0.3, 0.6, 0.9, 1],
        )
        close_button.bind(on_press=self.close_tracks_window)
        main_layout.add_widget(close_button)

        Clock.schedule_once(self.load_tracks, 0.1)

        return main_layout

    def _create_header(self):
        header_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(60), spacing=dp(5)
        )

        playlist_name = self.playlist_data.get("name", "Unknown Playlist")
        name_label = Label(
            text=playlist_name,
            font_size=dp(20),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(30),
            text_size=(None, None),
            halign="center",
        )
        header_layout.add_widget(name_label)

        track_count = self.playlist_data.get("tracks", {}).get("total", 0)
        owner = self.playlist_data.get("owner", {}).get("display_name", "Unknown")
        info_text = f"{track_count} tracks • by {owner}"

        info_label = Label(
            text=info_text,
            font_size=dp(14),
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(25),
        )
        header_layout.add_widget(info_label)

        return header_layout

    def load_tracks(self, dt):
        threading.Thread(target=self._load_tracks_worker, daemon=True).start()

    def _load_tracks_worker(self):
        try:
            app = App.get_running_app()
            if not app.token_info or not app.token_info.get("access_token"):
                Clock.schedule_once(
                    lambda dt: self._show_error("Authentication error"), 0
                )
                return

            sp = create_spotify_client_with_refresh(app.token_info)
            if not sp:
                Clock.schedule_once(
                    lambda dt: self._show_error("Authentication error"), 0
                )
                return
            playlist_id = self.playlist_data.get("id")

            if not playlist_id:
                Clock.schedule_once(
                    lambda dt: self._show_error("Invalid playlist ID"), 0
                )
                return

            tracks = []
            results = sp.playlist_tracks(playlist_id, limit=100)

            while results:
                for item in results["items"]:
                    try:
                        track = item.get("track")
                        if track and track.get("type") == "track":
                            artists = ", ".join(
                                [
                                    artist.get("name", "Unknown")
                                    for artist in track.get("artists", [])
                                ]
                            )

                            album_name = track.get("album", {}).get(
                                "name", "Unknown Album"
                            )
                            track_name = track.get("name", "Unknown Track")

                            duration_ms = track.get("duration_ms", 0)
                            duration_min = duration_ms // 60000
                            duration_sec = (duration_ms % 60000) // 1000
                            duration_str = f"{duration_min}:{duration_sec:02d}"

                            tracks.append(
                                {
                                    "title": track_name,
                                    "artist": artists,
                                    "album": album_name,
                                    "duration": duration_str,
                                    "explicit": track.get("explicit", False),
                                }
                            )
                    except Exception as exc:
                        logger.warning("Error processing track: %s", exc)
                        continue

                if results["next"]:
                    results = sp.next(results)
                else:
                    break

            self.tracks_data = tracks
            Clock.schedule_once(self._display_tracks, 0)

        except Exception as exc:
            logger.error("Error loading tracks: %s", exc)
            Clock.schedule_once(
                lambda dt: self._show_error(
                    f"Error loading tracks: {str(exc)[:50]}..."
                ),
                0,
            )

    def _display_tracks(self, dt=None):
        try:
            self.table_container.clear_widgets()

            if not self.tracks_data:
                no_tracks_label = Label(
                    text="No tracks found in this playlist",
                    font_size=dp(16),
                    color=(0.6, 0.6, 0.6, 1),
                    size_hint_y=None,
                    height=dp(50),
                )
                self.table_container.add_widget(no_tracks_label)
                return

            row_data = []
            for index, track in enumerate(self.tracks_data):
                explicit_badge = " 🔞" if track.get("explicit") else ""
                row_data.append(
                    (
                        str(index + 1),
                        f"{track['title']}{explicit_badge}",
                        track["artist"],
                        track["album"],
                        track["duration"],
                    )
                )

            self.data_table = MDDataTable(
                size_hint=(1, 1),
                column_data=self.column_data,
                row_data=row_data,
                use_pagination=False,
                check=False,
                elevation=1,
                rows_num=len(row_data) or 1,
            )

            self.table_container.add_widget(self.data_table)
        except Exception as exc:
            logger.error("Error displaying tracks: %s", exc)
            self._show_error(f"Error displaying tracks: {str(exc)[:50]}...")

    @mainthread
    def _show_error(self, message):
        """Display an error message in the scroll content."""
        self.table_container.clear_widgets()
        error_label = Label(
            text=f"Error: {message}",
            color=(1, 0.3, 0.3, 1),
            font_size=dp(14),
            halign="center",
            valign="middle",
            size_hint_y=None,
            height=dp(50),
        )
        self.table_container.add_widget(error_label)

    def close_tracks_window(self, instance):
        self.dismiss()


__all__ = ["TracksWindow"]
