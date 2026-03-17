"""Backend-integrated application bootstrap for Spotify Playlist Exporter V2."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from kivymd.app import MDApp
from kivy.clock import Clock
from kivy.config import Config
from kivy.lang.builder import Builder
from kivy.logger import Logger as logger
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager

# Import backend components
from ..services.backend_client import BackendClient, get_backend_client, set_backend_url
from ..auth.backend_login_screen import BackendLoginScreen, create_backend_login_screen
from ..caching.backend_cache import BackendCacheManager, get_cache_manager, set_cache_manager
from ..config.backend_config import (
    ENABLE_BACKEND_SELECTOR,
    resolve_startup_backend_url,
    save_backend_url,
    validate_config,
    get_config_summary,
)
from ..screens.backend_main_screen_adapter import BackendMainScreenAdapter, create_backend_adapter
from ..ui.backend_selector_popup import BackendSelectorPopup

# Import original components for compatibility
from ...spotify_playlist_exporter_v2.screens.main_screen import MainScreen
from ...spotify_playlist_exporter_v2.logging_config import logger as original_logger
from ...spotify_playlist_exporter_v2.utils.platform_utils import diagnose_macos_issues, set_window_basics


class BackendSpotifyExporterApp(MDApp):
    """Backend-integrated Kivy application."""

    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self.token_info = None
        self.username = None
        self.screen_manager: ScreenManager | None = None
        
        # Backend components
        self.backend_client: Optional[BackendClient] = None
        self.cache_manager: Optional[BackendCacheManager] = None
        self.backend_adapter: Optional[BackendMainScreenAdapter] = None
        self.selected_backend_url: str = resolve_startup_backend_url()
        self.backend_selector_popup: Optional[Popup] = None
        self.pending_export_popup: Optional[Popup] = None
        
        # Match previous dark styling
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.primary_hue = "700"
        self.theme_cls.accent_palette = "Blue"
        self.theme_cls.accent_hue = "400"
        
        # Backend components are initialized after runtime backend selection.

    def _initialize_backend(self, backend_url: str) -> None:
        """Initialize backend components."""
        try:
            # Validate configuration
            config_issues = validate_config()
            if config_issues:
                original_logger.warning(f"Configuration issues: {config_issues}")

            self.selected_backend_url = backend_url.rstrip('/')

            # Initialize backend client and sync global singleton.
            set_backend_url(self.selected_backend_url)
            self.backend_client = get_backend_client()
            
            # Initialize cache manager bound to selected backend.
            self.cache_manager = BackendCacheManager(self.backend_client)
            set_cache_manager(self.cache_manager)
            
            # Initialize backend adapter
            self.backend_adapter = create_backend_adapter(self.backend_client)

            # Update login screen with selected backend.
            if hasattr(self, 'login_screen') and self.login_screen:
                self.login_screen.set_backend_client(self.backend_client)
            
            original_logger.info(f"Backend initialized with URL: {self.selected_backend_url}")
            
            # Log configuration summary in debug mode
            from ..config.backend_config import FeatureFlags
            if FeatureFlags.DEBUG_NETWORK:
                config_summary = get_config_summary()
                original_logger.info(f"Backend config: {config_summary}")
                
        except Exception as e:
            original_logger.error(f"Failed to initialize backend: {e}")
            # Continue without backend - will show error to user

    def build(self):  # type: ignore[override]
        try:
            self._setup_fonts()
            diagnose_macos_issues()
            set_window_basics('Spotify Playlist Exporter - Powered by ReccoBeats & Cloudflare')

            self.screen_manager = ScreenManager()
            
            # Create login screen (backend version)
            self.login_screen = create_backend_login_screen(
                self.backend_client,
                on_change_backend=self.open_backend_selector,
            )
            self.login_screen.name = 'login'
            
            # Create main screen (original version)
            self.main_screen = MainScreen(name='main')

            self.screen_manager.add_widget(self.login_screen)
            self.screen_manager.add_widget(self.main_screen)

            # Open selector first, or apply resolved default if selector disabled.
            if ENABLE_BACKEND_SELECTOR:
                Clock.schedule_once(lambda _dt: self.open_backend_selector(), 0)
            else:
                self._initialize_backend(self.selected_backend_url)
                self._try_auto_login()
            
            return self.screen_manager
            
        except Exception as exc:  # pragma: no cover - UI fallback
            original_logger.error("Error building backend app: %s", exc)
            return Label(text=f'Error starting app: {exc}')

    def open_backend_selector(self) -> None:
        """Open backend selector popup for runtime backend selection."""
        if self.backend_selector_popup:
            return

        self.backend_selector_popup = BackendSelectorPopup(
            default_url=self.selected_backend_url,
            on_apply=self.apply_backend_url,
            on_cancel=self._on_backend_selector_cancel,
        )
        self.backend_selector_popup.bind(on_dismiss=lambda _instance: self._clear_backend_selector_popup())
        self.backend_selector_popup.open()

    def _clear_backend_selector_popup(self) -> None:
        """Clear popup reference when selector closes."""
        self.backend_selector_popup = None

    def _on_backend_selector_cancel(self) -> None:
        """Fallback to resolved startup backend when selector is canceled."""
        self.apply_backend_url(self.selected_backend_url)

    def apply_backend_url(self, backend_url: str) -> None:
        """Apply user-selected backend URL and continue startup flow."""
        self._initialize_backend(backend_url)
        save_backend_url(self.selected_backend_url)

        # Check for cached authentication after backend is ready.
        self._try_auto_login()

    # ------------------------------------------------------------------
    # Screen switching helpers
    # ------------------------------------------------------------------
    def switch_to_main(self) -> None:
        """Switch to main screen."""
        if self.screen_manager:
            self.screen_manager.current = 'main'
            
            # Initialize main screen with backend adapter
            if hasattr(self.main_screen, 'initialize_with_backend') and self.backend_adapter:
                self.main_screen.initialize_with_backend(self.backend_adapter)
            Clock.schedule_once(lambda _dt: self._check_pending_export_after_login(), 0.2)

    def switch_to_login(self) -> None:
        """Switch to login screen."""
        if self.screen_manager:
            self.screen_manager.current = 'login'

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def _setup_fonts(self) -> None:
        """Setup fonts for the application."""
        try:
            from kivy.core.text import LabelBase
            LabelBase.register(
                name='DejaVuSans',
                fn_regular='DejaVuSans.ttf',
                fn_bold='DejaVuSans-Bold.ttf',
            )
            Config.set('kivy', 'default_font', ['DejaVuSans', 'DejaVuSans.ttf'])
            original_logger.info("Successfully set DejaVuSans as default font")
        except Exception:
            system_fonts = {
                'Windows': Path('C:/Windows/Fonts/DejaVuSans.ttf'),
                'Darwin': Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
                'Linux': Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
            }
            for path in system_fonts.values():
                if path.exists():
                    try:
                        from kivy.core.text import LabelBase
                        LabelBase.register(name='DejaVuSans', fn_regular=str(path))
                        Config.set('kivy', 'default_font', ['DejaVuSans'])
                        return
                    except Exception:
                        continue
            original_logger.warning("Falling back to Kivy default font")

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _try_auto_login(self) -> None:
        """Attempt to auto-login using cached token."""
        try:
            if not self.cache_manager:
                original_logger.debug("No cache manager available for auto-login")
                return
            
            # Load cached token
            cached_token = self.cache_manager.load_auth_token()
            if cached_token and cached_token.get('token'):
                # Set token in backend client
                if self.backend_client:
                    self.backend_client.set_auth_token(cached_token['token'])
                
                # Extract user info if available
                username = cached_token.get('username', 'User')
                
                # Set app state
                self.token_info = {'access_token': cached_token['token']}
                self.username = username
                
                original_logger.info(f"Auto-login successful for user: {username}")
                # Use standard transition so backend adapter hooks are initialized.
                self.switch_to_main()
            else:
                original_logger.debug("No valid cached token found")
                
        except Exception as e:
            original_logger.error(f"Auto-login failed: {e}")
            # Clear invalid token
            if self.cache_manager:
                self.cache_manager.clear_auth_token()

    def logout(self) -> None:
        """Logout user and clear all authentication state."""
        try:
            original_logger.info("Starting logout process")
            
            # Logout from backend adapter
            if self.backend_adapter:
                self.backend_adapter.logout()
            
            # Clear app state
            self.token_info = None
            self.username = None
            
            # Return to login screen
            if hasattr(self, 'screen_manager') and self.screen_manager:
                self.screen_manager.current = 'login'
                if self.pending_export_popup:
                    self.pending_export_popup.dismiss()
                
                # Refresh login screen connection status
                if hasattr(self.login_screen, 'refresh_connection_status'):
                    self.login_screen.refresh_connection_status()
            
            original_logger.info("Logout completed successfully")
            
        except Exception as e:
            original_logger.error(f"Error during logout: {e}")

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------
    def on_stop(self) -> None:  # type: ignore[override]
        """Handle app stop event."""
        try:
            # Cancel any ongoing export jobs
            from ...spotify_playlist_exporter_v2.state import current_export_job
            if current_export_job:
                current_export_job['cancelled'] = True
            
            # Save any pending cache data
            if self.cache_manager:
                # Cache manager automatically saves data, but we can ensure any
                # pending operations are completed here
                pass
            
            original_logger.info("Backend app stopped gracefully")
            
        except Exception as exc:
            original_logger.error("Error during app stop: %s", exc)

    # ------------------------------------------------------------------
    # Backend utility methods
    # ------------------------------------------------------------------
    def get_backend_status(self) -> Dict[str, Any]:
        """Get current backend status."""
        try:
            if not self.backend_client:
                return {'status': 'not_initialized', 'message': 'Backend not initialized'}
            
            health = self.backend_client.health_check()
            cache_stats = self.cache_manager.get_cache_stats() if self.cache_manager else {}
            
            return {
                'backend_health': health,
                'cache_stats': cache_stats,
                'authenticated': self.backend_client.is_authenticated(),
                'backend_url': self.selected_backend_url,
            }
            
        except Exception as e:
            original_logger.error(f"Error getting backend status: {e}")
            return {'status': 'error', 'error': str(e)}

    def _check_pending_export_after_login(self) -> None:
        """Prompt user after login if a resumable export job is stored locally."""
        if not self.cache_manager or not self.backend_client or not self.backend_adapter:
            return

        cached_job = self.cache_manager.get_active_export_job()
        if not isinstance(cached_job, dict):
            return

        job_id = str(cached_job.get('job_id') or '')
        if not job_id:
            self.cache_manager.clear_active_export_job()
            return

        try:
            status = self.backend_client.get_export_job_status(job_id)
        except Exception as exc:
            if getattr(exc, 'status_code', None) == 404:
                self.cache_manager.clear_active_export_job()
            else:
                original_logger.warning("Pending export status check failed: %s", exc)
            return

        if not isinstance(status, dict):
            return

        is_completed = str(status.get('status') or '') == 'completed' or not bool(status.get('continuation_required', True))
        playlist_names = cached_job.get('playlist_names') or []
        playlist_ids = cached_job.get('playlist_ids') or []
        output_path = str(cached_job.get('output_path') or '')
        if not isinstance(playlist_ids, list) or not output_path:
            return

        playlists = []
        for index, playlist_id in enumerate(playlist_ids):
            name = playlist_names[index] if isinstance(playlist_names, list) and index < len(playlist_names) else playlist_id
            playlists.append({'id': playlist_id, 'name': name})

        self._show_pending_export_popup(playlists, output_path, status, is_completed)

    def _show_pending_export_popup(self, playlists: list[dict[str, Any]], output_path: str, status: Dict[str, Any], is_completed: bool) -> None:
        """Render pending export resume/discard prompt after login."""
        if self.pending_export_popup:
            return

        title = 'Completed Export Available' if is_completed else 'Resume Pending Export'
        processed = int(status.get('processed_count', 0) or 0)
        total = int(status.get('playlist_count', len(playlists)) or len(playlists))
        phase = str(status.get('phase') or 'collect')
        body_text = (
            f"A previous export was found.\n\n"
            f"Progress: {processed}/{total} playlists\n"
            f"Phase: {phase}\n"
            f"Output: {Path(output_path).name}"
        )

        layout = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(16))
        layout.add_widget(Label(text=body_text, halign='center'))

        button_row = BoxLayout(orientation='horizontal', spacing=dp(12), size_hint_y=None, height=dp(42))
        resume_button = Button(text='Download' if is_completed else 'Resume')
        discard_button = Button(text='Discard')
        button_row.add_widget(resume_button)
        button_row.add_widget(discard_button)
        layout.add_widget(button_row)

        popup = Popup(title=title, content=layout, size_hint=(0.75, None), height=dp(240), auto_dismiss=False)
        self.pending_export_popup = popup

        def _dismiss(*_args: Any) -> None:
            if self.pending_export_popup:
                self.pending_export_popup.dismiss()
            self.pending_export_popup = None

        def _resume(*_args: Any) -> None:
            _dismiss()
            if hasattr(self.main_screen, 'begin_backend_export') and self.backend_adapter:
                self.main_screen.begin_backend_export(
                    playlists,
                    output_path,
                    resume_saved_job=True,
                )

        def _discard(*_args: Any) -> None:
            if self.backend_adapter:
                self.backend_adapter.clear_active_export_job()
            _dismiss()

        resume_button.bind(on_press=_resume)
        discard_button.bind(on_press=_discard)
        popup.bind(on_dismiss=lambda *_args: setattr(self, 'pending_export_popup', None))
        popup.open()

    def refresh_backend_connection(self) -> None:
        """Refresh backend connection status."""
        try:
            if self.login_screen and hasattr(self.login_screen, 'refresh_connection_status'):
                self.login_screen.refresh_connection_status()
                
            if self.backend_adapter and hasattr(self.backend_adapter, 'refresh_connection'):
                self.backend_adapter.refresh_connection()
                
        except Exception as e:
            original_logger.error(f"Error refreshing backend connection: {e}")


# Factory function for easy instantiation
def create_backend_app(**kwargs) -> BackendSpotifyExporterApp:
    """
    Create backend-integrated app instance.
    
    Args:
        **kwargs: Additional keyword arguments
        
    Returns:
        Backend app instance
    """
    return BackendSpotifyExporterApp(**kwargs)


# Legacy compatibility
def SpotifyExporterApp(**kwargs) -> BackendSpotifyExporterApp:
    """Legacy compatibility function."""
    return create_backend_app(**kwargs)


__all__ = [
    "BackendSpotifyExporterApp",
    "create_backend_app",
    "SpotifyExporterApp",
]
