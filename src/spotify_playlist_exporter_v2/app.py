"""Application bootstrap for Spotify Playlist Exporter V2."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import spotipy
from kivymd.app import MDApp
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.lang.builder import Builder
from kivy.logger import Logger as logger
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

from .config import CLIENT_ID, CLIENT_SECRET, CACHE_PATH, REDIRECT_URI, SCOPE
from .logging_config import logger
from .state import current_export_job

# Import screens after other imports to avoid circular imports
from .auth.login_screen import LoginScreen
from .screens.main_screen import MainScreen
from .utils.platform_utils import diagnose_macos_issues, set_window_basics


class SpotifyExporterApp(MDApp):
    """Primary Kivy application."""

    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self.token_info = None
        self.username = None
        self.screen_manager: ScreenManager | None = None
        # Match previous dark styling
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.primary_hue = "700"
        self.theme_cls.accent_palette = "Blue"
        self.theme_cls.accent_hue = "400"

    def build(self):  # type: ignore[override]
        try:
            self._setup_fonts()
            self._check_configuration()
            diagnose_macos_issues()
            set_window_basics('Spotify Playlist Exporter - Powered by ReccoBeats')

            self.screen_manager = ScreenManager()
            self.login_screen = LoginScreen(name='login')
            self.main_screen = MainScreen(name='main')

            self.screen_manager.add_widget(self.login_screen)
            self.screen_manager.add_widget(self.main_screen)

            # Check for cached token on startup
            self._try_auto_login()
            
            return self.screen_manager
        except Exception as exc:  # pragma: no cover - UI fallback
            logger.error("Error building app: %s", exc)
            return Label(text=f'Error starting app: {exc}')

    # ------------------------------------------------------------------
    # Screen switching helpers
    # ------------------------------------------------------------------
    def switch_to_main(self) -> None:
        if self.screen_manager:
            self.screen_manager.current = 'main'

    def switch_to_login(self) -> None:
        if self.screen_manager:
            self.screen_manager.current = 'login'

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def _setup_fonts(self) -> None:
        try:
            LabelBase.register(
                name='DejaVuSans',
                fn_regular='DejaVuSans.ttf',
                fn_bold='DejaVuSans-Bold.ttf',
            )
            Config.set('kivy', 'default_font', ['DejaVuSans', 'DejaVuSans.ttf'])
            logger.info("Successfully set DejaVuSans as default font")
        except Exception:
            system_fonts = {
                'Windows': Path('C:/Windows/Fonts/DejaVuSans.ttf'),
                'Darwin': Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
                'Linux': Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
            }
            for path in system_fonts.values():
                if path.exists():
                    try:
                        LabelBase.register(name='DejaVuSans', fn_regular=str(path))
                        Config.set('kivy', 'default_font', ['DejaVuSans'])
                        return
                    except Exception:
                        continue
            logger.warning("Falling back to Kivy default font")

    def _check_configuration(self) -> None:
        if CLIENT_ID == 'YOUR_CLIENT_ID_HERE' or CLIENT_SECRET == 'YOUR_CLIENT_SECRET_HERE':
            popup = Label(
                text='Please set your Spotify CLIENT_ID and CLIENT_SECRET\n'
                'in the environment before running the app.',
            )
            logger.warning("Spotify credentials not configured")
            raise RuntimeError('Spotify credentials not configured')

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------
    def _try_auto_login(self) -> None:
        """Attempt to log in using cached token if available."""
        try:
            # Check if we should force fresh OAuth (user logged out)
            from . import state
            if getattr(state, 'force_fresh_oauth', False):
                logger.info("Force fresh OAuth requested - skipping auto-login")
                state.force_fresh_oauth = False
                return
            
            # Use standard cache handler for normal token persistence
            cache_handler = CacheFileHandler(cache_path=CACHE_PATH)
            sp_oauth = SpotifyOAuth(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=REDIRECT_URI,
                scope=SCOPE,
                cache_handler=cache_handler
            )
            
            token_info = sp_oauth.get_cached_token()
            if token_info and not sp_oauth.is_token_expired(token_info):
                sp = spotipy.Spotify(auth=token_info['access_token'])
                user = sp.current_user()
                self.token_info = token_info
                self.username = user.get('display_name', user.get('id', 'User'))
                self.screen_manager.current = 'main'
                logger.info("Auto-login successful")
            else:
                logger.info("No valid cached token found - showing login screen")
        except Exception as e:
            logger.error(f"Auto-login failed: {e}")
            # Clear invalid token
            if os.path.exists(CACHE_PATH):
                try:
                    os.remove(CACHE_PATH)
                except Exception as e:
                    logger.error(f"Failed to remove invalid token: {e}")

    def logout(self) -> None:
        """Log out the current user and clear the token cache."""
        try:
            # Use the comprehensive auth state clearing function
            from .auth.login_screen import clear_all_auth_state
            clear_all_auth_state()
                
        except Exception as e:
            logger.error(f"Error during logout: {e}")
        finally:
            # Clear all authentication state
            self.token_info = None
            self.username = None
            
            # Return to login screen
            if hasattr(self, 'screen_manager'):
                self.screen_manager.current = 'login'
            
            logger.info("Logout completed - all auth state cleared")

    def on_stop(self) -> None:  # type: ignore[override]
        global current_export_job
        if current_export_job:
            current_export_job['cancelled'] = True
        try:
            if self.screen_manager and self.screen_manager.current == 'main':
                main_screen = self.screen_manager.get_screen('main')
                selected = sum(1 for w in main_screen.playlist_widgets if w.checkbox.active)
                if selected > 0:
                    logger.info("App closing with %s playlists selected", selected)
        except Exception as exc:
            logger.error("Error during app stop: %s", exc)


__all__ = ["SpotifyExporterApp"]
