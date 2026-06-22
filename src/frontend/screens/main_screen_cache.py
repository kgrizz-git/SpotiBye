"""Cache-related popup flows for MainScreen."""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from ...shared.logging_config import logger
from ..ui.cache_explorer import CacheExplorerPopup


def show_clear_cache_confirmation(screen, *_args) -> None:
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
    confirm_btn.bind(on_press=lambda *_: clear_all_cache(screen, popup))
    popup.open()


def clear_all_cache(screen, popup) -> None:
    """Clear all cache data and update UI.

    Delegates the actual cache deletion to screen.backend_adapter.cache_manager.
    Only env-hash-prefixed data files are cleared (default in clear_cache);
    auth tokens and backend selection are preserved.
    """
    try:
        popup.dismiss()

        if not getattr(screen, "backend_adapter", None):
            error_popup = Popup(
                title="Error",
                content=Label(text="Backend not initialized — nothing to clear"),
                size_hint=(0.6, 0.4),
                auto_dismiss=True,
            )
            error_popup.open()
            return

        screen.status_label.text = "Clearing cache..."
        screen.backend_adapter.cache_manager.clear_cache(None)
        screen.update_status_with_cache_info()

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
        screen.status_label.text = f"Error clearing cache: {exc}"

        error_popup = Popup(
            title="Error",
            content=Label(text=f"Failed to clear cache: {exc}"),
            size_hint=(0.6, 0.4),
            auto_dismiss=True,
        )
        error_popup.open()


def open_cache_explorer(screen, backend_available: bool, create_cache_explorer_fn, *_args) -> None:
    """Open the cache explorer popup with backend support."""
    try:
        if backend_available and create_cache_explorer_fn:
            # Use backend-aware cache explorer
            explorer_popup = create_cache_explorer_fn()
            logger.info("Backend cache explorer opened by user")
        else:
            # Use standard cache explorer
            explorer_popup = CacheExplorerPopup()
            logger.info("Standard cache explorer opened by user")

        explorer_popup.open()
    except Exception as exc:
        logger.error("Error opening cache explorer: %s", exc)
        screen.status_label.text = f"Error opening cache explorer: {exc}"

        error_popup = Popup(
            title="Cache Explorer Error",
            content=Label(text=f"Failed to open cache explorer:\n{exc}"),
            size_hint=(0.6, 0.4),
            auto_dismiss=True,
        )
        error_popup.open()
