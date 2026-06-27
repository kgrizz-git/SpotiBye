"""Cache Explorer popup — backend-path version with no disk-cache dependencies.

Data is always supplied externally via the ``cache_data`` attribute and
``populate_playlists_column()`` / ``_on_cache_data_loaded()`` calls made by
``BackendCacheExplorerPopup``.  The internal background worker returns an empty
structure so it never blocks on filesystem access.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from ...shared.logging_config import logger


class CacheExplorerPopup(Popup):
    """Column-based cache explorer whose data is injected by the caller."""

    def __init__(self, **kwargs):
        self.close_handler = kwargs.pop("close_handler", None)
        super().__init__(**kwargs)
        self.title = "Cache Explorer"
        self.size_hint = (0.9, 0.9)
        self.auto_dismiss = False

        self.cache_data: Dict[str, Any] = {}
        self.filter_text = ""

        self.selected_playlist = None
        self.selected_track = None

        self.playlists_column = None
        self.tracks_column = None
        self.details_column = None
        self.features_column = None

        self.search_input: Any = None
        self.breadcrumb_label: Any = None
        self.playlists_content: Any = None
        self.tracks_content: Any = None
        self.details_content: Any = None
        self.features_content: Any = None

        self.build_ui()
        self.load_cache_data()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def build_ui(self) -> None:
        main_layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

        header = self._create_header()
        main_layout.add_widget(header)

        self.columns_container = GridLayout(cols=4, spacing=dp(5), size_hint_y=1)

        self.playlists_column = self._create_playlists_column()
        self.tracks_column = self._create_tracks_column()
        self.details_column = self._create_details_column()
        self.features_column = self._create_features_column()

        self.tracks_column.opacity = 0
        self.details_column.opacity = 0
        self.features_column.opacity = 0

        self.columns_container.add_widget(self.playlists_column)
        self.columns_container.add_widget(self.tracks_column)
        self.columns_container.add_widget(self.details_column)
        self.columns_container.add_widget(self.features_column)

        main_layout.add_widget(self.columns_container)
        main_layout.add_widget(self._create_footer())

        self.content = main_layout

    def _create_header(self) -> BoxLayout:
        header = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
        )

        header.add_widget(
            Label(text="Search:", size_hint_x=None, width=dp(60), font_size=dp(14))
        )

        self.search_input = TextInput(
            multiline=False,
            size_hint_x=0.3,
            font_size=dp(14),
            hint_text="Filter cached playlists...",
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
        )
        self.search_input.bind(text=self.on_search_text)
        header.add_widget(self.search_input)

        refresh_btn = Button(
            text="Refresh",
            size_hint_x=None,
            width=dp(80),
            background_color=[0.3, 0.6, 0.3, 1],
            font_size=dp(14),
        )
        refresh_btn.bind(on_press=self.refresh_data)
        header.add_widget(refresh_btn)

        self.breadcrumb_label = Label(
            text="Playlists",
            font_size=dp(14),
            color=(0.7, 0.7, 0.7, 1),
            size_hint_x=0.4,
            halign="left",
        )
        header.add_widget(self.breadcrumb_label)

        return header

    def _create_footer(self) -> BoxLayout:
        footer = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40), padding=dp(5)
        )
        footer.add_widget(BoxLayout(size_hint_x=0.8))

        close_btn = Button(
            text="Close",
            size_hint_x=None,
            width=dp(80),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(14),
        )
        close_btn.bind(on_press=self._handle_close)
        footer.add_widget(close_btn)

        return footer

    def _handle_close(self, *_args) -> None:
        if self.close_handler is not None:
            self.close_handler()
            return
        self.dismiss()

    def _create_playlists_column(self) -> BoxLayout:
        column = BoxLayout(orientation="vertical", size_hint_x=0.22, spacing=dp(2))

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        header.add_widget(
            Label(
                text="Playlists", font_size=dp(16), bold=True, color=(0.3, 0.8, 0.3, 1)
            )
        )
        column.add_widget(header)

        scroll = ScrollView()
        self.playlists_content = GridLayout(
            cols=1, spacing=dp(2), size_hint_y=None, padding=dp(5)
        )
        self.playlists_content.bind(
            minimum_height=self.playlists_content.setter("height")
        )
        scroll.add_widget(self.playlists_content)
        column.add_widget(scroll)

        return column

    def _create_tracks_column(self) -> BoxLayout:
        column = BoxLayout(orientation="vertical", size_hint_x=0.22, spacing=dp(2))

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        header.add_widget(
            Label(text="Tracks", font_size=dp(16), bold=True, color=(0.3, 0.6, 0.8, 1))
        )

        close_btn = Button(
            text="X",
            size_hint_x=None,
            width=dp(30),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12),
        )
        close_btn.bind(on_press=lambda _: self.close_tracks_column())
        header.add_widget(close_btn)
        column.add_widget(header)

        scroll = ScrollView()
        self.tracks_content = GridLayout(
            cols=1, spacing=dp(2), size_hint_y=None, padding=dp(5)
        )
        self.tracks_content.bind(minimum_height=self.tracks_content.setter("height"))
        scroll.add_widget(self.tracks_content)
        column.add_widget(scroll)

        return column

    def _create_details_column(self) -> BoxLayout:
        column = BoxLayout(orientation="vertical", size_hint_x=0.22, spacing=dp(2))

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        header.add_widget(
            Label(
                text="Track Details",
                font_size=dp(16),
                bold=True,
                color=(0.8, 0.6, 0.3, 1),
            )
        )

        close_btn = Button(
            text="X",
            size_hint_x=None,
            width=dp(30),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12),
        )
        close_btn.bind(on_press=lambda _: self.close_details_column())
        header.add_widget(close_btn)
        column.add_widget(header)

        scroll = ScrollView()
        self.details_content = GridLayout(
            cols=1, spacing=dp(2), size_hint_y=None, padding=dp(5)
        )
        self.details_content.bind(minimum_height=self.details_content.setter("height"))
        scroll.add_widget(self.details_content)
        column.add_widget(scroll)

        return column

    def _create_features_column(self) -> BoxLayout:
        column = BoxLayout(orientation="vertical", size_hint_x=0.22, spacing=dp(2))

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        header.add_widget(
            Label(
                text="Reccobeats Analysis",
                font_size=dp(16),
                bold=True,
                color=(0.8, 0.3, 0.8, 1),
            )
        )

        close_btn = Button(
            text="X",
            size_hint_x=None,
            width=dp(30),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12),
        )
        close_btn.bind(on_press=lambda _: self.close_features_column())
        header.add_widget(close_btn)
        column.add_widget(header)

        scroll = ScrollView()
        self.features_content = GridLayout(
            cols=1, spacing=dp(2), size_hint_y=None, padding=dp(5)
        )
        self.features_content.bind(
            minimum_height=self.features_content.setter("height")
        )
        scroll.add_widget(self.features_content)
        column.add_widget(scroll)

        return column

    # ------------------------------------------------------------------
    # Data loading — no disk access; callers set cache_data directly
    # ------------------------------------------------------------------

    def load_cache_data(self) -> None:
        """Kick off background load; returns empty structure immediately."""
        try:
            self.playlists_content.clear_widgets()
            self.playlists_content.add_widget(
                Label(
                    text="Loading cache data...",
                    font_size=dp(16),
                    size_hint_y=None,
                    height=dp(30),
                )
            )
            threading.Thread(target=self._load_cache_data_worker, daemon=True).start()
        except Exception as exc:
            logger.error("Error starting cache data load: %s", exc)
            self.show_error(f"Error loading cache data: {exc}")

    def _load_cache_data_worker(self) -> None:
        """Return an empty structure — callers inject real data via cache_data."""
        empty: Dict[str, Any] = {
            "summary": {},
            "playlists": [],
            "tracks": [],
            "images": [],
            "analysis": [],
        }
        Clock.schedule_once(lambda _: self._on_cache_data_loaded(empty))

    def _on_cache_data_loaded(self, cache_data: Dict[str, Any]) -> None:
        try:
            self.cache_data = cache_data
            self.populate_playlists_column()
        except Exception as exc:
            logger.error("Error handling cache data loaded: %s", exc)
            self.show_error(f"Error displaying cache data: {exc}")

    # ------------------------------------------------------------------
    # Column population
    # ------------------------------------------------------------------

    def populate_playlists_column(self) -> None:
        self.playlists_content.clear_widgets()

        playlists = self.cache_data.get("playlists", [])
        if not playlists:
            self.playlists_content.add_widget(
                Label(text="No cached playlists found", font_size=dp(14))
            )
            return

        if self.filter_text:
            playlists = [
                p
                for p in playlists
                if self.filter_text.lower() in p.get("name", "").lower()
            ]

        for playlist in playlists[:50]:
            self.playlists_content.add_widget(self._create_playlist_widget(playlist))

    def _create_playlist_widget(self, playlist: Dict[str, Any]) -> Button:
        playlist_name = playlist.get("name", "Unknown Playlist")
        tracks_count = playlist.get("tracks_count", 0)
        cached_time = datetime.fromtimestamp(playlist.get("cached_at", 0)).strftime(
            "%Y-%m-%d %H:%M"
        )
        size_mb = playlist.get("size_mb", 0)

        char_width = dp(7)
        max_chars = int(dp(280) / char_width)
        if len(playlist_name) > max_chars:
            playlist_name = playlist_name[: max_chars - 3] + "..."

        text = (
            f"{playlist_name}\n({tracks_count} tracks)\n{size_mb:.1f}MB • {cached_time}"
        )

        btn = Button(
            text=text,
            size_hint_y=None,
            height=dp(60),
            background_color=[0.2, 0.4, 0.2, 1]
            if playlist == self.selected_playlist
            else [0.3, 0.3, 0.3, 1],
            font_size=dp(11),
            halign="left",
            padding=(dp(15), dp(5)),
            text_size=(dp(270), None),
        )
        btn.bind(on_press=lambda _: self.select_playlist(playlist))
        return btn

    def select_playlist(self, playlist: Dict[str, Any]) -> None:
        self.selected_playlist = playlist
        self.selected_track = None

        playlist_name = playlist.get("name", "Unknown Playlist")
        self.breadcrumb_label.text = f"Playlists > {playlist_name}"

        self.tracks_column.opacity = 1
        self.details_column.opacity = 0
        self.features_column.opacity = 0
        self.details_content.clear_widgets()
        self.features_content.clear_widgets()

        self.populate_tracks_column(playlist)
        self.populate_playlists_column()

    def populate_tracks_column(self, playlist: Dict[str, Any]) -> None:
        """Show tracks for the selected playlist from injected cache_data."""
        self.tracks_content.clear_widgets()

        playlist_id = playlist.get("playlist_id", "")
        tracks_by_playlist: Dict[str, Any] = self.cache_data.get(
            "tracks_by_playlist", {}
        )
        tracks = tracks_by_playlist.get(playlist_id, [])

        if not tracks:
            self.tracks_content.add_widget(
                Label(
                    text="No track data available\n(open in app to cache tracks)",
                    font_size=dp(14),
                )
            )
            return

        if self.filter_text:
            tracks = [
                t
                for t in tracks
                if self.filter_text.lower() in t.get("name", "").lower()
                or self.filter_text.lower() in t.get("id", "").lower()
            ]

        for track in tracks[:100]:
            self.tracks_content.add_widget(self._create_track_widget(track))

    def _create_track_widget(self, track: Dict[str, Any]) -> Button:
        track_name = track.get("name", "Unknown Track")
        artists = track.get("artists", [])
        duration_ms = track.get("duration_ms", 0)

        spotify_cached = track.get("spotify_cached", False)
        reccobeats_cached = track.get("reccobeats_cached", False)

        if artists:
            valid_artists = [str(a) for a in artists if a is not None]
            artists_text = ", ".join(valid_artists[:2])
            if len(valid_artists) > 2:
                artists_text += "..."
        else:
            artists_text = "Unknown Artist"

        duration_text = ""
        if duration_ms:
            minutes = duration_ms // 60000
            seconds = (duration_ms % 60000) // 1000
            duration_text = f"{minutes}:{seconds:02d}"

        sources = []
        if spotify_cached:
            sources.append("S")
        if reccobeats_cached:
            sources.append("R")
        sources_text = f"[{','.join(sources)}]" if sources else "[ ]"

        char_width = dp(7)
        max_chars = int(dp(280) / char_width)
        if len(track_name) > max_chars:
            track_name = track_name[: max_chars - 3] + "..."
        if len(artists_text) > max_chars:
            artists_text = artists_text[: max_chars - 3] + "..."

        text = f"{track_name}\n{artists_text}\n{duration_text} {sources_text}"

        btn = Button(
            text=text,
            size_hint_y=None,
            height=dp(60),
            background_color=[0.2, 0.4, 0.4, 1]
            if track == self.selected_track
            else [0.3, 0.3, 0.3, 1],
            font_size=dp(11),
            halign="left",
            padding=(dp(15), dp(5)),
            text_size=(dp(270), None),
        )
        btn.bind(on_press=lambda _: self.select_track(track))
        return btn

    def select_track(self, track: Dict[str, Any]) -> None:
        self.selected_track = track

        track_name = track.get("name", "Unknown Track")
        if len(track_name) > 20:
            track_name = track_name[:17] + "..."
        self.breadcrumb_label.text = f"Playlists > {self.selected_playlist.get('name', 'Unknown')} > {track_name}"

        self.details_column.opacity = 1
        self.features_column.opacity = 1

        self.populate_details_column(track)
        if self.selected_playlist is not None:
            self.populate_tracks_column(self.selected_playlist)

    def populate_details_column(self, track: Dict[str, Any]) -> None:
        self.details_content.clear_widgets()

        track_name = track.get("name", "Unknown Track")
        artists = track.get("artists", [])
        album = track.get("album", {})
        spotify_id = track.get("id", "")
        duration_ms = track.get("duration_ms", 0)
        spotify_cached = track.get("spotify_cached", False)
        reccobeats_cached = track.get("reccobeats_cached", False)

        duration_text = ""
        if duration_ms:
            minutes = duration_ms // 60000
            seconds = (duration_ms % 60000) // 1000
            duration_text = f"{minutes}:{seconds:02d}"

        details = [
            ("Track Name", track_name),
            (
                "Artists",
                ", ".join([str(a) for a in artists if a is not None])
                if artists
                else "Unknown",
            ),
            (
                "Album",
                album.get("name", "Unknown") if isinstance(album, dict) else str(album),
            ),
            ("Spotify ID", spotify_id),
            ("Duration", duration_text),
            ("Spotify Cached", "Yes" if spotify_cached else "No"),
            ("ReccoBeats Cached", "Yes" if reccobeats_cached else "No"),
        ]

        for label, value in details:
            self.details_content.add_widget(self._create_detail_item(label, value))

        Clock.schedule_once(lambda _: self.show_features_column(track))

    def _create_detail_item(self, label: str, value: str) -> Button:
        max_value_length = 35
        if len(value) > max_value_length:
            value = value[: max_value_length - 3] + "..."

        btn = Button(
            text=f"{label}:\n{value}",
            size_hint_y=None,
            height=dp(60),
            background_color=[0.3, 0.3, 0.3, 1],
            font_size=dp(11),
            halign="left",
            padding=(dp(15), dp(5)),
            text_size=(dp(270), None),
        )
        return btn

    def show_features_column(self, track: Dict[str, Any]) -> None:
        if self.features_column.opacity == 0:
            self.features_column.opacity = 1
        self.populate_features_column(track)

    def populate_features_column(self, track: Dict[str, Any]) -> None:
        """Show ReccoBeats features from injected cache_data."""
        self.features_content.clear_widgets()

        try:
            spotify_id = track.get("id", "")
            if not spotify_id:
                self.features_content.add_widget(
                    Label(text="No track ID available", font_size=dp(14))
                )
                return

            features_by_track: Dict[str, Any] = self.cache_data.get(
                "features_by_track", {}
            )
            features = features_by_track.get(spotify_id)

            if not features:
                self.features_content.add_widget(
                    Label(text="No analysis available", font_size=dp(14))
                )
                return

            feature_items = [
                ("Danceability", features.get("danceability", 0), "{:.3f}"),
                ("Energy", features.get("energy", 0), "{:.3f}"),
                ("Valence", features.get("valence", 0), "{:.3f}"),
                ("Tempo", features.get("tempo", 0), "{:.1f} BPM"),
                ("Acousticness", features.get("acousticness", 0), "{:.3f}"),
                ("Instrumentalness", features.get("instrumentalness", 0), "{:.3f}"),
                ("Liveness", features.get("liveness", 0), "{:.3f}"),
                ("Speechiness", features.get("speechiness", 0), "{:.3f}"),
                ("Key", features.get("key", 0), "{}"),
                ("Mode", "Major" if features.get("mode", 0) == 1 else "Minor", "{}"),
                ("Loudness", features.get("loudness", 0), "{:.1f} dB"),
            ]

            for feature_name, value, format_str in feature_items:
                self.features_content.add_widget(
                    self._create_feature_item(feature_name, value, format_str)
                )

        except Exception as exc:
            logger.error("Error loading ReccoBeats features: %s", exc)
            self.features_content.add_widget(
                Label(text=f"Error loading features: {exc}", font_size=dp(14))
            )

    def _create_feature_item(self, name: str, value: Any, format_str: str) -> Button:
        formatted_value = format_str.format(value) if value is not None else "N/A"

        max_value_length = 25
        if len(formatted_value) > max_value_length:
            formatted_value = formatted_value[: max_value_length - 3] + "..."

        btn = Button(
            text=f"{name}:\n{formatted_value}",
            size_hint_y=None,
            height=dp(60),
            background_color=[0.3, 0.3, 0.3, 1],
            font_size=dp(11),
            halign="left",
            padding=(dp(15), dp(5)),
            text_size=(dp(270), None),
        )
        return btn

    # ------------------------------------------------------------------
    # Column close / navigation
    # ------------------------------------------------------------------

    def close_tracks_column(self) -> None:
        self.tracks_column.opacity = 0
        self.tracks_content.clear_widgets()
        self.selected_playlist = None
        self.close_details_column()
        self.close_features_column()
        self.breadcrumb_label.text = "Playlists"
        self.populate_playlists_column()

    def close_details_column(self) -> None:
        self.details_column.opacity = 0
        self.details_content.clear_widgets()
        self.selected_track = None
        self.close_features_column()
        if self.selected_playlist:
            playlist_name = self.selected_playlist.get("name", "Unknown")
            self.breadcrumb_label.text = f"Playlists > {playlist_name}"

    def close_features_column(self) -> None:
        self.features_column.opacity = 0
        self.features_content.clear_widgets()

    def refresh_data(self, *_args) -> None:
        self.load_cache_data()

    def on_search_text(self, instance, value: str) -> None:
        self.filter_text = value.lower()
        if hasattr(self, "cache_data") and self.cache_data:
            self.populate_playlists_column()

    def show_error(self, error_message: str) -> None:
        self.playlists_content.clear_widgets()
        self.playlists_content.add_widget(
            Label(
                text=f"Error: {error_message}",
                font_size=dp(14),
                color=(0.8, 0.3, 0.3, 1),
                size_hint_y=None,
                height=dp(30),
            )
        )


__all__ = ["CacheExplorerPopup"]
