"""Tracks-popup mixin for BackendPlaylistCard.

Defines PlaylistCardTracksPopupMixin — the track-list window opened from
the analysis popup's "Show Tracks" button, the row-rendering helper,
and the async worker that fetches tracks via the backend adapter.
Calls self._make_track_row / self._build_tracks_popup_content /
self._set_tracks_error / self._populate_tracks via self.* — all defined
on this same mixin.

Thread-safety: _load_tracks_worker runs on a daemon thread and marshals
all UI mutations back to the Kivy main thread via Clock.schedule_once.
_open_tracks_window guards with hasattr(content, "_tracks_layout")
(source line 816) before spawning the thread, and the worker receives
tracks_layout as an argument, never re-reading it off self.content at
runtime.

Depends on kivy, threading, ...shared.logging_config.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from ...shared.logging_config import logger


class PlaylistCardTracksPopupMixin:
    """Tracks-popup mixin for BackendPlaylistCard.

    Provides the "Show Tracks" window with a column-layout track table,
    async worker fetch, and error/loading states. The popup content
    attribute content._tracks_layout is preserved for worker-thread
    access.
    """

    playlist_data: Any = None
    _tracks_popup: Optional[Any] = None

    # Column layout for track rows (no duration column)
    _COL_NUM: float = dp(32)
    _COL_TRACK: float = 0.33
    _COL_ART: float = 0.28
    _COL_ALB: float = 0.39

    def _open_tracks_window(self, _btn) -> None:
        if self._tracks_popup and self._tracks_popup.parent:
            return

        name = self.playlist_data.get("name", "Playlist")
        content = self._build_tracks_popup_content()
        self._tracks_popup = Popup(
            title=f"Tracks: {name}",
            title_size=dp(16),
            title_color=(1, 1, 1, 1),
            size_hint=(0.72, 0.82),
            background_color=(0.15, 0.15, 0.15, 0.97),
            auto_dismiss=True,
            overlay_color=(0, 0, 0, 0.5),
            content=content,
        )
        self._tracks_popup.open()

        playlist_id = self.playlist_data.get("id")
        if playlist_id and hasattr(content, "_tracks_layout"):
            threading.Thread(
                target=self._load_tracks_worker,
                args=(playlist_id, content._tracks_layout, False),
                daemon=True,
            ).start()

    def _build_tracks_popup_content(self) -> BoxLayout:
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))

        # Sub-header
        name = self.playlist_data.get("name", "")
        track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
        owner = (self.playlist_data.get("owner") or {}).get("display_name", "Unknown")
        root.add_widget(
            Label(
                text=name,
                font_size=dp(15),
                bold=True,
                color=(1, 1, 1, 1),
                halign="center",
                size_hint_y=None,
                height=dp(28),
            )
        )
        root.add_widget(
            Label(
                text=f"{track_count} tracks \u00b7 by {owner}",
                font_size=dp(12),
                color=(0.65, 0.65, 0.65, 1),
                halign="center",
                size_hint_y=None,
                height=dp(20),
            )
        )

        # Table header row
        root.add_widget(
            self._make_track_row(
                "#",
                "Title",
                "Artist",
                "Album",
                row_color=(0.12, 0.12, 0.12, 1),
                text_color=(0.55, 0.55, 0.55, 1),
                bold=True,
            )
        )

        # Scrollable track list
        scroll = ScrollView(size_hint=(1, 1))
        tracks_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=0)
        tracks_layout.bind(minimum_height=tracks_layout.setter("height"))
        tracks_layout.add_widget(
            Label(
                text="Loading tracks\u2026",
                font_size=dp(12),
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(32),
            )
        )
        scroll.add_widget(tracks_layout)
        root.add_widget(scroll)

        action_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        refresh_btn = Button(
            text="Refresh playlist tracks",
            size_hint=(0.7, 1),
            background_color=(0.28, 0.38, 0.22, 1),
            color=(1, 1, 1, 1),
        )
        refresh_btn.bind(on_release=self._refresh_tracks_popup)
        action_row.add_widget(refresh_btn)
        close_btn = Button(
            text="Close",
            size_hint=(0.3, 1),
            background_color=(0.22, 0.22, 0.22, 1),
            color=(1, 1, 1, 1),
        )
        close_btn.bind(
            on_release=lambda _: self._tracks_popup and self._tracks_popup.dismiss()
        )
        action_row.add_widget(close_btn)
        root.add_widget(action_row)

        root._tracks_layout = tracks_layout
        return root

    def _refresh_tracks_popup(self, _btn) -> None:
        playlist_id = self.playlist_data.get("id")
        popup = self._tracks_popup
        content = getattr(popup, "content", None)
        if not playlist_id or content is None or not hasattr(content, "_tracks_layout"):
            return

        tracks_layout = content._tracks_layout
        tracks_layout.clear_widgets()
        tracks_layout.add_widget(
            Label(
                text="Refreshing tracks\u2026",
                font_size=dp(12),
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(32),
            )
        )
        threading.Thread(
            target=self._load_tracks_worker,
            args=(playlist_id, tracks_layout, True),
            daemon=True,
        ).start()

    def _make_track_row(
        self,
        num: str,
        track: str,
        artist: str,
        album: str,
        row_color=(0.2, 0.2, 0.2, 1),
        text_color=(0.88, 0.88, 0.88, 1),
        bold: bool = False,
    ) -> BoxLayout:
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(30),
            padding=[dp(4), 0],
        )
        with row.canvas.before:
            Color(*row_color)
            rect = Rectangle(size=row.size, pos=row.pos)
        row.bind(size=lambda w, v, r=rect: setattr(r, "size", v))
        row.bind(pos=lambda w, v, r=rect: setattr(r, "pos", v))

        def cell(text, size_hint_x=None, width=None, align="left"):
            kw = dict(
                text=text,
                font_size=dp(11),
                bold=bold,
                color=text_color,
                halign=align,
                valign="middle",
            )
            if width is not None:
                kw.update(
                    size_hint=(None, 1),  # pyright: ignore[reportArgumentType]
                    width=width,
                    text_size=(width - dp(4), None),  # pyright: ignore[reportArgumentType]
                )
            else:
                kw.update(
                    size_hint=(size_hint_x, 1),  # pyright: ignore[reportArgumentType]
                    text_size=(None, None),  # pyright: ignore[reportArgumentType]
                )
            return Label(**kw)

        row.add_widget(cell(num, width=self._COL_NUM, align="right"))
        row.add_widget(cell(track, size_hint_x=self._COL_TRACK))
        row.add_widget(cell(artist, size_hint_x=self._COL_ART))
        row.add_widget(cell(album, size_hint_x=self._COL_ALB))
        return row

    def _load_tracks_worker(
        self, playlist_id: str, tracks_layout: BoxLayout, force_refresh: bool = False
    ) -> None:
        try:
            app = App.get_running_app()
            adapter = getattr(app, "backend_adapter", None)
            if adapter is None:
                Clock.schedule_once(
                    lambda _dt: self._set_tracks_error(
                        tracks_layout, "No backend connection"
                    ),
                    0,
                )
                return

            if force_refresh and hasattr(adapter, "refresh_playlist_tracks_only"):
                tracks = adapter.refresh_playlist_tracks_only(playlist_id)
            else:
                tracks = adapter.get_playlist_tracks(playlist_id)
            Clock.schedule_once(
                lambda _dt: self._populate_tracks(tracks_layout, tracks), 0
            )
        except Exception as exc:
            logger.warning("BackendPlaylistCard: error loading tracks: %s", exc)
            Clock.schedule_once(
                lambda _dt, _e=exc: self._set_tracks_error(tracks_layout, str(_e)), 0
            )

    def _populate_tracks(self, tracks_layout: BoxLayout, tracks) -> None:
        tracks_layout.clear_widgets()
        if not tracks:
            tracks_layout.add_widget(
                Label(
                    text="No tracks found",
                    font_size=dp(12),
                    color=(0.5, 0.5, 0.5, 1),
                    size_hint_y=None,
                    height=dp(32),
                )
            )
            return

        for i, track_item in enumerate(tracks):
            track = (
                track_item.get("track") or track_item
                if isinstance(track_item, dict) and "track" in track_item
                else track_item
            )
            if not isinstance(track, dict):
                continue

            name = track.get("name") or "Unknown"
            artists = (
                ", ".join(
                    a.get("name", "")
                    for a in (track.get("artists") or [])
                    if a.get("name")
                )
                or "\u2014"
            )
            album = (track.get("album") or {}).get("name") or "\u2014"

            row_color = (0.20, 0.20, 0.20, 1) if i % 2 == 0 else (0.17, 0.17, 0.17, 1)
            row = self._make_track_row(
                str(i + 1),
                name,
                artists,
                album,
                row_color=row_color,
            )
            tracks_layout.add_widget(row)

    def _set_tracks_error(self, tracks_layout: BoxLayout, message: str) -> None:
        tracks_layout.clear_widgets()
        tracks_layout.add_widget(
            Label(
                text=f"Could not load tracks: {message}",
                font_size=dp(12),
                color=(0.7, 0.4, 0.4, 1),
                size_hint_y=None,
                height=dp(32),
            )
        )


__all__ = ["PlaylistCardTracksPopupMixin"]
