"""Logout confirmation flow for MainScreen."""

from __future__ import annotations

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from ...shared.logging_config import logger


def logout(screen, *_args) -> None:
    """Handle logout request."""
    selected_count = sum(1 for w in screen.playlist_widgets if w.checkbox.active)
    if selected_count > 0:
        show_logout_confirmation(screen, selected_count)
    else:
        perform_logout()


def show_logout_confirmation(screen, selected_count: int) -> None:
    """Show logout confirmation dialog."""
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
    logout_btn.bind(on_press=lambda *_: handle_logout_confirmed(screen, popup))
    popup.open()


def handle_logout_confirmed(screen, popup) -> None:
    """Handle logout confirmation."""
    popup.dismiss()
    perform_logout()


def perform_logout() -> None:
    """Perform logout operation."""
    try:
        app = App.get_running_app()
        if app and hasattr(app, "logout"):
            # Use the comprehensive auth state clearing function from the app
            app.logout()
    except Exception as exc:
        logger.error("Error performing logout: %s", exc)
