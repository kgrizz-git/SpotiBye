"""Main application screen (backend-mode-only) — no v2 standalone dependencies."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from ...shared.logging_config import logger
from . import main_screen_cache, main_screen_error_popup, main_screen_logout
from .main_screen_export import MainScreenExportOrchestrator
from .main_screen_scheduler import KivyScheduler
from .main_screen_filenames import (
    generate_default_filename,
    get_file_extension,
    increment_filename_suffix,
    sanitize_export_filename_component,
    selected_export_format,
)
from .main_screen_sort_filter import filter_playlists, sort_playlists
from ..ui.layouts import ResponsiveGridLayout
from ..config.backend_config import EXPORT_DIR as SAVE_DIR

# Import backend cache explorer adapter if available.
# Prefer the runtime path used by the packaged launcher (`src.frontend...`),
# then fall back to `frontend...` for editable/local package layouts.
try:
    from src.frontend.screens.cache_explorer_adapter import create_cache_explorer

    BACKEND_CACHE_EXPLORER_AVAILABLE = True
except ImportError:
    try:
        from frontend.screens.cache_explorer_adapter import create_cache_explorer

        BACKEND_CACHE_EXPLORER_AVAILABLE = True
    except ImportError:
        BACKEND_CACHE_EXPLORER_AVAILABLE = False


class MainScreen(Screen):
    """Main screen with playlist selection and export (backend mode only)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend_adapter = None
        self.playlists: List[dict] = []
        self.playlist_widgets: List = []
        self.selected_playlist_ids: Set[str] = set()
        self.filtered_playlists: List[dict] = []
        self.current_sort_key = "default"
        self.current_sort_reverse = False
        self.search_query = ""
        self._search_trigger = None  # For debouncing search
        self._search_debounce_seconds = 0.3  # 300ms debounce interval
        self._sort_trigger = None  # For debouncing sort
        self._sort_debounce_seconds = 0.5  # 500ms debounce interval for sorting
        self._backend_error_phase = "idle"
        self._backend_error_step = ""
        self.trace_mode_enabled = os.getenv("SPOTIBYE_TRACE_MODE", "0").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._current_trace_id: str = ""
        self._backend_resume_popup: Optional[Popup] = None
        
        # Refactored orchestration components
        self.scheduler = KivyScheduler()
        self.export_orchestrator = MainScreenExportOrchestrator(self, self.scheduler)
        
        self.build_ui()

    def _set_backend_error_context(self, phase: str, step: str = "") -> None:
        """Track current backend operation phase so error popups include precise context."""
        self._backend_error_phase = phase
        self._backend_error_step = step

    def initialize_with_backend(self, backend_adapter) -> None:
        """Enable backend-integrated mode for playlist loading/export actions."""
        self.backend_adapter = backend_adapter
        if self.backend_adapter:
            self.backend_adapter.set_callbacks(
                playlists_loaded=self._on_backend_playlists_loaded,
                error=self._on_backend_error,
                progress=self._on_backend_progress,
            )

    @property
    def backend_mode_enabled(self) -> bool:
        """Return True when screen should use backend adapter APIs."""
        return self.backend_adapter is not None

    def build_ui(self) -> None:
        main_layout = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(6))
        header = self._create_header()
        controls = self._create_controls()
        scroll = self._create_scroll_view()
        self.playlist_layout = ResponsiveGridLayout()
        scroll.add_widget(self.playlist_layout)
        export_section = self._create_export_section()

        main_layout.add_widget(header)
        main_layout.add_widget(controls)
        main_layout.add_widget(scroll)
        main_layout.add_widget(export_section)

        self.add_widget(main_layout)

    def _create_header(self) -> RelativeLayout:
        header = RelativeLayout(size_hint_y=None, height=dp(40))
        header.add_widget(
            Label(
                text="Audio Analysis powered by ReccoBeats API",
                font_size=dp(12),
                color=(0.2, 0.8, 0.2, 1),
                size_hint=(None, None),
                size=(dp(280), dp(40)),
                text_size=(dp(270), None),
                halign="left",
                valign="center",
                pos_hint={"x": 0, "y": 0},
            )
        )

        header.add_widget(
            Label(
                text="Select Playlists to Export",
                font_size=dp(18),
                bold=True,
                size_hint=(None, None),
                size=(dp(300), dp(40)),
                text_size=(dp(300), None),
                halign="center",
                valign="center",
                pos_hint={"center_x": 0.5, "y": 0},
            )
        )

        app = App.get_running_app()
        username = getattr(app, "username", "Unknown User")
        self.username_label = Label(
            text=f"Logged in as: {username}",
            font_size=dp(14),
            color=(0.8, 0.8, 0.8, 1),
            size_hint=(None, None),
            size=(dp(200), dp(40)),
            text_size=(dp(190), None),
            halign="right",
            valign="center",
            pos_hint={"right": 1, "y": 0},
        )
        header.add_widget(self.username_label)
        return header

    def _create_controls(self) -> BoxLayout:
        # Main horizontal layout for all controls
        controls = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),  # Reduced from dp(10) to give more space to filter
            padding=(dp(3), 0, dp(3), 0),  # Reduced from (dp(5), 0, dp(5), 0)
        )

        # 1. Left section - Sort controls
        sort_section = BoxLayout(
            orientation="horizontal", size_hint_x=None, width=dp(245), spacing=dp(4)
        )  # Reduced width and spacing

        # Sort label
        sort_section.add_widget(
            Label(
                text="Sort:",
                size_hint_x=None,
                width=dp(35),
                font_size=dp(14),
                color=(0.9, 0.9, 0.9, 1),
            )
        )

        # Sort spinner
        self.sort_spinner = Spinner(
            text="Default",
            values=["Default", "Playlist Title", "# of Tracks", "Owner"],
            size_hint_x=None,
            width=dp(100),
            font_size=dp(14),
            text_size=(dp(90), None),
            halign="center",
            background_color=[0.55, 0.55, 0.55, 1],
        )
        self.sort_spinner.bind(on_press=self.configure_dropdown)
        self.sort_spinner.bind(text=self.on_sort_change)
        sort_section.add_widget(self.sort_spinner)

        # Sort direction button
        self.by_label = Label(
            text="By:",
            size_hint_x=None,
            width=dp(25),
            font_size=dp(14),
            color=(0.9, 0.9, 0.9, 1),
        )
        sort_section.add_widget(self.by_label)

        self.sort_direction_btn = Button(
            text="A-Z",
            size_hint_x=None,
            width=dp(60),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        self.sort_direction_btn.bind(on_press=self.toggle_sort_direction)
        sort_section.add_widget(self.sort_direction_btn)

        # 2. Search section - More flexible layout
        search_section = BoxLayout(
            orientation="horizontal",
            size_hint_x=0.85,  # Further increased from 0.8 to give more space to filter
            spacing=dp(2),  # Reduced from dp(3)
            padding=(dp(5), 0, dp(3), 0),  # Further reduced padding
        )

        # Search label and input
        search_section.add_widget(
            Label(
                text="Search:",
                size_hint_x=None,
                width=dp(55),  # Reduced width for better space utilization
                font_size=dp(14),
                color=(0.9, 0.9, 0.9, 1),
            )
        )

        # Container for search input and clear button
        search_input_container = BoxLayout(
            orientation="horizontal",
            size_hint_x=1,  # Take all available space
            spacing=dp(2),  # Reduced spacing between input and clear button
        )

        self.search_input = TextInput(
            multiline=False,
            size_hint_x=0.94,  # Further increased from 0.92 to make textbox even wider
            size_hint_max_x=dp(350),  # Maximum width to prevent excessive expansion
            font_size=dp(14),
            hint_text="Filter playlists...",
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.6, 0.6, 0.6, 1),
            padding=(dp(8), dp(5)),  # Added top/bottom padding for better appearance
            background_active="",
            background_normal="",
            write_tab=False,
        )
        search_input_container.add_widget(self.search_input)

        # Clear search button
        clear_btn = Button(
            text="×",
            size_hint_x=None,
            width=dp(28),  # Reduced from 30 to save space
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=dp(18),
            color=(0.8, 0.8, 0.8, 1),
        )
        clear_btn.bind(on_press=self.clear_search)
        search_input_container.add_widget(clear_btn)

        search_section.add_widget(search_input_container)
        self.search_input.bind(text=self.on_search_text)

        # 3. Action buttons section - Right-aligned with more compact layout
        action_buttons = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(325),  # Further reduced from 340 for more compact layout
            spacing=dp(2),  # Further reduced from dp(3)
        )

        # Add Select All button
        self.select_all_btn = Button(
            text="Select All",
            size_hint_x=None,
            width=dp(100),
            background_color=[0.25, 0.85, 0.25, 1],
            font_size=dp(14),
        )
        self.select_all_btn.bind(on_press=self.toggle_select_all)
        action_buttons.add_widget(self.select_all_btn)

        # Add Clear All button
        clear_btn = Button(
            text="Clear All",
            size_hint_x=None,
            width=dp(100),
            background_color=[0.8, 0.2, 0.2, 1],
            font_size=dp(14),
        )
        clear_btn.bind(on_press=self.deselect_all)
        action_buttons.add_widget(clear_btn)

        reload_btn = Button(
            text="Reload",
            size_hint_x=None,
            width=dp(90),
            background_color=[0.32, 0.32, 0.88, 1],
            font_size=dp(14),
        )
        reload_btn.bind(on_press=self.load_playlists_with_cache)
        action_buttons.add_widget(reload_btn)

        # 4. Right section - Selection counter and logout
        right_section = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(220),  # Further reduced from 230 for more compact layout
            spacing=dp(3),  # Further reduced from dp(5)
            padding=(dp(3), 0, dp(3), 0),  # Further reduced padding
        )

        # Selection counter
        self.selection_label = Label(
            text="0 selected",
            font_size=dp(14),
            halign="right",
            color=(0.88, 0.88, 0.88, 1),
            size_hint_x=0.7,
        )
        right_section.add_widget(self.selection_label)

        # Logout button
        logout_btn = Button(
            text="Logout",
            size_hint_x=None,
            width=dp(75),
            height=dp(35),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        logout_btn.bind(on_press=self.logout)
        right_section.add_widget(logout_btn)

        # Add all sections to the main layout in order
        controls.add_widget(sort_section)  # Left: Sort controls
        controls.add_widget(search_section)  # Left-Center: Search
        controls.add_widget(
            Widget(size_hint_x=0.2)
        )  # Further reduced spacer from 0.3 to 0.2
        controls.add_widget(action_buttons)  # Action buttons (right-aligned)
        controls.add_widget(right_section)  # Selection counter & logout (far right)
        return controls

    def _create_scroll_view(self) -> ScrollView:
        return ScrollView(
            scroll_type=["bars", "content"],
            bar_width=dp(10),
            bar_color=[0.75, 0.75, 0.75, 0.8],
            bar_inactive_color=[0.75, 0.75, 0.75, 0.4],
            scroll_wheel_distance=dp(50),
            smooth_scroll_end=10,
            scroll_distance=dp(40),
            scroll_timeout=45,
            always_overscroll=True,
            do_scroll_x=False,
        )

    def _create_export_section(self) -> BoxLayout:
        export_section = BoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(238), spacing=dp(8)
        )
        with export_section.canvas.before:
            Color(0.1, 0.1, 0.1, 1)
            export_section.bg_rect = Rectangle(
                size=export_section.size, pos=export_section.pos
            )
        export_section.bind(
            size=lambda instance, value: setattr(export_section.bg_rect, "size", value),
            pos=lambda instance, value: setattr(export_section.bg_rect, "pos", value),
        )

        filename_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8)
        )
        filename_layout.add_widget(
            Label(text="Filename:", size_hint_x=None, width=dp(70), font_size=dp(15))
        )
        self.filename_input = TextInput(
            text=self._generate_default_filename("xlsx"),
            multiline=False,
            size_hint_y=None,
            height=dp(30),
            font_size=dp(15),
        )
        filename_layout.add_widget(self.filename_input)
        export_section.add_widget(filename_layout)

        # Add format selection dropdown
        format_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8)
        )
        format_layout.add_widget(
            Label(text="Format:", size_hint_x=None, width=dp(60), font_size=dp(15))
        )

        self.format_spinner = Spinner(
            text="XLSX",  # Default format
            values=["XLSX", "CSV", "JSON"],
            size_hint_x=None,
            width=dp(100),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        self.format_spinner.bind(text=self.on_format_change)
        format_layout.add_widget(self.format_spinner)
        export_section.add_widget(format_layout)

        save_info = Label(
            text=f"Files will be saved to: {SAVE_DIR}",
            font_size=dp(13),
            color=(0.75, 0.75, 0.75, 1),
            size_hint_y=None,
            height=dp(25),
            halign="center",
        )
        export_section.add_widget(save_info)

        self.export_btn = Button(
            text="Export Selected Playlists",
            size_hint_y=None,
            height=dp(45),
            font_size=dp(16),
        )
        self.export_btn.bind(on_press=self.start_export)
        export_section.add_widget(self.export_btn)

        self.cancel_btn = Button(
            text="Cancel Export",
            size_hint_y=None,
            height=dp(45),
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
            opacity=0,
            disabled=True,
        )
        self.cancel_btn.bind(on_press=self.cancel_export)
        export_section.add_widget(self.cancel_btn)

        self.progress_bar = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(18)
        )
        export_section.add_widget(self.progress_bar)

        # Create status bar container with RelativeLayout for proper overlay
        from kivy.uix.relativelayout import RelativeLayout

        status_bar_container = RelativeLayout(size_hint_y=None, height=dp(30))

        # Centered status label with adjusted positioning for perfect center
        self.status_label = Label(
            text="Ready to export",
            font_size=dp(14),
            size_hint=(None, None),
            width=dp(400),  # Fixed width
            height=dp(30),
            halign="center",  # Center text within the label
            valign="middle",  # Vertically center text
            pos_hint={"center_x": 0.51, "center_y": 0.5},  # Center
        )
        status_bar_container.add_widget(self.status_label)

        # Button container positioned on the right
        button_container = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(200),
            height=dp(30),
            spacing=dp(5),
            pos_hint={"right": 1, "top": 1},  # Position on the right
        )

        # Clear Cache button
        self.clear_cache_btn = Button(
            text="Clear Cache",
            size_hint_x=None,
            width=dp(90),
            height=dp(28),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12),
        )
        self.clear_cache_btn.bind(on_press=self.show_clear_cache_confirmation)
        button_container.add_widget(self.clear_cache_btn)

        # Cache Explorer button
        self.cache_explorer_btn = Button(
            text="Cache Explorer",
            size_hint_x=None,
            width=dp(100),
            height=dp(28),
            background_color=[0.3, 0.5, 0.8, 1],
            font_size=dp(12),
        )
        self.cache_explorer_btn.bind(on_press=self.open_cache_explorer)
        button_container.add_widget(self.cache_explorer_btn)

        status_bar_container.add_widget(button_container)
        export_section.add_widget(status_bar_container)
        return export_section

    # Sorting --------------------------------------------------------------
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
            self.sort_playlists()
        except Exception as exc:
            logger.warning("Error changing sort: %s", exc)

    def update_sort_controls_visibility(self) -> None:
        try:
            if not hasattr(self, "by_label") or not hasattr(self, "sort_direction_btn"):
                return
            is_default = self.current_sort_key == "default"
            if is_default:
                self.by_label.opacity = 0
                self.by_label.width = 0
                self.sort_direction_btn.opacity = 0
                self.sort_direction_btn.width = 0
                self.sort_direction_btn.disabled = True
            else:
                self.by_label.opacity = 1
                self.by_label.width = dp(25)
                self.sort_direction_btn.opacity = 1
                self.sort_direction_btn.width = dp(67)
                self.sort_direction_btn.disabled = False
        except Exception as exc:
            logger.error("Error updating sort controls visibility: %s", exc)

    def update_sort_direction_button(self) -> None:
        try:
            if self.current_sort_key in ["default", "name", "owner"]:
                if self.current_sort_reverse:
                    self.sort_direction_btn.text = "Z-A"
                    self.sort_direction_btn.background_color = [0.7, 0.4, 0.4, 1]
                else:
                    self.sort_direction_btn.text = "A-Z"
                    self.sort_direction_btn.background_color = [0.55, 0.55, 0.55, 1]
            else:
                if self.current_sort_reverse:
                    self.sort_direction_btn.text = "+ -"
                    self.sort_direction_btn.background_color = [0.7, 0.4, 0.4, 1]
                else:
                    self.sort_direction_btn.text = "- +"
                    self.sort_direction_btn.background_color = [0.55, 0.55, 0.55, 1]
        except Exception as exc:
            logger.warning("Error updating sort direction button: %s", exc)

    def toggle_sort_direction(self, *_args) -> None:
        if self.sort_direction_btn.disabled:
            return
        self.current_sort_reverse = not self.current_sort_reverse
        self.update_sort_direction_button()
        self.sort_playlists()

    def sort_playlists(self) -> None:
        """Sort the currently displayed playlists with debouncing.

        This method preserves the current search filter while applying the sort.
        Uses debouncing to prevent rapid UI updates during sort changes.
        """
        try:
            # Cancel existing sort trigger if any
            if self._sort_trigger:
                self._sort_trigger.cancel()

            # Schedule debounced sort
            self._sort_trigger = Clock.schedule_once(
                lambda dt: self._perform_sort(), self._sort_debounce_seconds
            )

        except Exception as exc:
            logger.warning("Error scheduling sort: %s", exc)

    def _perform_sort(self) -> None:
        """Perform the actual sorting operation.

        Subclasses must override this to use their specific widget type.
        """
        raise NotImplementedError("_perform_sort must be implemented by subclass")

    # Screen lifecycle ---------------------------------------------------
    def on_format_change(self, spinner, text):
        """Update filename extension when format changes."""
        current_filename = self.filename_input.text or ""
        if current_filename:
            # Remove existing extension and add new one
            base_name = os.path.splitext(current_filename)[0]
            extension = self._get_file_extension(text.lower())
            self.filename_input.text = f"{base_name}{extension}"
        else:
            # If no filename, generate default with selected format
            self.filename_input.text = self._generate_default_filename(text.lower())

    def _get_file_extension(self, format_type: str) -> str:
        """Get file extension for export format."""
        return get_file_extension(format_type)

    def _selected_export_format(self) -> str:
        """Return the user-selected export format ('xlsx', 'csv', or 'json')."""
        spinner = getattr(self, "format_spinner", None)
        text = (spinner.text if spinner else "") or "xlsx"
        return selected_export_format(text)

    def on_enter(self):
        app = App.get_running_app()
        username = getattr(app, "username", "Unknown User")
        self.username_label.text = f"Logged in as: {username}"
        Clock.schedule_once(lambda _: self.update_sort_controls_visibility(), 0.2)

        # Update filename with correct username after login
        if hasattr(self, "filename_input"):
            current_filename = self.filename_input.text or ""
            # Only update if the current filename still has the default 'user' or 'None' placeholder
            if "_user_" in current_filename or "_None_" in current_filename:
                self.filename_input.text = self._generate_default_filename()

        self.load_playlists_with_cache()

    # Playlist loading ---------------------------------------------------
    def load_playlists_with_cache(self, *_args) -> None:
        self.current_sort_key = "default"
        self.current_sort_reverse = False
        self.sort_spinner.text = "Default"
        self.update_sort_direction_button()
        self.status_label.text = "Loading playlists..."
        self.playlist_layout.clear_widgets()
        self.playlist_widgets = []
        self.update_selection_counter()

        if self.backend_mode_enabled:
            self.filtered_playlists = []
            self.backend_adapter.load_playlists(force_refresh=False)
            return

        # Standalone path not supported in this frontend-only build.
        self.status_label.text = "Backend adapter not initialized"

    @mainthread
    def _on_backend_playlists_loaded(self, playlists: List[Dict[str, Any]]) -> None:
        """Callback for playlist data loaded via backend adapter."""
        self.playlists = playlists or []
        self.display_playlists_with_cache()

    @mainthread
    def _on_backend_error(self, error_msg: str) -> None:
        """Callback for backend loading errors."""
        logger.error("Backend request failed: %s", error_msg)
        message = str(error_msg or "")
        self.status_label.text = f"Backend error: {message}"
        self._show_backend_error_popup(message)

        lowered = message.lower()
        auth_related = (
            "session expired" in lowered
            or "session expired or invalid" in lowered
            or "token expired" in lowered
            or "unauthorized" in lowered
            or "http 401" in lowered
        )

        if auth_related:
            self.status_label.text = "Session expired. Please login again."
            app = App.get_running_app()
            if app and hasattr(app, "prompt_reauthentication"):
                Clock.schedule_once(
                    lambda _: app.prompt_reauthentication(
                        "Your Spotify session expired. Log out and log in again."
                    ),
                    0.2,
                )
            elif app and hasattr(app, "logout"):
                Clock.schedule_once(lambda _: app.logout(), 0.2)
            elif app and hasattr(app, "switch_to_login"):
                Clock.schedule_once(lambda _: app.switch_to_login(), 0.2)

    def _show_backend_error_popup(self, message: str) -> None:
        main_screen_error_popup.show_backend_error_popup(self, message)

    def _get_recoverable_backend_export_context(self) -> Optional[Dict[str, Any]]:
        return main_screen_error_popup.get_recoverable_backend_export_context(self)

    @mainthread
    def _on_backend_progress(self, status: str) -> None:
        """Callback for backend progress updates."""
        if status:
            trace = self._current_trace_id or "none"
            logger.info("[backend-progress][trace=%s] %s", trace, status)
            self.status_label.text = status

    def load_playlists_worker_with_cache(self) -> None:
        """Worker for loading playlists. In backend mode, delegates to backend adapter."""
        if self.backend_mode_enabled:
            self.backend_adapter.load_playlists(force_refresh=False)
            return

        # Standalone path not supported in this frontend-only build.
        Clock.schedule_once(
            lambda _: setattr(
                self.status_label, "text", "Backend adapter not initialized"
            ),
            0,
        )

    def display_playlists_with_cache(self) -> None:
        """Display playlists in the UI. 

        Subclasses must override this to create the appropriate widget type.
        """
        raise NotImplementedError(
            "display_playlists_with_cache must be implemented by subclass"
        )

    def _make_playlist_widget(self, playlist: dict):
        """Create a playlist widget for a playlist row."""
        raise NotImplementedError("_make_playlist_widget must be implemented by subclass")

    def _get_filtered_playlists(self) -> List[dict]:
        """Get playlists filtered by the current search query."""
        try:
            return filter_playlists(self.playlists, self.search_query)
        except Exception as exc:
            logger.warning("Error filtering playlists: %s", exc)
            return self.playlists.copy()

    def _sort_playlists(self, playlists: List[dict]) -> List[dict]:
        """Sort playlists based on current sort key and direction."""
        return sort_playlists(playlists, self.current_sort_key, self.current_sort_reverse)

    def update_status_with_cache_info(self) -> None:
        """Update the status bar with current playlist information.

        Subclasses may override to add backend/cache-specific details.
        """
        try:
            total_playlists = len(self.playlists)

            if self.search_query:
                shown_playlists = len(self.filtered_playlists)
                if shown_playlists == 0:
                    self.status_label.text = f'No matches for "{self.search_query}"'
                else:
                    self.status_label.text = (
                        f"Showing {shown_playlists} of {total_playlists}"
                    )
            else:
                self.status_label.text = f"Loaded {total_playlists} playlists"

        except Exception as exc:
            logger.warning("Error updating status: %s", exc, exc_info=True)
            self.status_label.text = "Error updating status"

    def on_search_text(self, instance, value):
        """Handle search text changes with debouncing.

        Args:
            instance: The TextInput instance that triggered the event
            value: The current text in the search input
        """
        # Cancel any pending search
        if self._search_trigger:
            self._search_trigger.cancel()

        # Schedule a new search with debouncing
        self._search_trigger = Clock.schedule_once(
            lambda dt: self._perform_search(value), self._search_debounce_seconds
        )

    def _perform_search(self, search_text):
        """Perform the actual search operation.

        Args:
            search_text: The text to search for
        """
        try:
            self.search_query = search_text.strip().lower()
            self.display_playlists_with_cache()
        except Exception as exc:
            logger.error("Error performing search: %s", exc)
            self.status_label.text = f"Search error: {str(exc)}"

    def clear_search(self, instance):
        """Clear search and reset display.

        Args:
            instance: The button instance that triggered this action
        """
        # Cancel any pending search
        if self._search_trigger:
            self._search_trigger.cancel()
            self._search_trigger = None

        self.search_input.text = ""
        self.search_query = ""

        # Reset to first page and refresh display
        if hasattr(self.playlist_layout.parent, "scroll_y"):
            self.playlist_layout.parent.scroll_y = 1.0

        self.display_playlists_with_cache()

    def toggle_select_all(self, instance):
        """Toggle selection for currently visible (filtered) playlists only."""
        if not hasattr(self, "playlist_widgets") or not self.playlist_widgets:
            return

        # Check if all are selected
        all_selected = all(w.checkbox.active for w in self.playlist_widgets)

        # Toggle all checkboxes
        for widget in self.playlist_widgets:
            widget.checkbox.active = not all_selected

        # Update visible-toggle label and global counter
        self.update_selection_counter()

    def update_selection_counter(self):
        """Update the selection counter label."""
        try:
            selected = len(self.selected_playlist_ids)
            total = len(self.playlists)
            self.selection_label.text = f"Selected: {selected} of {total}"
            self._update_select_all_button_label()
        except Exception as exc:
            logger.warning("Error updating selection counter: %s", exc)

    def _update_select_all_button_label(self) -> None:
        """Update visible-toggle button text based on currently filtered cards."""
        if not hasattr(self, "select_all_btn"):
            return

        visible_cards = len(self.playlist_widgets)
        if visible_cards == 0:
            self.select_all_btn.text = "Select Visible"
            return

        visible_selected = sum(1 for w in self.playlist_widgets if w.checkbox.active)
        if visible_selected == visible_cards:
            self.select_all_btn.text = "Unselect Visible"
        else:
            self.select_all_btn.text = "Select Visible"

    def _on_playlist_checkbox_changed(self, playlist_id: str, is_active: bool) -> None:
        """Keep playlist selection persistent even when filtering hides cards."""
        if not playlist_id:
            return
        if is_active:
            self.selected_playlist_ids.add(playlist_id)
        else:
            self.selected_playlist_ids.discard(playlist_id)
        self.update_selection_counter()

    def select_all(self, *_args) -> None:
        for widget in self.playlist_widgets:
            widget.checkbox.active = True
        self.update_selection_counter()

    def deselect_all(self, *_args) -> None:
        self.selected_playlist_ids.clear()
        for widget in self.playlist_widgets:
            widget.checkbox.active = False
        self.update_selection_counter()

    # Export --------------------------------------------------------------
    def start_export(self, *_args) -> None:
        try:
            if not self.backend_mode_enabled:
                self.status_label.text = "Backend adapter not initialized"
                return

            selected = [
                p for p in self.playlists if p.get("id") in self.selected_playlist_ids
            ]
            if not selected:
                Popup(
                    title="No Selection",
                    content=Label(
                        text="Please select at least one playlist to export."
                    ),
                    size_hint=(0.6, 0.4),
                ).open()
                return

            self._start_backend_export(selected)
        except Exception as exc:
            logger.error("Error starting export: %s", exc)
            self.status_label.text = f"Export error: {exc}"
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def _start_backend_export(self, playlists) -> None:
        """Start export flow using backend endpoints (no direct Spotify API calls)."""
        self.export_orchestrator._start_backend_export(playlists)

    def _show_backend_overwrite_confirmation(
        self, playlists, output_path, filename
    ) -> None:
        self.export_orchestrator._show_backend_overwrite_confirmation(playlists, output_path, filename)

    def _handle_backend_overwrite_confirmed(
        self, popup, playlists, output_path
    ) -> None:
        self.export_orchestrator._handle_backend_overwrite_confirmed(popup, playlists, output_path)

    def begin_backend_export(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Begin backend export worker for one or more playlists."""
        self.export_orchestrator.begin_backend_export(playlists, output_path, resume_saved_job)

    def _sanitize_export_filename_component(self, value: str) -> str:
        """Sanitize playlist/file name component for cross-platform safe filenames."""
        return sanitize_export_filename_component(value)

    def _build_backend_output_path(
        self, base_output_path: str, multiple: bool
    ) -> str:
        """Build output file path for backend export."""
        return self.export_orchestrator._build_backend_output_path(base_output_path, multiple)

    def backend_export_worker(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Worker that generates and downloads export(s) from backend API."""
        self.export_orchestrator.backend_export_worker(playlists, output_path, resume_saved_job)

    def _backend_export_fallback_sequential(
        self, playlists: List[Dict[str, Any]], base_output_path: str
    ) -> Dict[str, Any]:
        """Fallback export strategy: generate one backend export per playlist."""
        return self.export_orchestrator._backend_export_fallback_sequential(playlists, base_output_path)

    def cancel_export(self, *_args) -> None:
        self.export_orchestrator.cancel_export(*_args)

    def cleanup_after_export(self) -> None:
        self.export_orchestrator.cleanup_after_export()

    def handle_export_cancelled(self) -> None:
        """Handle the UI updates when an export is cancelled."""
        self.export_orchestrator.handle_export_cancelled()

    def logout(self, *_args) -> None:
        main_screen_logout.logout(self, *_args)

    def _show_logout_confirmation(self, selected_count: int) -> None:
        main_screen_logout.show_logout_confirmation(self, selected_count)

    def _handle_logout_confirmed(self, popup) -> None:
        main_screen_logout.handle_logout_confirmed(self, popup)

    def _perform_logout(self) -> None:
        main_screen_logout.perform_logout()

    # Cache management ----------------------------------------------------
    def show_clear_cache_confirmation(self, *_args) -> None:
        main_screen_cache.show_clear_cache_confirmation(self, *_args)

    def clear_all_cache(self, popup) -> None:
        main_screen_cache.clear_all_cache(self, popup)

    def open_cache_explorer(self, *_args) -> None:
        main_screen_cache.open_cache_explorer(
            self, BACKEND_CACHE_EXPLORER_AVAILABLE, create_cache_explorer, *_args
        )

    # Filename helpers ----------------------------------------------------
    def _generate_default_filename(self, format_type: str = "xlsx") -> str:
        app = App.get_running_app()
        username = getattr(app, "username", None)
        return generate_default_filename(username, format_type)

    def _refresh_filename_after_export(self):
        if hasattr(self, "filename_input"):
            try:
                current_filename = self.filename_input.text or ""
                new_default = self._generate_default_filename()

                # Check if current filename is the same as the new default (without extension)
                current_base = os.path.splitext(current_filename)[0]
                new_base = os.path.splitext(new_default)[0]

                if current_base == new_base:
                    # Apply incremental numbering
                    self.filename_input.text = self._increment_filename_suffix(
                        new_default
                    )
                else:
                    # Use the new default filename
                    self.filename_input.text = new_default
            except Exception:
                pass

    def _increment_filename_suffix(self, filename: str) -> str:
        """Increment filename suffix from _2 to _5 as needed."""
        return increment_filename_suffix(filename)
