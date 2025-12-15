"""Backend-integrated application bootstrap for Spotify Playlist Exporter V2."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from kivy.app import MDApp
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.lang.builder import Builder
from kivy.logger import Logger as logger
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager

# Import backend components
from ..services.backend_client import BackendClient, get_backend_client
from ..auth.backend_login_screen import BackendLoginScreen, create_backend_login_screen
from ..caching.backend_cache import BackendCacheManager, get_cache_manager
from ..config.backend_config import CURRENT_BACKEND_URL, validate_config, get_config_summary
from ..screens.backend_main_screen_adapter import BackendMainScreenAdapter, create_backend_adapter

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
        
        # Match previous dark styling
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.primary_hue = "700"
        self.theme_cls.accent_palette = "Blue"
        self.theme_cls.accent_hue = "400"
        
        # Initialize backend components
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize backend components."""
        try:
            # Validate configuration
            config_issues = validate_config()
            if config_issues:
                original_logger.warning(f"Configuration issues: {config_issues}")
            
            # Initialize backend client
            self.backend_client = BackendClient(CURRENT_BACKEND_URL)
            get_backend_client().base_url = CURRENT_BACKEND_URL
            
            # Initialize cache manager
            self.cache_manager = get_cache_manager()
            
            # Initialize backend adapter
            self.backend_adapter = create_backend_adapter(self.backend_client)
            
            original_logger.info(f"Backend initialized with URL: {CURRENT_BACKEND_URL}")
            
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
            self.login_screen = create_backend_login_screen(self.backend_client)
            self.login_screen.name = 'login'
            
            # Create main screen (original version)
            self.main_screen = MainScreen(name='main')

            self.screen_manager.add_widget(self.login_screen)
            self.screen_manager.add_widget(self.main_screen)

            # Check for cached authentication
            self._try_auto_login()
            
            return self.screen_manager
            
        except Exception as exc:  # pragma: no cover - UI fallback
            original_logger.error("Error building backend app: %s", exc)
            return Label(text=f'Error starting app: {exc}')

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
                self.screen_manager.current = 'main'
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
                'backend_url': CURRENT_BACKEND_URL,
            }
            
        except Exception as e:
            original_logger.error(f"Error getting backend status: {e}")
            return {'status': 'error', 'error': str(e)}

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
