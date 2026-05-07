"""Main application screen (backend-mode-only) — no v2 standalone dependencies."""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from kivy.app import App
from kivy.core.clipboard import Clipboard
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
from ..state import current_export_job
from ..ui.layouts import ResponsiveGridLayout
from ..ui.cache_explorer import CacheExplorerPopup
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
        self._search_debounce_seconds = 0.3  # 300ms debounce time
        self._sort_trigger = None  # For debouncing sort
        self._sort_debounce_seconds = 0.5  # 500ms debounce time for sorting
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
        extensions = {"xlsx": ".xlsx", "csv": ".csv", "json": ".json"}
        return extensions.get(format_type, ".xlsx")

    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show user-friendly error dialog."""

        def show_dialog(dt):
            popup = Popup(
                title=title,
                content=Label(text=message, text_size=dp(14)),
                size_hint=(0.8, 0.4),
                auto_dismiss=True,
            )
            popup.open()

        Clock.schedule_once(show_dialog)

    def _log_error(self, error_message: str, context: Dict = None) -> None:
        """Log error with context information for debugging."""
        if context:
            logger.error(f"Export Error: {error_message}", extra=context)
        else:
            logger.error(f"Export Error: {error_message}")

    def _update_export_status(self, message):
        """Update the status label from a background thread."""

        def update():
            self.status_label.text = message

        Clock.schedule_once(lambda dt: update())

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
        """Show backend error details with one-click copy for diagnostics sharing."""
        if not message:
            return

        phase = self._backend_error_phase or "unknown"
        step = self._backend_error_step or "n/a"
        trace_id = self._current_trace_id or "n/a"
        details = (
            f"Time: {datetime.now().isoformat()}\n"
            f"Screen: MainScreen\n"
            f"TraceId: {trace_id}\n"
            f"Phase: {phase}\n"
            f"Step: {step}\n"
            f"Error: {message}"
        )
        resumable_export = self._get_recoverable_backend_export_context()

        def _open_popup(_dt):
            if self._backend_resume_popup:
                self._backend_resume_popup.dismiss()

            content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

            if resumable_export:
                resume_summary = Label(
                    text=resumable_export["summary"],
                    size_hint_y=None,
                    height=dp(72),
                    halign="center",
                    valign="middle",
                    text_size=(dp(420), None),
                )
                content.add_widget(resume_summary)

            details_input = TextInput(
                text=details,
                readonly=True,
                multiline=True,
                size_hint_y=1,
                font_size=dp(13),
                background_color=(0.15, 0.15, 0.15, 1),
                foreground_color=(1, 1, 1, 1),
            )
            content.add_widget(details_input)

            if resumable_export:
                action_row = BoxLayout(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(42),
                    spacing=dp(8),
                )
                resume_btn = Button(
                    text="Resume Export", background_color=[0.2, 0.6, 0.35, 1]
                )
                discard_btn = Button(
                    text="Discard Resume", background_color=[0.55, 0.35, 0.2, 1]
                )
                action_row.add_widget(resume_btn)
                action_row.add_widget(discard_btn)
                content.add_widget(action_row)

            button_row = BoxLayout(
                orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8)
            )
            copy_btn = Button(
                text="Copy Error Details", background_color=[0.2, 0.55, 0.85, 1]
            )
            close_btn = Button(text="Close", background_color=[0.45, 0.45, 0.45, 1])
            button_row.add_widget(copy_btn)
            button_row.add_widget(close_btn)
            content.add_widget(button_row)

            popup = Popup(
                title="Backend Error Details",
                content=content,
                size_hint=(0.86, 0.58),
                auto_dismiss=True,
            )
            self._backend_resume_popup = popup

            def _copy_details(_instance):
                Clipboard.copy(details)
                self.status_label.text = "Backend error details copied to clipboard"

            def _clear_resume_job(_instance):
                if self.backend_adapter:
                    self.backend_adapter.clear_active_export_job()
                self.status_label.text = "Discarded resumable export state"
                popup.dismiss()

            def _resume_export(_instance):
                popup.dismiss()
                self.begin_backend_export(
                    resumable_export["playlists"],
                    resumable_export["output_path"],
                    resume_saved_job=True,
                )

            copy_btn.bind(on_press=_copy_details)
            close_btn.bind(on_press=popup.dismiss)
            if resumable_export:
                resume_btn.bind(on_press=_resume_export)
                discard_btn.bind(on_press=_clear_resume_job)
            popup.bind(
                on_dismiss=lambda *_args: setattr(self, "_backend_resume_popup", None)
            )
            popup.open()

        Clock.schedule_once(_open_popup, 0)

    def _get_recoverable_backend_export_context(self) -> Optional[Dict[str, Any]]:
        """Return cached resumable export details when the current failure can be resumed."""
        if not self.backend_adapter:
            return None

        if self._backend_error_phase not in {
            "chunked-combined",
            "sequential-fallback",
            "failed",
        }:
            return None

        cached_job = self.backend_adapter.get_active_export_job()
        if not isinstance(cached_job, dict):
            return None

        playlist_ids = cached_job.get("playlist_ids") or []
        playlist_names = cached_job.get("playlist_names") or []
        output_path = str(cached_job.get("output_path") or "")
        job_id = str(cached_job.get("job_id") or "")
        current_cursor = str(cached_job.get("current_cursor") or "")
        current_resume_token = str(cached_job.get("current_resume_token") or "")
        if (
            not isinstance(playlist_ids, list)
            or not playlist_ids
            or not output_path
            or not job_id
        ):
            return None

        if not current_cursor or not current_resume_token:
            return None

        playlists = []
        for index, playlist_id in enumerate(playlist_ids):
            playlist_name = (
                playlist_names[index]
                if isinstance(playlist_names, list) and index < len(playlist_names)
                else playlist_id
            )
            playlists.append({"id": playlist_id, "name": playlist_name})

        processed = int(cached_job.get("processed_count", 0) or 0)
        total = int(cached_job.get("playlist_count", len(playlists)) or len(playlists))
        phase = str(cached_job.get("phase") or "collect")
        summary = (
            f"A resumable export is still available.\n"
            f"Progress: {processed}/{total} playlists\n"
            f"Phase: {phase}\n"
            f"Output: {os.path.basename(output_path)}"
        )

        return {
            "playlists": playlists,
            "output_path": output_path,
            "summary": summary,
        }

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
        """Display playlists with current search and sort applied.

        Subclasses must override this to create the appropriate widget type.
        """
        raise NotImplementedError(
            "display_playlists_with_cache must be implemented by subclass"
        )

    def _get_filtered_playlists(self) -> List[dict]:
        """Get playlists filtered by the current search query.

        Returns:
            List of playlist dictionaries that match the search criteria
        """
        if not self.search_query:
            return self.playlists.copy()

        try:
            # Compile search query once for better performance
            search_terms = [
                term.strip() for term in self.search_query.split() if term.strip()
            ]

            def matches_search(playlist):
                playlist_name = playlist.get("name", "").lower()
                owner_name = playlist.get("owner", {}).get("display_name", "").lower()

                # Match all search terms (AND logic)
                return all(
                    term in playlist_name or term in owner_name for term in search_terms
                )

            return [p for p in self.playlists if matches_search(p)]

        except Exception as exc:
            logger.warning("Error filtering playlists: %s", exc)
            return self.playlists.copy()

    def _sort_playlists(self, playlists: List[dict]) -> List[dict]:
        """Sort playlists based on current sort key and direction.

        Args:
            playlists: List of playlist dictionaries to sort

        Returns:
            Sorted list of playlists
        """
        if not playlists or self.current_sort_key == "default":
            return playlists

        def key_fn(pl):
            if self.current_sort_key == "name":
                return pl.get("name", "").lower()
            if self.current_sort_key == "tracks":
                return pl.get("tracks", {}).get("total", 0)
            if self.current_sort_key == "owner":
                return pl.get("owner", {}).get("display_name", "").lower()
            return ""

        return sorted(playlists, key=key_fn, reverse=self.current_sort_reverse)

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
        if not self.backend_adapter:
            self.status_label.text = "Backend export unavailable"
            return

        filename = (
            (self.filename_input.text or "").strip()
            if hasattr(self, "filename_input")
            else ""
        )
        if not filename:
            filename = os.path.splitext(self._generate_default_filename())[0]

        if not filename.lower().endswith(".xlsx"):
            filename = f"{os.path.splitext(filename)[0]}.xlsx"

        output_path = os.path.join(SAVE_DIR, filename)

        if len(playlists) == 1 and os.path.exists(output_path):
            self._show_backend_overwrite_confirmation(playlists, output_path, filename)
        else:
            self.begin_backend_export(playlists, output_path)

    def _show_backend_overwrite_confirmation(
        self, playlists, output_path, filename
    ) -> None:
        popup_content = BoxLayout(
            orientation="vertical", spacing=dp(10), padding=dp(20)
        )
        popup_content.add_widget(Widget(size_hint_y=0.3))
        popup_content.add_widget(
            Label(
                text=f'The file "{filename}" already exists.\n\nDo you want to overwrite it?',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(80),
                halign="center",
                valign="center",
                text_size=(dp(400), dp(80)),
            )
        )
        popup_content.add_widget(Widget(size_hint_y=0.4))
        buttons = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(15)
        )
        cancel_btn = Button(
            text="Cancel",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.6, 0.6, 0.6, 1],
        )
        overwrite_btn = Button(
            text="Overwrite",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
        )
        buttons.add_widget(cancel_btn)
        buttons.add_widget(overwrite_btn)
        popup_content.add_widget(buttons)
        popup = Popup(
            title="File Already Exists",
            content=popup_content,
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
        )
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        overwrite_btn.bind(
            on_press=lambda *_: self._handle_backend_overwrite_confirmed(
                popup, playlists, output_path
            )
        )
        popup.open()

    def _handle_backend_overwrite_confirmed(
        self, popup, playlists, output_path
    ) -> None:
        popup.dismiss()
        self.begin_backend_export(playlists, output_path)

    def begin_backend_export(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Begin backend export worker for one or more playlists."""
        try:
            if self.trace_mode_enabled:
                self._current_trace_id = uuid.uuid4().hex[:12]
            else:
                self._current_trace_id = ""

            if self.backend_adapter:
                self.backend_adapter.set_trace_id(self._current_trace_id)

            self.export_btn.disabled = True
            self.cancel_btn.opacity = 1
            self.cancel_btn.disabled = True
            total = len(playlists) if isinstance(playlists, list) else 1
            filename = os.path.basename(output_path)
            self.status_label.text = (
                f"Exporting {total} playlist(s) via backend to: {filename}"
            )
            self.progress_bar.value = 5
            threading.Thread(
                target=self.backend_export_worker,
                args=(playlists, output_path, resume_saved_job),
                daemon=True,
            ).start()
        except Exception as exc:
            logger.error("Error beginning backend export: %s", exc)
            self.export_btn.disabled = False
            self.cancel_btn.opacity = 0
            self.cancel_btn.disabled = True
            self.status_label.text = f"Export error: {exc}"
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def _sanitize_export_filename_component(self, value: str) -> str:
        """Sanitize playlist/file name component for cross-platform safe filenames."""
        safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", value or "").strip()
        return safe[:80] if safe else "playlist"

    def _build_backend_output_path(
        self, playlist: dict, base_output_path: str, multiple: bool
    ) -> str:
        """Build output file path for backend export."""
        if not multiple:
            return base_output_path

        base_dir = os.path.dirname(base_output_path)
        base_name = os.path.splitext(os.path.basename(base_output_path))[0]
        return os.path.join(base_dir, f"{base_name}.xlsx")

    def backend_export_worker(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Worker that generates and downloads export(s) from backend API."""
        try:
            if not self.backend_adapter:
                Clock.schedule_once(
                    lambda _: setattr(
                        self.status_label, "text", "Backend export unavailable"
                    ),
                    0,
                )
                Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
                return

            selected_playlists = (
                playlists if isinstance(playlists, list) else [playlists]
            )
            valid_playlists = [
                p for p in selected_playlists if isinstance(p, dict) and p.get("id")
            ]
            if not valid_playlists:
                Clock.schedule_once(
                    lambda _: setattr(
                        self.status_label,
                        "text",
                        "No valid playlists selected for export",
                    ),
                    0,
                )
                Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
                Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)
                return

            total = len(valid_playlists)
            playlist_ids = [p.get("id") for p in valid_playlists if p.get("id")]
            target_path = self._build_backend_output_path(
                valid_playlists[0], output_path, total > 1
            )
            resume_context = {
                "allow_resume": resume_saved_job,
                "output_path": target_path,
                "playlist_names": [p.get("name", "") for p in valid_playlists],
            }
            self._set_backend_error_context(
                "chunked-combined", f"prepare ({total} playlists)"
            )

            Clock.schedule_once(
                lambda _, t=total: setattr(
                    self.status_label,
                    "text",
                    f"Generating combined backend export for {t} playlist(s) (chunked)...",
                ),
                0,
            )
            Clock.schedule_once(lambda _: setattr(self.progress_bar, "value", 35), 0)

            # Use chunked processing to avoid per-invocation subrequest caps on Cloudflare free plans.
            self._set_backend_error_context("chunked-combined", "generate")
            export_info = self.backend_adapter.generate_batch_export_chunked(
                playlist_ids,
                "xlsx",
                chunk_size=1,
                report_errors=False,
                resume_context=resume_context,
            )
            if not export_info:
                # Fallback: combined export can exceed Worker subrequest limits for larger selections.
                # Degrade gracefully to sequential per-playlist exports so the user still gets files.
                self._set_backend_error_context("sequential-fallback", "start")
                fallback_result = self._backend_export_fallback_sequential(
                    valid_playlists, output_path
                )
                if (
                    fallback_result.get("success_count", 0) > 0
                    and fallback_result.get("failed_count", 0) == 0
                ):
                    self.backend_adapter.clear_active_export_job()
                    Clock.schedule_once(
                        lambda _, c=total: setattr(
                            self.status_label,
                            "text",
                            f"Export complete ({c} playlist(s), sequential fallback)",
                        ),
                        0,
                    )
                    Clock.schedule_once(
                        lambda _: setattr(self.progress_bar, "value", 100), 0
                    )
                elif fallback_result.get("success_count", 0) > 0:
                    s = fallback_result.get("success_count", 0)
                    f = fallback_result.get("failed_count", 0)
                    Clock.schedule_once(
                        lambda _, ss=s, ff=f: setattr(
                            self.status_label,
                            "text",
                            f"Partial export complete ({ss} saved, {ff} failed)",
                        ),
                        0,
                    )
                    Clock.schedule_once(
                        lambda _: setattr(self.progress_bar, "value", 100), 0
                    )
                    self._show_backend_error_popup(
                        f"Sequential fallback partially succeeded. Saved {s}, failed {f}. Failed IDs: {', '.join(fallback_result.get('failed_playlist_ids', []))}"
                    )
                else:
                    Clock.schedule_once(
                        lambda _: setattr(
                            self.status_label,
                            "text",
                            "Backend combined export generation failed",
                        ),
                        0,
                    )
                    self._show_backend_error_popup(
                        "Combined export generation failed after retries and sequential fallback"
                    )
                Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
                Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)
                return

            export_id = (
                export_info.get("job_id", "") if isinstance(export_info, dict) else ""
            )
            total_tracks = (
                int(export_info.get("track_count", 0))
                if isinstance(export_info, dict)
                else 0
            )
            if total_tracks >= 2400:
                Clock.schedule_once(
                    lambda _, t=total_tracks: setattr(
                        self.status_label,
                        "text",
                        f"Large export ({t} tracks): reliability mode active; combined file prioritized over heavy styling.",
                    ),
                    0,
                )

            self._set_backend_error_context(
                "chunked-combined", f'download job={export_id or "unknown"}'
            )

            Clock.schedule_once(
                lambda _: setattr(
                    self.status_label, "text", "Downloading combined backend export..."
                ),
                0,
            )
            Clock.schedule_once(lambda _: setattr(self.progress_bar, "value", 80), 0)

            success = self.backend_adapter.download_batch_export(
                export_id, target_path, report_errors=False
            )
            if not success:
                # Recovery pass: try to resume/reconcile combined job state and retry combined download once.
                self._set_backend_error_context(
                    "chunked-combined", "recover-and-redownload"
                )
                Clock.schedule_once(
                    lambda _: setattr(
                        self.status_label,
                        "text",
                        "Combined download failed; retrying combined export recovery...",
                    ),
                    0,
                )
                recovered_info = self.backend_adapter.generate_batch_export_chunked(
                    playlist_ids,
                    "xlsx",
                    chunk_size=1,
                    max_steps=240,
                    report_errors=False,
                    resume_context={
                        "allow_resume": True,
                        "output_path": target_path,
                        "playlist_names": [p.get("name", "") for p in valid_playlists],
                    },
                )
                recovered_export_id = (
                    recovered_info.get("job_id", "")
                    if isinstance(recovered_info, dict)
                    else ""
                ) or export_id

                if recovered_export_id:
                    success = self.backend_adapter.download_batch_export(
                        recovered_export_id, target_path, report_errors=False
                    )

            if not success:
                self._set_backend_error_context(
                    "sequential-fallback", "start-after-combined-failure"
                )
                # Combined path failed after retries/recovery; now degrade to sequential.
                time.sleep(6.0)
                fallback_result = self._backend_export_fallback_sequential(
                    valid_playlists, output_path
                )
                if (
                    fallback_result.get("success_count", 0) > 0
                    and fallback_result.get("failed_count", 0) == 0
                ):
                    self.backend_adapter.clear_active_export_job(export_id or None)
                    Clock.schedule_once(
                        lambda _, c=total: setattr(
                            self.status_label,
                            "text",
                            f"Export complete ({c} playlist(s), sequential fallback)",
                        ),
                        0,
                    )
                    Clock.schedule_once(
                        lambda _: setattr(self.progress_bar, "value", 100), 0
                    )
                elif fallback_result.get("success_count", 0) > 0:
                    s = fallback_result.get("success_count", 0)
                    f = fallback_result.get("failed_count", 0)
                    Clock.schedule_once(
                        lambda _, ss=s, ff=f: setattr(
                            self.status_label,
                            "text",
                            f"Partial export complete ({ss} saved, {ff} failed)",
                        ),
                        0,
                    )
                    Clock.schedule_once(
                        lambda _: setattr(self.progress_bar, "value", 100), 0
                    )
                    self._show_backend_error_popup(
                        f"Combined download failed; sequential fallback partially succeeded. Saved {s}, failed {f}. Failed IDs: {', '.join(fallback_result.get('failed_playlist_ids', []))}"
                    )
                else:
                    Clock.schedule_once(
                        lambda _: setattr(
                            self.status_label,
                            "text",
                            "Backend combined export download failed",
                        ),
                        0,
                    )
                    self._show_backend_error_popup(
                        "Combined export download failed after retries and sequential fallback"
                    )
                Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
                Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)
                return

            Clock.schedule_once(lambda _: setattr(self.progress_bar, "value", 100), 0)
            Clock.schedule_once(
                lambda _, c=total: setattr(
                    self.status_label, "text", f"Export complete ({c} playlist(s))"
                ),
                0,
            )
            self._set_backend_error_context(
                "completed", f"combined success ({total} playlists)"
            )
            Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

        except Exception as exc:
            logger.error("Backend export failed: %s", exc)
            Clock.schedule_once(
                lambda _, err=str(exc): setattr(
                    self.status_label, "text", f"Backend export failed: {err}"
                ),
                0,
            )
            self._set_backend_error_context("failed", "backend-export-worker")
            self._show_backend_error_popup(f"Backend export failed: {str(exc)}")
            Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def _backend_export_fallback_sequential(
        self, playlists: List[Dict[str, Any]], base_output_path: str
    ) -> Dict[str, Any]:
        """Fallback export strategy: generate one backend export per playlist.

        Returns summary with partial successes preserved.
        """
        if not self.backend_adapter:
            return {
                "success_count": 0,
                "failed_count": len(playlists),
                "failed_playlist_ids": [
                    p.get("id", "") for p in playlists if p.get("id")
                ],
            }

        total = len(playlists)
        base_dir = os.path.dirname(base_output_path)
        base_name = os.path.splitext(os.path.basename(base_output_path))[0]
        success_count = 0
        failed_playlist_ids: List[str] = []

        for index, playlist in enumerate(playlists, start=1):
            playlist_id = playlist.get("id")
            if not playlist_id:
                continue

            playlist_name = self._sanitize_export_filename_component(
                playlist.get("name", "playlist")
            )
            safe_id = self._sanitize_export_filename_component(playlist_id)
            target_file = f"{base_name} - {playlist_name} ({safe_id}).xlsx"
            target_path = os.path.join(base_dir, target_file)

            Clock.schedule_once(
                lambda _, i=index, t=total, name=playlist_name: setattr(
                    self.status_label,
                    "text",
                    f"Fallback [{i}/{t}] Generating export for {name}...",
                ),
                0,
            )
            Clock.schedule_once(
                lambda _, i=index, t=total: setattr(
                    self.progress_bar, "value", int(((i - 1) / t) * 100) + 10
                ),
                0,
            )
            self._set_backend_error_context(
                "sequential-fallback",
                f"generate {index}/{total} playlist={playlist_id}",
            )

            export_info = self.backend_adapter.generate_export(
                playlist_id, "xlsx", report_errors=False
            )
            if not export_info:
                failed_playlist_ids.append(playlist_id)
                continue

            export_id = (
                export_info.get("job_id", "") if isinstance(export_info, dict) else ""
            )

            Clock.schedule_once(
                lambda _, i=index, t=total, name=playlist_name: setattr(
                    self.status_label,
                    "text",
                    f"Fallback [{i}/{t}] Downloading export for {name}...",
                ),
                0,
            )
            Clock.schedule_once(
                lambda _, i=index, t=total: setattr(
                    self.progress_bar, "value", int(((i - 1) / t) * 100) + 60
                ),
                0,
            )
            self._set_backend_error_context(
                "sequential-fallback",
                f"download {index}/{total} playlist={playlist_id}",
            )

            success = self.backend_adapter.download_export(
                playlist_id, export_id, target_path
            )
            if not success:
                failed_playlist_ids.append(playlist_id)
                continue

            success_count += 1

            # Pace long sequential runs slightly to reduce backend/upstream burst failures.
            if index < total:
                time.sleep(0.5)

        if success_count > 0 and not failed_playlist_ids:
            self._set_backend_error_context(
                "completed", f"sequential fallback success ({total} playlists)"
            )
        elif success_count > 0:
            self._set_backend_error_context(
                "completed",
                f"sequential fallback partial ({success_count}/{total} playlists)",
            )
        else:
            self._set_backend_error_context(
                "failed", f"sequential fallback failed ({total} playlists)"
            )

        return {
            "success_count": success_count,
            "failed_count": len(failed_playlist_ids),
            "failed_playlist_ids": failed_playlist_ids,
        }

    def cancel_export(self, *_args) -> None:
        global current_export_job
        if current_export_job:
            current_export_job["cancelled"] = True
            if self.backend_adapter:
                self.backend_adapter.clear_active_export_job()
            self.cancel_btn.disabled = True
            self.cancel_btn.text = "Cancelling..."
            self.status_label.text = "Cancelling export..."
            Clock.schedule_once(lambda _: self.cleanup_after_export(), 3.0)
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 3.0)

    def cleanup_after_export(self) -> None:
        self.export_btn.disabled = False
        self.cancel_btn.opacity = 0
        self.cancel_btn.disabled = True
        self.cancel_btn.text = "Cancel Export"
        self.progress_bar.value = 0
        if self.backend_adapter:
            self.backend_adapter.set_trace_id(None)

    def handle_export_cancelled(self) -> None:
        """Handle the UI updates when an export is cancelled."""
        self.status_label.text = "Export cancelled"
        self.cleanup_after_export()
        Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def logout(self, *_args) -> None:
        selected_count = sum(1 for w in self.playlist_widgets if w.checkbox.active)
        if selected_count > 0:
            self._show_logout_confirmation(selected_count)
        else:
            self._perform_logout()

    def _show_logout_confirmation(self, selected_count: int) -> None:
        content = BoxLayout(orientation="vertical", spacing=dp(15), padding=dp(20))
        content.add_widget(Widget(size_hint_y=0.2))
        plural = "playlist" if selected_count == 1 else "playlists"
        content.add_widget(
            Label(
                text=f"You have {selected_count} {plural} selected.\n\nAre you sure you want to log out?",
                font_size=dp(16),
                size_hint_y=None,
                height=dp(80),
                halign="center",
                valign="center",
                text_size=(dp(400), dp(80)),
            )
        )
        content.add_widget(Widget(size_hint_y=0.3))
        buttons = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(15)
        )
        cancel_btn = Button(
            text="Cancel",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.6, 0.6, 0.6, 1],
        )
        logout_btn = Button(
            text="Log Out",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
        )
        buttons.add_widget(cancel_btn)
        buttons.add_widget(logout_btn)
        content.add_widget(buttons)
        popup = Popup(
            title="Confirm Logout",
            content=content,
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
        )
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        logout_btn.bind(on_press=lambda *_: self._handle_logout_confirmed(popup))
        popup.open()

    def _handle_logout_confirmed(self, popup) -> None:
        popup.dismiss()
        self._perform_logout()

    def _perform_logout(self) -> None:
        try:
            app = App.get_running_app()
            # Use the comprehensive auth state clearing function from the app
            app.logout()
        except Exception as exc:
            logger.error("Error performing logout: %s", exc)

    # Cache management ----------------------------------------------------
    def show_clear_cache_confirmation(self, *_args) -> None:
        """Show confirmation dialog for clearing cache."""
        content = BoxLayout(orientation="vertical", spacing=dp(15), padding=dp(20))
        content.add_widget(Widget(size_hint_y=0.2))

        content.add_widget(
            Label(
                text="This will clear all downloaded data. Are you sure?",
                font_size=dp(16),
                size_hint_y=None,
                height=dp(60),
                halign="center",
                valign="center",
                text_size=(dp(400), dp(60)),
            )
        )
        content.add_widget(Widget(size_hint_y=0.3))

        buttons = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(15)
        )
        cancel_btn = Button(
            text="No",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.6, 0.6, 0.6, 1],
        )
        confirm_btn = Button(
            text="Yes",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
        )

        buttons.add_widget(cancel_btn)
        buttons.add_widget(confirm_btn)
        content.add_widget(buttons)

        popup = Popup(
            title="Confirm Cache Clear",
            content=content,
            size_hint=(0.7, 0.5),
            auto_dismiss=False,
        )

        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        confirm_btn.bind(on_press=lambda *_: self.clear_all_cache(popup))
        popup.open()

    def clear_all_cache(self, popup) -> None:
        """Clear all cache data and update UI."""
        try:
            popup.dismiss()
            self.status_label.text = "Clearing cache..."
            self.update_status_with_cache_info()

            success_popup = Popup(
                title="Cache Cleared",
                content=Label(text="All cached data has been cleared successfully."),
                size_hint=(0.6, 0.4),
                auto_dismiss=True,
            )
            success_popup.open()

            logger.info("Cache cleared by user")

        except Exception as exc:
            logger.error("Error clearing cache: %s", exc)
            self.status_label.text = f"Error clearing cache: {exc}"

            error_popup = Popup(
                title="Error",
                content=Label(text=f"Failed to clear cache: {exc}"),
                size_hint=(0.6, 0.4),
                auto_dismiss=True,
            )
            error_popup.open()

    def open_cache_explorer(self, *_args) -> None:
        """Open the cache explorer popup with backend support."""
        try:
            if BACKEND_CACHE_EXPLORER_AVAILABLE:
                # Use backend-aware cache explorer
                explorer_popup = create_cache_explorer()
                logger.info("Backend cache explorer opened by user")
            else:
                # Use standard cache explorer
                explorer_popup = CacheExplorerPopup()
                logger.info("Standard cache explorer opened by user")

            explorer_popup.open()
        except Exception as exc:
            logger.error("Error opening cache explorer: %s", exc)
            self.status_label.text = f"Error opening cache explorer: {exc}"

            error_popup = Popup(
                title="Cache Explorer Error",
                content=Label(text=f"Failed to open cache explorer:\n{exc}"),
                size_hint=(0.6, 0.4),
                auto_dismiss=True,
            )
            error_popup.open()

    # Filename helpers ----------------------------------------------------
    def _generate_default_filename(self, format_type: str = "xlsx") -> str:
        # Get username from the app with better fallback
        app = App.get_running_app()
        username = getattr(app, "username", None)

        # Handle None or empty username cases
        if not username or username == "None":
            username = "user"

        # Format: YYYY-MM-DD_HH-MM-SSAM/PM
        timestamp = datetime.now().strftime("%Y-%m-%d_%I-%M-%S%p")

        return f"Spotify_Playlists_{username}_{timestamp}.{format_type}"

    def _refresh_filename_after_export(self):
        if hasattr(self, "filename_input"):
            try:
                current_filename = self.filename_input.text or ""
                new_default = self._generate_default_filename()

                # Check if current filename is the same as the new default (without extension)
                current_base = current_filename.replace(".xlsx", "")
                new_base = new_default.replace(".xlsx", "")

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
        """Increment filename suffix from _2 to _5 as needed.

        Args:
            filename: Base filename (e.g., 'spotify_playlists_20231122_143022.xlsx')

        Returns:
            Filename with incremented suffix or original if no suffix pattern found
        """
        base = filename.replace(".xlsx", "")

        # Check for existing suffix pattern
        if base.endswith("_5"):
            # Already at _5, keep as is (could cycle back to _2 or stay at _5)
            return filename
        elif base.endswith("_4"):
            return base.replace("_4", "_5") + ".xlsx"
        elif base.endswith("_3"):
            return base.replace("_3", "_4") + ".xlsx"
        elif base.endswith("_2"):
            return base.replace("_2", "_3") + ".xlsx"
        else:
            # No suffix, add _2
            return base + "_2.xlsx"
