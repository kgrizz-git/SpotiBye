"""Playlist card widget extracted from the original monolithic script (part 1)."""

from __future__ import annotations

import platform
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import spotipy
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from .cached_async_image import CachedAsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from ..caching.analysis import (
    AnalysisTask,
    cache_playlist_analysis,
    cleanup_analysis_task,
    get_cached_playlist_analysis,
)
from ..caching.persistent_cache import persistent_cache
from ..caching.track_cache import (
    cache_spotify_track,
    get_cached_spotify_track,
    get_or_update_playlist_tracks,
)
from ..logging_config import logger
from ..auth.login_screen import create_spotify_client_with_refresh
from ..config import UIConstants
from ..state import active_analysis_tasks
from ..services.reccobeats import ReccoBeatsAPI
from .hover_manager import PlaylistHoverManager
from .tracks_window import TracksWindow


reccobeats_api = ReccoBeatsAPI()


class ProgressWindow(Popup):
    """Dedicated popup window for showing playlist loading progress."""

    def __init__(self, playlist_name: str, track_count: int, **kwargs):
        super().__init__(
            title=f"Loading {playlist_name}",
            title_size=dp(18),
            title_color=(1, 1, 1, 1),
            size_hint=(0.4, 0.3),
            background_color=(0.15, 0.15, 0.15, 0.95),
            auto_dismiss=False,  # Don't allow manual dismiss during loading
            overlay_color=(0, 0, 0, 0.5),
            **kwargs,
        )

        self.playlist_name = playlist_name
        self.track_count = track_count

        # Create content layout
        content_layout = BoxLayout(
            orientation="vertical", spacing=dp(15), padding=dp(20)
        )

        # Track count label
        self.track_label = Label(
            text=f"Loading {track_count:,} tracks...",
            font_size=dp(16),
            color=(0.9, 0.9, 0.9, 1),
            halign="center",
        )
        content_layout.add_widget(self.track_label)

        # Progress bar
        self.progress_bar = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(12)
        )
        content_layout.add_widget(self.progress_bar)

        # Status label
        self.status_label = Label(
            text="Initializing...",
            font_size=dp(14),
            color=(0.7, 0.7, 0.7, 1),
            halign="center",
        )
        content_layout.add_widget(self.status_label)

        # Cancel button
        self.cancel_button = Button(
            text="Cancel",
            size_hint=(None, None),
            size=(dp(100), dp(35)),
            pos_hint={"center_x": 0.5},
            background_color=(0.8, 0.3, 0.3, 1),
        )
        self.cancel_button.bind(on_press=self._on_cancel_pressed)
        content_layout.add_widget(self.cancel_button)

        self.content = content_layout
        self.is_cancelled = False
        self.is_dismissed = False

    def _on_cancel_pressed(self, instance):
        """Handle cancel button press."""
        self.is_cancelled = True
        self.set_completed()  # Allow dismissal
        self.dismiss()

    def update_progress(self, percent: int, message: str):
        """Update progress bar and status message."""

        def update_ui():
            self.progress_bar.value = percent
            self.status_label.text = message

        Clock.schedule_once(lambda dt: update_ui())

    def set_completed(self):
        """Mark loading as completed and enable auto-dismiss."""
        self.auto_dismiss = True
        self.cancel_button.text = "Close"
        self.cancel_button.background_color = (0.3, 0.6, 0.3, 1)

    def dismiss(self, *args):
        """Override dismiss to set is_dismissed flag."""
        self.is_dismissed = True
        super().dismiss(*args)

    def set_error(self, error_message: str):
        """Show error state."""
        self.status_label.text = f"Error: {error_message}"
        self.status_label.color = (0.8, 0.4, 0.4, 1)
        self.auto_dismiss = True
        self.cancel_button.text = "Close"
        self.cancel_button.background_color = (0.8, 0.3, 0.3, 1)


class PlaylistCard(BoxLayout):
    """Widget for displaying a single playlist in grid format (initial port)."""

    def __init__(self, playlist_data: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(190)
        self.padding = dp(8)
        self.spacing = dp(0)

        self.playlist_data = playlist_data

        self.tooltip_popup = None
        self.hover_event = None
        self.long_press_event = None
        self.is_touch_down = False
        self.touch_start_time = 0
        self.touch_start_pos = None
        self.last_click_time = 0
        self.double_click_threshold = 0.4
        self.movement_threshold = dp(
            12
        )  # 12dp movement threshold to distinguish scroll from click
        self.min_click_duration = (
            0.05  # 50ms minimum duration for real clicks (trackpad scrolling is faster)
        )
        self.pending_single_click = None
        self._graphics_initialized = False

        self._build_card_ui()
        self._setup_interactions()

        # Start progressive loading after UI is built
        Clock.schedule_once(lambda dt: self.start_progressive_loading(), 0.1)

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_card_ui(self) -> None:
        with self.canvas.before:
            Color(0.18, 0.18, 0.18, 1)
            self.card_bg = Rectangle(size=self.size, pos=self.pos)

        image_url = self._get_playlist_image_url()
        self.cover_image = CachedAsyncImage(
            source=image_url,
            size_hint_y=None,
            height=dp(110),
            fit_mode="cover",
            anim_delay=0.05,  # Reduced from 0.1 for faster loading
        )
        self.add_widget(self.cover_image)

        info_container = BoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(65)
        )
        with info_container.canvas.before:
            Color(0.25, 0.25, 0.25, 1)
            self.info_bg = Rectangle(size=info_container.size, pos=info_container.pos)

        text_section = self._create_text_section()
        info_container.add_widget(text_section)
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

        info_container.bind(size=self.update_info_bg, pos=self.update_info_bg)
        Clock.schedule_once(self.init_checkbox_graphics, 0)
        self.checkbox.bind(active=self.on_checkbox_change)
        self.bind(size=self.schedule_graphics_update, pos=self.schedule_graphics_update)
        self._graphics_update_scheduled = False

    def _get_playlist_image_url(self) -> str:
        try:
            if (
                self.playlist_data.get("images")
                and len(self.playlist_data["images"]) > 0
            ):
                images = self.playlist_data["images"]
                image_url = images[0]["url"]
                for img in images:
                    img_width = img.get("width")
                    if img_width is not None and img_width <= 300:
                        image_url = img["url"]
                        break
                return image_url
        except Exception as exc:
            logger.warning("Error getting playlist image: %s", exc)
        return ""

    def _create_text_section(self) -> BoxLayout:
        text_section = BoxLayout(
            orientation="vertical",
            spacing=dp(1),
            padding=[dp(16), dp(3), dp(6), dp(3)],
            size_hint_y=1,
        )

        name = self.playlist_data.get("name", "Untitled Playlist")
        track_count = self.playlist_data.get("tracks", {}).get("total", 0)
        owner = self.playlist_data.get("owner", {}).get("display_name", "Unknown")

        available_width = dp(140)
        max_chars = int(available_width / dp(8))
        if len(name) > max_chars:
            name = name[: max_chars - 3] + "..."

        name_label = Label(
            text=name,
            font_size=dp(13),
            bold=True,
            text_size=(available_width, dp(18)),
            halign="left",
            valign="center",
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(18),
            shorten=True,
            shorten_from="right",
        )
        text_section.add_widget(name_label)

        details_label = Label(
            text=f"{track_count} tracks",
            font_size=dp(12),
            color=(0.8, 0.8, 0.8, 1),
            text_size=(available_width, dp(14)),
            halign="left",
            valign="center",
            size_hint_y=None,
            height=dp(14),
        )
        text_section.add_widget(details_label)

        owner_label = Label(
            text=f"by {owner}",
            font_size=dp(11),
            color=(0.65, 0.65, 0.65, 1),
            text_size=(available_width, dp(18)),
            halign="left",
            valign="center",
            size_hint_y=None,
            height=dp(18),
            shorten=True,
            shorten_from="right",
        )
        text_section.add_widget(owner_label)

        return text_section

    # ------------------------------------------------------------------
    # Progressive loading support
    # ------------------------------------------------------------------
    def is_visible_in_viewport(self) -> bool:
        """Check if this card is currently visible in the viewport."""
        try:
            if not self.parent:
                return False

            # Get the scroll view parent
            scroll_view = self.parent
            while scroll_view and not isinstance(scroll_view, ScrollView):
                scroll_view = scroll_view.parent

            if not scroll_view:
                return True  # If no scroll view, assume visible

            # Get viewport bounds
            viewport_top = scroll_view.y + scroll_view.height
            viewport_bottom = scroll_view.y

            # Get card bounds in scroll view coordinates
            card_top = self.to_window(0, self.height)[1]
            card_bottom = self.to_window(0, 0)[1]

            # Check if card is visible (with some margin for better UX)
            margin = dp(50)  # 50dp margin
            return (
                card_top > viewport_bottom - margin
                and card_bottom < viewport_top + margin
            )

        except Exception as exc:
            logger.warning("Error checking viewport visibility: %s", exc)
            return True  # Default to visible on error

    def start_progressive_loading(self):
        """Start progressive loading when card becomes visible."""
        if hasattr(self, "_progressive_loading_started"):
            return

        self._progressive_loading_started = True

        # Check if card is visible, delay loading if not
        if self.is_visible_in_viewport():
            self._load_cover_image()
        else:
            # Schedule a check for when card becomes visible
            Clock.schedule_once(self._check_visibility_and_load, 0.1)

    def _check_visibility_and_load(self, dt):
        """Periodically check visibility and load image when visible."""
        if not hasattr(self, "_progressive_loading_started"):
            return

        if self.is_visible_in_viewport():
            self._load_cover_image()
        else:
            # Check again in 100ms
            Clock.schedule_once(self._check_visibility_and_load, 0.1)

    def _load_cover_image(self):
        """Load the cover image if not already loaded."""
        try:
            if hasattr(self, "cover_image") and self.cover_image:
                # Trigger the cached async image loading
                if hasattr(self.cover_image, "reload_with_cache"):
                    self.cover_image.reload_with_cache()
                # logger.debug("Progressive loading cover image for playlist: %s",
                #            self.playlist_data.get('name', 'Unknown'))
        except Exception as exc:
            logger.warning("Error in progressive loading: %s", exc)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------
    def _setup_interactions(self) -> None:
        self.bind(on_touch_down=self.on_card_touch_down)
        self.bind(on_touch_up=self.on_card_touch_up)

        try:
            system = platform.system()
            if system in ["Darwin", "Windows", "Linux"]:
                self.mouse_over = False
                self.register_with_hover_manager()
        except Exception:
            pass

    def register_with_hover_manager(self) -> None:
        try:
            if not hasattr(Window, "_playlist_hover_manager"):
                Window._playlist_hover_manager = PlaylistHoverManager()
            Window._playlist_hover_manager.register_card(self)
        except Exception as exc:
            logger.warning("Error registering with hover manager: %s", exc)

    # ------------------------------------------------------------------
    # Touch handling (single / double click + long-press)
    # ------------------------------------------------------------------
    def on_card_touch_down(self, _instance, touch):
        try:
            if not self.collide_point(*touch.pos):
                return False

            # Debug logging for touch events
            logger.debug(
                f"[TOUCH DOWN] pos={touch.pos}, button={getattr(touch, 'button', None)}, profile={getattr(touch, 'profile', None)}"
            )

            if getattr(touch, "button", None) == "right":
                self.show_simple_tooltip(touch.pos)
                return True

            self.is_touch_down = True
            self.touch_start_time = time.time()
            self.touch_start_pos = touch.pos

            if self.long_press_event:
                self.long_press_event.cancel()
            self.long_press_event = Clock.schedule_once(
                lambda _dt: self.show_detailed_playlist_window()
                if self.is_touch_down
                else None,
                0.8,
            )
            return True
        except Exception as exc:
            logger.warning("Error handling touch down: %s", exc)
            return False

    def on_card_touch_up(self, _instance, touch):
        try:
            if not self.collide_point(*touch.pos):
                self.is_touch_down = False
                self.touch_start_pos = None
                if self.long_press_event:
                    self.long_press_event.cancel()
                    self.long_press_event = None
                return False

            if getattr(touch, "button", None) == "right":
                self.touch_start_pos = None
                return True

            touch_duration = (
                time.time() - self.touch_start_time if self.touch_start_time else 0
            )
            self.is_touch_down = False

            # Calculate movement distance to distinguish scroll from click
            movement_distance = 0
            if self.touch_start_pos and touch.pos:
                dx = touch.pos[0] - self.touch_start_pos[0]
                dy = touch.pos[1] - self.touch_start_pos[1]
                movement_distance = (dx * dx + dy * dy) ** 0.5

            # Debug logging for movement analysis
            logger.debug(
                f"[TOUCH UP] pos={touch.pos}, duration={touch_duration:.3f}s, movement={movement_distance:.1f}px, threshold={self.movement_threshold:.1f}px"
            )

            # If movement exceeds threshold, treat as scroll/pan gesture, not a click
            if movement_distance > self.movement_threshold:
                logger.debug(
                    f"[TOUCH] Ignored as scroll gesture - movement {movement_distance:.1f}px > threshold {self.movement_threshold:.1f}px"
                )
                self.touch_start_pos = None
                return True

            # If duration is too short, treat as trackpad scroll, not a real click
            if touch_duration < self.min_click_duration and movement_distance == 0:
                logger.debug(
                    f"[TOUCH] Ignored as trackpad scroll - duration {touch_duration:.3f}s < min {self.min_click_duration:.3f}s with zero movement"
                )
                self.touch_start_pos = None
                return True

            if self.long_press_event:
                self.long_press_event.cancel()
                self.long_press_event = None

            current_time = time.time()
            if touch_duration < 0.8:
                logger.debug(
                    f"[TOUCH] Processing as click - duration {touch_duration:.3f}s < 0.8s"
                )
                time_since_last_click = current_time - self.last_click_time
                if time_since_last_click < self.double_click_threshold:
                    logger.debug(
                        f"[TOUCH] Double click detected - time since last {time_since_last_click:.3f}s < threshold {self.double_click_threshold:.3f}s"
                    )
                    if self.pending_single_click:
                        self.pending_single_click.cancel()
                        self.pending_single_click = None
                    self.show_detailed_playlist_window()
                    self.last_click_time = 0
                    return True

                self.last_click_time = current_time
                if self.pending_single_click:
                    self.pending_single_click.cancel()

                if not self.tooltip_popup:
                    self.pending_single_click = Clock.schedule_once(
                        self.handle_delayed_single_click,
                        self.double_click_threshold + 0.05,
                    )
            elif self.tooltip_popup:
                self.hide_tooltip()

            # Reset touch start position for next touch
            self.touch_start_pos = None
            return True
        except Exception as exc:
            logger.warning("Error handling touch up: %s", exc)
            self.touch_start_pos = None
            return False

    def handle_delayed_single_click(self, _dt):
        try:
            self.pending_single_click = None
            if not self.tooltip_popup:
                self.checkbox.active = not self.checkbox.active
        except Exception as exc:
            logger.warning("Error in delayed single click handler: %s", exc)

    def create_info_label(
        self,
        text,
        font_size=dp(14),
        color=(0.85, 0.85, 0.85, 1),
        height=UIConstants.STANDARD_SPACING,
    ):
        return Label(
            text=text,
            font_size=font_size,
            color=color,
            text_size=(UIConstants.POPUP_WIDTH, None),
            halign="left",
            valign="top",
            size_hint_y=None,
            height=height,
        )

    def create_technical_details_widgets(self, owner_id, playlist_id, snapshot_id):
        tech_widgets = []

        if owner_id != "Unknown" or playlist_id or snapshot_id != "Unknown":
            tech_header = self.create_info_label(
                "Technical Details:",
                font_size=dp(14),
                color=(0.7, 0.7, 0.7, 1),
                height=UIConstants.LARGE_SPACING,
            )
            tech_header.bold = True
            tech_widgets.append(tech_header)

            if owner_id != "Unknown":
                tech_widgets.append(
                    self.create_info_label(
                        f"Owner ID: {owner_id}",
                        font_size=UIConstants.TECH_DETAILS_FONT,
                        color=(0.6, 0.6, 0.6, 1),
                        height=UIConstants.STANDARD_SPACING,
                    )
                )

            if playlist_id:
                tech_widgets.append(
                    self.create_info_label(
                        f"Playlist ID: {playlist_id}",
                        font_size=UIConstants.TECH_DETAILS_FONT,
                        color=(0.6, 0.6, 0.6, 1),
                        height=UIConstants.STANDARD_SPACING,
                    )
                )

            if snapshot_id != "Unknown":
                display_snapshot = snapshot_id[:20] + (
                    "..." if len(snapshot_id) > 20 else ""
                )
                tech_widgets.append(
                    self.create_info_label(
                        f"Version: {display_snapshot}",
                        font_size=UIConstants.TECH_DETAILS_FONT,
                        color=(0.6, 0.6, 0.6, 1),
                        height=UIConstants.STANDARD_SPACING,
                    )
                )

        return tech_widgets

    def is_visible_in_window(self):
        try:
            card_window_pos = self.to_window(0, 0)
            if not card_window_pos:
                return False

            card_x, card_y = card_window_pos
            card_width, card_height = self.size
            card_right = card_x + card_width
            card_top = card_y + card_height

            return (
                card_right > 0
                and card_x < Window.width
                and card_top > 0
                and card_y < Window.height
            )

        except Exception as exc:
            logger.warning("Error checking visibility for card: %s", exc)
            return False

    def get_window_bounds(self):
        try:
            card_window_pos = self.to_window(0, 0)
            if not card_window_pos:
                return None

            card_x, card_y = card_window_pos
            card_width, card_height = self.size

            return {
                "x": card_x,
                "y": card_y,
                "width": card_width,
                "height": card_height,
                "right": card_x + card_width,
                "top": card_y + card_height,
            }

        except Exception as exc:
            logger.warning("Error getting window bounds: %s", exc)
            return None

    def _add_show_tracks_button(
        self, info_layout: BoxLayout, playlist_info: Dict[str, Any]
    ) -> None:
        try:
            for widget in self.master_content_container.children:
                if getattr(widget, "text", "") == playlist_info["playlist_name"]:
                    title_container = BoxLayout(
                        orientation="horizontal",
                        size_hint_y=None,
                        height=dp(40),
                        spacing=dp(10),
                    )
                    self.master_content_container.remove_widget(widget)

                    title_label = Label(
                        text=playlist_info["playlist_name"],
                        font_size=dp(24),
                        bold=True,
                        color=(1, 1, 1, 1),
                        halign="left",
                        valign="center",
                        size_hint_x=0.75,
                    )
                    title_container.add_widget(title_label)

                    show_tracks_btn = Button(
                        text="Show Tracks",
                        size_hint_x=0.25,
                        font_size=dp(14),
                        background_color=[0.3, 0.6, 0.9, 1],
                    )
                    show_tracks_btn.bind(on_press=lambda _: self.show_tracks_window())
                    title_container.add_widget(show_tracks_btn)

                    self.master_content_container.add_widget(
                        title_container,
                        index=len(self.master_content_container.children),
                    )
                    break
        except Exception as exc:
            logger.error("Error adding Show Tracks button: %s", exc)

    def show_tracks_window(self) -> None:
        try:
            TracksWindow(self.playlist_data).open()
        except Exception as exc:
            logger.error("Error opening tracks window: %s", exc)

    # ------------------------------------------------------------------
    # Legacy helpers preserved for parity
    # ------------------------------------------------------------------
    def update_loading_message(self, loading_label: Label, message: str) -> None:
        try:
            loading_label.text = message
            lowered = message.lower()
            if "error" in lowered or "failed" in lowered:
                loading_label.color = (0.8, 0.4, 0.4, 1)
            elif "reccobeats" in lowered:
                loading_label.color = (0.2, 0.8, 0.2, 1)
            else:
                loading_label.color = (0.7, 0.7, 0.7, 1)
        except Exception as exc:
            logger.warning("Error updating loading message: %s", exc)

    def update_spotify_analysis_cached(
        self,
        loading_label: Label,
        info_layout: BoxLayout,
        spotify_analysis: Dict[str, Any],
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> None:
        try:
            if analysis_task and analysis_task.is_cancelled():
                return

            cached_data = get_cached_playlist_analysis(playlist_id)
            reccobeats_data = cached_data.get("reccobeats") if cached_data else None
            has_cached_reccobeats = bool(
                reccobeats_data
                and isinstance(reccobeats_data, dict)
                and reccobeats_data
                and any(
                    key in reccobeats_data
                    for key in [
                        "mood_prediction",
                        "audio_features",
                        "musical_characteristics",
                        "mood_analysis",
                    ]
                )
            )

            logger.info(
                "ReccoBeats analysis status for playlist %s: has_cached=%s",
                playlist_id,
                has_cached_reccobeats,
            )
            if reccobeats_data:
                logger.debug("ReccoBeats data keys: %s", list(reccobeats_data.keys()))

            track_ids = spotify_analysis.get("track_ids", [])
            self.update_spotify_analysis(
                loading_label,
                info_layout,
                spotify_analysis,
                owner_id,
                playlist_id,
                snapshot_id,
                track_ids,
                analysis_task,
                skip_reccobeats=has_cached_reccobeats,
            )

            if has_cached_reccobeats:
                Clock.schedule_once(
                    lambda _dt: self.update_reccobeats_analysis_from_cache(
                        reccobeats_data, info_layout, owner_id, playlist_id, snapshot_id
                    ),
                    0.8,
                )
        except Exception as exc:
            logger.error("Error updating cached Spotify analysis: %s", exc)

    # ------------------------------------------------------------------
    # Playlist details popup
    # ------------------------------------------------------------------
    def show_detailed_playlist_window(self) -> None:
        try:
            # Check if popup exists and is still open
            if getattr(self, "detailed_popup", None):
                try:
                    # Check if the popup is still attached to a window (not dismissed)
                    if self.detailed_popup.parent:
                        return  # Popup is still open, don't create another one
                    else:
                        # Popup exists but is dismissed, clean it up
                        self.detailed_popup = None
                except Exception:
                    # Error checking popup state, clean it up and continue
                    self.detailed_popup = None

            playlist_id = self.playlist_data.get("id")
            if not playlist_id:
                return

            self.cancel_existing_analysis(playlist_id)
            playlist_info = self._extract_playlist_info()
            self.playlist_info = playlist_info  # Store as instance variable
            cached_data = get_cached_playlist_analysis(playlist_id)

            popup_content = self._create_popup_content_with_cache_support(
                playlist_info, cached_data
            )
            self.detailed_popup = Popup(
                title="Playlist Analysis",
                title_size=dp(20),
                title_color=(1, 1, 1, 1),
                size_hint=(0.85, 0.8),
                background_color=(0.15, 0.15, 0.15, 0.95),
                auto_dismiss=True,
                overlay_color=(0, 0, 0, 0.5),
                content=popup_content,
            )
            self.detailed_popup.bind(
                on_dismiss=lambda *_: self.cleanup_on_popup_close(playlist_id)
            )
            self.detailed_popup.open()

            self.start_analysis_with_cached_data(playlist_info, cached_data)
        except Exception as exc:
            logger.error("Error showing detailed playlist window: %s", exc)
            # Ensure cleanup on error
            self.detailed_popup = None

    def _extract_playlist_info(self) -> Dict[str, Any]:
        return {
            "playlist_name": str(self.playlist_data.get("name", "Untitled Playlist")),
            "owner_name": self.playlist_data.get("owner", {}).get(
                "display_name", "Unknown"
            ),
            "owner_id": self.playlist_data.get("owner", {}).get("id", "Unknown"),
            "owner_type": self.playlist_data.get("owner", {}).get("type", "Unknown"),
            "owner_url": self.playlist_data.get("owner", {})
            .get("external_urls", {})
            .get("spotify", ""),
            "playlist_description": self.playlist_data.get("description", ""),
            "track_count": self.playlist_data.get("tracks", {}).get("total", 0),
            "playlist_id": self.playlist_data.get("id", ""),
            "spotify_url": self.playlist_data.get("external_urls", {}).get(
                "spotify", ""
            ),
            "followers_count": self.playlist_data.get("followers", {}).get("total")
            if self.playlist_data.get("followers")
            else None,
            "snapshot_id": self.playlist_data.get("snapshot_id", "Unknown"),
            "is_public": self.playlist_data.get("public", False),
            "is_collaborative": self.playlist_data.get("collaborative", False),
        }

    def _create_popup_content_with_cache_support(self, playlist_info, cached_data):
        return self._create_popup_content_with_immediate_details(playlist_info)

    def _create_popup_content_with_immediate_details(self, playlist_info):
        scroll_content = BoxLayout(
            orientation="horizontal",
            padding=[dp(10), dp(20), dp(10), dp(20)],
            spacing=dp(2),
            size_hint_y=None,  # Disable vertical size_hint for ScrollView
        )

        # Bind height to minimum_height for proper scrolling
        scroll_content.bind(minimum_height=scroll_content.setter("height"))

        scroll_view = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_wheel_distance=dp(30),
            size_hint=(1, 1),
        )
        scroll_view.add_widget(scroll_content)

        # Create info layout and image container
        info_layout = self._create_basic_info_section_only(playlist_info)
        image_container = playlist_info["image_container"] = (
            self._create_image_section_with_immediate_tech(playlist_info)
        )
        self.image_container = (
            image_container  # Store as instance variable for cache refresh
        )

        # Add both containers to scroll content
        scroll_content.add_widget(image_container)
        scroll_content.add_widget(info_layout)

        main_container = BoxLayout(orientation="vertical", padding=dp(5), spacing=dp(5))
        main_container.add_widget(scroll_view)

        close_container = RelativeLayout(size_hint_y=None, height=dp(50))
        close_button = Button(
            text="Close",
            size_hint=(None, None),
            size=(dp(100), dp(40)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            font_size=dp(16),
            background_color=[0.6, 0.6, 0.6, 1],
        )
        close_button.bind(on_press=lambda *_: self.close_detailed_window())
        close_container.add_widget(close_button)
        main_container.add_widget(close_container)

        playlist_info["info_layout"] = info_layout
        playlist_info["image_container"] = image_container

        return main_container

    def _create_image_section_with_immediate_tech(self, playlist_info):
        image_container = BoxLayout(
            orientation="vertical", size_hint_x=None, width=dp(220)
        )
        image_container.bind(minimum_height=image_container.setter("height"))

        image_url = self._get_playlist_image_url()
        if image_url:
            playlist_image = CachedAsyncImage(
                source=image_url,
                size_hint=(None, None),
                size=(dp(180), dp(180)),
                fit_mode="cover",
            )

            def on_image_load(_instance, _value):
                try:
                    Clock.schedule_once(lambda _dt: image_container.do_layout(), 0.1)
                    if getattr(self, "detailed_popup", None):
                        scroll_content = self.detailed_popup.content.children[
                            1
                        ].children[0]
                        Clock.schedule_once(lambda _dt: scroll_content.do_layout(), 0.1)
                except Exception as exc:
                    logger.warning("Error updating layout after image load: %s", exc)

            playlist_image.bind(texture=on_image_load)
        else:
            playlist_image = Label(
                text="No Image",
                size_hint=(None, None),
                size=(dp(180), dp(180)),
                color=(0.6, 0.6, 0.6, 1),
            )
            with playlist_image.canvas.before:
                Color(0.3, 0.3, 0.3, 1)
                Rectangle(size=(dp(180), dp(180)), pos=playlist_image.pos)
            playlist_image.bind(
                pos=lambda inst, value: setattr(
                    playlist_image.canvas.before.children[-1], "pos", value
                )
            )

        image_container.add_widget(playlist_image)

        if image_url:
            try:
                images = self.playlist_data.get("images", [])
                image_dimensions = ""
                for img in images:
                    if img.get("url") == image_url:
                        width = img.get("width")
                        height = img.get("height")
                        if width and height:
                            image_dimensions = f"{width}×{height}"
                        break

                if image_dimensions:
                    available_sizes = []
                    for img in images:
                        w = img.get("width")
                        h = img.get("height")
                        if w and h:
                            available_sizes.append(f"{w}×{h}")
                    if available_sizes and len(available_sizes) > 1:
                        image_dimensions += (
                            f" (Available: {', '.join(available_sizes)})"
                        )

                    image_info = Label(
                        text=f"Image: {image_dimensions}",
                        font_size=dp(10),
                        color=(0.6, 0.6, 0.6, 1),
                        size_hint=(None, None),
                        size=(dp(180), dp(30)),
                        text_size=(dp(180), None),
                        halign="left",
                        valign="center",
                    )
                    image_container.add_widget(image_info)
            except Exception as exc:
                logger.warning("Error processing image info: %s", exc)

        image_container.add_widget(
            Widget(size_hint_y=None, height=dp(15))
        )  # Reverted to original spacing
        tech_widgets = self.create_technical_details_widgets_for_left_side(
            playlist_info["owner_id"],
            playlist_info["playlist_id"],
            playlist_info["snapshot_id"],
        )
        for widget in tech_widgets:
            image_container.add_widget(widget)

        image_container.add_widget(Widget())
        # Schedule multiple layout updates to ensure proper positioning
        Clock.schedule_once(lambda _dt: image_container.do_layout(), 0)
        Clock.schedule_once(lambda _dt: image_container.do_layout(), 0.1)
        Clock.schedule_once(lambda _dt: image_container.do_layout(), 0.2)
        Clock.schedule_once(
            lambda _dt: image_container.do_layout(), 0.3
        )  # Extra refresh
        return image_container

    def _create_basic_info_section_only(self, playlist_info):
        info_layout = BoxLayout(
            orientation="vertical",
            spacing=dp(5),
            size_hint_y=None,
            padding=[0, 0, dp(5), 0],
        )
        info_layout.bind(minimum_height=info_layout.setter("height"))

        self.master_content_container = BoxLayout(
            orientation="vertical", spacing=dp(5), size_hint_y=None
        )
        self.master_content_container.bind(
            minimum_height=self.master_content_container.setter("height")
        )

        def update_text_sizes(layout, size):
            try:
                actual_width = max(dp(280), size[0] - dp(40))
                for widget in layout.children:
                    if (
                        hasattr(widget, "text_size")
                        and widget.text_size
                        and widget.text_size[0] != actual_width
                    ):
                        widget.text_size = (actual_width, widget.text_size[1])
            except Exception as exc:
                logger.warning("Error updating text sizes: %s", exc)

        self.master_content_container.bind(size=update_text_sizes)
        self._add_basic_info_widgets(self.master_content_container, playlist_info)

        # Add Show Tracks button to the title
        self._add_show_tracks_button(self.master_content_container, playlist_info)

        # Add loading label (progress will be shown in separate window for large playlists)
        loading_label = self.create_info_label(
            "Loading playlist analysis...",
            color=(0.7, 0.7, 0.7, 1),
            height=dp(14),
        )
        self.master_content_container.add_widget(loading_label)
        playlist_info["loading_label"] = loading_label

        info_layout.add_widget(self.master_content_container)

        # Ensure the layout updates its height immediately
        def update_layout_height(delta_time):
            info_layout.height = info_layout.minimum_height

        Clock.schedule_once(update_layout_height, 0.1)

        return info_layout

    def _add_basic_info_widgets(self, layout, playlist_info):
        title_label = Label(
            text=playlist_info["playlist_name"],
            font_size=dp(24),
            bold=True,
            color=(1, 1, 1, 1),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(40),
        )
        layout.add_widget(title_label)

        owner_info = f"Created by: {playlist_info['owner_name']}"
        if playlist_info["owner_type"] not in ["Unknown", "user"]:
            owner_info += f" ({playlist_info['owner_type'].title()})"
        layout.add_widget(
            self.create_info_label(owner_info, font_size=dp(16), height=dp(25))
        )

        if playlist_info["spotify_url"]:
            layout.add_widget(
                self.create_info_label(
                    f"Playlist URL: {playlist_info['spotify_url']}",
                    font_size=dp(12),
                    color=(0.6, 0.8, 1, 1),
                    height=dp(20),
                )
            )
        if playlist_info["owner_url"]:
            layout.add_widget(
                self.create_info_label(
                    f"Owner URL: {playlist_info['owner_url']}",
                    font_size=dp(12),
                    color=(0.6, 0.8, 1, 1),
                    height=dp(20),
                )
            )

        layout.add_widget(Widget(size_hint_y=None, height=dp(4)))

        description = re.sub(
            r"<[^>]+>", "", playlist_info["playlist_description"] or ""
        ).strip()
        if description:
            desc_header = Label(
                text="Description:",
                font_size=dp(18),
                color=(0.9, 0.9, 0.9, 1),
                bold=True,
                size_hint_y=None,
                height=dp(12),
            )
            layout.add_widget(desc_header)

            desc_height = max(
                dp(20), min(dp(100), len(description) // 60 * dp(14) + dp(3))
            )
            desc_label = Label(
                text=description,
                font_size=dp(13),
                color=(0.8, 0.8, 0.8, 1),
                text_size=(UIConstants.POPUP_WIDTH, None),
                halign="left",
                valign="top",
                size_hint_y=None,
                height=desc_height,
            )
            layout.add_widget(desc_label)
            layout.add_widget(Widget(size_hint_y=None, height=dp(4)))

        playlist_type = ["Public" if playlist_info["is_public"] else "Private"]
        if playlist_info["is_collaborative"]:
            playlist_type.append("Collaborative")
        layout.add_widget(
            self.create_info_label(
                f"Type: {', '.join(playlist_type)}", font_size=dp(16), height=dp(22)
            )
        )
        layout.add_widget(Widget(size_hint_y=None, height=dp(4)))

        stats_text = f"Tracks: {playlist_info['track_count']:,}"
        followers = playlist_info["followers_count"]
        if followers:
            stats_text += f" • Followers: {followers:,}"
        self.stats_widget = self.create_info_label(
            stats_text, font_size=dp(16), height=dp(12)
        )
        layout.add_widget(self.stats_widget)

    def create_technical_details_widgets_for_left_side(
        self, owner_id, playlist_id, snapshot_id
    ):
        widgets: List[Widget] = []
        if owner_id != "Unknown" or playlist_id or snapshot_id != "Unknown":
            widgets.append(
                Label(
                    text="Technical Details:",
                    font_size=dp(14),
                    color=(0.8, 0.8, 0.8, 1),
                    bold=True,
                    size_hint_y=None,
                    height=dp(22),
                    text_size=(dp(215), None),
                    halign="left",
                    valign="center",
                )
            )
            if owner_id != "Unknown":
                widgets.extend(
                    [
                        Label(
                            text="Owner ID:",
                            font_size=dp(12),
                            color=(0.8, 0.8, 0.8, 1),
                            bold=True,
                            size_hint_y=None,
                            height=dp(20),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="center",
                        ),
                        Label(
                            text=owner_id,
                            font_size=dp(11),
                            color=(0.7, 0.7, 0.7, 1),
                            size_hint_y=None,
                            height=dp(20),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="top",
                        ),
                    ]
                )
            if playlist_id:
                display_id = playlist_id
                if len(display_id) > 25:
                    display_id = f"{playlist_id[:25]}...\n...{playlist_id[-25:]}"
                widgets.extend(
                    [
                        Label(
                            text="Playlist ID:",
                            font_size=dp(12),
                            color=(0.8, 0.8, 0.8, 1),
                            bold=True,
                            size_hint_y=None,
                            height=dp(20),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="center",
                        ),
                        Label(
                            text=display_id,
                            font_size=dp(11),
                            color=(0.7, 0.7, 0.7, 1),
                            size_hint_y=None,
                            height=dp(20),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="top",
                        ),
                    ]
                )
            if snapshot_id != "Unknown":
                display_snapshot = snapshot_id
                if len(display_snapshot) > 25:
                    display_snapshot = f"{snapshot_id[:25]}...\n...{snapshot_id[-25:]}"
                widgets.extend(
                    [
                        Label(
                            text="Version:",
                            font_size=dp(12),
                            color=(0.8, 0.8, 0.8, 1),
                            bold=True,
                            size_hint_y=None,
                            height=dp(20),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="center",
                        ),
                        Label(
                            text=display_snapshot,
                            font_size=dp(11),
                            color=(0.7, 0.7, 0.7, 1),
                            size_hint_y=None,
                            height=dp(20),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="top",
                        ),
                    ]
                )

        # Add cache statistics right after Technical Details
        cache_widgets = self.create_cache_statistics_widgets(playlist_id)
        widgets.extend(cache_widgets)

        return widgets

    def create_cache_statistics_widgets(self, playlist_id: str) -> List[Widget]:
        """Create cache statistics widgets for the Technical Details section."""
        widgets: List[Widget] = []

        if not playlist_id:
            return widgets

        try:
            # Get user_id for cache lookup
            app = App.get_running_app()
            user_id = getattr(app, "user_id", None)

            if not user_id:
                # Try to get user_id from Spotify API
                token_info = getattr(app, "token_info", None)
                if token_info:
                    sp = create_spotify_client_with_refresh(token_info)
                    if sp:
                        user_id = sp.current_user().get("id")

            if not user_id:
                return widgets

            # Get cached playlist tracks data
            cached_data = persistent_cache.get_cached_playlist_tracks(
                playlist_id, user_id
            )

            if cached_data:
                total_tracks = cached_data.get("total_tracks", 0)
                spotify_cached = cached_data.get("spotify_cached_count", 0)
                reccobeats_cached = cached_data.get("reccobeats_cached_count", 0)
                last_updated = cached_data.get("last_updated", 0)

                # Format last updated time
                import time

                if last_updated > 0:
                    time_diff = time.time() - last_updated
                    if time_diff < 5:
                        last_updated_text = "Just now"
                    elif time_diff < 60:
                        last_updated_text = f"{int(time_diff)} seconds ago"
                    elif time_diff < 3600:
                        last_updated_text = f"{int(time_diff // 60)} minutes ago"
                    elif time_diff < 86400:
                        last_updated_text = f"{int(time_diff // 3600)} hours ago"
                    else:
                        last_updated_text = f"{int(time_diff // 86400)} days ago"
                else:
                    last_updated_text = "Unknown"

                # Add cache status header
                widgets.append(
                    Label(
                        text="Cache Status:",
                        font_size=dp(12),
                        color=(0.8, 0.8, 0.8, 1),
                        bold=True,
                        size_hint_y=None,
                        height=dp(20),
                        text_size=(dp(215), None),
                        halign="left",
                        valign="center",
                    )
                )

                # Add Spotify cache info
                spotify_percentage = (
                    (spotify_cached / total_tracks * 100) if total_tracks > 0 else 0
                )
                widgets.append(
                    Label(
                        text=f"Spotify: {spotify_cached}/{total_tracks} ({spotify_percentage:.0f}%)",
                        font_size=dp(11),
                        color=(0.2, 0.8, 0.2, 1)
                        if spotify_percentage >= 80
                        else (0.8, 0.8, 0.2, 1)
                        if spotify_percentage >= 50
                        else (0.8, 0.4, 0.4, 1),
                        size_hint_y=None,
                        height=dp(18),
                        text_size=(dp(215), None),
                        halign="left",
                        valign="center",
                    )
                )

                # Add ReccoBeats cache info
                reccobeats_percentage = (
                    (reccobeats_cached / total_tracks * 100) if total_tracks > 0 else 0
                )
                widgets.append(
                    Label(
                        text=f"ReccoBeats: {reccobeats_cached}/{total_tracks} ({reccobeats_percentage:.0f}%)",
                        font_size=dp(11),
                        color=(0.2, 0.8, 0.2, 1)
                        if reccobeats_percentage >= 80
                        else (0.8, 0.8, 0.2, 1)
                        if reccobeats_percentage >= 50
                        else (0.8, 0.4, 0.4, 1),
                        size_hint_y=None,
                        height=dp(18),
                        text_size=(dp(215), None),
                        halign="left",
                        valign="center",
                    )
                )

                # Add last updated info
                widgets.append(
                    Label(
                        text=f"Updated: {last_updated_text}",
                        font_size=dp(10),
                        color=(0.6, 0.6, 0.6, 1),
                        size_hint_y=None,
                        height=dp(16),
                        text_size=(dp(215), None),
                        halign="left",
                        valign="center",
                    )
                )
            else:
                # No cache data available - show loading or not available message
                widgets.append(
                    Label(
                        text="Cache Status:",
                        font_size=dp(12),
                        color=(0.8, 0.8, 0.8, 1),
                        bold=True,
                        size_hint_y=None,
                        height=dp(20),
                        text_size=(dp(215), None),
                        halign="left",
                        valign="center",
                    )
                )

                # Check if we're currently loading (cache update in progress)
                is_loading = hasattr(self, "_cache_loading") and self._cache_loading
                if is_loading:
                    widgets.append(
                        Label(
                            text="Loading cache data...",
                            font_size=dp(11),
                            color=(0.8, 0.8, 0.2, 1),
                            size_hint_y=None,
                            height=dp(18),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="center",
                        )
                    )
                else:
                    widgets.append(
                        Label(
                            text="No cache data available\n(Open Details to update)",
                            font_size=dp(11),
                            color=(0.6, 0.6, 0.6, 1),
                            size_hint_y=None,
                            height=dp(36),
                            text_size=(dp(215), None),
                            halign="left",
                            valign="center",
                        )
                    )

        except Exception as exc:
            logger.warning("Error creating cache statistics widgets: %s", exc)

        return widgets

    def refresh_cache_statistics_display(
        self, playlist_id: str, force_refresh: bool = False
    ) -> None:
        """Refresh the cache statistics display in the Details window."""
        try:
            logger.debug(
                "CACHE REFRESH: Starting refresh for playlist %s (force: %s)",
                playlist_id,
                force_refresh,
            )

            if not hasattr(self, "detailed_popup") or not self.detailed_popup:
                logger.debug("CACHE REFRESH: No detailed popup found")
                return

            # Prevent recursive calls that cause infinite loops
            current_time = time.time()
            last_refresh = getattr(self, "_last_cache_refresh", 0)
            is_refreshing = getattr(self, "_is_refreshing", False)

            # Debounce: minimum time between refreshes, and prevent concurrent refreshes
            # Allow more frequent refreshes during lightweight mode for better UI updates
            # Allow immediate refreshes if force_refresh is True (for ReccoBeats updates)
            lightweight_mode = getattr(self, "_lightweight_refresh_mode", False)

            if not force_refresh:
                debounce_time = (
                    0.5 if lightweight_mode else 1.0
                )  # Faster refresh during lightweight mode

                if is_refreshing or (current_time - last_refresh < debounce_time):
                    logger.debug(
                        "CACHE REFRESH: Skipping - debounced (is_refreshing: %s, time_since: %.1fs, lightweight: %s, debounce: %.1fs)",
                        is_refreshing,
                        current_time - last_refresh,
                        lightweight_mode,
                        debounce_time,
                    )
                    return

            # Set refreshing flag to prevent recursive calls
            self._is_refreshing = True
            self._last_cache_refresh = current_time

            # Find the image container and update cache statistics
            image_container = getattr(self, "image_container", None)
            if not image_container:
                logger.debug("CACHE REFRESH: No image container found")
                self._is_refreshing = False
                return

            # Use lightweight mode during intensive processing
            lightweight_mode = getattr(self, "_lightweight_refresh_mode", False)

            # logger.debug("CACHE REFRESH: Found image container with %d widgets (lightweight: %s)", len(image_container.children), lightweight_mode)

            # In lightweight mode, only update existing widgets without full rebuild
            if lightweight_mode:
                self._lightweight_cache_update(image_container, playlist_id)
                self._is_refreshing = False
                return

            # Calculate cache statistics
            app = App.get_running_app()
            user_id = getattr(app, "user_id", None)

            # Try to get user_id from Spotify API if not available
            if not user_id:
                token_info = getattr(app, "token_info", None)
                if token_info:
                    try:
                        sp = create_spotify_client_with_refresh(token_info)
                        if sp:
                            user_data = sp.current_user()
                            user_id = user_data.get("id")
                            logger.debug(
                                "CACHE REFRESH: Retrieved user_id from Spotify API: %s",
                                user_id,
                            )
                    except Exception as exc:
                        logger.debug(
                            "CACHE REFRESH: Error getting user_id from Spotify API: %s",
                            exc,
                        )

            if not user_id:
                logger.debug("CACHE REFRESH: No user_id found")
                self._is_refreshing = False
                return

            cached_data = persistent_cache.get_cached_playlist_tracks(
                playlist_id, user_id
            )
            if not cached_data:
                logger.debug("CACHE REFRESH: No cached data found")
                self._is_refreshing = False
                return

            total_tracks = cached_data.get("total_tracks", 0)
            spotify_cached_count = cached_data.get("spotify_cached_count", 0)
            reccobeats_cached_count = cached_data.get("reccobeats_cached_count", 0)

            # Update existing cache widgets in place (like lightweight mode)
            widgets_updated = 0

            # Update existing cache widgets (same logic as lightweight update)
            for widget in image_container.children:
                if isinstance(widget, Label):
                    if widget.text.startswith("Spotify:"):
                        spotify_percentage = (
                            int((spotify_cached_count / total_tracks * 100))
                            if total_tracks > 0
                            else 0
                        )
                        new_text = f"Spotify: {spotify_cached_count}/{total_tracks} ({spotify_percentage}%)"
                        if widget.text != new_text:
                            widget.text = new_text
                            # Update color coding based on percentage
                            if spotify_percentage >= 80:
                                widget.color = (0.2, 0.8, 0.2, 1)  # Green
                            elif spotify_percentage >= 50:
                                widget.color = (0.8, 0.8, 0.2, 1)  # Yellow
                            else:
                                widget.color = (0.8, 0.4, 0.4, 1)  # Red
                            widgets_updated += 1
                            logger.debug(
                                "Updated Spotify to %s (color: %s)",
                                new_text,
                                widget.color,
                            )
                    elif widget.text.startswith("ReccoBeats:"):
                        reccobeats_percentage = (
                            int((reccobeats_cached_count / total_tracks * 100))
                            if total_tracks > 0
                            else 0
                        )
                        new_text = f"ReccoBeats: {reccobeats_cached_count}/{total_tracks} ({reccobeats_percentage}%)"
                        if widget.text != new_text:
                            widget.text = new_text
                            # Update color coding based on percentage
                            if reccobeats_percentage >= 80:
                                widget.color = (0.2, 0.8, 0.2, 1)  # Green
                            elif reccobeats_percentage >= 50:
                                widget.color = (0.8, 0.8, 0.2, 1)  # Yellow
                            else:
                                widget.color = (0.8, 0.4, 0.4, 1)  # Red
                            widgets_updated += 1
                            logger.debug(
                                "Updated ReccoBeats to %s (color: %s)",
                                new_text,
                                widget.color,
                            )
                    elif widget.text.startswith("Updated:"):
                        # Calculate last updated time
                        cached_data = persistent_cache.get_cached_playlist_tracks(
                            playlist_id, user_id
                        )
                        last_updated = (
                            cached_data.get("last_updated") if cached_data else None
                        )
                        if last_updated:
                            time_diff = time.time() - last_updated
                            if time_diff < 60:
                                last_updated_text = "Just now"
                            elif time_diff < 3600:
                                last_updated_text = (
                                    f"{int(time_diff // 60)} minutes ago"
                                )
                            elif time_diff < 86400:
                                last_updated_text = (
                                    f"{int(time_diff // 3600)} hours ago"
                                )
                            else:
                                last_updated_text = (
                                    f"{int(time_diff // 86400)} days ago"
                                )
                        else:
                            last_updated_text = "Unknown"

                        new_text = f"Updated: {last_updated_text}"
                        if widget.text != new_text:
                            widget.text = new_text
                            widgets_updated += 1
                            logger.debug("Updated 'Updated' field to %s", new_text)

            logger.debug(
                "Cache refresh completed - updated %d widgets", widgets_updated
            )

            # Force layout update
            image_container.do_layout()
            if hasattr(self, "detailed_popup") and self.detailed_popup:
                try:
                    scroll_content = self.detailed_popup.content.children[1].children[0]
                    scroll_content.do_layout()
                except Exception as exc:
                    logger.debug("Error updating scroll layout: %s", exc)

            logger.debug(
                "Successfully refreshed cache statistics display for playlist %s",
                playlist_id,
            )

        except Exception as exc:
            logger.warning("Error refreshing cache statistics display: %s", exc)
        finally:
            # Always clear the refreshing flag to prevent getting stuck
            self._is_refreshing = False

    def _lightweight_cache_update(self, image_container, playlist_id: str) -> None:
        """Lightweight cache update that minimizes UI operations during intensive processing."""
        try:
            logger.debug(
                "LIGHTWEIGHT UPDATE: Starting lightweight update for playlist %s",
                playlist_id,
            )

            # Get user_id for cache lookup (same logic as create_cache_statistics_widgets)
            app = App.get_running_app()
            user_id = getattr(app, "user_id", None)

            if not user_id:
                # Try to get user_id from Spotify API
                token_info = getattr(app, "token_info", None)
                if token_info:
                    sp = create_spotify_client_with_refresh(token_info)
                    if sp:
                        user_id = sp.current_user().get("id")

            if not user_id:
                logger.debug("LIGHTWEIGHT UPDATE: No user_id found")
                return

            # Get cached playlist tracks data
            cached_data = persistent_cache.get_cached_playlist_tracks(
                playlist_id, user_id
            )
            if not cached_data:
                logger.debug("LIGHTWEIGHT UPDATE: No cached data found")
                return

            total_tracks = cached_data.get("total_tracks", 0)

            # Calculate real-time cache status instead of relying on potentially stale snapshot
            from ..caching.track_cache import (
                get_cached_spotify_track,
                get_cached_reccobeats_features,
            )

            # Get actual track list and count cached items in real-time
            tracks_data = cached_data.get("tracks", [])
            if not tracks_data:
                logger.debug("LIGHTWEIGHT UPDATE: No tracks data found")
                return

            # Count actual cached tracks in real-time
            spotify_cached_count = 0
            reccobeats_cached_count = 0

            for track_info in tracks_data:
                track_id = track_info.get("id")
                if track_id:
                    # Check if Spotify track is actually cached
                    if get_cached_spotify_track(track_id):
                        spotify_cached_count += 1

                    # Check if ReccoBeats features are actually cached
                    if get_cached_reccobeats_features(track_id):
                        reccobeats_cached_count += 1

            last_updated = cached_data.get("last_updated", 0)

            logger.debug(
                "LIGHTWEIGHT UPDATE: Real-time cache stats - Spotify: %d/%d, ReccoBeats: %d/%d (last_updated: %d)",
                spotify_cached_count,
                total_tracks,
                reccobeats_cached_count,
                total_tracks,
                last_updated,
            )

            # Log the comparison with cached snapshot for debugging
            snapshot_spotify = cached_data.get("spotify_cached_count", 0)
            snapshot_reccobeats = cached_data.get("reccobeats_cached_count", 0)
            logger.debug(
                "LIGHTWEIGHT UPDATE: Snapshot vs Real-time - Spotify: %d→%d, ReccoBeats: %d→%d",
                snapshot_spotify,
                spotify_cached_count,
                snapshot_reccobeats,
                reccobeats_cached_count,
            )

            # Alert if there's a significant discrepancy
            if (
                abs(spotify_cached_count - snapshot_spotify) > 5
                or abs(reccobeats_cached_count - snapshot_reccobeats) > 5
            ):
                logger.warning(
                    "LIGHTWEIGHT UPDATE: Cache snapshot is stale! Using real-time counts instead."
                )

            # Format last updated time (use current time if cache is actively being updated)
            import time

            current_time = time.time()

            # If we're in lightweight mode and cache is being actively updated, show "Just now" or recent time
            if getattr(self, "_lightweight_refresh_mode", False) and (
                spotify_cached_count > snapshot_spotify
                or reccobeats_cached_count > snapshot_reccobeats
            ):
                # Cache is being actively updated right now
                last_updated_text = "Just now"
                logger.debug("LIGHTWEIGHT UPDATE: Using 'Just now' for active updates")
            elif last_updated > 0:
                time_diff = current_time - last_updated
                if time_diff < 5:
                    last_updated_text = "Just now"
                elif time_diff < 60:
                    last_updated_text = f"{int(time_diff)} seconds ago"
                elif time_diff < 3600:
                    last_updated_text = f"{int(time_diff // 60)} minutes ago"
                elif time_diff < 86400:
                    last_updated_text = f"{int(time_diff // 3600)} hours ago"
                else:
                    last_updated_text = f"{int(time_diff // 86400)} days ago"
            else:
                last_updated_text = "Unknown"

            # Find existing cache widgets and update their text in place
            widgets_updated = 0
            no_cache_widget_found = False

            # First pass: check for existing cache widgets and "No cache data available" widget
            for widget in image_container.children:
                if isinstance(widget, Label):
                    if widget.text.startswith("Spotify:"):
                        spotify_percentage = (
                            int((spotify_cached_count / total_tracks * 100))
                            if total_tracks > 0
                            else 0
                        )
                        new_text = f"Spotify: {spotify_cached_count}/{total_tracks} ({spotify_percentage}%)"
                        if widget.text != new_text:
                            widget.text = new_text
                            # Update color coding based on percentage
                            if spotify_percentage >= 80:
                                widget.color = (0.2, 0.8, 0.2, 1)  # Green
                            elif spotify_percentage >= 50:
                                widget.color = (0.8, 0.8, 0.2, 1)  # Yellow
                            else:
                                widget.color = (0.8, 0.4, 0.4, 1)  # Red
                            widgets_updated += 1
                            logger.debug(
                                "LIGHTWEIGHT UPDATE: Updated Spotify to %s (color: %s)",
                                new_text,
                                widget.color,
                            )
                    elif widget.text.startswith("ReccoBeats:"):
                        reccobeats_percentage = (
                            int((reccobeats_cached_count / total_tracks * 100))
                            if total_tracks > 0
                            else 0
                        )
                        new_text = f"ReccoBeats: {reccobeats_cached_count}/{total_tracks} ({reccobeats_percentage}%)"
                        if widget.text != new_text:
                            widget.text = new_text
                            # Update color coding based on percentage
                            if reccobeats_percentage >= 80:
                                widget.color = (0.2, 0.8, 0.2, 1)  # Green
                            elif reccobeats_percentage >= 50:
                                widget.color = (0.8, 0.8, 0.2, 1)  # Yellow
                            else:
                                widget.color = (0.8, 0.4, 0.4, 1)  # Red
                            widgets_updated += 1
                            logger.debug(
                                "LIGHTWEIGHT UPDATE: Updated ReccoBeats to %s (color: %s)",
                                new_text,
                                widget.color,
                            )
                    elif widget.text.startswith("Updated:"):
                        new_text = f"Updated: {last_updated_text}"
                        if widget.text != new_text:
                            widget.text = new_text
                            widgets_updated += 1
                            logger.debug(
                                "LIGHTWEIGHT UPDATE: Updated 'Updated' field to %s",
                                new_text,
                            )
                    elif "No cache data available" in widget.text:
                        no_cache_widget_found = True
                        logger.debug(
                            "LIGHTWEIGHT UPDATE: Found 'No cache data available' widget"
                        )

            # If we found "No cache data available" widget and now have cache data, replace it
            if no_cache_widget_found and (
                spotify_cached_count > 0 or reccobeats_cached_count > 0
            ):
                logger.debug(
                    "LIGHTWEIGHT UPDATE: Replacing 'No cache data' widget with actual cache statistics"
                )

                # Find and remove both the "Cache Status:" header and "No cache data available" widget
                widgets_to_remove = []
                for widget in list(image_container.children):
                    if isinstance(widget, Label) and (
                        "No cache data available" in widget.text
                        or (
                            widget.text == "Cache Status:" and no_cache_widget_found
                        )  # Only remove header if it's the no-cache header
                    ):
                        widgets_to_remove.append(widget)

                for widget in widgets_to_remove:
                    image_container.remove_widget(widget)
                    logger.debug(
                        "LIGHTWEIGHT UPDATE: Removed widget: %s", widget.text[:30]
                    )

                # Create proper cache widgets
                new_cache_widgets = self.create_cache_statistics_widgets(playlist_id)
                logger.debug(
                    "LIGHTWEIGHT UPDATE: Adding %d new cache widgets",
                    len(new_cache_widgets),
                )

                # Add widgets in normal order (not reversed) to fix the order issue
                for widget in new_cache_widgets:
                    image_container.add_widget(widget)
                    widgets_updated += 1
                    logger.debug(
                        "LIGHTWEIGHT UPDATE: Added cache widget: %s", widget.text[:30]
                    )

                # Refresh layout to ensure proper positioning after cache updates
                Clock.schedule_once(lambda _dt: image_container.do_layout(), 0.1)

            logger.debug(
                "LIGHTWEIGHT UPDATE: Completed - updated %d widgets", widgets_updated
            )

        except Exception as exc:
            logger.debug("Error in lightweight cache update: %s", exc)

    # ------------------------------------------------------------------
    # Analysis + caching coordination (subset)
    # ------------------------------------------------------------------
    def start_analysis_with_cached_data(
        self, playlist_info: Dict[str, Any], cached_data: Optional[Dict[str, Any]]
    ) -> None:
        track_count = playlist_info.get("track_count", 0)

        # For large playlists, show progress and load in background
        if track_count > 1000:
            # Create and open progress window on main thread first
            playlist_name = playlist_info.get("playlist_name", "Unknown Playlist")
            progress_window = ProgressWindow(playlist_name, track_count)
            progress_window.open()
            playlist_info["progress_window"] = progress_window

            # Start background track loading with progress
            threading.Thread(
                target=self._load_tracks_with_progress,
                args=(playlist_info, cached_data, progress_window),
                daemon=True,
            ).start()
        else:
            # For smaller playlists, use the original approach
            self._load_tracks_immediately(playlist_info, cached_data)

    def _load_tracks_immediately(
        self, playlist_info: Dict[str, Any], cached_data: Optional[Dict[str, Any]]
    ) -> None:
        """Load tracks immediately for smaller playlists (original behavior)."""
        playlist_id = playlist_info["playlist_id"]

        # Update cache when Details window opens
        try:
            app = App.get_running_app()
            token_info = getattr(app, "token_info", None)
            if token_info:
                sp = create_spotify_client_with_refresh(token_info)
                if sp:
                    user_id = getattr(app, "user_id", None) or sp.current_user().get(
                        "id"
                    )
                    if user_id:
                        # Set loading state
                        self._cache_loading = True

                        # Update playlist track cache immediately
                        tracks_data = get_or_update_playlist_tracks(
                            sp, playlist_id, user_id
                        )
                        logger.info(
                            "Updated cache for playlist %s (Details window opened) - %d tracks, %d Spotify cached, %d ReccoBeats cached",
                            playlist_info.get("playlist_name", "Unknown"),
                            tracks_data["total_tracks"],
                            tracks_data["spotify_cached_count"],
                            tracks_data["reccobeats_cached_count"],
                        )

                        # Clear loading state and schedule cache display refresh
                        self._cache_loading = False

                        # Refresh immediately and again after a short delay to ensure UI updates
                        Clock.schedule_once(
                            lambda dt: self.refresh_cache_statistics_display(
                                playlist_id
                            ),
                            0.1,
                        )
                        Clock.schedule_once(
                            lambda dt: self.refresh_cache_statistics_display(
                                playlist_id
                            ),
                            0.8,
                        )
        except Exception as exc:
            logger.warning("Error updating cache on Details window open: %s", exc)
            self._cache_loading = False  # Ensure loading state is cleared on error

        # Start analysis
        analysis_task = AnalysisTask(playlist_id)
        active_analysis_tasks[playlist_id] = analysis_task
        threading.Thread(
            target=self.fetch_analysis_with_cached_data_display,
            args=(playlist_info, cached_data, analysis_task),
            daemon=True,
        ).start()

    def _load_tracks_with_progress(
        self,
        playlist_info: Dict[str, Any],
        cached_data: Optional[Dict[str, Any]],
        progress_window: ProgressWindow,
    ) -> None:
        """Load tracks in background with separate progress window for large playlists."""
        playlist_id = playlist_info["playlist_id"]
        track_count = playlist_info.get("track_count", 0)
        playlist_name = playlist_info.get("playlist_name", "Unknown Playlist")

        # Progress window was already created on main thread

        def update_progress(percent: int, message: str):
            """Update progress window from background thread."""
            if not progress_window.is_cancelled:
                progress_window.update_progress(percent, message)

        # Start background loading
        def background_loading():
            try:
                update_progress(5, "Connecting to Spotify...")

                app = App.get_running_app()
                token_info = getattr(app, "token_info", None)
                if not token_info:
                    update_progress(0, "Authentication error")
                    progress_window.set_error("Authentication failed")
                    return

                sp = create_spotify_client_with_refresh(token_info)
                if not sp:
                    update_progress(0, "Spotify client error")
                    progress_window.set_error("Failed to connect to Spotify")
                    return

                user_id = getattr(app, "user_id", None) or sp.current_user().get("id")
                if not user_id:
                    update_progress(0, "User ID error")
                    progress_window.set_error("Failed to get user information")
                    return

                update_progress(10, f"Loading {track_count:,} tracks...")

                # Load tracks with progress tracking
                self._cache_loading = True
                tracks_data = self._get_or_update_playlist_tracks_with_progress(
                    sp, playlist_id, user_id, track_count, update_progress
                )

                if progress_window.is_cancelled:
                    logger.info(
                        "Track loading cancelled by user for playlist %s", playlist_name
                    )
                    return

                update_progress(90, "Processing track data...")

                logger.info(
                    "Updated cache for playlist %s (Details window opened) - %d tracks, %d Spotify cached, %d ReccoBeats cached",
                    playlist_name,
                    tracks_data["total_tracks"],
                    tracks_data["spotify_cached_count"],
                    tracks_data["reccobeats_cached_count"],
                )

                # Clear loading state
                self._cache_loading = False

                update_progress(95, "Starting analysis...")

                # Close progress window and start analysis
                def close_progress_and_start():
                    if not progress_window.is_cancelled:
                        progress_window.set_completed()
                        Clock.schedule_once(
                            lambda dt: progress_window.dismiss(), 1.0
                        )  # Auto-close after 1 second

                    # Update loading label in main window
                    loading_label = playlist_info.get("loading_label")
                    if loading_label:
                        loading_label.text = "Running playlist analysis..."

                    # Refresh cache display
                    Clock.schedule_once(
                        lambda dt: self.refresh_cache_statistics_display(playlist_id),
                        0.1,
                    )
                    Clock.schedule_once(
                        lambda dt: self.refresh_cache_statistics_display(playlist_id),
                        0.8,
                    )

                    # Start analysis
                    if not progress_window.is_cancelled:
                        analysis_task = AnalysisTask(playlist_id)
                        active_analysis_tasks[playlist_id] = analysis_task
                        threading.Thread(
                            target=self.fetch_analysis_with_cached_data_display,
                            args=(playlist_info, cached_data, analysis_task),
                            daemon=True,
                        ).start()

                Clock.schedule_once(lambda dt: close_progress_and_start())

            except Exception as exc:
                logger.error("Error loading tracks with progress: %s", exc)
                update_progress(0, f"Error: {str(exc)[:30]}...")
                self._cache_loading = False

                # Show error in progress window
                progress_window.set_error(str(exc)[:50])

                # Update main window with error
                loading_label = playlist_info.get("loading_label")
                if loading_label:
                    loading_label.text = f"Error loading tracks: {str(exc)[:30]}..."
                    loading_label.color = (0.8, 0.4, 0.4, 1)

        # Start background loading thread
        threading.Thread(target=background_loading, daemon=True).start()

    def _get_or_update_playlist_tracks_with_progress(
        self, sp, playlist_id: str, user_id: str, total_tracks: int, update_progress
    ) -> Dict[str, Any]:
        """Get playlist tracks with progress updates."""
        try:
            # Get current tracks from Spotify API
            results = sp.playlist_tracks(
                playlist_id, limit=50
            )  # Smaller batch size for more frequent updates
            current_tracks = []
            processed = 0

            while results:
                for item in results["items"]:
                    track = item.get("track")
                    if track:
                        # Add position and added_at from the playlist item
                        track_data = track.copy()
                        track_data["position"] = item.get(
                            "position", len(current_tracks)
                        )
                        track_data["added_at"] = item.get("added_at")
                        current_tracks.append(track_data)

                    processed += 1
                    # Update progress every 50 tracks or at the end
                    if processed % 50 == 0 or processed >= total_tracks:
                        progress_percent = 10 + int(
                            (processed / total_tracks) * 75
                        )  # 10% to 85%
                        update_progress(
                            progress_percent,
                            f"Loaded {processed:,}/{total_tracks:,} tracks...",
                        )

                if results["next"]:
                    results = sp.next(results)
                else:
                    break

            # Cache the tracks with status
            persistent_cache.cache_playlist_tracks(playlist_id, user_id, current_tracks)

            # Get the cached data with status information
            cached_data = persistent_cache.get_cached_playlist_tracks(
                playlist_id, user_id
            )

            return {
                "tracks": current_tracks,
                "total_tracks": len(current_tracks),
                "cache_data": cached_data,
                "spotify_cached_count": cached_data.get("spotify_cached_count", 0)
                if cached_data
                else 0,
                "reccobeats_cached_count": cached_data.get("reccobeats_cached_count", 0)
                if cached_data
                else 0,
                "new_tracks": len(current_tracks)
                - (cached_data.get("total_tracks", 0) if cached_data else 0),
            }

        except Exception as exc:
            logger.error("Error getting playlist tracks with progress: %s", exc)
            update_progress(0, "Error loading tracks")
            return {
                "tracks": [],
                "total_tracks": 0,
                "cache_data": None,
                "spotify_cached_count": 0,
                "reccobeats_cached_count": 0,
                "new_tracks": 0,
            }

    def fetch_analysis_with_cached_data_display(
        self,
        playlist_info: Dict[str, Any],
        cached_data: Optional[Dict[str, Any]],
        analysis_task: AnalysisTask,
    ) -> None:
        try:
            playlist_id = playlist_info["playlist_id"]
            loading_label = playlist_info["loading_label"]
            info_layout = playlist_info["info_layout"]
            owner_id = playlist_info["owner_id"]
            snapshot_id = playlist_info["snapshot_id"]

            if analysis_task and analysis_task.is_cancelled():
                return

            app = App.get_running_app()
            if not app.token_info or not app.token_info.get("access_token"):
                Clock.schedule_once(
                    lambda dt: self.update_loading_message(
                        loading_label, "Authentication error"
                    ),
                    0,
                )
                return

            sp = create_spotify_client_with_refresh(app.token_info)
            if not sp:
                Clock.schedule_once(
                    lambda dt: self.update_loading_message(
                        loading_label, "Authentication error"
                    ),
                    0,
                )
                return

            if cached_data and cached_data.get("spotify"):
                spotify_analysis = cached_data["spotify"]
                Clock.schedule_once(
                    lambda dt: self.display_cached_spotify_analysis(
                        loading_label,
                        info_layout,
                        spotify_analysis,
                        owner_id,
                        playlist_id,
                        snapshot_id,
                        analysis_task,
                        cached_data,
                    ),
                    0,
                )
            else:
                Clock.schedule_once(
                    lambda dt: self.update_loading_message(
                        loading_label, "Fetching track data from Spotify..."
                    ),
                    0,
                )
                # Add initial spacer after "Fetching track data from Spotify" message
                Clock.schedule_once(
                    lambda dt: self.manage_spacer("add_initial"),
                    0.1,
                )
                (
                    tracks_data,
                    track_ids,
                    artist_ids,
                    total_duration_ms,
                ) = self._fetch_playlist_tracks_cancellable(
                    sp, playlist_id, analysis_task
                )
                if analysis_task and analysis_task.is_cancelled():
                    return
                if not tracks_data:
                    Clock.schedule_once(
                        lambda dt: self.update_loading_message(
                            loading_label, "No tracks found"
                        ),
                        0,
                    )
                    return

                duration_str = self._format_duration(total_duration_ms)
                Clock.schedule_once(
                    lambda dt: self.update_loading_message(
                        loading_label, "Analyzing artists and genres..."
                    ),
                    0,
                )

                artist_genres, artist_details = self._fetch_artist_data_cancellable(
                    sp, list(artist_ids), analysis_task
                )
                if analysis_task and analysis_task.is_cancelled():
                    return

                spotify_analysis = self.analyze_spotify_data(
                    tracks_data, artist_genres, artist_details, duration_str
                )
                spotify_analysis["track_ids"] = track_ids
                spotify_analysis["track_rows"] = self._build_spotify_track_rows(
                    tracks_data
                )
                spotify_analysis["source"] = "spotify"
                cache_playlist_analysis(playlist_id, spotify_data=spotify_analysis)

                # Strategic refresh when Spotify analysis completes (bypass debouncing)
                if hasattr(self, "detailed_popup") and self.detailed_popup:
                    logger.debug(
                        "SPOTIFY COMPLETION: Forcing cache refresh for playlist %s",
                        playlist_id,
                    )
                    setattr(
                        self, "_last_cache_refresh", 0
                    )  # Reset debouncing to force refresh
                    Clock.schedule_once(
                        lambda dt: self.refresh_cache_statistics_display(playlist_id),
                        0.2,
                    )
                else:
                    logger.debug(
                        "SPOTIFY COMPLETION: No detailed popup found for playlist %s",
                        playlist_id,
                    )

                Clock.schedule_once(
                    lambda dt: self.display_cached_spotify_analysis(
                        loading_label,
                        info_layout,
                        spotify_analysis,
                        owner_id,
                        playlist_id,
                        snapshot_id,
                        analysis_task,
                        cached_data,
                    ),
                    0,
                )

        except Exception as exc:
            logger.error(
                "Error fetching analysis with cached data display: %s",
                exc,
            )
            Clock.schedule_once(
                lambda dt, err=str(exc): self.update_loading_message(
                    playlist_info["loading_label"],
                    f"Analysis error: {err[:30]}...",
                ),
                0,
            )

    @mainthread
    def display_cached_spotify_analysis(
        self,
        loading_label: Label,
        info_layout: BoxLayout,
        spotify_analysis: Dict[str, Any],
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
        analysis_task: AnalysisTask,
        cached_data: Optional[Dict[str, Any]],
    ) -> None:
        try:
            if analysis_task and analysis_task.is_cancelled():
                return

            cached_reccobeats = cached_data.get("reccobeats") if cached_data else None
            has_cached_reccobeats = bool(
                cached_reccobeats
                and isinstance(cached_reccobeats, dict)
                and cached_reccobeats
            )

            track_ids = spotify_analysis.get("track_ids", [])
            self.update_spotify_analysis(
                loading_label,
                info_layout,
                spotify_analysis,
                owner_id,
                playlist_id,
                snapshot_id,
                track_ids,
                analysis_task,
                skip_reccobeats=has_cached_reccobeats,
            )

            if has_cached_reccobeats:
                Clock.schedule_once(
                    lambda dt: self.update_reccobeats_analysis_from_cache(
                        cached_reccobeats,
                        info_layout,
                        owner_id,
                        playlist_id,
                        snapshot_id,
                    ),
                    0.8,
                )

        except Exception as exc:
            logger.error("Error displaying cached Spotify analysis: %s", exc)

    def cancel_existing_analysis(self, playlist_id: str) -> None:
        try:
            if playlist_id in active_analysis_tasks:
                active_analysis_tasks[playlist_id].cancel()
                logger.info("Cancelled existing analysis for playlist: %s", playlist_id)
        except Exception as exc:
            logger.warning("Error cancelling existing analysis: %s", exc)

    def cleanup_on_popup_close(self, playlist_id: str) -> None:
        try:
            if playlist_id in active_analysis_tasks:
                active_analysis_tasks[playlist_id].cancel()
                cleanup_analysis_task(playlist_id)

            # Clean up progress window if it exists
            if hasattr(self, "playlist_info") and self.playlist_info:
                progress_window = self.playlist_info.get("progress_window")
                if progress_window:
                    progress_window.is_cancelled = True
                    if not progress_window.is_dismissed:
                        progress_window.dismiss()

            # Clean up any existing spacer
            self.safely_remove_dummy_spacer()

            self.detailed_popup = None
        except Exception as exc:
            logger.warning("Error cleaning up popup close: %s", exc)

    def close_detailed_window(self) -> None:
        try:
            if getattr(self, "detailed_popup", None):
                self.detailed_popup.dismiss()
        except Exception as exc:
            logger.warning("Error closing detailed window: %s", exc)

    # ------------------------------------------------------------------
    # Spotify data fetch + analysis helpers
    # ------------------------------------------------------------------
    def _fetch_playlist_tracks_cancellable(
        self, sp: spotipy.Spotify, playlist_id: str, analysis_task: AnalysisTask
    ) -> Tuple[List[Dict[str, Any]], List[str], set, int]:
        tracks_data: List[Dict[str, Any]] = []
        artist_ids: set = set()
        track_ids: List[str] = []
        total_duration_ms = 0

        try:
            results = sp.playlist_tracks(playlist_id, limit=100)
            while results:
                if analysis_task and analysis_task.is_cancelled():
                    return tracks_data, track_ids, artist_ids, total_duration_ms

                for item in results["items"]:
                    if analysis_task and analysis_task.is_cancelled():
                        return tracks_data, track_ids, artist_ids, total_duration_ms

                    track = item.get("track")
                    if track and track.get("type") == "track":
                        track_payload = dict(track)
                        added_at = item.get("added_at")
                        if added_at:
                            track_payload["added_at"] = added_at

                        track_id = track_payload.get("id")
                        if track_id:
                            track_ids.append(track_id)
                        normalized_track = self._get_or_cache_spotify_track(
                            track_payload
                        )
                        if normalized_track:
                            duration_ms = normalized_track.get("duration_ms", 0)
                            total_duration_ms += duration_ms

                            for artist_id in normalized_track.get("artist_ids", []):
                                artist_ids.add(artist_id)

                            if normalized_track.get("artists"):
                                tracks_data.append(normalized_track)
                        else:
                            duration_ms = track.get("duration_ms", 0)
                            total_duration_ms += duration_ms

                if results["next"] and not (
                    analysis_task and analysis_task.is_cancelled()
                ):
                    results = sp.next(results)
                else:
                    break
        except Exception as exc:
            logger.error("Error fetching tracks with cancellation: %s", exc)

        return tracks_data, track_ids, artist_ids, total_duration_ms

    def _get_or_cache_spotify_track(
        self, track: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        # logger.debug("_get_or_cache_spotify_track called for track %s", track.get('id') if track else 'None')

        if not track:
            logger.debug("Track is None, returning None")
            return None

        track_id = track.get("id")
        if not track_id:
            logger.debug("Track ID is None, returning None")
            return None

        cached_entry = get_cached_spotify_track(track_id)
        if cached_entry:
            # logger.debug("Found cached entry for track %s", track_id)
            return cached_entry

        # logger.debug("Caching new track %s", track_id)
        # Cache new track and refresh display
        cached_track = cache_spotify_track(track)
        # logger.debug("Cache result: %s", 'success' if cached_track else 'failed')

        if cached_track:
            # Try to get playlist info from instance variable or extract it
            playlist_info = getattr(self, "playlist_info", None)
            if not playlist_info:
                # Fallback: extract playlist info from playlist_data
                playlist_info = {
                    "playlist_id": self.playlist_data.get("id"),
                    "playlist_name": self.playlist_data.get("name", "Unknown"),
                }

            playlist_id = playlist_info.get("playlist_id")
            user_id = getattr(App.get_running_app(), "user_id", None)

            # Fallback: try to get user_id from owner_id if user_id is None
            if not user_id:
                user_id = playlist_info.get("owner_id")

            # logger.debug("Playlist info: %s, User ID: %s", playlist_id, user_id)

            if playlist_id and user_id:
                # Update playlist track cache status
                # logger.debug("Updating playlist track cache status for track %s", track_id)
                persistent_cache.update_playlist_track_cache_status(
                    playlist_id, user_id, track_id
                )
                # Schedule cache display refresh with multiple attempts on main thread
                # logger.debug("Scheduling cache display refresh for Spotify track %s", track_id)

                # Only schedule refresh if Details window is still open and respect debouncing
                if hasattr(self, "detailed_popup") and self.detailed_popup:
                    current_time = time.time()
                    last_refresh = getattr(self, "_last_cache_refresh", 0)
                    is_refreshing = getattr(self, "_is_refreshing", False)

                    # Don't trigger refreshes if we're already refreshing or in lightweight mode
                    if not is_refreshing and not getattr(
                        self, "_lightweight_refresh_mode", False
                    ):
                        # Only refresh if enough time has passed, or if this might be the first refresh
                        if (
                            current_time - last_refresh >= 2.0
                        ):  # Minimum 2 seconds between individual track refreshes
                            setattr(self, "_last_cache_refresh", current_time)
                            Clock.schedule_once(
                                lambda dt: self.refresh_cache_statistics_display(
                                    playlist_id
                                ),
                                0.1,
                            )
                        else:
                            # logger.debug("Skipping cache refresh for track %s - debounced", track_id)
                            pass
                    else:
                        # logger.debug("Skipping cache refresh for track %s - refreshing: %s, lightweight: %s",
                        #            track_id, is_refreshing, getattr(self, '_lightweight_refresh_mode', False))
                        pass
                else:
                    # logger.debug("Details window not open, skipping cache refresh")
                    pass
            else:
                logger.debug(
                    "Missing playlist_id or user_id - playlist_id: %s, user_id: %s",
                    playlist_id,
                    user_id,
                )
        else:
            logger.debug("Failed to cache track %s", track_id)

        return cached_track

    def _fetch_artist_data_cancellable(
        self,
        sp: spotipy.Spotify,
        artist_ids_list: List[str],
        analysis_task: AnalysisTask,
    ) -> Tuple[List[str], Dict[str, Any]]:
        artist_genres: List[str] = []
        artist_details: Dict[str, Any] = {}

        for i in range(0, len(artist_ids_list), 50):
            if analysis_task and analysis_task.is_cancelled():
                break

            batch = artist_ids_list[i : i + 50]
            try:
                artists_batch = sp.artists(batch)
                if artists_batch and "artists" in artists_batch:
                    for artist in artists_batch["artists"]:
                        if analysis_task and analysis_task.is_cancelled():
                            break
                        artist_id = artist.get("id")
                        if artist_id:
                            artist_details[artist_id] = artist
                            artist_genres.extend(artist.get("genres", []))
            except Exception as exc:
                logger.warning("Error getting artists batch with cancellation: %s", exc)
                continue

        return artist_genres, artist_details

    def _format_duration(self, total_duration_ms: int) -> str:
        hours = total_duration_ms // 3_600_000
        minutes = (total_duration_ms % 3_600_000) // 60_000
        seconds = (total_duration_ms % 60_000) // 1_000
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"

    def _format_track_duration(self, duration_ms: int) -> str:
        minutes = duration_ms // 60_000
        seconds = (duration_ms % 60_000) // 1_000
        return f"{minutes}:{seconds:02d}"

    def _build_spotify_track_rows(
        self, tracks_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for index, track in enumerate(tracks_data, start=1):
            duration_ms = track.get("duration_ms", 0)
            rows.append(
                {
                    "source": "spotify",
                    "track_number": index,
                    "spotify_id": track.get("id"),
                    "title": track.get("title") or track.get("name"),
                    "artists": ", ".join(track.get("artists", [])),
                    "album": track.get("album", ""),
                    "duration_ms": duration_ms,
                    "duration": self._format_track_duration(duration_ms),
                    "popularity": track.get("popularity"),
                    "explicit": track.get("explicit"),
                    "spotify_url": track.get("spotify_url"),
                    "spotify_uri": track.get("spotify_uri"),
                    "added_at": track.get("added_at"),
                }
            )
        return rows

    def analyze_spotify_data(
        self,
        tracks_data: List[Dict[str, Any]],
        artist_genres: List[str],
        artist_details: Dict[str, Any],
        duration_str: str,
    ) -> Dict[str, Any]:
        try:
            from collections import Counter

            results: Dict[str, Any] = {
                "duration": duration_str,
                "track_count": len(tracks_data),
                "artist_stats": {},
                "genre_analysis": {},
                "spotify_only": True,
            }

            all_artists: List[str] = []
            for track in tracks_data:
                all_artists.extend(track["artists"])

            if all_artists:
                artist_counts = Counter(all_artists)
                results["artist_stats"] = {
                    "unique_count": len(set(all_artists)),
                    "total_appearances": len(all_artists),
                    "most_frequent": artist_counts.most_common(5),
                    "diversity_ratio": len(set(all_artists)) / len(all_artists),
                }

            if artist_genres:
                genre_counts = Counter(artist_genres)
                results["genre_analysis"] = {
                    "total_genres": len(set(artist_genres)),
                    "most_common": genre_counts.most_common(10),
                    "grouped": self.group_genres(genre_counts),
                }

            return results
        except Exception as exc:
            logger.error("Error analyzing Spotify data: %s", exc)
            return {
                "error": str(exc),
                "spotify_only": True,
                "duration": duration_str,
                "track_count": len(tracks_data),
            }

    def group_genres(self, genre_counts: Dict[str, int]) -> Dict[str, int]:
        genre_groups = {
            "Pop": 0,
            "Rock": 0,
            "Hip-Hop/Rap": 0,
            "Electronic/Dance": 0,
            "R&B/Soul": 0,
            "Country": 0,
            "Jazz": 0,
            "Classical": 0,
            "Folk/Indie": 0,
            "Metal": 0,
            "Other": 0,
        }

        genre_keywords = {
            "Pop": ["pop", "electropop", "synthpop"],
            "Rock": ["rock", "alternative", "grunge", "punk"],
            "Hip-Hop/Rap": ["hip hop", "rap", "trap", "hip-hop"],
            "Electronic/Dance": [
                "electronic",
                "edm",
                "house",
                "techno",
                "dance",
                "dubstep",
            ],
            "R&B/Soul": ["r&b", "soul", "funk", "neo soul"],
            "Country": ["country", "bluegrass", "americana"],
            "Jazz": ["jazz", "blues", "swing"],
            "Classical": ["classical", "opera", "symphony"],
            "Folk/Indie": ["folk", "indie", "singer-songwriter", "acoustic"],
            "Metal": ["metal", "heavy", "death", "black metal"],
        }

        try:
            for genre, count in genre_counts.items():
                genre_lower = genre.lower()
                for category, keywords in genre_keywords.items():
                    if any(keyword in genre_lower for keyword in keywords):
                        genre_groups[category] += count
                        break
                else:
                    genre_groups["Other"] += count
            return {k: v for k, v in genre_groups.items() if v > 0}
        except Exception as exc:
            logger.error("Error grouping genres: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # ReccoBeats integration helpers
    # ------------------------------------------------------------------
    def update_spotify_analysis(
        self,
        loading_label: Label,
        info_layout: BoxLayout,
        spotify_analysis: Dict[str, Any],
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
        track_ids: List[str],
        analysis_task: Optional[AnalysisTask] = None,
        skip_reccobeats: bool = False,
    ) -> None:
        try:
            # Remove initial spacer before adding Spotify widgets
            self.manage_spacer("remove_before_spotify")

            basic_widgets = [
                w for w in self.master_content_container.children if w != loading_label
            ]
            self.master_content_container.clear_widgets()
            for widget in reversed(basic_widgets):
                self.master_content_container.add_widget(widget)

            analysis_widgets = self._create_spotify_analysis_widgets(spotify_analysis)

            # Add Spotify widgets first
            for widget in analysis_widgets:
                self.master_content_container.add_widget(widget)

            if not skip_reccobeats:
                # Note: ReccoBeats spacer will be added in background thread when API work starts
                reccobeats_loading_label = self.create_info_label(
                    "Loading audio features from ReccoBeats...",
                    color=(0.2, 0.8, 0.2, 1),
                    height=14,
                )
                self.master_content_container.add_widget(reccobeats_loading_label)

            self._trigger_layout_updates()
            Clock.schedule_once(self._improved_scroll_to_top, 0.1)
            Clock.schedule_once(self._improved_scroll_to_top, 0.3)

            if not skip_reccobeats:
                # Start periodic cache refreshes during ReccoBeats processing
                def schedule_periodic_refresh(dt):
                    logger.debug(
                        "PERIODIC REFRESH: Checking if should update (active=%s, popup=%s)",
                        getattr(self, "_periodic_refresh_active", False),
                        hasattr(self, "detailed_popup") and self.detailed_popup,
                    )
                    if (
                        getattr(self, "_periodic_refresh_active", False)
                        and hasattr(self, "detailed_popup")
                        and self.detailed_popup
                    ):
                        # Check if we're already refreshing to prevent conflicts
                        is_refreshing = getattr(self, "_is_refreshing", False)
                        if is_refreshing:
                            logger.debug(
                                "PERIODIC REFRESH: Skipping - already refreshing"
                            )
                            Clock.schedule_once(schedule_periodic_refresh, 3.0)
                            return

                        # Force refresh during lightweight mode to show ReccoBeats progress
                        lightweight_mode = getattr(
                            self, "_lightweight_refresh_mode", False
                        )
                        if lightweight_mode:
                            logger.debug(
                                "PERIODIC REFRESH: Forcing cache refresh during ReccoBeats processing"
                            )
                            Clock.schedule_once(
                                lambda dt: self.refresh_cache_statistics_display(
                                    playlist_id, force_refresh=True
                                ),
                                0.1,
                            )
                        else:
                            # Only refresh if enough time has passed since last refresh (debouncing)
                            current_time = time.time()
                            last_refresh = getattr(self, "_last_cache_refresh", 0)
                            time_since_last = current_time - last_refresh
                            logger.debug(
                                "PERIODIC REFRESH: Time since last refresh=%.1fs (need 3.0s)",
                                time_since_last,
                            )
                            if (
                                time_since_last >= 3.0
                            ):  # Maximum 1 refresh per 3 seconds
                                logger.debug(
                                    "PERIODIC REFRESH: Scheduling cache refresh for playlist %s",
                                    playlist_id,
                                )
                                setattr(self, "_last_cache_refresh", current_time)
                                Clock.schedule_once(
                                    lambda dt: self.refresh_cache_statistics_display(
                                        playlist_id
                                    ),
                                    0.1,
                                )
                        # Schedule next refresh if still active and Details window is still open
                        Clock.schedule_once(
                            schedule_periodic_refresh, 3.0
                        )  # Check every 3 seconds
                    else:
                        logger.debug(
                            "PERIODIC REFRESH: Stopping - not active or no popup"
                        )

                # Start periodic refreshes after a longer delay to let ReccoBeats start
                logger.debug(
                    "PERIODIC REFRESH: Starting periodic refreshes in 5 seconds for playlist %s",
                    playlist_id,
                )
                Clock.schedule_once(schedule_periodic_refresh, 5.0)

                # Store the refresh function so we can stop it later
                setattr(self, "_periodic_refresh_active", True)
                setattr(
                    self, "_lightweight_refresh_mode", True
                )  # Use lightweight mode during processing
                setattr(self, "_last_cache_refresh", 0)  # Initialize refresh timestamp

                threading.Thread(
                    target=self.fetch_reccobeats_with_cancellation,
                    args=(
                        track_ids,
                        reccobeats_loading_label,
                        info_layout,
                        owner_id,
                        playlist_id,
                        snapshot_id,
                        analysis_task,
                    ),
                    daemon=True,
                ).start()

        except Exception as exc:
            logger.error("Error updating Spotify analysis: %s", exc)

    def _create_spotify_analysis_widgets(
        self, spotify_analysis: Dict[str, Any]
    ) -> List[Widget]:
        widgets: List[Widget] = []
        if "duration" in spotify_analysis and hasattr(self, "stats_widget"):
            current_text = self.stats_widget.text
            self.stats_widget.text = (
                f"{current_text} • Duration: {spotify_analysis['duration']}"
            )
        else:
            widgets.append(
                self.create_info_label(
                    f"Total Duration: {spotify_analysis.get('duration', 'Unknown')}",
                    font_size=dp(16),
                    height=dp(8),
                )
            )

        if spotify_analysis.get("genre_analysis"):
            genre_data = spotify_analysis["genre_analysis"]
            header = self.create_info_label(
                "Genre Distribution:",
                font_size=dp(18),
                height=UIConstants.HEADER_HEIGHT,
            )
            header.bold = True
            widgets.append(header)
            grouped = genre_data.get("grouped")
            if grouped:
                total = sum(grouped.values())
                for genre, count in sorted(
                    grouped.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    percentage = int((count / total) * 100) if total else 0
                    widgets.append(
                        self.create_info_label(
                            f"{genre}: {percentage}% ({count} tracks)",
                            font_size=dp(13),
                        )
                    )

        if spotify_analysis.get("artist_stats"):
            artist_data = spotify_analysis["artist_stats"]
            header = self.create_info_label(
                "Artist Analysis:", font_size=dp(18), height=UIConstants.HEADER_HEIGHT
            )
            header.bold = True
            widgets.append(header)
            widgets.append(
                self.create_info_label(
                    f"Unique Artists: {artist_data['unique_count']} • Diversity: {int(artist_data['diversity_ratio'] * 100)}%"
                )
            )
            if artist_data.get("most_frequent"):
                top_artists = artist_data["most_frequent"][:3]
                widgets.append(
                    self.create_info_label(
                        "Top Artists: "
                        + ", ".join(
                            [f"{artist} ({count})" for artist, count in top_artists]
                        ),
                        font_size=dp(13),
                    )
                )

        return widgets

    def fetch_reccobeats_with_cancellation(
        self,
        track_ids: List[str],
        loading_label: Label,
        info_layout: BoxLayout,
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
        analysis_task: Optional[AnalysisTask] = None,
    ) -> None:
        try:
            if analysis_task and analysis_task.is_cancelled():
                setattr(self, "_periodic_refresh_active", False)
                setattr(self, "_lightweight_refresh_mode", False)
                return

            cached_data = get_cached_playlist_analysis(playlist_id)
            if cached_data is not None and cached_data.get("reccobeats"):
                Clock.schedule_once(
                    lambda dt: self.update_reccobeats_analysis_from_cache(
                        cached_data["reccobeats"],
                        info_layout,
                        owner_id,
                        playlist_id,
                        snapshot_id,
                    ),
                    0,
                )
                setattr(self, "_periodic_refresh_active", False)
                setattr(self, "_lightweight_refresh_mode", False)
                return

            Clock.schedule_once(
                lambda dt: self.update_loading_message(
                    loading_label, "Retrieving analysis from ReccoBeats API..."
                ),
                0,
            )
            # Add spacer right after the API message update
            Clock.schedule_once(
                lambda dt: self._debug_spacer_action(
                    "add_after_spacer", "After API message update"
                ),
                0.1,
            )

            if analysis_task and analysis_task.is_cancelled():
                fetched_count = len(
                    [
                        row
                        for row in (cached_data or {})
                        .get("reccobeats", {})
                        .get("track_rows", [])
                    ]
                )
                logger.info(
                    "ReccoBeats fetch cancelled early for %s (%s/%s tracks cached)",
                    playlist_id,
                    fetched_count,
                    len(track_ids),
                )
                return

            audio_features_map = reccobeats_api.get_multiple_track_audio_features_safe(
                track_ids, max_concurrent=2, analysis_task=analysis_task
            )

            logger.info(
                "Fetched ReccoBeats features for %s/%s tracks (playlist=%s)",
                len(audio_features_map),
                len(track_ids),
                playlist_id,
            )

            # Refresh cache display when new ReccoBeats features are fetched
            if audio_features_map:
                # Try to get playlist info from instance variable or extract it
                playlist_info = getattr(self, "playlist_info", None)
                if not playlist_info:
                    # Fallback: extract playlist info from playlist_data
                    playlist_info = {
                        "playlist_id": self.playlist_data.get("id"),
                        "playlist_name": self.playlist_data.get("name", "Unknown"),
                    }

                user_id = getattr(App.get_running_app(), "user_id", None)

                # Fallback: try to get user_id from owner_id if user_id is None
                if not user_id:
                    user_id = playlist_info.get("owner_id")

                if user_id:
                    # Update cache status for all tracks that got ReccoBeats features
                    # logger.debug("Updating playlist track cache status for %d ReccoBeats tracks", len(audio_features_map))
                    tracks_updated = 0
                    for track_id in audio_features_map.keys():
                        persistent_cache.update_playlist_track_cache_status(
                            playlist_id, user_id, track_id
                        )
                        tracks_updated += 1
                    logger.debug(
                        "Updated cache status for %d/%d ReccoBeats tracks",
                        tracks_updated,
                        len(audio_features_map),
                    )

                    # Debug: Check cache state immediately after update
                    updated_cache_data = persistent_cache.get_cached_playlist_tracks(
                        playlist_id, user_id
                    )
                    if updated_cache_data:
                        logger.debug(
                            "CACHE CHECK AFTER UPDATE: Spotify: %d/%d, ReccoBeats: %d/%d",
                            updated_cache_data.get("spotify_cached_count", 0),
                            updated_cache_data.get("total_tracks", 0),
                            updated_cache_data.get("reccobeats_cached_count", 0),
                            updated_cache_data.get("total_tracks", 0),
                        )
                    else:
                        logger.debug("CACHE CHECK AFTER UPDATE: No cache data found")

                # logger.debug("Scheduling cache display refresh for ReccoBeats features (%d tracks)", len(audio_features_map))

                # Only schedule refresh if Details window is still open and respect debouncing
                if hasattr(self, "detailed_popup") and self.detailed_popup:
                    # Force refresh when ReccoBeats features are actually updated
                    # logger.debug("Scheduling cache display refresh for ReccoBeats features (%d tracks) - FORCE REFRESH", len(audio_features_map))
                    Clock.schedule_once(
                        lambda dt: self.refresh_cache_statistics_display(
                            playlist_id, force_refresh=True
                        ),
                        0.2,
                    )
                else:
                    # logger.debug("Details window not open, skipping cache refresh")
                    pass

            if analysis_task and analysis_task.is_cancelled():
                return

            if not audio_features_map:
                Clock.schedule_once(
                    lambda dt: self.update_reccobeats_status_with_tech(
                        loading_label,
                        "No audio features returned from ReccoBeats",
                        info_layout,
                        owner_id,
                        playlist_id,
                        snapshot_id,
                    ),
                    0,
                )
                setattr(self, "_periodic_refresh_active", False)
                setattr(self, "_lightweight_refresh_mode", False)
                return

            reccobeats_analysis = self.analyze_reccobeats_features(
                audio_features_map, track_ids
            )
            if analysis_task and analysis_task.is_cancelled():
                setattr(self, "_periodic_refresh_active", False)
                setattr(self, "_lightweight_refresh_mode", False)
                return

            cache_playlist_analysis(playlist_id, reccobeats_data=reccobeats_analysis)

            # Strategic refresh when ReccoBeats analysis completes (switch back to normal mode)
            setattr(
                self, "_lightweight_refresh_mode", False
            )  # Disable lightweight mode for final refresh
            if hasattr(self, "detailed_popup") and self.detailed_popup:
                setattr(
                    self, "_last_cache_refresh", 0
                )  # Reset debouncing to force refresh
                Clock.schedule_once(
                    lambda dt: self.refresh_cache_statistics_display(playlist_id), 0.2
                )

            logger.info(
                "Cached ReccoBeats analysis for %s (%s/%s tracks)",
                playlist_id,
                len(reccobeats_analysis.get("track_rows", [])),
                len(track_ids),
            )
            Clock.schedule_once(
                lambda dt: self.update_reccobeats_analysis(
                    loading_label,
                    info_layout,
                    reccobeats_analysis,
                    owner_id,
                    playlist_id,
                    snapshot_id,
                ),
                0,
            )

        except Exception as exc:
            error_msg = f"ReccoBeats error: {str(exc)[:30]}..."
            logger.error("Error in ReccoBeats with cancellation: %s", exc)
            Clock.schedule_once(
                lambda dt, msg=error_msg: self.update_reccobeats_status_with_tech(
                    loading_label,
                    msg,
                    info_layout,
                    owner_id,
                    playlist_id,
                    snapshot_id,
                ),
                0,
            )
        finally:
            # Stop periodic refreshes when ReccoBeats processing completes
            setattr(self, "_periodic_refresh_active", False)
            setattr(
                self, "_lightweight_refresh_mode", False
            )  # Disable lightweight mode
            setattr(self, "_is_refreshing", False)  # Clear refreshing flag

    def _debug_spacer_action(self, action: str, context: str):
        """Debug spacer actions with context."""
        # logger.debug(f"[SPACER DEBUG] About to {action} - Context: {context}")
        self.manage_spacer(action)
        # logger.debug(f"[SPACER DEBUG] Completed {action} - Context: {context}")

    def manage_spacer(self, action: str, stage: str = None):
        """Unified spacer management for different stages."""
        try:
            if action == "add_initial":
                # Add dp(360) spacer after "Fetching tracks and genres"
                self._dummy_spacer = Widget(
                    size_hint_y=None,
                    height=dp(360),
                    opacity=0.0,  # Completely invisible
                    size_hint_x=1.0,  # Fill available width
                )
                self.master_content_container.add_widget(self._dummy_spacer)
                # logger.debug("Added initial spacer (dp(360))")
            elif action == "remove_before_spotify":
                # Remove dp(360) spacer before adding Spotify widgets
                if hasattr(self, "_dummy_spacer") and self._dummy_spacer:
                    self.master_content_container.remove_widget(self._dummy_spacer)
                    self._dummy_spacer = None
                    # logger.debug("Removed initial spacer before Spotify")
            elif action == "add_after_spotify":
                # Add dp(320) spacer after Spotify widgets, before ReccoBeats
                self._dummy_spacer = Widget(
                    size_hint_y=None,
                    height=dp(320),
                    opacity=0.0,  # Completely invisible
                    size_hint_x=1.0,  # Fill available width
                )
                self.master_content_container.add_widget(self._dummy_spacer)
                logger.debug("Added ReccoBeats spacer (dp(320))")
            elif action == "remove_before_reccobeats":
                # Remove dp(320) spacer before adding ReccoBeats content
                if hasattr(self, "_dummy_spacer") and self._dummy_spacer:
                    self.master_content_container.remove_widget(self._dummy_spacer)
                    self._dummy_spacer = None
                    logger.debug("Removed ReccoBeats spacer before content")
        except Exception as exc:
            logger.debug("Error managing spacer (%s): %s", action, exc)

    def safely_remove_dummy_spacer(self):
        """Safely remove any existing dummy spacer."""
        if hasattr(self, "_dummy_spacer") and self._dummy_spacer:
            try:
                self.master_content_container.remove_widget(self._dummy_spacer)
            except Exception as exc:
                logger.debug("Error removing dummy spacer: %s", exc)
            finally:
                self._dummy_spacer = None

    def update_reccobeats_analysis_from_cache(
        self,
        cached_reccobeats: Dict[str, Any],
        info_layout: BoxLayout,
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
    ) -> None:
        try:
            # Remove ReccoBeats spacer before adding cached content
            self.manage_spacer("remove_before_reccobeats")

            widgets_to_remove = []
            for widget in self.master_content_container.children:
                if hasattr(widget, "text") and widget.text:
                    text = str(widget.text)
                    if any(
                        phrase in text
                        for phrase in [
                            "Loading audio features",
                            "ReccoBeats:",
                            "Playlist Mood (ReccoBeats)",
                            "Musical Characteristics (ReccoBeats)",
                            "Audio Characteristics (ReccoBeats)",
                        ]
                    ):
                        widgets_to_remove.append(widget)

            for widget in widgets_to_remove:
                self.master_content_container.remove_widget(widget)

            Clock.schedule_once(
                lambda dt: self._add_cached_reccobeats_widgets(
                    cached_reccobeats, info_layout, owner_id, playlist_id, snapshot_id
                ),
                0.1,
            )
        except Exception as exc:
            logger.error("Error updating from cached ReccoBeats analysis: %s", exc)

    def _add_cached_reccobeats_widgets(
        self,
        cached_reccobeats: Dict[str, Any],
        info_layout: BoxLayout,
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
    ) -> None:
        try:
            dummy_label = Label(
                text="ReccoBeats: Analysis complete (from cache)",
                color=(0.2, 0.8, 0.2, 1),
            )
            self.update_reccobeats_analysis(
                dummy_label,
                info_layout,
                cached_reccobeats,
                owner_id,
                playlist_id,
                snapshot_id,
            )
            self._trigger_layout_updates()
            Clock.schedule_once(self._improved_scroll_to_top, 0.1)
        except Exception as exc:
            logger.error("Error adding cached ReccoBeats widgets: %s", exc)

    def analyze_reccobeats_features(
        self, audio_features_map: Dict[str, Dict[str, Any]], track_ids: List[str]
    ) -> Dict[str, Any]:
        try:
            audio_features: List[Dict[str, Any]] = []
            per_track_rows: List[Dict[str, Any]] = []
            for track_id in track_ids:
                if track_id in audio_features_map:
                    features = audio_features_map[track_id]
                    features["id"] = track_id
                    audio_features.append(features)
                    row = dict(features)
                    row["spotify_id"] = track_id
                    row["source"] = "reccobeats"
                    per_track_rows.append(row)

            results: Dict[str, Any] = {
                "audio_features": {},
                "mood_analysis": {},
                "tempo_analysis": {},
                "musical_keys": {},
                "coverage": len(audio_features) / len(track_ids) * 100
                if track_ids
                else 0,
                "track_rows": per_track_rows,
                "source": "reccobeats",
            }

            if not audio_features:
                results["no_features"] = True
                return results

            feature_names = [
                "danceability",
                "energy",
                "valence",
                "acousticness",
                "instrumentalness",
                "speechiness",
                "loudness",
                "tempo",
            ]
            for feature in feature_names:
                values = [
                    f.get(feature)
                    for f in audio_features
                    if f and f.get(feature) is not None
                ]
                if values:
                    if feature in ["loudness", "tempo"]:
                        results["audio_features"][feature] = {
                            "avg": sum(values) / len(values),
                            "min": min(values),
                            "max": max(values),
                        }
                    else:
                        avg_val = sum(values) / len(values)
                        results["audio_features"][feature] = {
                            "avg": avg_val,
                            "percentage": int(avg_val * 100),
                        }

            valence_values = [
                f.get("valence")
                for f in audio_features
                if f and f.get("valence") is not None
            ]
            energy_values = [
                f.get("energy")
                for f in audio_features
                if f and f.get("energy") is not None
            ]
            if valence_values and energy_values:
                avg_valence = sum(valence_values) / len(valence_values)
                avg_energy = sum(energy_values) / len(energy_values)

                if avg_valence > 0.6 and avg_energy > 0.6:
                    mood, mood_color = "Happy & Energetic", (0.2, 0.8, 0.2, 1)
                elif avg_valence > 0.6 and avg_energy <= 0.6:
                    mood, mood_color = "Happy & Chill", (0.2, 0.6, 0.8, 1)
                elif avg_valence <= 0.4 and avg_energy > 0.6:
                    mood, mood_color = "Intense & Dark", (0.8, 0.4, 0.2, 1)
                elif avg_valence <= 0.4 and avg_energy <= 0.6:
                    mood, mood_color = "Sad & Mellow", (0.6, 0.4, 0.8, 1)
                else:
                    mood, mood_color = "Balanced", (0.7, 0.7, 0.7, 1)

                results["mood_analysis"] = {
                    "mood": mood,
                    "color": mood_color,
                    "valence_pct": int(avg_valence * 100),
                    "energy_pct": int(avg_energy * 100),
                }

            results["musical_keys"] = self.analyze_musical_keys_reccobeats(
                audio_features
            )

            return results

        except Exception as exc:
            logger.error("Error analyzing ReccoBeats features: %s", exc)
            return {"error": str(exc), "no_features": True}

    def analyze_musical_keys_reccobeats(
        self, audio_features: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        try:
            key_names = [
                "C",
                "C#",
                "D",
                "D#",
                "E",
                "F",
                "F#",
                "G",
                "G#",
                "A",
                "A#",
                "B",
            ]
            mode_names = {0: "minor", 1: "major"}

            key_mode_combinations: List[str] = []
            key_values: List[int] = []
            mode_values: List[int] = []

            for features in audio_features:
                if not features:
                    continue
                key = features.get("key")
                mode = features.get("mode")

                if key is not None and 0 <= key <= 11:
                    key_values.append(key)
                    key_name = key_names[key]
                    if mode is not None and mode in mode_names:
                        mode_values.append(mode)
                        key_mode_combinations.append(f"{key_name} {mode_names[mode]}")
                    else:
                        key_mode_combinations.append(f"{key_name} unknown")

            if not key_mode_combinations:
                return {
                    "unavailable": True,
                    "reason": "No valid key/mode data found in ReccoBeats response",
                    "total_tracks_checked": len(audio_features),
                }

            from collections import Counter

            key_mode_counts = Counter(key_mode_combinations)
            key_counts = Counter(key_names[k] for k in key_values)
            mode_counts = Counter(mode_names[m] for m in mode_values)

            total_with_keys = len(key_mode_combinations)
            top_combinations = key_mode_counts.most_common(5)

            mode_distribution: Dict[str, Dict[str, int]] = {}
            if mode_values:
                total_modes = len(mode_values)
                for mode_num, name in mode_names.items():
                    count = mode_counts.get(name, 0)
                    percentage = int((count / total_modes) * 100) if total_modes else 0
                    mode_distribution[name] = {"count": count, "percentage": percentage}

            return {
                "available": True,
                "total_tracks": len(audio_features),
                "tracks_with_keys": total_with_keys,
                "coverage_percentage": int(
                    (total_with_keys / len(audio_features)) * 100
                )
                if audio_features
                else 0,
                "top_combinations": top_combinations,
                "mode_distribution": mode_distribution,
                "key_distribution": key_counts.most_common(12),
                "most_common_key": key_counts.most_common(1)[0] if key_counts else None,
                "most_common_combination": top_combinations[0]
                if top_combinations
                else None,
            }

        except Exception as exc:
            logger.error("Error analyzing musical keys from ReccoBeats: %s", exc)
            return {
                "error": str(exc),
                "unavailable": True,
                "reason": f"Error processing key data: {str(exc)[:50]}",
            }

    @mainthread
    def update_reccobeats_analysis(
        self,
        loading_label: Label,
        info_layout: BoxLayout,
        reccobeats_data: Dict[str, Any],
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
    ) -> None:
        try:
            # Remove ReccoBeats spacer before adding live content
            self.manage_spacer("remove_before_reccobeats")

            # Remove loading message and any existing ReccoBeats widgets
            existing_widgets = [
                w for w in self.master_content_container.children if w != loading_label
            ]
            self.master_content_container.clear_widgets()
            for widget in reversed(existing_widgets):
                self.master_content_container.add_widget(widget)

            widgets: List[Widget] = []
            if reccobeats_data.get("no_features"):
                widgets.append(
                    self.create_info_label(
                        "ReccoBeats: Audio analysis not available",
                        color=(0.9, 0.6, 0.2, 1),
                        height=UIConstants.REDUCED_SPACING,
                    )
                )
            else:
                coverage = int(reccobeats_data.get("coverage", 0))
                widgets.append(
                    self.create_info_label(
                        f"ReccoBeats: Audio analysis complete ({coverage}% coverage)",
                        color=(0.2, 0.8, 0.2, 1),
                        height=dp(8),
                    )
                )
                mood = reccobeats_data.get("mood_analysis")
                if mood:
                    header = self.create_info_label(
                        "Playlist Mood (ReccoBeats):", font_size=dp(18), height=dp(24)
                    )
                    header.bold = True
                    widgets.append(header)
                    mood_label = self.create_info_label(
                        mood.get("mood", "Unknown"),
                        font_size=dp(16),
                        color=mood.get("color", (1, 1, 1, 1)),
                        height=UIConstants.STANDARD_SPACING,
                    )
                    mood_label.bold = True
                    widgets.append(mood_label)
                    widgets.append(
                        self.create_info_label(
                            f"Happiness: {mood.get('valence_pct', 0)}% • Energy: {mood.get('energy_pct', 0)}%",
                            color=(0.8, 0.8, 0.8, 1),
                            height=UIConstants.STANDARD_SPACING,
                        )
                    )

                tempo = reccobeats_data.get("tempo_analysis")
                musical_keys = reccobeats_data.get("musical_keys")
                if tempo or (musical_keys and not musical_keys.get("unavailable")):
                    header = self.create_info_label(
                        "Musical Characteristics (ReccoBeats):",
                        font_size=dp(18),
                        height=UIConstants.HEADER_HEIGHT,
                    )
                    header.bold = True
                    widgets.append(header)
                    if tempo:
                        widgets.append(
                            self.create_info_label(
                                f"Tempo: {tempo['average']} BPM ({tempo.get('category', 'N/A')}) • Range: {tempo['min']}-{tempo['max']} BPM",
                                height=UIConstants.STANDARD_SPACING,
                            )
                        )
                    if musical_keys and musical_keys.get("top_combinations"):
                        combos = musical_keys["top_combinations"][:3]
                        combo_text = "Most Common Keys: " + ", ".join(
                            [f"{name} ({count})" for name, count in combos]
                        )
                        widgets.append(
                            self.create_info_label(
                                combo_text, height=UIConstants.STANDARD_SPACING
                            )
                        )
                        mode_dist = musical_keys.get("mode_distribution")
                        if mode_dist:
                            major_pct = mode_dist.get("major", {}).get("percentage", 0)
                            minor_pct = mode_dist.get("minor", {}).get("percentage", 0)
                            widgets.append(
                                self.create_info_label(
                                    f"Mode Distribution: Major {major_pct}%, Minor {minor_pct}%"
                                )
                            )

                features = reccobeats_data.get("audio_features")
                if features:
                    header = self.create_info_label(
                        "Audio Characteristics (ReccoBeats):",
                        font_size=dp(18),
                        height=UIConstants.HEADER_HEIGHT,
                    )
                    header.bold = True
                    widgets.append(header)
                    if "danceability" in features:
                        widgets.append(
                            self.create_info_label(
                                f"Danceability: {features['danceability'].get('percentage', 0)}%",
                                height=UIConstants.STANDARD_SPACING,
                            )
                        )
                    if "acousticness" in features:
                        widgets.append(
                            self.create_info_label(
                                f"Acousticness: {features['acousticness'].get('percentage', 0)}% • Instrumentalness: {features.get('instrumentalness', {}).get('percentage', 'N/A')}%",
                                height=UIConstants.STANDARD_SPACING,
                            )
                        )
                    if "speechiness" in features:
                        widgets.append(
                            self.create_info_label(
                                f"Speechiness: {features['speechiness'].get('percentage', 0)}%",
                                height=UIConstants.STANDARD_SPACING,
                            )
                        )

            for widget in widgets:
                self.master_content_container.add_widget(widget)

            self._trigger_layout_updates()
            Clock.schedule_once(self._improved_scroll_to_top, 0.1)
            Clock.schedule_once(self._improved_scroll_to_top, 0.3)

        except Exception as exc:
            logger.error("Error updating ReccoBeats analysis: %s", exc)

    def _trigger_layout_updates(self) -> None:
        try:
            if hasattr(self, "master_content_container"):
                self.master_content_container.do_layout()

            if hasattr(self, "detailed_popup") and self.detailed_popup:
                main_container = self.detailed_popup.content
                if main_container and len(main_container.children) > 1:
                    scroll_view = main_container.children[1]
                    if getattr(scroll_view, "children", None):
                        scroll_content = scroll_view.children[0]
                        scroll_content.do_layout()
                        if hasattr(scroll_view, "_update_effect_bounds"):
                            scroll_view._update_effect_bounds()
                        if hasattr(scroll_view, "update_effect_bounds"):
                            scroll_view.update_effect_bounds()

        except Exception as exc:
            logger.warning("Error triggering layout updates: %s", exc)

    def _improved_scroll_to_top(self, dt) -> None:
        try:
            if hasattr(self, "detailed_popup") and self.detailed_popup:
                main_container = self.detailed_popup.content
                if main_container and len(main_container.children) > 1:
                    scroll_view = main_container.children[1]
                    if getattr(scroll_view, "children", None):
                        scroll_content = scroll_view.children[0]
                        if hasattr(self, "master_content_container"):
                            self.master_content_container.do_layout()
                        scroll_content.do_layout()
                        if hasattr(scroll_view, "_update_effect_bounds"):
                            scroll_view._update_effect_bounds()
                        scroll_view.scroll_y = 1.0
                        if hasattr(scroll_view, "_update_effect_bounds"):
                            scroll_view._update_effect_bounds()
                        Clock.schedule_once(
                            lambda _: setattr(scroll_view, "scroll_y", 1.0), 0.1
                        )

        except Exception as exc:
            logger.warning("Error in improved scroll to top: %s", exc)

    @mainthread
    def update_reccobeats_status_with_tech(
        self,
        loading_label: Label,
        message: str,
        info_layout: BoxLayout,
        owner_id: str,
        playlist_id: str,
        snapshot_id: str,
    ) -> None:
        try:
            if loading_label in self.master_content_container.children:
                self.master_content_container.remove_widget(loading_label)
            status_label = self.create_info_label(
                f"ReccoBeats: {message}",
                color=(0.9, 0.6, 0.2, 1),
            )
            self.master_content_container.add_widget(status_label)
            # Add spacer to prevent cover image from being cut off when no ReccoBeats data
            spacer_widget = Widget(
                size_hint_y=None, height=dp(320), opacity=0.0, size_hint_x=1.0
            )
            self.master_content_container.add_widget(spacer_widget)
            self._trigger_layout_updates()
            Clock.schedule_once(self._improved_scroll_to_top, 0.1)
        except Exception as exc:
            logger.warning("Error updating ReccoBeats status: %s", exc)

    # ------------------------------------------------------------------
    # Tooltip & hover helpers
    # ------------------------------------------------------------------
    def show_simple_tooltip(self, pos) -> None:
        try:
            if self.tooltip_popup:
                return
            full_name = str(self.playlist_data.get("name", "Untitled Playlist"))
            tooltip_width = max(dp(150), min(dp(350), len(full_name) * dp(10) + dp(40)))
            tooltip_height = dp(60)
            tooltip_content = Label(
                text=full_name,
                font_size=dp(16),
                bold=True,
                color=(1, 1, 1, 1),
                size_hint=(1, 1),
                halign="center",
                valign="center",
            )
            self.tooltip_popup = Popup(
                content=tooltip_content,
                size_hint=(None, None),
                size=(tooltip_width, tooltip_height),
                background_color=(0.1, 0.1, 0.1, 0.7),
                title="",
                separator_height=0,
                auto_dismiss=True,
                overlay_color=(0, 0, 0, 0),
            )
            window_center_x = Window.width / 2
            window_center_y = Window.height / 2
            self.tooltip_popup.pos = (
                window_center_x - tooltip_width / 2,
                window_center_y - tooltip_height / 2,
            )
            self.tooltip_popup.open()
            Clock.schedule_once(lambda _: self.hide_tooltip(), 3.0)
        except Exception as exc:
            logger.error("Error showing simple tooltip: %s", exc)

    def show_tooltip_positioned_on_card(self, mouse_pos) -> None:
        try:
            if self.tooltip_popup:
                return
            full_name = str(self.playlist_data.get("name", "Untitled Playlist"))
            tooltip_content = Label(
                text=full_name,
                font_size=dp(13),
                color=(1, 1, 1, 1),
                text_size=(None, None),
                halign="center",
                valign="center",
                size_hint=(1, 1),
            )
            tooltip_width = max(dp(150), min(dp(350), len(full_name) * dp(8) + dp(20)))
            tooltip_height = dp(40)
            self.tooltip_popup = Popup(
                content=tooltip_content,
                size_hint=(None, None),
                size=(tooltip_width, tooltip_height),
                background_color=(0.1, 0.1, 0.1, 0.95),
                title="",
                separator_height=0,
                auto_dismiss=True,
                overlay_color=(0, 0, 0, 0),
            )
            try:
                if isinstance(mouse_pos, (list, tuple)) and len(mouse_pos) >= 2:
                    mouse_x, mouse_y = float(mouse_pos[0]), float(mouse_pos[1])
                else:
                    logger.warning("Invalid mouse_pos format: %s", mouse_pos)
                    return
                tooltip_x = mouse_x - tooltip_width / 2
                tooltip_y = mouse_y + dp(25)
                tooltip_x = max(
                    dp(5), min(tooltip_x, Window.width - tooltip_width - dp(5))
                )
                if tooltip_y + tooltip_height > Window.height - dp(10):
                    tooltip_y = mouse_y - tooltip_height - dp(10)
                tooltip_y = max(
                    dp(5), min(tooltip_y, Window.height - tooltip_height - dp(5))
                )
                self.tooltip_popup.pos = (tooltip_x, tooltip_y)
            except Exception as exc:
                logger.error("Error positioning hover tooltip: %s", exc)
                self.tooltip_popup.pos = (100, 100)
            self.tooltip_popup.open()
            Clock.schedule_once(lambda _: self.hide_tooltip(), 4.0)
        except Exception as exc:
            logger.error("Error showing hover tooltip: %s", exc)

    def close_detailed_popup(self):
        """Close the detailed popup and clean up resources."""
        # Stop any periodic refreshes and clear all flags
        setattr(self, "_periodic_refresh_active", False)
        setattr(self, "_lightweight_refresh_mode", False)
        setattr(self, "_is_refreshing", False)

        if self.detailed_popup:
            self.detailed_popup.dismiss()
            self.detailed_popup = None

    def _cancel_hover(self) -> None:
        if hasattr(self, "mouse_over"):
            self.mouse_over = False
        if getattr(self, "hover_event", None):
            self.hover_event.cancel()
            self.hover_event = None
        self.hide_tooltip()

    def schedule_graphics_update(self, *args) -> None:
        if not self._graphics_update_scheduled:
            self._graphics_update_scheduled = True
            Clock.schedule_once(self._do_graphics_update, 0.1)

    def _do_graphics_update(self, dt) -> None:
        self._graphics_update_scheduled = False
        self.update_graphics()

    def init_checkbox_graphics(self, dt) -> None:
        try:
            self.checkbox.canvas.before.clear()
            with self.checkbox.canvas.before:
                Color(1, 1, 1, 0.98)
                self.checkbox_bg = Rectangle(
                    size=(dp(16), dp(16)), pos=(self.checkbox.x, self.checkbox.y)
                )
        except Exception as exc:
            logger.warning("Error initializing checkbox graphics: %s", exc)

    def update_info_bg(self, instance, value) -> None:
        try:
            self.info_bg.size = instance.size
            self.info_bg.pos = instance.pos
        except AttributeError:
            pass

    def update_graphics(self, *args) -> None:
        try:
            self.card_bg.size = self.size
            self.card_bg.pos = self.pos
            if hasattr(self, "checkbox_bg"):
                self.checkbox_bg.size = (dp(18), dp(18))
                self.checkbox_bg.pos = (self.checkbox.x, self.checkbox.y)
        except AttributeError:
            Clock.schedule_once(self.init_checkbox_graphics, 0.1)
        except Exception as exc:
            logger.warning("Error updating graphics: %s", exc)

    def on_checkbox_change(self, checkbox, value) -> None:
        try:
            with self.canvas.before:
                Color(0.2, 0.4, 0.6, 1) if value else Color(0.18, 0.18, 0.18, 1)
                self.card_bg = Rectangle(size=self.size, pos=self.pos)
            self.checkbox.canvas.before.clear()
            with self.checkbox.canvas.before:
                Color(1, 1, 1, 0.98)
                self.checkbox_bg = Rectangle(
                    size=(dp(18), dp(18)), pos=(self.checkbox.x, self.checkbox.y)
                )
        except Exception as exc:
            logger.warning("Error changing checkbox state: %s", exc)

    def __del__(self):
        try:
            if hasattr(Window, "_playlist_hover_manager"):
                Window._playlist_hover_manager.unregister_card(self)
            for attr in ["hover_event", "long_press_event", "pending_single_click"]:
                timer = getattr(self, attr, None)
                if timer:
                    timer.cancel()
        except Exception:
            pass


__all__ = ["PlaylistCard"]
