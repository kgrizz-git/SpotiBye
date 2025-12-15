"""Main application screen (playlist selection, caching, export)."""

from __future__ import annotations

import os
import openpyxl
import platform
import re
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import spotipy
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
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from spotipy.exceptions import SpotifyException

from ..config import SAVE_DIR
from ..auth.login_screen import create_spotify_client_with_refresh
from ..caching.persistent_cache import persistent_cache
from ..caching.track_cache import (
    cache_reccobeats_features,
    cache_spotify_track,
    get_cached_reccobeats_features,
    get_cached_spotify_track,
    get_or_update_playlist_tracks,
)
from ..logging_config import logger
from ..services.reccobeats import ReccoBeatsAPI
from ..state import current_export_job
from ..ui.layouts import ResponsiveGridLayout
from ..ui.playlist_card import PlaylistCard
from ..ui.cache_explorer import CacheExplorerPopup

# Import backend cache explorer adapter if available
try:
    from ..frontend.screens.cache_explorer_adapter import create_cache_explorer
    BACKEND_CACHE_EXPLORER_AVAILABLE = True
except ImportError:
    BACKEND_CACHE_EXPLORER_AVAILABLE = False
from ..utils.platform_utils import is_mobile_platform


reccobeats_api = ReccoBeatsAPI()


class MainScreen(Screen):
    """Main screen with playlist selection and export."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.playlists: List[dict] = []
        self.playlist_widgets: List[PlaylistCard] = []
        self.filtered_playlists: List[dict] = []
        self.current_sort_key = 'default'
        self.current_sort_reverse = False
        self.search_query = ""
        self._search_trigger = None  # For debouncing search
        self._search_debounce_seconds = 0.3  # 300ms debounce time
        self._sort_trigger = None  # For debouncing sort
        self._sort_debounce_seconds = 0.5  # 500ms debounce time for sorting
        self.build_ui()

    def build_ui(self) -> None:
        main_layout = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(6))
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
                text='Audio Analysis powered by ReccoBeats API',
                font_size=dp(12),
                color=(0.2, 0.8, 0.2, 1),
                size_hint=(None, None),
                size=(dp(280), dp(40)),
                text_size=(dp(270), None),
                halign='left',
                valign='center',
                pos_hint={'x': 0, 'y': 0},
            )
        )

        header.add_widget(
            Label(
                text='Select Playlists to Export',
                font_size=dp(18),
                bold=True,
                size_hint=(None, None),
                size=(dp(300), dp(40)),
                text_size=(dp(300), None),
                halign='center',
                valign='center',
                pos_hint={'center_x': 0.5, 'y': 0},
            )
        )

        app = App.get_running_app()
        username = getattr(app, 'username', 'Unknown User')
        self.username_label = Label(
            text=f'Logged in as: {username}',
            font_size=dp(14),
            color=(0.8, 0.8, 0.8, 1),
            size_hint=(None, None),
            size=(dp(200), dp(40)),
            text_size=(dp(190), None),
            halign='right',
            valign='center',
            pos_hint={'right': 1, 'y': 0},
        )
        header.add_widget(self.username_label)
        return header

    def _create_controls(self) -> BoxLayout:
        # Main horizontal layout for all controls
        controls = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),  # Reduced from dp(10) to give more space to filter
            padding=(dp(3), 0, dp(3), 0)  # Reduced from (dp(5), 0, dp(5), 0)
        )

        # 1. Left section - Sort controls
        sort_section = BoxLayout(orientation='horizontal', size_hint_x=None, width=dp(245), spacing=dp(4))  # Reduced width and spacing
        
        # Sort label
        sort_section.add_widget(
            Label(
                text='Sort:',
                size_hint_x=None,
                width=dp(35),
                font_size=dp(14),
                color=(0.9, 0.9, 0.9, 1)
            )
        )
        
        # Sort spinner
        self.sort_spinner = Spinner(
            text='Default',
            values=['Default', 'Playlist Title', '# of Tracks', 'Owner'],
            size_hint_x=None,
            width=dp(100),
            font_size=dp(14),
            text_size=(dp(90), None),
            halign='center',
            background_color=[0.55, 0.55, 0.55, 1],
        )
        self.sort_spinner.bind(on_press=self.configure_dropdown)
        self.sort_spinner.bind(text=self.on_sort_change)
        sort_section.add_widget(self.sort_spinner)

        # Sort direction button
        self.by_label = Label(
            text='By:',
            size_hint_x=None,
            width=dp(25),
            font_size=dp(14),
            color=(0.9, 0.9, 0.9, 1)
        )
        sort_section.add_widget(self.by_label)

        self.sort_direction_btn = Button(
            text='A-Z',
            size_hint_x=None,
            width=dp(60),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        self.sort_direction_btn.bind(on_press=self.toggle_sort_direction)
        sort_section.add_widget(self.sort_direction_btn)
        
        # 2. Search section - More flexible layout
        search_section = BoxLayout(
            orientation='horizontal',
            size_hint_x=0.85,  # Further increased from 0.8 to give more space to filter
            spacing=dp(2),   # Reduced from dp(3)
            padding=(dp(5), 0, dp(3), 0)  # Further reduced padding
        )
        
        # Search label and input
        search_section.add_widget(
            Label(
                text='Search:',
                size_hint_x=None,
                width=dp(55),  # Reduced width for better space utilization
                font_size=dp(14),
                color=(0.9, 0.9, 0.9, 1)
            )
        )
        
        # Container for search input and clear button
        search_input_container = BoxLayout(
            orientation='horizontal',
            size_hint_x=1,  # Take all available space
            spacing=dp(2)   # Reduced spacing between input and clear button
        )
        
        self.search_input = TextInput(
            multiline=False,
            size_hint_x=0.94,  # Further increased from 0.92 to make textbox even wider
            size_hint_max_x=dp(350),  # Maximum width to prevent excessive expansion
            font_size=dp(14),
            hint_text='Filter playlists...',
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.6, 0.6, 0.6, 1),
            padding=(dp(8), dp(5)),  # Added top/bottom padding for better appearance
            background_active='',
            background_normal='',
            write_tab=False
        )
        search_input_container.add_widget(self.search_input)
        
        # Clear search button
        clear_btn = Button(
            text='×',
            size_hint_x=None,
            width=dp(28),  # Reduced from 30 to save space
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=dp(18),
            color=(0.8, 0.8, 0.8, 1)
        )
        clear_btn.bind(on_press=self.clear_search)
        search_input_container.add_widget(clear_btn)
        
        search_section.add_widget(search_input_container)
        self.search_input.bind(text=self.on_search_text)
        
        # 3. Action buttons section - Right-aligned with more compact layout
        action_buttons = BoxLayout(
            orientation='horizontal',
            size_hint_x=None,
            width=dp(325),  # Further reduced from 340 for more compact layout
            spacing=dp(2)   # Further reduced from dp(3)
        )
        
        # Add Select All button
        self.select_all_btn = Button(
            text='Select All',
            size_hint_x=None,
            width=dp(100),
            background_color=[0.25, 0.85, 0.25, 1],
            font_size=dp(14),
        )
        self.select_all_btn.bind(on_press=self.toggle_select_all)
        action_buttons.add_widget(self.select_all_btn)
        
        # Add Clear All button
        clear_btn = Button(
            text='Clear All',
            size_hint_x=None,
            width=dp(100),
            background_color=[0.8, 0.2, 0.2, 1],
            font_size=dp(14),
        )
        clear_btn.bind(on_press=self.deselect_all)
        action_buttons.add_widget(clear_btn)
        
        reload_btn = Button(
            text='Reload',
            size_hint_x=None,
            width=dp(90),
            background_color=[0.32, 0.32, 0.88, 1],
            font_size=dp(14),
        )
        reload_btn.bind(on_press=self.load_playlists_with_cache)
        action_buttons.add_widget(reload_btn)
        
        # 4. Right section - Selection counter and logout
        right_section = BoxLayout(
            orientation='horizontal',
            size_hint_x=None,
            width=dp(220),  # Further reduced from 230 for more compact layout
            spacing=dp(3),  # Further reduced from dp(5)
            padding=(dp(3), 0, dp(3), 0)  # Further reduced padding
        )
        
        # Selection counter
        self.selection_label = Label(
            text='0 selected',
            font_size=dp(14),
            halign='right',
            color=(0.88, 0.88, 0.88, 1),
            size_hint_x=0.7
        )
        right_section.add_widget(self.selection_label)
        
        # Logout button
        logout_btn = Button(
            text='Logout',
            size_hint_x=None,
            width=dp(75),
            height=dp(35),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        logout_btn.bind(on_press=self.logout)
        right_section.add_widget(logout_btn)
        
        # Add all sections to the main layout in order
        controls.add_widget(sort_section)      # Left: Sort controls
        controls.add_widget(search_section)    # Left-Center: Search
        controls.add_widget(Widget(size_hint_x=0.2))  # Further reduced spacer from 0.3 to 0.2
        controls.add_widget(action_buttons)    # Action buttons (right-aligned)
        controls.add_widget(right_section)     # Selection counter & logout (far right)
        return controls

    def _create_scroll_view(self) -> ScrollView:
        return ScrollView(
            scroll_type=['bars', 'content'],
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
        export_section = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(238), spacing=dp(8))
        with export_section.canvas.before:
            Color(0.1, 0.1, 0.1, 1)
            export_section.bg_rect = Rectangle(size=export_section.size, pos=export_section.pos)
        export_section.bind(
            size=lambda instance, value: setattr(export_section.bg_rect, 'size', value),
            pos=lambda instance, value: setattr(export_section.bg_rect, 'pos', value),
        )

        filename_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        filename_layout.add_widget(Label(text='Filename:', size_hint_x=None, width=dp(70), font_size=dp(15)))
        self.filename_input = TextInput(
            text=self._generate_default_filename(),
            multiline=False,
            size_hint_y=None,
            height=dp(30),
            font_size=dp(15),
        )
        filename_layout.add_widget(self.filename_input)
        export_section.add_widget(filename_layout)

        save_info = Label(
            text=f'Files will be saved to: {SAVE_DIR}',
            font_size=dp(13),
            color=(0.75, 0.75, 0.75, 1),
            size_hint_y=None,
            height=dp(25),
            halign='center',
        )
        export_section.add_widget(save_info)

        self.export_btn = Button(text='Export Selected Playlists', size_hint_y=None, height=dp(45), font_size=dp(16))
        self.export_btn.bind(on_press=self.start_export)
        export_section.add_widget(self.export_btn)

        self.cancel_btn = Button(
            text='Cancel Export',
            size_hint_y=None,
            height=dp(45),
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
            opacity=0,
            disabled=True,
        )
        self.cancel_btn.bind(on_press=self.cancel_export)
        export_section.add_widget(self.cancel_btn)

        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(18))
        export_section.add_widget(self.progress_bar)

        self.status_label = Label(text='Ready to export', font_size=dp(14), size_hint_y=None, height=dp(30))
        
        # Create status bar container with buttons
        status_bar_container = BoxLayout(
            orientation='horizontal', 
            size_hint_y=None, 
            height=dp(30),
            spacing=dp(10)
        )
        
        # Left spacer for centering
        left_spacer = Widget(size_hint_x=0.4)
        status_bar_container.add_widget(left_spacer)
        
        # Centered status label
        status_bar_container.add_widget(self.status_label)
        
        # Right spacer for centering
        right_spacer = Widget(size_hint_x=0.2)
        status_bar_container.add_widget(right_spacer)
        
        # Button container on the far right
        button_container = BoxLayout(
            orientation='horizontal',
            size_hint_x=None,
            width=dp(200),
            spacing=dp(5)
        )
        
        # Clear Cache button
        self.clear_cache_btn = Button(
            text='Clear Cache',
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
            text='Cache Explorer',
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
            dropdown = getattr(spinner, '_dropdown', None)
            if dropdown and dropdown.children:
                for option in dropdown.children[0].children:
                    if hasattr(option, 'height'):
                        option.height = dp(30)
                        option.size_hint_y = None
                    if hasattr(option, 'font_size'):
                        option.font_size = dp(12)
        except Exception as exc:
            logger.warning("Error configuring dropdown: %s", exc)

    def on_sort_change(self, spinner, text) -> None:
        try:
            sort_map = {
                'Default': 'default',
                'Playlist Title': 'name',
                '# of Tracks': 'tracks',
                'Owner': 'owner',
            }
            self.current_sort_key = sort_map.get(text, 'default')
            Clock.schedule_once(lambda _: self.update_sort_controls_visibility(), 0.1)
            self.update_sort_direction_button()
            self.sort_playlists()
        except Exception as exc:
            logger.warning("Error changing sort: %s", exc)

    def update_sort_controls_visibility(self) -> None:
        try:
            if not hasattr(self, 'by_label') or not hasattr(self, 'sort_direction_btn'):
                return
            is_default = self.current_sort_key == 'default'
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
            if self.current_sort_key in ['default', 'name', 'owner']:
                if self.current_sort_reverse:
                    self.sort_direction_btn.text = 'Z-A'
                    self.sort_direction_btn.background_color = [0.7, 0.4, 0.4, 1]
                else:
                    self.sort_direction_btn.text = 'A-Z'
                    self.sort_direction_btn.background_color = [0.55, 0.55, 0.55, 1]
            else:
                if self.current_sort_reverse:
                    self.sort_direction_btn.text = '+ -'
                    self.sort_direction_btn.background_color = [0.7, 0.4, 0.4, 1]
                else:
                    self.sort_direction_btn.text = '- +'
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
                lambda dt: self._perform_sort(),
                self._sort_debounce_seconds
            )
            
        except Exception as exc:
            logger.warning("Error scheduling sort: %s", exc)
    
    def _perform_sort(self) -> None:
        """Perform the actual sorting operation."""
        try:
            if not self.playlist_widgets:
                return
                
            # Store checkbox states to preserve selection
            states = {w.playlist_data.get('id', ''): w.checkbox.active 
                     for w in self.playlist_widgets}
            
            # Get current scroll position
            scroll_y = getattr(self.playlist_layout.parent, 'scroll_y', 1.0)
            
            # Clear and rebuild the display with current sort
            self.playlist_layout.clear_widgets()
            self.playlist_widgets = []
            
            # Get filtered playlists and apply sort
            playlists = self._get_filtered_playlists()
            sorted_playlists = self._sort_playlists(playlists)
            
            # Create new widgets with preserved states
            for playlist in sorted_playlists:
                try:
                    widget = PlaylistCard(playlist)
                    playlist_id = playlist.get('id', '')
                    if playlist_id in states:
                        widget.checkbox.active = states[playlist_id]
                    widget.checkbox.bind(active=lambda *_: self.update_selection_counter())
                    self.playlist_widgets.append(widget)
                    self.playlist_layout.add_widget(widget)
                except Exception as exc:
                    logger.warning("Error creating playlist widget during sort: %s", exc)
                    continue
            
            # Restore scroll position
            if hasattr(self.playlist_layout.parent, 'scroll_y'):
                self.playlist_layout.parent.scroll_y = scroll_y
            
            self.update_selection_counter()
            self.update_status_with_cache_info()
            
        except Exception as exc:
            logger.error("Error sorting playlists: %s", exc, exc_info=True)
            self.status_label.text = f'Error sorting playlists: {exc}'

    # Screen lifecycle ---------------------------------------------------
    def export_selected(self, instance):
        """Export all selected playlists to Excel files."""
        selected_playlists = [w for w in self.playlist_widgets if w.checkbox.active]
        if not selected_playlists:
            self.status_label.text = 'Please select at least one playlist to export'
            return

        self.status_label.text = f'Preparing to export {len(selected_playlists)} playlists...'
        
        # Start export in a separate thread to avoid freezing the UI
        threading.Thread(target=self._export_playlists_worker, args=(selected_playlists,), daemon=True).start()

    def _export_playlists_worker(self, playlist_widgets):
        """Worker thread for exporting playlists."""
        try:
            app = App.get_running_app()
            sp = create_spotify_client_with_refresh(app.token_info)
            if not sp:
                self._update_export_status('Authentication error - please login again')
                return

            for i, widget in enumerate(playlist_widgets):
                playlist = widget.playlist
                self._update_export_status(f'Exporting {i+1}/{len(playlist_widgets)}: {playlist["name"]}...')

                try:
                    track_data = self._prepare_playlist_track_rows(sp, playlist, job_state=None, include_reccobeats=True)
                    rows = track_data['combined_rows']
                    if not rows:
                        logger.warning("No rows generated for playlist %s", playlist.get('name'))
                        continue

                    # Use the full row data directly instead of creating a simplified version
                    df = pd.DataFrame(rows)
                    
                    # Remove internal columns that start with underscore
                    internal_cols = [col for col in df.columns if str(col).startswith('_')]
                    if internal_cols:
                        df = df.drop(columns=internal_cols, errors='ignore')

                    os.makedirs(SAVE_DIR, exist_ok=True)
                    safe_name = re.sub(r'[\\/*?:"<>|]', "", playlist['name'])
                    file_path = os.path.join(SAVE_DIR, f"{safe_name}.xlsx")

                    df.to_excel(file_path, index=False, engine='openpyxl')
                    self._format_excel_file(file_path, playlist['name'])

                    self._update_export_status(f'Exported: {playlist["name"]} ({len(df)} tracks)')

                except Exception as e:
                    logger.error(f"Error exporting playlist {playlist['name']}: {e}")
                    self._update_export_status(f"Error exporting {playlist['name']}: {str(e)}")

            self._update_export_status(f'Export complete. Files saved to: {os.path.abspath(SAVE_DIR)}')

        except Exception as e:
            logger.error(f"Error in export worker: {e}")
            self._update_export_status(f"Export failed: {str(e)}")
    
    def _update_export_status(self, message):
        """Update the status label from a background thread."""
        def update():
            self.status_label.text = message
        Clock.schedule_once(lambda dt: update())
    
    def _format_excel_file(self, file_path, playlist_name):
        """Format the Excel file with styles and column widths."""
        try:
            wb = load_workbook(file_path)
            ws = wb.active

            # Set column widths
            ws.column_dimensions['A'].width = 30  # Track Name
            ws.column_dimensions['B'].width = 25  # Artist
            ws.column_dimensions['C'].width = 30  # Album
            ws.column_dimensions['D'].width = 40  # Track URI
            ws.column_dimensions['E'].width = 20  # Added At

            header_row = self._format_playlist_sheet(ws)
            if header_row:
                self._apply_table_style(ws, header_row)
                self._convert_track_urls_to_hyperlinks(ws)

            # Save the changes
            wb.save(file_path)

        except Exception as e:
            logger.error(f"Error formatting Excel file: {e}")
            # Continue even if formatting fails
            pass

    def on_enter(self):
        app = App.get_running_app()
        username = getattr(app, 'username', 'Unknown User')
        self.username_label.text = f"Logged in as: {username}"
        Clock.schedule_once(lambda _: self.update_sort_controls_visibility(), 0.2)
        
        # Update filename with correct username after login
        if hasattr(self, 'filename_input'):
            current_filename = self.filename_input.text or ''
            # Only update if the current filename still has the default 'user' or 'None' placeholder
            if '_user_' in current_filename or '_None_' in current_filename:
                self.filename_input.text = self._generate_default_filename()
        
        self.load_playlists_with_cache()

    # Playlist loading ---------------------------------------------------
    def load_playlists_with_cache(self, *_args) -> None:
        self.current_sort_key = 'default'
        self.current_sort_reverse = False
        self.sort_spinner.text = 'Default'
        self.update_sort_direction_button()
        self.status_label.text = 'Loading playlists...'
        self.playlist_layout.clear_widgets()
        self.playlist_widgets = []
        self.update_selection_counter()
        persistent_cache.cleanup_old_cache()
        threading.Thread(target=self.load_playlists_worker_with_cache, daemon=True).start()

    def load_playlists_worker_with_cache(self) -> None:
        try:
            app = App.get_running_app()
            token_info = getattr(app, 'token_info', None)
            if not token_info:
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Please login again'), 0)
                return

            sp = create_spotify_client_with_refresh(token_info)
            if not sp:
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Please login again'), 0)
                return
            user_id = sp.current_user().get('id')

            playlists: List[dict] = []
            results = sp.current_user_playlists(limit=50)
            while results:
                for playlist in results['items']:
                    playlist_id = playlist.get('id')
                    cached = persistent_cache.get_cached_playlist_data(playlist_id, user_id)
                    if cached:
                        playlists.append(cached)
                    else:
                        persistent_cache.cache_playlist_data(playlist_id, playlist, user_id)
                        playlists.append(playlist)
                if results['next']:
                    results = sp.next(results)
                else:
                    break

            self.playlists = playlists
            worksheet = None  # Initialize worksheet to prevent scope error
            Clock.schedule_once(lambda _: self.display_playlists_with_cache(), 0)

        except SpotifyException as exc:
            logger.error("Spotify API error: %s", exc)
            if exc.http_status == 401:
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Session expired. Please login again.'), 0)
                Clock.schedule_once(lambda _: App.get_running_app().switch_to_login(), 2)
            else:
                error_msg = f'Spotify error: {exc}'
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', error_msg), 0)
        except Exception as exc:
            logger.error("Error loading playlists: %s", exc)
            error_msg = f'Error loading playlists: {exc}'
            Clock.schedule_once(lambda _: setattr(self.status_label, 'text', error_msg), 0)

    def display_playlists_with_cache(self) -> None:
        """Display playlists with current search and sort applied.
        
        This method handles both the initial display and updates when search or sort changes.
        It maintains the current sort order and applies the search filter.
        Preserves checkbox states across filter changes.
        """
        try:
            # Store current scroll position if possible
            scroll_y = getattr(self.playlist_layout.parent, 'scroll_y', 1.0)
            
            # Store checkbox states to preserve selection
            states = {w.playlist_data.get('id', ''): w.checkbox.active 
                     for w in self.playlist_widgets}
            
            # Clear existing widgets
            self.playlist_layout.clear_widgets()
            self.playlist_widgets = []
            
            # Show loading indicator
            loading_text = 'Searching...' if self.search_query else 'Loading...'
            self.status_label.text = loading_text
            
            # Get playlists to display based on search
            playlists_to_display = self._get_filtered_playlists()
            
            # Apply current sort
            if self.current_sort_key != 'default' or self.current_sort_reverse:
                playlists_to_display = self._sort_playlists(playlists_to_display)
            
            # Update filtered playlists for status display
            self.filtered_playlists = playlists_to_display
            
            # Create and add widgets for filtered playlists
            for playlist in playlists_to_display:
                try:
                    widget = PlaylistCard(playlist)
                    playlist_id = playlist.get('id', '')
                    # Restore checkbox state if it was previously selected
                    if playlist_id in states:
                        widget.checkbox.active = states[playlist_id]
                    widget.checkbox.bind(active=lambda *_: self.update_selection_counter())
                    self.playlist_widgets.append(widget)
                except Exception as exc:
                    logger.warning("Error creating playlist widget: %s", exc)
                    continue
            
            # Add widgets to layout
            for widget in self.playlist_widgets:
                self.playlist_layout.add_widget(widget)
            
            # Restore scroll position
            if hasattr(self.playlist_layout.parent, 'scroll_y'):
                self.playlist_layout.parent.scroll_y = scroll_y
            
            self.update_status_with_cache_info()
            self.update_selection_counter()
            
        except Exception as exc:
            logger.error("Error displaying playlists: %s", exc, exc_info=True)
            self.status_label.text = f'Error displaying playlists: {exc}'
    
    def _get_filtered_playlists(self) -> List[dict]:
        """Get playlists filtered by the current search query.
        
        Returns:
            List of playlist dictionaries that match the search criteria
        """
        if not self.search_query:
            return self.playlists.copy()
        
        try:
            # Compile search query once for better performance
            search_terms = [term.strip() for term in self.search_query.split() if term.strip()]
            
            def matches_search(playlist):
                playlist_name = playlist.get('name', '').lower()
                owner_name = playlist.get('owner', {}).get('display_name', '').lower()
                
                # Match all search terms (AND logic)
                return all(
                    term in playlist_name or term in owner_name
                    for term in search_terms
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
        if not playlists or self.current_sort_key == 'default':
            return playlists
        
        def key_fn(pl):
            if self.current_sort_key == 'name':
                return pl.get('name', '').lower()
            if self.current_sort_key == 'tracks':
                return pl.get('tracks', {}).get('total', 0)
            if self.current_sort_key == 'owner':
                return pl.get('owner', {}).get('display_name', '').lower()
            return ''
        
        return sorted(playlists, key=key_fn, reverse=self.current_sort_reverse)

    def update_status_with_cache_info(self) -> None:
        """Update the status bar with current playlist and cache information.
        
        Shows total playlists, filtered count (if searching), and cache info.
        """
        try:
            stats = persistent_cache.get_cache_stats()
            cache_size = stats.get('total_size_mb', 0)
            cache_files = stats.get('file_count', 0)
            
            # Prepare status message parts
            cache_info = f" • Cache: {cache_size:.1f}MB ({cache_files} files)" if cache_size else ''
            
            # Add search info if there's an active search
            status_parts = []
            total_playlists = len(self.playlists)
            
            if self.search_query:
                shown_playlists = len(self.filtered_playlists)
                if shown_playlists == 0:
                    status_parts.append(f'No matches for "{self.search_query}"')
                else:
                    status_parts.append(f'Showing {shown_playlists} of {total_playlists}')
            else:
                status_parts.append(f'Loaded {total_playlists} playlists')
            
            # Add cache info if available
            if cache_info:
                status_parts.append(cache_info)
            
            # Update status label
            self.status_label.text = ' • '.join(status_parts)
            
        except Exception as exc:
            logger.warning("Error updating status: %s", exc, exc_info=True)
            self.status_label.text = 'Error updating status'

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
            lambda dt: self._perform_search(value),
            self._search_debounce_seconds
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
            self.status_label.text = f'Search error: {str(exc)}'

    def clear_search(self, instance):
        """Clear search and reset display.
        
        Args:
            instance: The button instance that triggered this action
        """
        # Cancel any pending search
        if self._search_trigger:
            self._search_trigger.cancel()
            self._search_trigger = None
            
        self.search_input.text = ''
        self.search_query = ''
        
        # Reset to first page and refresh display
        if hasattr(self.playlist_layout.parent, 'scroll_y'):
            self.playlist_layout.parent.scroll_y = 1.0
            
        self.display_playlists_with_cache()

    def toggle_select_all(self, instance):
        """Toggle selection of all playlists."""
        if not hasattr(self, 'playlist_widgets') or not self.playlist_widgets:
            return
            
        # Check if all are selected
        all_selected = all(w.checkbox.active for w in self.playlist_widgets)
        
        # Toggle all checkboxes
        for widget in self.playlist_widgets:
            widget.checkbox.active = not all_selected
            
        # Update the button text and counter
        self.update_selection_counter()
        
    def update_selection_counter(self):
        """Update the selection counter label."""
        try:
            if not hasattr(self, 'playlist_widgets') or not self.playlist_widgets:
                return
                
            selected = sum(1 for w in self.playlist_widgets if w.checkbox.active)
            total = len(self.playlist_widgets)
            self.selection_label.text = f'Selected: {selected} of {total}'
        except Exception as exc:
            logger.warning("Error updating selection counter: %s", exc)

    def select_all(self, *_args) -> None:
        for widget in self.playlist_widgets:
            widget.checkbox.active = True
        self.update_selection_counter()

    def deselect_all(self, *_args) -> None:
        for widget in self.playlist_widgets:
            widget.checkbox.active = False
        self.update_selection_counter()

    # Export --------------------------------------------------------------
    def start_export(self, *_args) -> None:
        try:
            selected = [w.playlist_data for w in self.playlist_widgets if w.checkbox.active]
            if not selected:
                Popup(
                    title='No Selection',
                    content=Label(text='Please select at least one playlist to export.'),
                    size_hint=(0.6, 0.4),
                ).open()
                return

            # Check cache status before proceeding
            self._check_cache_status_and_proceed(selected)
        except Exception as exc:
            logger.error("Error starting export: %s", exc)
            self.status_label.text = f'Export error: {exc}'
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def _check_cache_status_and_proceed(self, playlists) -> None:
        """Check cache status for selected playlists and show warning if needed."""
        try:
            self.status_label.text = 'Checking cache status...'
            
            # Get current user ID for cache checking
            app = App.get_running_app()
            sp = create_spotify_client_with_refresh(app.token_info)
            if not sp:
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Authentication error - please login again'), 0)
                return
                
            user_id = sp.current_user().get('id')
            
            # Check cache status for each selected playlist
            total_tracks = 0
            tracks_missing_reccobeats = 0
            
            for playlist in playlists:
                playlist_id = playlist.get('id')
                if not playlist_id:
                    continue
                    
                try:
                    # Get cached playlist tracks data with timeout protection
                    cached_data = persistent_cache.get_cached_playlist_tracks(playlist_id, user_id)
                    if cached_data:
                        tracks = cached_data.get('tracks', [])
                        reccobeats_cached_count = cached_data.get('reccobeats_cached_count', 0)
                        
                        # Tracks missing Reccobeats data are those not cached for ReccoBeats
                        playlist_tracks_missing_reccobeats = len(tracks) - reccobeats_cached_count
                        tracks_missing_reccobeats += playlist_tracks_missing_reccobeats
                        total_tracks += len(tracks)
                    else:
                        # No cache data - assume all tracks are missing Reccobeats data
                        track_count = playlist.get('tracks', {}).get('total', 0)
                        tracks_missing_reccobeats += track_count
                        total_tracks += track_count
                except Exception as exc:
                    logger.warning("Error checking cache for playlist %s: %s", playlist_id, exc)
                    # If cache check fails for a playlist, assume all tracks are missing Reccobeats data
                    track_count = playlist.get('tracks', {}).get('total', 0)
                    tracks_missing_reccobeats += track_count
                    total_tracks += track_count
            
            # Always show feature selection dialog with Reccobeats estimate
            self._show_feature_selection_popup(playlists, tracks_missing_reccobeats, total_tracks)
                
        except Exception as exc:
            logger.error("Error checking cache status: %s", exc)
            # If cache check fails, show feature selection dialog with zero estimate
            self._show_feature_selection_popup(playlists, 0, sum(p.get('tracks', {}).get('total', 0) for p in playlists))

    def _show_feature_selection_popup(self, playlists, tracks_missing_reccobeats, total_tracks) -> None:
        """Show popup asking whether to include Reccobeats features."""
        popup_content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        popup_content.add_widget(Widget(size_hint_y=0.2))
        
        question_text = 'Include Reccobeats features (tempo, musical key, other features)?'
        estimate_text = f'An estimated {tracks_missing_reccobeats} out of {total_tracks} tracks are missing Reccobeats data.'
        warning_text = 'This may take several minutes, but you can cancel at any time.'
        
        full_text = f'{question_text}\n\n{estimate_text}\n\n{warning_text}'
        
        popup_content.add_widget(
            Label(
                text=full_text,
                font_size=dp(16),
                size_hint_y=None,
                height=dp(120),
                halign='center',
                valign='center',
                text_size=(dp(450), dp(120)),
            )
        )
        popup_content.add_widget(Widget(size_hint_y=0.3))
        
        buttons = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
        no_btn = Button(text='No', size_hint_x=0.5, font_size=dp(16), background_color=[0.6, 0.6, 0.6, 1])
        yes_btn = Button(text='Yes', size_hint_x=0.5, font_size=dp(16), background_color=[0.25, 0.85, 0.25, 1])
        buttons.add_widget(no_btn)
        buttons.add_widget(yes_btn)
        popup_content.add_widget(buttons)
        
        popup = Popup(title='Export Options', content=popup_content, size_hint=(0.7, 0.5), auto_dismiss=False)
        no_btn.bind(on_press=lambda *_: self._handle_feature_selection_response(popup, playlists, False))
        yes_btn.bind(on_press=lambda *_: self._handle_feature_selection_response(popup, playlists, True))
        popup.open()

    def _handle_feature_selection_response(self, popup, playlists, include_reccobeats) -> None:
        """Handle user's choice about including Reccobeats features."""
        popup.dismiss()
        self._proceed_with_export_after_cache_check(playlists, include_reccobeats)

    def _handle_cache_warning_continue(self, popup, playlists) -> None:
        """Handle user choosing to continue despite cache warning."""
        popup.dismiss()
        self._proceed_with_export_after_cache_check(playlists)

    def _proceed_with_export_after_cache_check(self, playlists, include_reccobeats=True) -> None:
        """Proceed with export after cache check is complete."""
        filename = (self.filename_input.text or '').strip() if hasattr(self, 'filename_input') else ''
        if not filename:
            filename = self._generate_default_filename()
        elif not filename.lower().endswith('.xlsx'):
            filename += '.xlsx'
        output_path = os.path.join(SAVE_DIR, filename)

        if os.path.exists(output_path):
            self._show_overwrite_confirmation(playlists, output_path, filename, include_reccobeats)
        else:
            self.begin_export(playlists, output_path, include_reccobeats)

    def _show_overwrite_confirmation(self, playlists, output_path, filename, include_reccobeats=True) -> None:
        popup_content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        popup_content.add_widget(Widget(size_hint_y=0.3))
        popup_content.add_widget(
            Label(
                text=f'The file "{filename}" already exists.\n\nDo you want to overwrite it?',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(80),
                halign='center',
                valign='center',
                text_size=(dp(400), dp(80)),
            )
        )
        popup_content.add_widget(Widget(size_hint_y=0.4))
        buttons = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
        cancel_btn = Button(text='Cancel', size_hint_x=0.5, font_size=dp(16), background_color=[0.6, 0.6, 0.6, 1])
        overwrite_btn = Button(text='Overwrite', size_hint_x=0.5, font_size=dp(16), background_color=[0.8, 0.3, 0.3, 1])
        buttons.add_widget(cancel_btn)
        buttons.add_widget(overwrite_btn)
        popup_content.add_widget(buttons)
        popup = Popup(title='File Already Exists', content=popup_content, size_hint=(0.6, 0.4), auto_dismiss=False)
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        overwrite_btn.bind(on_press=lambda *_: self._handle_overwrite_confirmed(popup, playlists, output_path, include_reccobeats))
        popup.open()

    def _handle_overwrite_confirmed(self, popup, playlists, output_path, include_reccobeats=True) -> None:
        popup.dismiss()
        self.begin_export(playlists, output_path, include_reccobeats)

    def begin_export(self, playlists, output_path, include_reccobeats=True) -> None:
        try:
            self.export_btn.disabled = True
            self.cancel_btn.opacity = 1
            self.cancel_btn.disabled = False
            filename = os.path.basename(output_path)
            self.status_label.text = f'Exporting to: {filename}'
            self.progress_bar.value = 0
            threading.Thread(target=self.export_worker, args=(playlists, output_path, include_reccobeats), daemon=True).start()
        except Exception as exc:
            logger.error("Error beginning export: %s", exc)
            self.export_btn.disabled = False
            self.cancel_btn.opacity = 0
            self.cancel_btn.disabled = True
            self.status_label.text = f'Export error: {exc}'
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def cancel_export(self, *_args) -> None:
        global current_export_job
        if current_export_job:
            current_export_job['cancelled'] = True
            self.cancel_btn.disabled = True
            self.cancel_btn.text = 'Cancelling...'
            self.status_label.text = 'Cancelling export...'
            Clock.schedule_once(lambda _: self.cleanup_after_export(), 3.0)
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 3.0)

    def cleanup_after_export(self) -> None:
        self.export_btn.disabled = False
        self.cancel_btn.opacity = 0
        self.cancel_btn.disabled = True
        self.cancel_btn.text = 'Cancel Export'
        self.progress_bar.value = 0

    def handle_export_cancelled(self) -> None:
        """Handle the UI updates when an export is cancelled."""
        self.status_label.text = 'Export cancelled'
        self.cleanup_after_export()
        Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def export_worker(self, playlists, output_path, include_reccobeats=True) -> None:
        global current_export_job
        current_export_job = {'cancelled': False}
        temp_files = []  # List to keep track of temporary files
        logger.info("Starting export process...")
        try:
            app = App.get_running_app()
            if current_export_job['cancelled']:
                Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)
                return
            if not getattr(app, 'token_info', None):
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Authentication error - please login again'), 0)
                Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
                Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)
                return
            sp = create_spotify_client_with_refresh(app.token_info)
            if not sp:
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Authentication error - please login again'), 0)
                Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
                Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)
                return
            Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Creating Excel file...'), 0)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create a new workbook with one sheet
            wb = openpyxl.Workbook()
            # Rename the default sheet to a meaningful name
            default_sheet = wb.active
            default_sheet.title = "Playlists"
            # Add headers to the default sheet
            headers = ['Playlist Name', 'Owner', 'Track Count', 'Duration']
            default_sheet.append(headers)
            
            # Format the Playlists sheet headers
            header_fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
            header_font = Font(color='FFFFFF', bold=True)
            
            for cell in default_sheet[1]:  # First row is the header
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            
            # Set column widths for the Playlists sheet
            default_sheet.column_dimensions['A'].width = 40  # Playlist Name
            default_sheet.column_dimensions['B'].width = 30  # Owner
            default_sheet.column_dimensions['C'].width = 12  # Track Count
            default_sheet.column_dimensions['D'].width = 15  # Duration
            
            wb.save(output_path)
            wb.close()
            
            # Now open with pandas ExcelWriter in append mode
            with pd.ExcelWriter(output_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                total = len(playlists)
                sheets_created = 0
                worksheet = None  # Initialize worksheet to prevent scope error

                workbook = writer.book
                summary_sheet = workbook['Playlists']
                
                # Skip formatting the Playlists sheet since we've already formatted it
                formatted_sheets = {'Playlists'}

                for index, playlist in enumerate(playlists):
                    if current_export_job['cancelled']:
                        Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)
                        return

                    progress = int((index / max(total, 1)) * 40)  # Adjusted progress range
                    Clock.schedule_once(lambda _, p=progress: setattr(self.progress_bar, 'value', p), 0)
                    playlist_name = playlist.get('name', 'Unknown Playlist')
                    Clock.schedule_once(
                        lambda _, name=playlist_name: setattr(self.status_label, 'text', f'Processing: {name[:30]}...'),
                        0,
                    )

                    track_data = self._prepare_playlist_track_rows(sp, playlist, current_export_job, include_reccobeats)
                    tracks = track_data['combined_rows']
                    if current_export_job['cancelled']:
                        Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)
                        return

                    # Skip this playlist if no tracks are found
                    if not tracks:
                        logger.warning(f"No tracks found in playlist: {playlist_name}")
                        continue

                    track_count = len(tracks)
                    duration_str = self._format_duration_from_ms(track_data['total_duration_ms'])
                    summary_sheet.append(
                        [
                            playlist.get('name', 'Unknown'),
                            playlist.get('owner', {}).get('display_name', 'Unknown'),
                            track_count,
                            duration_str,
                        ]
                    )

                    # Create a DataFrame for the tracks with correct column order
                    df = pd.DataFrame(tracks) if tracks else pd.DataFrame(
                        columns=['Track', 'Artist', 'Album', 'Duration', 'Spotify URL']
                    )
                    hidden_cols = [col for col in df.columns if str(col).startswith('_')]
                    if hidden_cols:
                        df = df.drop(columns=hidden_cols, errors='ignore')
                    if df.empty:
                        df.loc[0] = ['No tracks found', '', '', '', '']

                    # Add the sheet with tracks starting at row 10 (leaving room for metadata)
                    sheet_name = self._sanitize_sheet_name(f"{playlist_name} - {playlist.get('owner', {}).get('display_name', 'Unknown')}")
                    logger.info(f"Processing playlist: {sheet_name}")
                    
                    df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=10)
                    sheets_created += 1
                    logger.info("Worksheet created successfully")
                    
                    # Get the workbook and worksheet objects
                    workbook = writer.book
                    worksheet = writer.sheets[sheet_name]
                    
                    # Ensure the worksheet is active
                    workbook.active = workbook.index(writer.sheets[sheet_name])
                    
                    # Add metadata directly to the worksheet
                    playlist_meta = self._get_playlist_metadata(playlist)
                    total_duration = duration_str
                    
                    # Add cover image first (if available)
                    cover_url = self._get_playlist_cover_url(playlist)
                    if cover_url:
                        try:
                            temp_path = self.download_and_cache_image(cover_url, playlist_meta['name'])
                            if temp_path:
                                temp_files.append(temp_path)  # Track the temp file
                                img = OpenpyxlImage(temp_path)
                                img.width = 120
                                img.height = 120
                                img.anchor = 'B1'
                                worksheet.add_image(img)
                        except Exception as exc:
                            logger.warning("Error adding cover image: %s", exc)
                    
                    # Add metadata text
                    try:
                        logger.info(f"Adding metadata for {playlist_meta['name']}")
                        logger.debug(f"Metadata content: {playlist_meta}")
                        
                        # Add title in column A
                        title_cell = worksheet.cell(row=1, column=1, value=playlist_meta['name'])
                        title_cell.font = Font(bold=True, size=16)
                        
                        # Recalculate worksheet dimensions
                        worksheet.calculate_dimension()
                        
                        logger.info("Title added successfully")
                    except Exception as e:
                        logger.error(f"Error adding title: {e}")
                        raise
                    
                    # Add metadata rows with proper formatting
                    try:
                        metadata_rows = [
                            (f"Created by: {playlist_meta['owner']}", 2),
                            (f"Followers: {playlist_meta['followers']}", 3),
                            (f"Tracks exported: {track_count}", 4),
                            (f"Total duration: {total_duration}", 5),
                            (f"Playlist URL: {playlist_meta['url']}", 6),
                            (f"Description: {playlist_meta['description']}", 7)
                        ]
                        
                        for text, row in metadata_rows:
                            cell = worksheet.cell(row=row, column=1, value=text)
                            if 'URL:' in text and 'N/A' not in text and 'http' in playlist_meta['url']:
                                cell.hyperlink = playlist_meta['url']
                                cell.style = 'Hyperlink'
                        logger.info("Metadata added successfully")
                    except Exception as e:
                        logger.error(f"Error adding metadata: {e}")
                        raise
                    
                    # Set column widths for better readability
                    worksheet.column_dimensions['A'].width = 30  # Artist
                    worksheet.column_dimensions['B'].width = 40  # Album
                    worksheet.column_dimensions['C'].width = 40  # Track
                    worksheet.column_dimensions['D'].width = 15  # Duration
                    worksheet.column_dimensions['E'].width = 60  # URL
                
                # Convert track URLs to hyperlinks
                if worksheet is not None:
                    for row_idx, row in enumerate(worksheet.iter_rows(min_row=11, min_col=5, max_col=5), start=11):
                        for cell in row:
                            if cell.value and isinstance(cell.value, str) and cell.value.startswith('https://'):
                                cell.hyperlink = cell.value
                                cell.style = 'Hyperlink'

            # If no sheets were created (all playlists were empty), create a default sheet
            if sheets_created == 0:
                logger.warning("No playlists with tracks found, creating a default sheet")
                df = pd.DataFrame([['No tracks found in any playlists', '', '', '', '']], 
                                columns=['Track', 'Artist', 'Album', 'Duration', 'Spotify URL'])
                df.to_excel(writer, sheet_name='No Tracks', index=False)
                workbook = writer.book
                worksheet = writer.sheets['No Tracks']
                workbook.active = workbook.index(worksheet)
                sheets_created = 1

            if current_export_job['cancelled']:
                Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)
                return

            # Only proceed with formatting if we have sheets
            if sheets_created > 0:
                Clock.schedule_once(lambda _: setattr(self.status_label, 'text', 'Adding table formatting...'), 0)
                Clock.schedule_once(lambda _: setattr(self.progress_bar, 'value', 95), 0)
                self._add_table_formatting(output_path, current_export_job)

                try:
                    workbook = load_workbook(output_path)
                    summary_sheet = workbook['Playlists']

                    header_fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
                    header_font = Font(bold=True, size=13, color='FFFFFF')
                    header_row = summary_sheet[1]
                    for cell in header_row:
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

                    for row in summary_sheet.iter_rows(min_row=2):
                        for cell in row:
                            cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

                    column_widths = {
                        'A': 29,
                        'B': 24,
                        'C': 16,
                        'D': 19,
                    }
                    for column_letter, width in column_widths.items():
                        summary_sheet.column_dimensions[column_letter].width = width

                    workbook.save(output_path)
                    workbook.close()
                except Exception as exc:
                    logger.warning("Error styling summary sheet: %s", exc)

            # Adjust column widths for all sheets
            self._adjust_column_widths(output_path, current_export_job)

            if current_export_job['cancelled']:
                Clock.schedule_once(lambda _: self.handle_export_cancelled(), 0)
                return

            Clock.schedule_once(lambda _: setattr(self.progress_bar, 'value', 100), 0)
            filename = os.path.basename(output_path)
            Clock.schedule_once(lambda _: setattr(self.status_label, 'text', f'Export complete! Saved: {filename}'), 0)
            Clock.schedule_once(lambda _: self._show_completion_popup(os.path.basename(output_path), output_path), 0)
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

        except PermissionError:
            Clock.schedule_once(
                lambda _: setattr(
                    self.status_label,
                    'text',
                    'Permission denied: File may be open in Excel',
                ),
                0,
            )
        except Exception as exc:
            logger.error("Export failed: %s", exc)
            # Capture the exception in the lambda's closure
            error_message = str(exc)
            Clock.schedule_once(
                lambda _, msg=error_message: setattr(self.status_label, 'text', f'Export failed: {msg[:50]}...'),
                0,
            )
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)
        finally:
            # Clean up all temporary files
            for temp_file in temp_files:
                try:
                    if temp_file and os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as exc:
                    logger.warning("Error removing temporary file %s: %s", temp_file, exc)
            
            Clock.schedule_once(lambda _: self.cleanup_after_export(), 0)
            current_export_job = None

    # Workbook helpers ---------------------------------------------------
    def _get_playlist_tracks(self, sp, playlist, job_state):
        tracks = []
        playlist_id = playlist.get('id')
        if not playlist_id:
            return tracks
            
        try:
            # First, get all track IDs with pagination
            track_ids = []
            track_id_to_index = {}
            
            # Initial request
            results = sp.playlist_tracks(
                playlist_id, 
                limit=100, 
                fields='items(track(id, name, artists, album(name), duration_ms, external_urls(spotify), type)),next',
                offset=0
            )
            
            while results and 'items' in results:
                if job_state['cancelled']:
                    return []
                    
                for item in results['items']:
                    track = item.get('track')
                    if track and track.get('type') == 'track' and track.get('id'):
                        track_id = track['id']
                        if track_id not in track_id_to_index:  # Avoid duplicates
                            track_ids.append(track_id)
                            track_id_to_index[track_id] = len(track_ids) - 1
                
                # Check if there are more tracks to fetch
                if results.get('next'):
                    # Use the next URL to get the next page
                    results = sp.next(results)
                else:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching playlist tracks: {e}")
            return []
        
        # Get audio features for all tracks in smaller batches with retries
        audio_features_map = {}
        batch_size = 50  # Reduced batch size to avoid rate limiting
        for i in range(0, len(track_ids), batch_size):
            if job_state['cancelled']:
                return []
                
            batch = track_ids[i:i+batch_size]
            max_retries = 3
            retry_delay = 1  # Start with 1 second delay
            
            for attempt in range(max_retries):
                try:
                    features = sp.audio_features(batch)
                    if features and any(features):  # Check if we got any features back
                        for feature in features:
                            if feature and 'id' in feature:
                                audio_features_map[feature['id']] = feature
                        break  # Success, exit retry loop
                    else:
                        logger.warning(f"Empty audio features response on attempt {attempt + 1}")
                except Exception as e:
                    logger.warning(f"Error fetching audio features (attempt {attempt + 1}): {e}")
                    if attempt == max_retries - 1:  # Last attempt failed
                        logger.error("Max retries reached for audio features, continuing without them")
                        break
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
        
        try:
            # Now get full track details and include audio features
            offset = 0
            limit = 100
            
            while True:
                if job_state['cancelled']:
                    return []
                    
                # Get a page of tracks
                results = sp.playlist_tracks(
                    playlist_id,
                    limit=limit,
                    offset=offset,
                    fields='items(track(id,name,artists,album(name),duration_ms,external_urls(spotify),type)),next'
                )
                
                if not results or 'items' not in results or not results['items']:
                    break
                    
                for item in results['items']:
                    track = item.get('track')
                    if not track or track.get('type') != 'track':
                        continue
                        
                    track_id = track.get('id')
                    if not track_id:
                        continue
                        
                    # Get track details
                    artists = ', '.join([artist.get('name', 'Unknown') for artist in track.get('artists', [])])
                    duration_ms = track.get('duration_ms', 0)
                    duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
                    
                    # Get audio features for this track if available
                    audio_features = audio_features_map.get(track_id, {})
                    
                    # Map musical key number to note
                    key_map = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                    mode_map = ['minor', 'major']
                    key = key_map[audio_features.get('key', 0)] if 'key' in audio_features else 'N/A'
                    mode = mode_map[audio_features.get('mode', 1)] if 'mode' in audio_features else 'N/A'
                    
                    tracks.append({
                        'Artist': artists,
                        'Album': track.get('album', {}).get('name', ''),
                        'Track': track.get('name', ''),
                        'Duration': duration_str,
                        'Spotify URL': track.get('external_urls', {}).get('spotify', ''),
                        'Tempo': round(audio_features.get('tempo', 0), 2) if 'tempo' in audio_features else 'N/A',
                        'Key': f"{key} {mode}" if key != 'N/A' and mode != 'N/A' else 'N/A',
                        'Danceability': round(audio_features.get('danceability', 0), 3) if 'danceability' in audio_features else 'N/A',
                        'Energy': round(audio_features.get('energy', 0), 3) if 'energy' in audio_features else 'N/A',
                        'Valence': round(audio_features.get('valence', 0), 3) if 'valence' in audio_features else 'N/A',
                        'Acousticness': round(audio_features.get('acousticness', 0), 3) if 'acousticness' in audio_features else 'N/A',
                        'Instrumentalness': round(audio_features.get('instrumentalness', 0), 3) if 'instrumentalness' in audio_features else 'N/A',
                        'Liveness': round(audio_features.get('liveness', 0), 3) if 'liveness' in audio_features else 'N/A',
                        'Speechiness': round(audio_features.get('speechiness', 0), 3) if 'speechiness' in audio_features else 'N/A',
                        'Loudness': round(audio_features.get('loudness', 0), 1) if 'loudness' in audio_features else 'N/A',
                        'Time Signature': audio_features.get('time_signature', 'N/A') if 'time_signature' in audio_features else 'N/A'
                    })
                
                # Check if there are more tracks to fetch
                if not results.get('next'):
                    break
                    
                offset += limit
                
        except Exception as e:
            logger.error(f"Error processing playlist tracks: {e}")
            return tracks  # Return whatever tracks we've collected so far
                
        return tracks

    def _calculate_total_duration_from_df(self, df):
        """Calculate total duration in milliseconds from a DataFrame with 'Duration' column."""
        try:
            total_ms = 0
            for duration_str in df['Duration']:
                if ':' in str(duration_str):
                    parts = str(duration_str).split(':')
                    if len(parts) == 2:  # MM:SS format
                        minutes, seconds = map(int, parts)
                        total_ms += (minutes * 60 + seconds) * 1000
                    elif len(parts) == 3:  # HH:MM:SS format
                        hours, minutes, seconds = map(int, parts)
                        total_ms += (hours * 3600 + minutes * 60 + seconds) * 1000
            return total_ms
        except Exception as e:
            logger.error(f"Error calculating total duration: {e}")
            return 0

    def _calculate_total_duration_from_df(self, df):
        """Calculate total duration in milliseconds from a DataFrame with 'Duration' column."""
        try:
            total_ms = 0
            for duration_str in df['Duration']:
                if isinstance(duration_str, str) and ':' in duration_str:
                    parts = duration_str.split(':')
                    if len(parts) == 2:  # MM:SS format
                        minutes, seconds = map(int, parts)
                        total_ms += (minutes * 60 + seconds) * 1000
                    elif len(parts) == 3:  # HH:MM:SS format
                        hours, minutes, seconds = map(int, parts)
                        total_ms += (hours * 3600 + minutes * 60 + seconds) * 1000
            return total_ms
        except Exception as e:
            logger.error(f"Error calculating total duration: {e}")
            return 0

    def _format_duration_from_ms(self, total_duration_ms: int) -> str:
        minutes = total_duration_ms // 60_000
        seconds = (total_duration_ms % 60_000) // 1_000
        hours = minutes // 60
        minutes = minutes % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _prepare_playlist_track_rows(self, sp, playlist, job_state, include_reccobeats=True) -> Dict[str, Any]:
        playlist_id = playlist.get('id')
        result: Dict[str, Any] = {
            'combined_rows': [],
            'spotify_rows': [],
            'reccobeats_rows': [],
            'total_duration_ms': 0,
        }

        if not playlist_id:
            return result

        # Get user_id for cache tracking
        app = App.get_running_app()
        user_id = getattr(app, 'user_id', sp.current_user().get('id'))

        # Update playlist track cache and get current tracks
        tracks_data = get_or_update_playlist_tracks(sp, playlist_id, user_id)
        current_tracks = tracks_data['tracks']
        
        # Log cache statistics
        cache_info = f"Cache: {tracks_data['spotify_cached_count']}/{tracks_data['total_tracks']} Spotify, {tracks_data['reccobeats_cached_count']}/{tracks_data['total_tracks']} ReccoBeats"
        if tracks_data['new_tracks'] > 0:
            cache_info += f" ({tracks_data['new_tracks']} new tracks)"
        logger.info("Playlist %s: %s", playlist.get('name', 'Unknown'), cache_info)

        row_lookup: Dict[str, Dict[str, Any]] = {}
        track_order: List[str] = []
        missing_reccobeats: List[str] = []
        total_duration_ms = 0

        try:
            # Process the tracks we already fetched
            for track in current_tracks:
                if job_state and job_state.get('cancelled'):
                    return result

                if not track or track.get('type') != 'track':
                    continue

                spotify_id = track.get('id')
                if not spotify_id:
                    continue

                track_order.append(spotify_id)

                normalized = get_cached_spotify_track(spotify_id) or cache_spotify_track(track)
                if not normalized:
                    artists = [artist.get('name', '') for artist in track.get('artists', [])]
                    normalized = {
                        'id': spotify_id,
                        'artists': artists,
                        'album': track.get('album', {}).get('name', ''),
                        'title': track.get('name', ''),
                        'duration_ms': track.get('duration_ms', 0) or 0,
                        'Spotify_url': track.get('external_urls', {}).get('spotify', ''),
                    }

                total_duration_ms += normalized.get('duration_ms', 0) or 0
                row = self._build_export_row_from_spotify(normalized)
                row_lookup[spotify_id] = row
                result['combined_rows'].append(row)
                result['spotify_rows'].append(normalized)

                # Only process Reccobeats features if they are included in the export
                if include_reccobeats:
                    cached_features = get_cached_reccobeats_features(spotify_id)
                    if cached_features:
                        self._apply_reccobeats_to_row(row, cached_features)
                        result['reccobeats_rows'].append(cached_features)
                    else:
                        missing_reccobeats.append(spotify_id)

        except Exception as exc:
            logger.error("Error preparing playlist rows for %s: %s", playlist_id, exc)

        # Only fetch missing Reccobeats features if they are included in the export
        if missing_reccobeats and include_reccobeats:
            try:
                feature_map = reccobeats_api.get_multiple_track_audio_features_safe(missing_reccobeats)
                for spotify_id, features in feature_map.items():
                    if not features:
                        continue
                    cache_reccobeats_features(spotify_id, features)
                    row = row_lookup.get(spotify_id)
                    if row:
                        self._apply_reccobeats_to_row(row, features)
                    result['reccobeats_rows'].append(features)
            except Exception as exc:
                logger.warning("Error fetching ReccoBeats audio features during export: %s", exc)

        ordered_rows = [row_lookup[sid] for sid in track_order if row_lookup.get(sid)]
        result['combined_rows'] = ordered_rows
        result['total_duration_ms'] = total_duration_ms
        return result

    def _build_export_row_from_spotify(self, normalized_track: Dict[str, Any]) -> Dict[str, Any]:
        duration_ms = normalized_track.get('duration_ms', 0) or 0
        artists = normalized_track.get('artists')
        if isinstance(artists, list):
            artist_text = ', '.join(artists)
        else:
            artist_text = str(artists or '')

        row = {
            'Artist': artist_text,
            'Album': normalized_track.get('album', ''),
            'Track': normalized_track.get('title') or normalized_track.get('name', ''),
            'Duration': self._format_duration_from_ms(duration_ms),
            'Spotify URL': normalized_track.get('spotify_url', ''),
            'Tempo': 'N/A',
            'Key': 'N/A',
            'Danceability': 'N/A',
            'Energy': 'N/A',
            'Valence': 'N/A',
            'Acousticness': 'N/A',
            'Instrumentalness': 'N/A',
            'Liveness': 'N/A',
            'Speechiness': 'N/A',
            'Loudness': 'N/A',
            'Time Signature': 'N/A',
        }
        row['_duration_ms'] = duration_ms
        row['_spotify_id'] = normalized_track.get('id')
        return row

    def _apply_reccobeats_to_row(self, row: Dict[str, Any], features: Dict[str, Any]) -> None:
        if not row or not features:
            return

        if 'tempo' in features and features['tempo'] is not None:
            row['Tempo'] = round(features['tempo'], 2)

        key = features.get('key')
        mode = features.get('mode')
        key_map = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        mode_map = {0: 'minor', 1: 'major'}
        if key is not None and 0 <= key < len(key_map):
            key_name = key_map[key]
            mode_name = mode_map.get(mode, '')
            row['Key'] = f"{key_name} {mode_name}".strip()

        feature_fields = [
            'danceability',
            'energy',
            'valence',
            'acousticness',
            'instrumentalness',
            'liveness',
            'speechiness',
        ]
        for field in feature_fields:
            value = features.get(field)
            if value is not None:
                row[field.capitalize()] = round(value, 3)

        loudness = features.get('loudness')
        if loudness is not None:
            row['Loudness'] = round(loudness, 1)

        time_signature = features.get('time_signature')
        if time_signature is not None:
            row['Time Signature'] = time_signature

    def _find_data_header_row(self, worksheet) -> Optional[int]:
        header_aliases = {
            'track',
            'track name',
            'artist',
            'album',
            'spotify url',
            'track uri',
        }

        max_row = worksheet.max_row or 0
        max_col = worksheet.max_column or 0
        for row_idx in range(1, max_row + 1):
            matches = 0
            for col_idx in range(1, max_col + 1):
                value = worksheet.cell(row=row_idx, column=col_idx).value
                if isinstance(value, str) and value.strip().lower() in header_aliases:
                    matches += 1
            if matches >= 2:
                return row_idx
        return None

    def _apply_table_style(self, worksheet, header_row: int) -> None:
        if header_row <= 0 or worksheet.max_row < header_row:
            return

        start_cell = f"A{header_row}"
        end_cell = f"{get_column_letter(worksheet.max_column)}{worksheet.max_row}"
        table_range = f"{start_cell}:{end_cell}"

        base_name = re.sub(r'[^A-Za-z0-9_]', '', f"tbl_{worksheet.title}") or "PlaylistTable"
        base_name = base_name[:31]

        existing_names = set(getattr(worksheet, 'tables', {}).keys())
        unique_name = base_name
        suffix = 1
        while unique_name in existing_names:
            unique_name = f"{base_name[:25]}_{suffix}"
            suffix += 1

        for existing in list(getattr(worksheet, 'tables', {}).keys()):
            del worksheet.tables[existing]

        table = Table(displayName=unique_name, ref=table_range)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        worksheet.add_table(table)

    def _format_playlist_sheet(self, worksheet, auto_resize: bool = False) -> Optional[int]:
        column_widths = {
            'A': 30,
            'B': 40,
            'C': 40,
            'D': 15,
            'E': 60,
            'F': 12,
            'G': 15,
            'H': 15,
            'I': 12,
            'J': 12,
            'K': 15,
            'L': 20,
            'M': 12,
            'N': 15,
            'O': 12,
            'P': 15,
        }

        for col_letter, width in column_widths.items():
            worksheet.column_dimensions[col_letter].width = width

        header_row = self._find_data_header_row(worksheet)
        if not header_row:
            return None

        header_cells = list(
            worksheet.iter_rows(
                min_row=header_row,
                max_row=header_row,
                min_col=1,
                max_col=worksheet.max_column,
            )
        )[0]
        header_letters = {cell.column_letter for cell in header_cells if cell.value}

        header_fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        for cell in header_cells:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

        for row_idx in range(1, min(header_row, 10)):
            if row_idx == 1:
                worksheet.row_dimensions[row_idx].height = 30
            elif row_idx <= 7:
                worksheet.row_dimensions[row_idx].height = 20

        self._apply_table_style(worksheet, header_row)

        if auto_resize:
            for column in worksheet.columns:
                column_letter = column[0].column_letter
                if column_letter in column_widths:
                    continue
                max_length = 0
                for cell in column[header_row - 1:]:
                    try:
                        if cell.value is not None:
                            max_length = max(max_length, len(str(cell.value)))
                    except Exception:
                        continue
                if max_length:
                    adjusted_width = min((max_length + 2) * 1.1, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        for row in worksheet.iter_rows(min_row=1, max_row=worksheet.max_row, min_col=1, max_col=worksheet.max_column):
            for cell in row:
                wrap = False if cell.row <= 7 else True
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=wrap)

        return header_row

    def _add_table_formatting(self, output_path, job_state):
        try:
            workbook = load_workbook(output_path)
            if not workbook.sheetnames:
                worksheet = workbook.create_sheet("Playlist Data")
                headers = ['Artist', 'Album', 'Track', 'Duration', 'Spotify URL', 'Tempo', 'Key',
                           'Danceability', 'Energy', 'Valence', 'Acousticness', 'Instrumentalness',
                           'Liveness', 'Speechiness', 'Loudness', 'Time Signature']
                worksheet.append(headers)

            for sheet_name in workbook.sheetnames:
                if job_state and job_state.get('cancelled'):
                    workbook.close()
                    return

                worksheet = workbook[sheet_name]
                if worksheet.max_row < 2:
                    headers = ['Artist', 'Album', 'Track', 'Duration', 'Spotify URL', 'Tempo', 'Key',
                               'Danceability', 'Energy', 'Valence', 'Acousticness', 'Instrumentalness',
                               'Liveness', 'Speechiness', 'Loudness', 'Time Signature']
                    if worksheet.max_row == 0:
                        worksheet.append(headers)
                    if worksheet.max_row < 2:
                        worksheet.append(['No tracks found', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])

                header_row = self._format_playlist_sheet(worksheet, auto_resize=True)
                if header_row:
                    self._apply_table_style(worksheet, header_row)
                    self._convert_track_urls_to_hyperlinks(worksheet)

            workbook.save(output_path)
            workbook.close()

        except Exception as e:
            logger.error(f"Error formatting Excel file: {e}")
            if 'workbook' in locals():
                workbook.close()

    def _convert_track_urls_to_hyperlinks(self, worksheet):
        try:
            header_row = None
            url_col = 5  # Column E
            for row in range(1, worksheet.max_row + 1):
                value = worksheet.cell(row=row, column=url_col).value
                if isinstance(value, str) and value.lower().strip() in {'spotify url', 'track url'}:
                    header_row = row
                    break

            if not header_row:
                return

            for row in range(header_row + 1, worksheet.max_row + 1):
                cell = worksheet.cell(row=row, column=url_col)
                url = cell.value
                if isinstance(url, str) and url.startswith('http'):
                    cell.hyperlink = url
                    cell.style = 'Hyperlink'
        except Exception as exc:
            logger.warning("Error converting URLs to hyperlinks: %s", exc)

    def _adjust_column_widths(self, file_path, job_state):
        try:
            wb = load_workbook(file_path)
            for sheet_name in wb.sheetnames:
                if job_state and job_state.get('cancelled'):
                    wb.close()
                    return

                ws = wb[sheet_name]
                if sheet_name != 'Playlists':
                    # Format playlist sheets with table styling
                    self._format_playlist_sheet(ws, auto_resize=True)
                if not self._find_data_header_row(ws):
                    continue

                self._convert_track_urls_to_hyperlinks(ws)

            wb.save(file_path)
            wb.close()

        except Exception as exc:
            logger.warning("Error adjusting column widths: %s", exc)

    def _refresh_filename_after_export(self):
        if hasattr(self, 'filename_input'):
            try:
                current_filename = self.filename_input.text or ''
                new_default = self._generate_default_filename()
                
                # Check if current filename is the same as the new default (without extension)
                current_base = current_filename.replace('.xlsx', '')
                new_base = new_default.replace('.xlsx', '')
                
                if current_base == new_base:
                    # Apply incremental numbering
                    self.filename_input.text = self._increment_filename_suffix(new_default)
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
        base = filename.replace('.xlsx', '')
        
        # Check for existing suffix pattern
        if base.endswith('_5'):
            # Already at _5, keep as is (could cycle back to _2 or stay at _5)
            return filename
        elif base.endswith('_4'):
            return base.replace('_4', '_5') + '.xlsx'
        elif base.endswith('_3'):
            return base.replace('_3', '_4') + '.xlsx'
        elif base.endswith('_2'):
            return base.replace('_2', '_3') + '.xlsx'
        else:
            # No suffix, add _2
            return base + '_2.xlsx'

    def _generate_default_filename(self) -> str:
        # Get username from the app with better fallback
        app = App.get_running_app()
        username = getattr(app, 'username', None)
        
        # Handle None or empty username cases
        if not username or username == 'None':
            username = 'user'
        
        # Format: YYYY-MM-DD_HH-MM-SSAM/PM
        timestamp = datetime.now().strftime('%Y-%m-%d_%I-%M-%S%p')
        
        return f'Spotify_Playlists_{username}_{timestamp}.xlsx'

    def _sanitize_sheet_name(self, name: str) -> str:
        sanitized = re.sub(r"[\[\]\\/?*:]", "_", name).strip("'")
        sanitized = sanitized[:31] or "Playlist"
        return sanitized

    def _get_playlist_metadata(self, playlist):
        owner_info = playlist.get('owner', {})
        owner_display = owner_info.get('display_name') or owner_info.get('id', 'Unknown')
        followers = playlist.get('followers', {}).get('total') if playlist.get('followers') else 'Unknown'
        description = (playlist.get('description') or '').strip() or 'No description available'
        return {
            'name': playlist.get('name', 'Unknown Playlist'),
            'owner': owner_display,
            'followers': followers,
            'description': description,
            'url': playlist.get('external_urls', {}).get('spotify', 'N/A'),
        }

    def _get_playlist_cover_url(self, playlist):
        try:
            images = playlist.get('images', []) or []
            if not images:
                return None
            for image in images:
                width = image.get('width')
                if width and 200 <= width <= 400:
                    return image.get('url')
            return images[0].get('url')
        except Exception as exc:
            logger.warning("Error retrieving playlist cover image: %s", exc)
            return None

    def download_and_cache_image(self, image_url, playlist_name):
        if not image_url:
            return None
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            temp_fd, temp_path = tempfile.mkstemp(prefix='playlist_cover_', suffix='.img')
            with os.fdopen(temp_fd, 'wb') as tmp:
                tmp.write(response.content)
            return temp_path
        except Exception as exc:
            logger.warning("Error downloading playlist image for %s: %s", playlist_name, exc)
            return None

    def _show_completion_popup(self, filename, output_path):
        is_mobile = is_mobile_platform()

        main_container = BoxLayout(orientation='vertical', size_hint=(1, 1))
        main_container.add_widget(Widget(size_hint_y=1))

        content = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            padding=dp(20),
            size_hint=(1, None),
            height=dp(300) if not is_mobile else dp(350),
        )

        success_label = Label(
            text='Export completed successfully!',
            font_size=dp(20),
            bold=True,
            size_hint_y=None,
            height=dp(35),
            halign='center',
            valign='middle',
        )
        success_label.bind(width=lambda *x: setattr(success_label, 'text_size', (success_label.width, None)))

        filename_label = Label(
            text=f'File saved as:\n{filename}',
            font_size=dp(18),
            size_hint_y=None,
            height=dp(60),
            halign='center',
            valign='middle',
            text_size=(dp(400), None),
        )

        location = os.path.dirname(output_path)
        location_label = Label(
            text=f'Location:\n{location}',
            font_size=dp(16),
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None,
            height=dp(60),
            halign='center',
            valign='middle',
            text_size=(dp(400), None),
        )

        content.add_widget(success_label)
        content.add_widget(filename_label)
        content.add_widget(location_label)

        if not is_mobile:
            question = Label(
                text='Would you like to open the file now?',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(35),
                halign='center',
                valign='middle',
            )
            question.bind(width=lambda *x: setattr(question, 'text_size', (question.width, None)))

            buttons = BoxLayout(
                orientation='horizontal',
                size_hint=(0.8, None),
                height=dp(50),
                spacing=dp(15),
                pos_hint={'center_x': 0.5},
            )

            close_btn = Button(
                text='Close',
                size_hint_x=0.5,
                font_size=dp(16),
                background_color=[0.6, 0.6, 0.6, 1],
            )

            open_btn = Button(
                text='Open File',
                size_hint_x=0.5,
                font_size=dp(16),
                background_color=[0.2, 0.6, 0.2, 1],
            )

            buttons.add_widget(close_btn)
            buttons.add_widget(open_btn)

            content.add_widget(Widget(size_hint_y=1))
            content.add_widget(question)
            content.add_widget(buttons)

            main_container.add_widget(content)
            main_container.add_widget(Widget(size_hint_y=1))

            popup = Popup(
                title='Export Complete',
                content=main_container,
                size_hint=(0.7, 0.65),
                auto_dismiss=False,
            )

            close_btn.bind(on_press=lambda *_: popup.dismiss())
            open_btn.bind(on_press=lambda *_: self._handle_open_file_request(popup, output_path))
        else:
            mobile_text = Label(
                text="Use your device's file manager to locate and open the exported file.",
                font_size=dp(14),
                color=(0.8, 0.8, 0.8, 1),
                size_hint_y=None,
                height=dp(60),
                halign='center',
                valign='middle',
                text_size=(dp(400), None),
            )

            ok_btn = Button(
                text='OK',
                size_hint=(0.5, None),
                height=dp(45),
                font_size=dp(16),
                pos_hint={'center_x': 0.5},
            )

            content.add_widget(mobile_text)
            content.add_widget(Widget(size_hint_y=1))
            content.add_widget(ok_btn)

            main_container.add_widget(content)
            main_container.add_widget(Widget(size_hint_y=1))

            popup = Popup(
                title='Export Complete',
                content=main_container,
                size_hint=(0.8, 0.7),
                auto_dismiss=False,
            )

            ok_btn.bind(on_press=lambda *_: popup.dismiss())

        popup.open()

    # File handling ------------------------------------------------------
    def _handle_open_file_request(self, popup, file_path):
        popup.dismiss()
        if not self._open_file_with_system_default(file_path):
            Popup(
                title='Unable to Open File',
                content=Label(text='Could not open the file with the system default application.\n\nPlease navigate to the file location and open it manually.', text_size=(dp(350), None), halign='center'),
                size_hint=(0.6, 0.4),
            ).open()

    def _open_file_with_system_default(self, file_path: str) -> bool:
        try:
            system = platform.system()
            if system == 'Darwin':
                subprocess.call(['open', file_path])
                return True
            if system == 'Windows':
                os.startfile(file_path)  # type: ignore[attr-defined]
                return True
            if system == 'Linux':
                subprocess.call(['xdg-open', file_path])
                return True
        except Exception as exc:
            logger.error("Error opening file %s: %s", file_path, exc)
        return False

    # Cache + logout -----------------------------------------------------
    def purge_cache(self, *_args) -> None:
        def confirm(_instance):
            try:
                persistent_cache.clear_all_cache()
                self.update_status_with_cache_info()
                Popup(
                    title='Cache Cleared',
                    content=Label(text='All cached data has been cleared successfully.'),
                    size_hint=(0.6, 0.4),
                    auto_dismiss=True,
                ).open()
            except Exception as exc:
                logger.error("Error clearing cache: %s", exc)
                Popup(
                    title='Error',
                    content=Label(text=f'Error clearing cache: {exc}'),
                    size_hint=(0.6, 0.4),
                    auto_dismiss=True,
                ).open()
            confirm_popup.dismiss()

        def cancel(_instance):
            confirm_popup.dismiss()

        content = BoxLayout(orientation='vertical', spacing=dp(10))
        message = Label(
            text='This will clear all cached playlists, images, and ReccoBeats data.\n\nAre you sure you want to continue?',
            text_size=(dp(300), None),
            halign='center',
            valign='middle',
        )
        content.add_widget(message)
        buttons = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(40))
        cancel_btn = Button(text='Cancel', size_hint_x=0.5)
        confirm_btn = Button(text='Clear Cache', size_hint_x=0.5, background_color=[0.8, 0.3, 0.3, 1])
        cancel_btn.bind(on_press=cancel)
        confirm_btn.bind(on_press=confirm)
        buttons.add_widget(cancel_btn)
        buttons.add_widget(confirm_btn)
        content.add_widget(buttons)
        confirm_popup = Popup(title='Confirm Cache Clear', content=content, size_hint=(0.7, 0.5), auto_dismiss=False)
        confirm_popup.open()

    def logout(self, *_args) -> None:
        selected_count = sum(1 for w in self.playlist_widgets if w.checkbox.active)
        if selected_count > 0:
            self._show_logout_confirmation(selected_count)
        else:
            self._perform_logout()

    def _show_logout_confirmation(self, selected_count: int) -> None:
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
        content.add_widget(Widget(size_hint_y=0.2))
        plural = 'playlist' if selected_count == 1 else 'playlists'
        content.add_widget(
            Label(
                text=f'You have {selected_count} {plural} selected.\n\nAre you sure you want to log out?',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(80),
                halign='center',
                valign='center',
                text_size=(dp(400), dp(80)),
            )
        )
        content.add_widget(Widget(size_hint_y=0.3))
        buttons = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
        cancel_btn = Button(text='Cancel', size_hint_x=0.5, font_size=dp(16), background_color=[0.6, 0.6, 0.6, 1])
        logout_btn = Button(text='Log Out', size_hint_x=0.5, font_size=dp(16), background_color=[0.8, 0.3, 0.3, 1])
        buttons.add_widget(cancel_btn)
        buttons.add_widget(logout_btn)
        content.add_widget(buttons)
        popup = Popup(title='Confirm Logout', content=content, size_hint=(0.6, 0.4), auto_dismiss=False)
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        logout_btn.bind(on_press=lambda *_: self._handle_logout_confirmed(popup))
        popup.open()

    def _handle_logout_confirmed(self, popup) -> None:
        popup.dismiss()
        self._perform_logout()

    def _perform_logout(self) -> None:
        try:
            app = App.get_running_app()
            app.token_info = None
            app.username = None
            login_screen = app.screen_manager.get_screen('login')
            login_screen.status_label.text = ''
            app.switch_to_login()
        except Exception as exc:
            logger.error("Error performing logout: %s", exc)

    # Cache management ----------------------------------------------------
    def show_clear_cache_confirmation(self, *_args) -> None:
        """Show confirmation dialog for clearing cache."""
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(20))
        content.add_widget(Widget(size_hint_y=0.2))
        
        content.add_widget(
            Label(
                text='This will clear all downloaded data. Are you sure?',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(60),
                halign='center',
                valign='center',
                text_size=(dp(400), dp(60)),
            )
        )
        content.add_widget(Widget(size_hint_y=0.3))
        
        buttons = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(15))
        cancel_btn = Button(text='No', size_hint_x=0.5, font_size=dp(16), background_color=[0.6, 0.6, 0.6, 1])
        confirm_btn = Button(text='Yes', size_hint_x=0.5, font_size=dp(16), background_color=[0.8, 0.3, 0.3, 1])
        
        buttons.add_widget(cancel_btn)
        buttons.add_widget(confirm_btn)
        content.add_widget(buttons)
        
        popup = Popup(title='Confirm Cache Clear', content=content, size_hint=(0.7, 0.5), auto_dismiss=False)
        
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        confirm_btn.bind(on_press=lambda *_: self.clear_all_cache(popup))
        popup.open()

    def clear_all_cache(self, popup) -> None:
        """Clear all cache data and update UI."""
        try:
            popup.dismiss()
            
            # Show progress message
            self.status_label.text = 'Clearing cache...'
            
            # Clear the cache
            persistent_cache.clear_all_cache()
            
            # Update status
            self.update_status_with_cache_info()
            
            # Show success message
            success_popup = Popup(
                title='Cache Cleared',
                content=Label(text='All cached data has been cleared successfully.'),
                size_hint=(0.6, 0.4),
                auto_dismiss=True
            )
            success_popup.open()
            
            logger.info("Cache cleared by user")
            
        except Exception as exc:
            logger.error("Error clearing cache: %s", exc)
            self.status_label.text = f'Error clearing cache: {exc}'
            
            # Show error message
            error_popup = Popup(
                title='Error',
                content=Label(text=f'Failed to clear cache: {exc}'),
                size_hint=(0.6, 0.4),
                auto_dismiss=True
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
            self.status_label.text = f'Error opening cache explorer: {exc}'
            
            # Show error message
            error_popup = Popup(
                title='Cache Explorer Error',
                content=Label(text=f'Failed to open cache explorer:\n{exc}'),
                size_hint=(0.6, 0.4),
                auto_dismiss=True
            )
            error_popup.open()
