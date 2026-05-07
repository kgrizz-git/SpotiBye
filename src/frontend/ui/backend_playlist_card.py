"""Lightweight playlist card widget for backend mode — no v2 dependencies."""

from __future__ import annotations

import threading
import time
from math import sqrt
from typing import Any, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView

from ...shared.logging_config import logger


class BackendPlaylistCard(BoxLayout):
    """Playlist card for backend mode — checkbox + cover image, no disk cache or ReccoBeats.

    Interactions:
      - Single click anywhere: toggle selection (checkbox + blue highlight)
      - Double click / long press: open details popup with track list
    """

    DOUBLE_CLICK_THRESHOLD = 0.4  # seconds
    LONG_PRESS_DURATION = 0.8  # seconds
    MOVEMENT_THRESHOLD = dp(12)
    MIN_CLICK_DURATION = 0.05  # seconds

    def __init__(self, playlist_data: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(190)
        self.padding = dp(8)
        self.spacing = dp(0)

        self.playlist_data = playlist_data
        self._graphics_update_scheduled = False

        # Touch-interaction state
        self._is_touch_down = False
        self._touch_start_time: float = 0.0
        self._touch_start_pos: Optional[tuple] = None
        self._last_click_time: float = 0.0
        self._long_press_event: Optional[Any] = None
        self._pending_single_click: Optional[Any] = None

        # Details popup
        self._detailed_popup: Optional[Popup] = None

        self._build_card_ui()
        self._setup_interactions()

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------

    def _build_card_ui(self) -> None:
        with self.canvas.before:
            self._bg_color = Color(0.18, 0.18, 0.18, 1)
            self.card_bg = Rectangle(size=self.size, pos=self.pos)

        image_url = self._get_playlist_image_url()
        self.cover_image = AsyncImage(
            source=image_url,
            size_hint_y=None,
            height=dp(110),
            allow_stretch=True,
            keep_ratio=False,
            anim_delay=0.05,
        )
        self.add_widget(self.cover_image)

        info_container = BoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(65)
        )
        with info_container.canvas.before:
            Color(0.25, 0.25, 0.25, 1)
            self.info_bg = Rectangle(size=info_container.size, pos=info_container.pos)

        info_container.add_widget(self._create_text_section())
        self.add_widget(info_container)

        checkbox_overlay = RelativeLayout(size_hint=(1, 1))
        self.checkbox = CheckBox(
            size_hint=(None, None),
            size=(dp(16), dp(16)),
            active=False,
            pos=(dp(130), dp(14)),
        )
        checkbox_overlay.add_widget(self.checkbox)
        self.add_widget(checkbox_overlay)

        info_container.bind(size=self._update_info_bg, pos=self._update_info_bg)
        self.bind(
            size=self._schedule_graphics_update, pos=self._schedule_graphics_update
        )
        self.checkbox.bind(active=self._on_checkbox_change)

    def _get_playlist_image_url(self) -> str:
        try:
            images = self.playlist_data.get("images") or []
            if images:
                url = images[0]["url"]
                for img in images:
                    if img.get("width") is not None and img["width"] <= 300:
                        url = img["url"]
                        break
                return url
        except Exception as exc:
            logger.warning("BackendPlaylistCard: error getting image url: %s", exc)
        return ""

    def _create_text_section(self) -> BoxLayout:
        text_section = BoxLayout(
            orientation="vertical",
            spacing=dp(1),
            padding=[dp(16), dp(3), dp(6), dp(3)],
            size_hint_y=1,
        )

        name = self.playlist_data.get("name", "Untitled Playlist")
        track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
        owner = (self.playlist_data.get("owner") or {}).get("display_name", "Unknown")

        available_width = dp(140)
        max_chars = int(available_width / dp(8))
        if len(name) > max_chars:
            name = name[: max_chars - 3] + "..."

        text_section.add_widget(
            Label(
                text=name,
                font_size=dp(13),
                bold=True,
                color=(1, 1, 1, 1),
                text_size=(dp(140), None),
                halign="left",
                valign="top",
                size_hint_y=None,
                height=dp(30),
            )
        )
        text_section.add_widget(
            Label(
                text=f"{track_count} tracks · {owner}",
                font_size=dp(10),
                color=(0.7, 0.7, 0.7, 1),
                text_size=(dp(140), None),
                halign="left",
                valign="top",
                size_hint_y=None,
                height=dp(20),
            )
        )
        return text_section

    # ------------------------------------------------------------------
    # Interaction — override methods directly and use touch.grab so the
    # paired on_touch_up is always delivered to this widget.
    # ------------------------------------------------------------------

    def _setup_interactions(self) -> None:
        pass  # handled by on_touch_down / on_touch_up overrides

    def on_touch_down(self, touch) -> bool:
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        touch.grab(self)
        self._is_touch_down = True
        self._touch_start_time = time.time()
        self._touch_start_pos = touch.pos

        if self._long_press_event:
            self._long_press_event.cancel()
        self._long_press_event = Clock.schedule_once(
            lambda _dt: self._trigger_long_press(),
            self.LONG_PRESS_DURATION,
        )
        # Do NOT call super — the checkbox is a visual-only indicator; we
        # toggle checkbox.active ourselves so it doesn't get double-toggled
        # (once by its own handler, once by _handle_delayed_single_click).
        return True

    def on_touch_move(self, touch) -> bool:
        if touch.grab_current is self and self._is_touch_down and self._touch_start_pos:
            dx = touch.pos[0] - self._touch_start_pos[0]
            dy = touch.pos[1] - self._touch_start_pos[1]
            if sqrt(dx * dx + dy * dy) > self.MOVEMENT_THRESHOLD:
                self._is_touch_down = False
                if self._long_press_event:
                    self._long_press_event.cancel()
        return super().on_touch_move(touch)

    def _trigger_long_press(self) -> None:
        if self._is_touch_down:
            self._is_touch_down = False
            self.show_detailed_playlist_window()

    def on_touch_up(self, touch) -> bool:
        # Only process the touch we grabbed; ignore the normal tree dispatch.
        if touch.grab_current is not self:
            return super().on_touch_up(touch)

        touch.ungrab(self)
        self._is_touch_down = False

        if self._long_press_event:
            self._long_press_event.cancel()

        # Ignore scroll gestures (belt-and-suspenders alongside on_touch_move).
        if self._touch_start_pos:
            dx = touch.pos[0] - self._touch_start_pos[0]
            dy = touch.pos[1] - self._touch_start_pos[1]
            if sqrt(dx * dx + dy * dy) > self.MOVEMENT_THRESHOLD:
                return True

        touch_duration = time.time() - self._touch_start_time
        # Long-press was already handled by the Clock callback.
        if touch_duration >= self.LONG_PRESS_DURATION:
            return True

        now = time.time()
        time_since_last = now - self._last_click_time

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            # Double-click
            if self._pending_single_click:
                self._pending_single_click.cancel()
                self._pending_single_click = None
            self._last_click_time = 0.0
            self.show_detailed_playlist_window()
        else:
            # Potential single click — wait to rule out a second click.
            self._last_click_time = now
            if self._pending_single_click:
                self._pending_single_click.cancel()
            self._pending_single_click = Clock.schedule_once(
                self._handle_delayed_single_click,
                self.DOUBLE_CLICK_THRESHOLD + 0.05,
            )

        return True

    def _handle_delayed_single_click(self, _dt) -> None:
        self._pending_single_click = None
        if not (self._detailed_popup and self._detailed_popup.parent):
            self.checkbox.active = not self.checkbox.active

    # ------------------------------------------------------------------
    # Selection highlight
    # ------------------------------------------------------------------

    def _on_checkbox_change(self, _checkbox, active: bool) -> None:
        if active:
            self._bg_color.rgba = (0.2, 0.4, 0.6, 1)
        else:
            self._bg_color.rgba = (0.18, 0.18, 0.18, 1)

    # ------------------------------------------------------------------
    # Details popup
    # ------------------------------------------------------------------

    def show_detailed_playlist_window(self) -> None:
        if self._detailed_popup and self._detailed_popup.parent:
            return

        content = self._build_popup_content()
        name = self.playlist_data.get("name", "Playlist Details")
        self._detailed_popup = Popup(
            title=name,
            title_size=dp(18),
            title_color=(1, 1, 1, 1),
            size_hint=(0.70, 0.75),
            background_color=(0.15, 0.15, 0.15, 0.97),
            auto_dismiss=True,
            overlay_color=(0, 0, 0, 0.5),
            content=content,
        )
        self._detailed_popup.open()

        # Load tracks in background
        playlist_id = self.playlist_data.get("id")
        if playlist_id and hasattr(content, "_tracks_layout"):
            threading.Thread(
                target=self._load_tracks_worker,
                args=(playlist_id, content._tracks_layout),
                daemon=True,
            ).start()

    def _build_popup_content(self) -> BoxLayout:
        import re

        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

        # Header: image + metadata
        header = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(110), spacing=dp(12)
        )
        image_url = self._get_playlist_image_url()
        header.add_widget(
            AsyncImage(
                source=image_url,
                size_hint=(None, 1),
                width=dp(100),
                allow_stretch=True,
                keep_ratio=True,
            )
        )

        meta = BoxLayout(
            orientation="vertical", spacing=dp(2), padding=[0, dp(4), 0, 0]
        )
        track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
        owner = (self.playlist_data.get("owner") or {}).get("display_name", "Unknown")
        description = self.playlist_data.get("description") or ""

        meta.add_widget(
            Label(
                text=f"By {owner}  ·  {track_count} tracks",
                font_size=dp(12),
                color=(0.75, 0.75, 0.75, 1),
                halign="left",
                valign="top",
                text_size=(dp(400), None),
                size_hint_y=None,
                height=dp(22),
            )
        )
        if description:
            clean_desc = re.sub(r"<[^>]+>", "", description)[:220]
            meta.add_widget(
                Label(
                    text=clean_desc,
                    font_size=dp(11),
                    color=(0.5, 0.5, 0.5, 1),
                    halign="left",
                    valign="top",
                    text_size=(dp(400), None),
                    size_hint_y=None,
                    height=dp(60),
                )
            )
        header.add_widget(meta)
        root.add_widget(header)

        # Table header row
        header_row = self._make_track_row(
            "#",
            "Track",
            "Artist",
            "Album",
            "Time",
            row_color=(0.12, 0.12, 0.12, 1),
            text_color=(0.55, 0.55, 0.55, 1),
            bold=True,
        )
        root.add_widget(header_row)

        # Scrollable track list
        scroll = ScrollView(size_hint=(1, 1))
        tracks_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=0)
        tracks_layout.bind(minimum_height=tracks_layout.setter("height"))
        tracks_layout.add_widget(
            Label(
                text="Loading tracks…",
                font_size=dp(12),
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(32),
            )
        )
        scroll.add_widget(tracks_layout)
        root.add_widget(scroll)

        root._tracks_layout = tracks_layout
        return root

    # Column widths (index / track / artist / album / duration)
    _COL_NUM = dp(30)
    _COL_DUR = dp(48)
    _COL_TRACK = 0.32
    _COL_ART = 0.26
    _COL_ALB = 0.42  # gets the remaining share

    def _make_track_row(
        self,
        num: str,
        track: str,
        artist: str,
        album: str,
        duration: str,
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
                    size_hint=(None, 1), width=width, text_size=(width - dp(4), None)
                )
            else:
                kw.update(size_hint=(size_hint_x, 1), text_size=(None, None))
            return Label(**kw)

        row.add_widget(cell(num, width=self._COL_NUM, align="right"))
        row.add_widget(cell(track, size_hint_x=self._COL_TRACK))
        row.add_widget(cell(artist, size_hint_x=self._COL_ART))
        row.add_widget(cell(album, size_hint_x=self._COL_ALB))
        row.add_widget(cell(duration, width=self._COL_DUR, align="right"))
        return row

    def _load_tracks_worker(self, playlist_id: str, tracks_layout: BoxLayout) -> None:
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
                or "—"
            )
            album = (track.get("album") or {}).get("name") or "—"
            dur_ms = track.get("duration_ms") or 0
            mins, secs = divmod(dur_ms // 1000, 60)
            duration = f"{mins}:{secs:02d}"

            row_color = (0.20, 0.20, 0.20, 1) if i % 2 == 0 else (0.17, 0.17, 0.17, 1)
            row = self._make_track_row(
                str(i + 1),
                name,
                artists,
                album,
                duration,
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

    # ------------------------------------------------------------------
    # Graphics helpers
    # ------------------------------------------------------------------

    def _update_info_bg(self, instance, _value) -> None:
        self.info_bg.size = instance.size
        self.info_bg.pos = instance.pos

    def _schedule_graphics_update(self, *_args) -> None:
        if not self._graphics_update_scheduled:
            self._graphics_update_scheduled = True
            Clock.schedule_once(self._update_card_bg, 0)

    def _update_card_bg(self, _dt) -> None:
        self._graphics_update_scheduled = False
        if hasattr(self, "card_bg"):
            self.card_bg.size = self.size
            self.card_bg.pos = self.pos
