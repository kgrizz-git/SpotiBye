"""UI construction mixin for BackendPlaylistCard.

Defines PlaylistCardUIMixin — card layout, image loading, text sections,
graphics updates (canvas Rectangle positioning), and selection highlight.
Depends on kivy and .backend_playlist_card_utils.
"""

from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout


class PlaylistCardUIMixin:
    """UI mixin for BackendPlaylistCard — builds widget tree and manages graphics.

    All canvas attributes (card_bg, info_bg, _bg_color) are created
    dynamically inside _build_card_ui's canvas.before block and declared
    here as class-level Any defaults for basedpyright.
    """

    card_bg: Any = None
    info_bg: Any = None
    _bg_color: Any = None
    cover_image: Any = None
    checkbox: Any = None
    _graphics_update_scheduled: Any = None

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
            from ...shared.logging_config import logger

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
                text=f"{track_count} tracks \u00b7 {owner}",
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

    def _on_checkbox_change(self, _checkbox, active: bool) -> None:
        if active:
            self._bg_color.rgba = (0.2, 0.4, 0.6, 1)
        else:
            self._bg_color.rgba = (0.18, 0.18, 0.18, 1)


__all__ = ["PlaylistCardUIMixin"]