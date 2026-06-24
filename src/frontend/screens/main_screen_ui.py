"""UI construction for MainScreen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from ..config.backend_config import EXPORT_DIR as SAVE_DIR
from ..ui.layouts import ResponsiveGridLayout

if TYPE_CHECKING:
    from .main_screen import MainScreen


class MainScreenUIBuilder:
    """Builds MainScreen widgets and binds events to screen facade methods."""

    def __init__(self, screen: MainScreen) -> None:
        self.screen = screen

    def build_ui(self) -> None:
        main_layout = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(6))
        header = self._create_header()
        controls = self._create_controls()
        scroll = self._create_scroll_view()
        self.screen.playlist_layout = ResponsiveGridLayout()
        scroll.add_widget(self.screen.playlist_layout)
        export_section = self._create_export_section()

        main_layout.add_widget(header)
        main_layout.add_widget(controls)
        main_layout.add_widget(scroll)
        main_layout.add_widget(export_section)

        self.screen.add_widget(main_layout)

    def _create_header(self) -> RelativeLayout:
        screen = self.screen
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
        screen.username_label = Label(
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
        header.add_widget(screen.username_label)
        return header

    def _create_controls(self) -> BoxLayout:
        screen = self.screen
        controls = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(6),
            padding=(dp(3), 0, dp(3), 0),
        )

        sort_section = BoxLayout(
            orientation="horizontal", size_hint_x=None, width=dp(245), spacing=dp(4)
        )

        sort_section.add_widget(
            Label(
                text="Sort:",
                size_hint_x=None,
                width=dp(35),
                font_size=dp(14),
                color=(0.9, 0.9, 0.9, 1),
            )
        )

        screen.sort_spinner = Spinner(
            text="Default",
            values=["Default", "Playlist Title", "# of Tracks", "Owner"],
            size_hint_x=None,
            width=dp(100),
            font_size=dp(14),
            text_size=(dp(90), None),
            halign="center",
            background_color=[0.55, 0.55, 0.55, 1],
        )
        screen.sort_spinner.bind(on_press=screen.configure_dropdown)
        screen.sort_spinner.bind(text=screen.on_sort_change)
        sort_section.add_widget(screen.sort_spinner)

        screen.by_label = Label(
            text="By:",
            size_hint_x=None,
            width=dp(25),
            font_size=dp(14),
            color=(0.9, 0.9, 0.9, 1),
        )
        sort_section.add_widget(screen.by_label)

        screen.sort_direction_btn = Button(
            text="A-Z",
            size_hint_x=None,
            width=dp(60),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        screen.sort_direction_btn.bind(on_press=screen.toggle_sort_direction)
        sort_section.add_widget(screen.sort_direction_btn)

        search_section = BoxLayout(
            orientation="horizontal",
            size_hint_x=0.85,
            spacing=dp(2),
            padding=(dp(5), 0, dp(3), 0),
        )

        search_section.add_widget(
            Label(
                text="Search:",
                size_hint_x=None,
                width=dp(55),
                font_size=dp(14),
                color=(0.9, 0.9, 0.9, 1),
            )
        )

        search_input_container = BoxLayout(
            orientation="horizontal",
            size_hint_x=1,
            spacing=dp(2),
        )

        screen.search_input = TextInput(
            multiline=False,
            size_hint_x=0.94,
            size_hint_max_x=dp(350),
            font_size=dp(14),
            hint_text="Filter playlists...",
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.6, 0.6, 0.6, 1),
            padding=(dp(8), dp(5)),
            background_active="",
            background_normal="",
            write_tab=False,
        )
        search_input_container.add_widget(screen.search_input)

        clear_search_btn = Button(
            text="×",
            size_hint_x=None,
            width=dp(28),
            background_color=(0.3, 0.3, 0.3, 1),
            font_size=dp(18),
            color=(0.8, 0.8, 0.8, 1),
        )
        clear_search_btn.bind(on_press=screen.clear_search)
        search_input_container.add_widget(clear_search_btn)

        search_section.add_widget(search_input_container)
        screen.search_input.bind(text=screen.on_search_text)

        action_buttons = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(325),
            spacing=dp(2),
        )

        screen.select_all_btn = Button(
            text="Select All",
            size_hint_x=None,
            width=dp(100),
            background_color=[0.25, 0.85, 0.25, 1],
            font_size=dp(14),
        )
        screen.select_all_btn.bind(on_press=screen.toggle_select_all)
        action_buttons.add_widget(screen.select_all_btn)

        clear_all_btn = Button(
            text="Clear All",
            size_hint_x=None,
            width=dp(100),
            background_color=[0.8, 0.2, 0.2, 1],
            font_size=dp(14),
        )
        clear_all_btn.bind(on_press=screen.deselect_all)
        action_buttons.add_widget(clear_all_btn)

        reload_btn = Button(
            text="Reload",
            size_hint_x=None,
            width=dp(90),
            background_color=[0.32, 0.32, 0.88, 1],
            font_size=dp(14),
        )
        reload_btn.bind(on_press=screen.load_playlists_with_cache)
        action_buttons.add_widget(reload_btn)

        right_section = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            width=dp(220),
            spacing=dp(3),
            padding=(dp(3), 0, dp(3), 0),
        )

        screen.selection_label = Label(
            text="0 selected",
            font_size=dp(14),
            halign="right",
            color=(0.88, 0.88, 0.88, 1),
            size_hint_x=0.7,
        )
        right_section.add_widget(screen.selection_label)

        logout_btn = Button(
            text="Logout",
            size_hint_x=None,
            width=dp(75),
            height=dp(35),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        logout_btn.bind(on_press=screen.logout)
        right_section.add_widget(logout_btn)

        controls.add_widget(sort_section)
        controls.add_widget(search_section)
        controls.add_widget(Widget(size_hint_x=0.2))
        controls.add_widget(action_buttons)
        controls.add_widget(right_section)
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
        screen = self.screen
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
        screen.filename_input = TextInput(
            text=screen._generate_default_filename("xlsx"),
            multiline=False,
            size_hint_y=None,
            height=dp(30),
            font_size=dp(15),
        )
        filename_layout.add_widget(screen.filename_input)
        export_section.add_widget(filename_layout)

        format_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8)
        )
        format_layout.add_widget(
            Label(text="Format:", size_hint_x=None, width=dp(60), font_size=dp(15))
        )

        screen.format_spinner = Spinner(
            text="XLSX",
            values=["XLSX", "CSV", "JSON"],
            size_hint_x=None,
            width=dp(100),
            font_size=dp(14),
            background_color=[0.55, 0.55, 0.55, 1],
        )
        screen.format_spinner.bind(text=screen.on_format_change)
        format_layout.add_widget(screen.format_spinner)
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

        screen.export_btn = Button(
            text="Export Selected Playlists",
            size_hint_y=None,
            height=dp(45),
            font_size=dp(16),
        )
        screen.export_btn.bind(on_press=screen.start_export)
        export_section.add_widget(screen.export_btn)

        screen.cancel_btn = Button(
            text="Cancel Export",
            size_hint_y=None,
            height=dp(45),
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
            opacity=0,
            disabled=True,
        )
        screen.cancel_btn.bind(on_press=screen.cancel_export)
        export_section.add_widget(screen.cancel_btn)

        screen.progress_bar = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(18)
        )
        export_section.add_widget(screen.progress_bar)

        status_bar_container = RelativeLayout(size_hint_y=None, height=dp(30))

        screen.status_label = Label(
            text="Ready to export",
            font_size=dp(14),
            size_hint=(None, None),
            width=dp(400),
            height=dp(30),
            halign="center",
            valign="middle",
            pos_hint={"center_x": 0.51, "center_y": 0.5},
        )
        status_bar_container.add_widget(screen.status_label)

        button_container = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(200),
            height=dp(30),
            spacing=dp(5),
            pos_hint={"right": 1, "top": 1},
        )

        screen.clear_cache_btn = Button(
            text="Clear Cache",
            size_hint_x=None,
            width=dp(90),
            height=dp(28),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12),
        )
        screen.clear_cache_btn.bind(on_press=screen.show_clear_cache_confirmation)
        button_container.add_widget(screen.clear_cache_btn)

        screen.cache_explorer_btn = Button(
            text="Cache Explorer",
            size_hint_x=None,
            width=dp(100),
            height=dp(28),
            background_color=[0.3, 0.5, 0.8, 1],
            font_size=dp(12),
        )
        screen.cache_explorer_btn.bind(on_press=screen.open_cache_explorer)
        button_container.add_widget(screen.cache_explorer_btn)

        status_bar_container.add_widget(button_container)
        export_section.add_widget(status_bar_container)
        return export_section
