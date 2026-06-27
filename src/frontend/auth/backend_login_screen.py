"""Backend-integrated login screen for Spotify authentication via Cloudflare Workers."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
import logging

from ..auth.backend_auth import BackendAuthenticator
from ..services.backend_client import BackendClient
from ..utils.network_utils import format_error_message, NetworkError

logger = logging.getLogger(__name__)


class BackendLoginScreen(Screen):
    """Login screen for Spotify authentication using Cloudflare Worker backend."""

    def __init__(
        self,
        backend_client: Optional[BackendClient] = None,
        on_change_backend: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ):
        """
        Initialize backend login screen.

        Args:
            backend_client: Backend client instance
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        self.backend_client = backend_client
        self.authenticator = (
            BackendAuthenticator(self.backend_client) if self.backend_client else None
        )
        self.on_change_backend = on_change_backend
        self.status_label: Label
        self.login_button: Button | None = None
        self.login_in_progress = False
        self.connection_status_label: Optional[Label] = None
        self.backend_url_label: Optional[Label] = None
        self.build_ui()
        if self.backend_client:
            self.check_backend_connection()
        else:
            self._update_connection_status(
                "Choose backend to begin", (0.9, 0.8, 0.3, 1)
            )

    def build_ui(self) -> None:
        """Build the login screen UI."""
        layout = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(15))

        # Title
        title = Label(
            text="Spotify Playlist Exporter",
            font_size=dp(24),
            size_hint_y=None,
            height=dp(50),
        )
        layout.add_widget(title)

        layout.add_widget(Widget(size_hint_y=0.1))

        # Connection status
        self.connection_status_label = Label(
            text="Checking backend connection...",
            font_size=dp(12),
            size_hint_y=None,
            height=dp(25),
            color=(0.7, 0.7, 0.7, 1),
        )
        layout.add_widget(self.connection_status_label)

        self.backend_url_label = Label(
            text="Backend: not selected",
            font_size=dp(11),
            size_hint_y=None,
            height=dp(20),
            color=(0.7, 0.7, 0.7, 1),
        )
        layout.add_widget(self.backend_url_label)

        layout.add_widget(Widget(size_hint_y=0.1))

        # Instructions
        instructions = Label(
            text="Click below to login with your Spotify account\nand start exporting your playlists to Excel files.\n\nNow with enhanced audio analysis powered by ReccoBeats!\n\nPowered by Cloudflare Workers for better performance.",
            text_size=(None, None),
            halign="center",
            font_size=dp(16),
            size_hint_y=None,
            height=dp(120),
        )
        layout.add_widget(instructions)

        # Login button
        login_btn = Button(
            text="Login with Spotify",
            size_hint=(None, None),
            size=(dp(180), dp(45)),
            pos_hint={"center_x": 0.5},
            font_size=dp(16),
        )
        login_btn.bind(on_press=self.start_login)  # pyright: ignore[reportAttributeAccessIssue]
        layout.add_widget(login_btn)
        self.login_button = login_btn

        change_backend_btn = Button(
            text="Change Backend",
            size_hint=(None, None),
            size=(dp(180), dp(38)),
            pos_hint={"center_x": 0.5},
            font_size=dp(14),
        )
        change_backend_btn.bind(on_press=self._on_change_backend)  # pyright: ignore[reportAttributeAccessIssue]
        layout.add_widget(change_backend_btn)

        # Status label
        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(35),
            font_size=dp(14),
        )
        layout.add_widget(self.status_label)

        layout.add_widget(Widget(size_hint_y=0.2))

        self.add_widget(layout)

    def check_backend_connection(self) -> None:
        """Check backend connection in background thread."""
        if not self.backend_client:
            self._update_connection_status(
                "Choose backend to begin", (0.9, 0.8, 0.3, 1)
            )
            return

        def check_connection():
            try:
                if self.backend_client is None:
                    return
                health = self.backend_client.health_check()
                if health.get("status") == "healthy":
                    self._update_connection_status(
                        "Connected to backend", (0.3, 1, 0.3, 1)
                    )
                else:
                    error = health.get("error", "Unknown error")
                    self._update_connection_status(
                        f"Backend error: {error}", (1, 0.3, 0.3, 1)
                    )
            except Exception as e:
                self._update_connection_status(
                    "Unable to connect to backend", (1, 0.3, 0.3, 1)
                )
                logger.error(f"Backend connection check failed: {e}")

        threading.Thread(target=check_connection, daemon=True).start()

    @mainthread
    def _update_connection_status(self, text: str, color: tuple[float, float, float, float]) -> None:
        """Update connection status label."""
        if self.connection_status_label:
            self.connection_status_label.text = text
            self.connection_status_label.color = color

    @mainthread
    def _update_backend_url_label(self, url: str) -> None:
        """Show currently selected backend URL."""
        if self.backend_url_label:
            self.backend_url_label.text = f"Backend: {url}"

    def set_backend_client(self, backend_client: BackendClient) -> None:
        """Set backend client after user picks a backend URL."""
        self.backend_client = backend_client
        self.authenticator = BackendAuthenticator(self.backend_client)
        self._update_backend_url_label(self.backend_client.base_url)
        self.check_backend_connection()

    def _on_change_backend(self, _instance) -> None:
        """Re-open backend selector from login screen."""
        if self.on_change_backend:
            self.on_change_backend()

    def start_login(self, instance) -> None:  # pragma: no cover - UI path
        """Start the login process."""
        logger.info("Backend login button pressed")

        if self.login_in_progress:
            self.status_label.text = "Login already in progress..."
            return

        if not self.backend_client or not self.authenticator:
            self.status_label.text = "Please choose a backend first."
            self.status_label.color = (1, 0.3, 0.3, 1)
            return

        # Check backend connection first
        try:
            health = self.backend_client.health_check()
            if health.get("status") != "healthy":
                self.status_label.text = (
                    "Backend is not available. Please try again later."
                )
                self.status_label.color = (1, 0.3, 0.3, 1)
                return
        except Exception as e:
            self.status_label.text = (
                "Cannot connect to backend. Check your internet connection."
            )
            self.status_label.color = (1, 0.3, 0.3, 1)
            logger.error(f"Backend health check failed: {e}")
            return

        self.status_label.text = "Opening browser for authentication..."
        self.status_label.color = (1, 1, 1, 1)
        self._set_login_state(True)

        # Start login in background thread
        threading.Thread(target=self.login_worker, daemon=True).start()

    def login_worker(self) -> None:
        """Background worker for login process."""
        logger.info("Backend login worker started")

        try:
            if self.authenticator is None:
                return
            # Start OAuth flow using backend authenticator
            success = self.authenticator.login(
                on_success=self._on_login_success, on_error=self._on_login_error
            )

            if not success:
                Clock.schedule_once(
                    lambda dt: self._on_login_error("Login flow failed to start"), 0
                )

        except Exception as e:
            logger.error(f"Backend login worker error: {e}")
            Clock.schedule_once(
                lambda dt, err=str(e): self._on_login_error(f"Login error: {err}"), 0
            )
        finally:
            Clock.schedule_once(lambda dt: self._set_login_state(False), 0)

    @mainthread
    def _on_login_success(self, token_response: dict[str, Any]) -> None:
        """Handle successful login."""
        try:
            user = (
                token_response.get("user", {})
                if isinstance(token_response.get("user"), dict)
                else {}
            )
            username = (
                token_response.get("username")
                or user.get("display_name")
                or user.get("id")
                or "User"
            )
            token = token_response.get("token")

            if not token:
                self._on_login_error("No authentication token received")
                return

            self.status_label.text = f"Welcome, {username}! Loading playlists..."
            self.status_label.color = (0.3, 1, 0.3, 1)

            # Update app state
            app = App.get_running_app()
            if app is None or self.backend_client is None:
                self._on_login_error("App or backend client unavailable")
                return
            app.token_info = {"access_token": token}  # Store JWT token
            app.username = username

            # Set backend client token
            self.backend_client.set_auth_token(token)

            # Persist token for startup auto-login
            cache_manager = getattr(app, "cache_manager", None)
            if cache_manager:
                cache_manager.save_auth_token(
                    {
                        "token": token,
                        "username": username,
                        "saved_at": int(time.time()),
                    }
                )
                logger.info("Saved backend auth token for auto-login")

            logger.info(f"Backend login successful for user: {username}")

            # Switch to main screen
            app.switch_to_main()

        except Exception as e:
            logger.error(f"Error handling login success: {e}")
            self._on_login_error(f"Login success handling failed: {str(e)}")

    @mainthread
    def _on_login_error(self, error_msg: str) -> None:
        """Handle login error."""
        logger.error(f"Backend login error: {error_msg}")

        # Format error message for user
        user_msg = format_error_message(NetworkError(error_msg))
        self.status_label.text = f"Login failed: {user_msg}"
        self.status_label.color = (1, 0.3, 0.3, 1)

    def _set_login_state(self, in_progress: bool) -> None:
        """Set login state and update UI."""
        self.login_in_progress = in_progress
        if self.login_button:
            self.login_button.disabled = in_progress
            if in_progress:
                self.login_button.text = "Logging in..."
            else:
                self.login_button.text = "Login with Spotify"

    def logout(self) -> None:
        """Logout user and clear authentication state."""
        try:
            if not self.backend_client or not self.authenticator:
                return

            # Logout from backend
            self.authenticator.logout()

            # Clear backend client token
            self.backend_client.clear_auth_token()

            # Clear app state
            app = App.get_running_app()
            if app is None:
                return
            app.token_info = None
            app.username = None

            # Clear persisted auth token
            cache_manager = getattr(app, "cache_manager", None)
            if cache_manager:
                cache_manager.clear_auth_token()

            # Reset UI
            self.status_label.text = ""
            self.status_label.color = (1, 1, 1, 1)

            logger.info("Backend logout completed")

        except Exception as e:
            logger.error(f"Backend logout error: {e}")

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        if not self.authenticator:
            return False
        return self.authenticator.is_authenticated()

    def refresh_connection_status(self) -> None:
        """Refresh backend connection status."""
        if self.backend_client:
            self.check_backend_connection()


# Factory function for easy integration
def create_backend_login_screen(
    backend_client: Optional[BackendClient] = None,
    on_change_backend: Optional[Callable[[], None]] = None,
) -> BackendLoginScreen:
    """
    Create a backend login screen instance.

    Args:
        backend_client: Optional backend client

    Returns:
        Backend login screen instance
    """
    return BackendLoginScreen(backend_client, on_change_backend=on_change_backend)


# Compatibility function for existing code
def create_login_screen(**kwargs) -> BackendLoginScreen:
    """Create login screen (backend version)."""
    return BackendLoginScreen(**kwargs)


__all__ = ["BackendLoginScreen", "create_backend_login_screen", "create_login_screen"]
