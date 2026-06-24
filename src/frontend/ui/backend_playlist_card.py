"""Lightweight playlist card widget for backend mode — no v2 dependencies."""

from __future__ import annotations

import threading
import time
from math import sqrt
from typing import Any, Optional

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from ...shared.logging_config import logger


class BackendPlaylistCard(BoxLayout):
    """Playlist card for backend mode — checkbox + cover image, no disk cache or ReccoBeats.

    Interactions:
      - Single click anywhere: toggle selection (checkbox + blue highlight)
      - Double click / long press: open Playlist Analysis popup
        → "Show Tracks" button inside opens the track-list window
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

        # Popup handles
        self._detailed_popup: Optional[Popup] = None  # analysis popup
        self._tracks_popup: Optional[Popup] = None  # tracks popup

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
    # Interaction
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
        if touch.grab_current is not self:
            return super().on_touch_up(touch)

        touch.ungrab(self)
        self._is_touch_down = False

        if self._long_press_event:
            self._long_press_event.cancel()

        if self._touch_start_pos:
            dx = touch.pos[0] - self._touch_start_pos[0]
            dy = touch.pos[1] - self._touch_start_pos[1]
            if sqrt(dx * dx + dy * dy) > self.MOVEMENT_THRESHOLD:
                return True

        touch_duration = time.time() - self._touch_start_time
        if touch_duration >= self.LONG_PRESS_DURATION:
            return True

        now = time.time()
        time_since_last = now - self._last_click_time

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            if self._pending_single_click:
                self._pending_single_click.cancel()
                self._pending_single_click = None
            self._last_click_time = 0.0
            self.show_detailed_playlist_window()
        else:
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
    # Playlist Analysis popup  (double-click / long-press)
    # ------------------------------------------------------------------

    def show_detailed_playlist_window(self) -> None:
        if self._detailed_popup and self._detailed_popup.parent:
            return

        content = self._build_analysis_popup_content()
        self._detailed_popup = Popup(
            title="Playlist Analysis",
            title_size=dp(16),
            title_color=(1, 1, 1, 1),
            size_hint=(0.75, 0.88),
            background_color=(0.15, 0.15, 0.15, 0.97),
            auto_dismiss=True,
            overlay_color=(0, 0, 0, 0.5),
            content=content,
        )
        self._detailed_popup.open()

        playlist_id = self.playlist_data.get("id")
        if playlist_id:
            threading.Thread(
                target=self._load_analysis_worker,
                args=(
                    playlist_id,
                    content._analysis_container,
                    content._duration_label,
                ),
                daemon=True,
            ).start()

    def _build_analysis_popup_content(self) -> BoxLayout:
        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

        # ── main area: left technical panel + right scrollable details ──
        main = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=1)

        # Left panel — cover image + technical details
        left = BoxLayout(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(170),
            spacing=dp(4),
        )

        image_url = self._get_playlist_image_url()
        left.add_widget(
            AsyncImage(
                source=image_url,
                size_hint=(1, None),
                height=dp(155),
                allow_stretch=True,
                keep_ratio=True,
            )
        )

        # Image dimension info from the API payload
        images = self.playlist_data.get("images") or []
        if images:
            first = images[0]
            w = first.get("width") or "?"
            h = first.get("height") or "?"
            available = ", ".join(
                f"{i.get('width', '?')}x{i.get('height', '?')}"
                for i in images
                if i.get("width")
            )
            img_text = f"Image: {w}x{h}"
            if available:
                img_text += f"\n(Available: {available})"
            left.add_widget(
                Label(
                    text=img_text,
                    font_size=dp(9),
                    color=(0.55, 0.55, 0.55, 1),
                    halign="left",
                    valign="top",
                    text_size=(dp(165), None),
                    size_hint_y=None,
                    height=dp(32),
                )
            )

        left.add_widget(
            Label(
                text="Technical Details:",
                font_size=dp(10),
                bold=True,
                color=(0.8, 0.8, 0.8, 1),
                halign="left",
                text_size=(dp(165), None),
                size_hint_y=None,
                height=dp(16),
            )
        )

        owner_id = (self.playlist_data.get("owner") or {}).get("id", "Unknown")
        playlist_id = self.playlist_data.get("id", "Unknown")
        snapshot_id = self.playlist_data.get("snapshot_id", "")
        snap_short = (
            (snapshot_id[:18] + "...") if len(snapshot_id) > 18 else snapshot_id
        )

        for label_text in (
            f"Owner ID:\n{owner_id}",
            f"Playlist ID:\n{playlist_id}",
            f"Version:\n{snap_short}",
        ):
            left.add_widget(
                Label(
                    text=label_text,
                    font_size=dp(9),
                    color=(0.6, 0.6, 0.6, 1),
                    halign="left",
                    valign="top",
                    text_size=(dp(165), None),
                    size_hint_y=None,
                    height=dp(30),
                )
            )

        left.add_widget(Widget())  # vertical spacer
        main.add_widget(left)

        # Right panel — scrollable playlist info + analysis
        scroll = ScrollView(size_hint=(1, 1))
        right = BoxLayout(
            orientation="vertical",
            spacing=dp(3),
            size_hint_y=None,
            padding=[0, 0, dp(6), 0],
        )
        right.bind(minimum_height=right.setter("height"))

        name = self.playlist_data.get("name", "Unknown Playlist")
        track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
        owner_display = (self.playlist_data.get("owner") or {}).get(
            "display_name", "Unknown"
        )
        playlist_url = (self.playlist_data.get("external_urls") or {}).get(
            "spotify", ""
        )
        owner_url = (
            (self.playlist_data.get("owner") or {}).get("external_urls") or {}
        ).get("spotify", "")
        is_public = self.playlist_data.get("public", True)

        def info_label(
            text,
            bold=False,
            color=(0.88, 0.88, 0.88, 1),
            font_size=dp(12),
            height=dp(20),
        ):
            right.add_widget(
                Label(
                    text=text,
                    font_size=font_size,
                    bold=bold,
                    color=color,
                    halign="left",
                    valign="top",
                    text_size=(dp(420), None),
                    size_hint_y=None,
                    height=height,
                )
            )

        info_label(name, bold=True, font_size=dp(17), height=dp(32))
        info_label(f"Created by: {owner_display}", color=(0.75, 0.75, 0.75, 1))
        if playlist_url:
            info_label(
                f"Playlist URL: {playlist_url}", color=(0.4, 0.6, 1.0, 1), height=dp(18)
            )
        if owner_url:
            info_label(
                f"Owner URL: {owner_url}", color=(0.4, 0.6, 1.0, 1), height=dp(18)
            )
        info_label(
            f"Type: {'Public' if is_public else 'Private'}", color=(0.75, 0.75, 0.75, 1)
        )

        # Duration label — updated after analysis loads
        duration_label = Label(
            text=f"Tracks: {track_count}",
            font_size=dp(12),
            color=(0.88, 0.88, 0.88, 1),
            halign="left",
            valign="top",
            text_size=(dp(420), None),
            size_hint_y=None,
            height=dp(20),
        )
        right.add_widget(duration_label)

        # Analysis container — replaced by _update_analysis_ui when data arrives
        analysis_container = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2)
        )
        analysis_container.bind(minimum_height=analysis_container.setter("height"))
        analysis_container.add_widget(
            Label(
                text="Genre Distribution:",
                font_size=dp(12),
                bold=True,
                color=(0.88, 0.88, 0.88, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(22),
            )
        )
        analysis_container.add_widget(
            Label(
                text="Retrieving analysis from ReccoBeats API...",
                font_size=dp(11),
                color=(0.75, 0.55, 0.15, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(20),
            )
        )
        right.add_widget(analysis_container)

        scroll.add_widget(right)

        # Right column wrapper: Show Tracks button pinned top-right, scroll below
        right_col = BoxLayout(orientation="vertical", spacing=dp(4))

        btn_row = BoxLayout(size_hint_y=None, height=dp(42))
        btn_row.add_widget(Widget())  # pushes button to the right
        show_tracks_btn = Button(
            text="Show Tracks",
            size_hint=(None, 1),
            width=dp(150),
            background_color=(0.22, 0.42, 0.72, 1),
            color=(1, 1, 1, 1),
        )
        show_tracks_btn.bind(on_release=self._open_tracks_window)
        btn_row.add_widget(show_tracks_btn)

        right_col.add_widget(btn_row)
        right_col.add_widget(scroll)

        main.add_widget(right_col)
        root.add_widget(main)

        root._analysis_container = analysis_container
        root._duration_label = duration_label
        return root

    # ------------------------------------------------------------------
    # Analysis loading
    # ------------------------------------------------------------------

    def _load_analysis_worker(
        self, playlist_id: str, analysis_container: BoxLayout, duration_label: Label
    ) -> None:
        try:
            app = App.get_running_app()
            adapter = getattr(app, "backend_adapter", None)
            if adapter is None:
                self._update_analysis_ui(
                    analysis_container, duration_label, None, "No backend connection"
                )
                return

            analysis = adapter.analyze_playlist(playlist_id)
            self._update_analysis_ui(analysis_container, duration_label, analysis, None)
        except Exception as exc:
            logger.warning("BackendPlaylistCard: analysis load error: %s", exc)
            self._update_analysis_ui(
                analysis_container, duration_label, None, str(exc)
            )

    @mainthread
    def _update_analysis_ui(
        self,
        analysis_container: BoxLayout,
        duration_label: Label,
        analysis: Optional[dict],
        error: Optional[str],
    ) -> None:
        analysis_container.clear_widgets()

        def _small_label(text, color=(0.75, 0.75, 0.75, 1), height=dp(18)):
            return Label(
                text=text,
                font_size=dp(11),
                color=color,
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=height,
            )

        def _section_header(text):
            return Label(
                text=text,
                font_size=dp(12),
                bold=True,
                color=(0.88, 0.88, 0.88, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(22),
            )

        if error or not analysis:
            msg = (
                f"Analysis unavailable: {error}" if error else "Analysis not available"
            )
            analysis_container.add_widget(_small_label(msg, color=(0.65, 0.4, 0.4, 1)))
            return

        # Normalise nested result wrapper
        results = analysis.get("results", analysis)

        # Duration
        overview = results.get("overview") or {}
        duration_str = overview.get("formatted_duration", "")
        if not duration_str:
            total_ms = overview.get("total_duration_ms", 0) or 0
            if total_ms:
                hrs = total_ms // 3_600_000
                mins = (total_ms % 3_600_000) // 60_000
                secs = (total_ms % 60_000) // 1000
                duration_str = f"{hrs}h {mins}m {secs}s" if hrs else f"{mins}m {secs}s"
        if duration_str:
            track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
            duration_label.text = f"Tracks: {track_count} · Duration: {duration_str}"

        # Genre distribution
        genre_dist = results.get("genre_distribution") or results.get("genres") or {}
        analysis_container.add_widget(_section_header("Genre Distribution:"))
        if genre_dist and isinstance(genre_dist, dict):
            entries = []
            for genre, val in genre_dist.items():
                if isinstance(val, dict):
                    pct = float(val.get("percentage", 0))
                    count = int(val.get("count", 0))
                elif isinstance(val, (int, float)):
                    pct = float(val) * 100 if float(val) <= 1 else float(val)
                    count = 0
                else:
                    continue
                entries.append((genre, pct, count))
            entries.sort(key=lambda x: x[1], reverse=True)
            for genre, pct, count in entries[:7]:
                line = (
                    f"{genre}: {pct:.0f}% ({count} tracks)"
                    if count
                    else f"{genre}: {pct:.0f}%"
                )
                analysis_container.add_widget(_small_label(line))
        else:
            analysis_container.add_widget(
                _small_label("No genre data available", color=(0.55, 0.55, 0.55, 1))
            )

        # Artist analysis
        artists_data = results.get("artists") or {}
        if artists_data:
            analysis_container.add_widget(_section_header("Artist Analysis:"))

            unique_artists = artists_data.get("unique_artists", 0)
            diversity = artists_data.get("diversity", 0) or 0
            diversity_pct = diversity * 100 if diversity <= 1 else diversity
            analysis_container.add_widget(
                _small_label(
                    f"Unique Artists: {unique_artists} · Diversity: {diversity_pct:.0f}%"
                )
            )

            top_artists = artists_data.get("top_artists") or []
            if top_artists:
                top_str = ", ".join(
                    f"{a.get('artist') or a.get('name', '?')} ({a.get('count', 0)})"
                    for a in top_artists[:5]
                )
                analysis_container.add_widget(_small_label(f"Top Artists: {top_str}"))

    # ------------------------------------------------------------------
    # Tracks window  (opened via "Show Tracks" button)
    # ------------------------------------------------------------------

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
                args=(playlist_id, content._tracks_layout),
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
                text=f"{track_count} tracks · by {owner}",
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
                text="Loading tracks…",
                font_size=dp(12),
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(32),
            )
        )
        scroll.add_widget(tracks_layout)
        root.add_widget(scroll)

        # Close button
        close_btn = Button(
            text="Close",
            size_hint=(1, None),
            height=dp(44),
            background_color=(0.22, 0.22, 0.22, 1),
            color=(1, 1, 1, 1),
        )
        close_btn.bind(
            on_release=lambda _: self._tracks_popup and self._tracks_popup.dismiss()
        )
        root.add_widget(close_btn)

        root._tracks_layout = tracks_layout
        return root

    # ------------------------------------------------------------------
    # Column layout for track rows (no duration column)
    # ------------------------------------------------------------------

    _COL_NUM = dp(32)
    _COL_TRACK = 0.33
    _COL_ART = 0.28
    _COL_ALB = 0.39

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
                    size_hint=(None, 1), width=width, text_size=(width - dp(4), None)
                )
            else:
                kw.update(size_hint=(size_hint_x, 1), text_size=(None, None))
            return Label(**kw)

        row.add_widget(cell(num, width=self._COL_NUM, align="right"))
        row.add_widget(cell(track, size_hint_x=self._COL_TRACK))
        row.add_widget(cell(artist, size_hint_x=self._COL_ART))
        row.add_widget(cell(album, size_hint_x=self._COL_ALB))
        return row

    # ------------------------------------------------------------------
    # Track loading
    # ------------------------------------------------------------------

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
