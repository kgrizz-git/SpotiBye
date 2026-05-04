"""Kivy LoginScreen handling Spotify OAuth."""

from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser
from http.server import HTTPServer
from typing import Any

import spotipy
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

from ..config import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPE,
    CACHE_PATH,
    OAUTH_PORTS,
)
from ..logging_config import logger
from .. import state
from .http_handler import AuthHandler


def _is_backend_authenticated_app(app: Any | None) -> bool:
    return bool(
        app and hasattr(app, "backend_client") and hasattr(app, "backend_adapter")
    )


def notify_spotify_session_expired(
    message: str = "Your Spotify session expired. Log out and log in again.",
) -> None:
    """Prompt the user to re-authenticate when Spotify rejects the session."""
    app = App.get_running_app()
    if app is None:
        return

    if _is_backend_authenticated_app(app):
        logger.debug(
            "Skipping desktop Spotify re-auth prompt in backend-authenticated app"
        )
        return

    if hasattr(app, "prompt_reauthentication"):
        Clock.schedule_once(lambda _dt: app.prompt_reauthentication(message), 0)
    elif hasattr(app, "logout"):
        Clock.schedule_once(lambda _dt: app.logout(), 0)
    elif hasattr(app, "switch_to_login"):
        Clock.schedule_once(lambda _dt: app.switch_to_login(), 0)


def is_port_available(port: int) -> bool:
    """Check if a port is available on localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            return result != 0  # Port is available if connection fails
    except Exception:
        return False


def find_available_port() -> int:
    """Find the first available port from the OAUTH_PORTS list."""
    for port in OAUTH_PORTS:
        if is_port_available(port):
            logger.info(f"Found available port: {port}")
            return port

    # If no preferred ports are available, use a random port
    import random

    fallback_port = random.randint(9000, 9999)
    logger.warning(f"No preferred ports available, using random port: {fallback_port}")
    return fallback_port


def clear_all_auth_state() -> None:
    """Clear all authentication state including cached tokens and OAuth managers."""
    try:
        # Clear token cache file (our app's cache)
        if os.path.exists(CACHE_PATH):
            os.remove(CACHE_PATH)
            logger.info("Token cache file removed")

        # Clear default spotipy cache file in user home directory
        default_cache_path = os.path.expanduser("~/.cache")
        if os.path.exists(default_cache_path):
            try:
                with open(default_cache_path, "r") as f:
                    content = f.read()
                    # Only remove if it looks like a Spotify token cache
                    if "access_token" in content and "refresh_token" in content:
                        os.remove(default_cache_path)
                        logger.info("Default spotipy cache file removed")
            except Exception as e:
                logger.warning(f"Could not check/remove default cache file: {e}")

        # Clear any in-memory cache in cache handlers
        try:
            cache_handler = CacheFileHandler(cache_path=CACHE_PATH)
            if hasattr(cache_handler, "_cache"):
                cache_handler._cache.clear()
            logger.info("Cache handler memory cleared")
        except Exception as e:
            logger.warning(f"Could not clear cache handler memory: {e}")

        # Clear any global auth state
        state.auth_token = None
        if hasattr(state, "auth_server") and state.auth_server:
            try:
                state.auth_server.shutdown()
                state.auth_server = None
                logger.info("Auth server shutdown")
            except Exception as e:
                logger.warning(f"Could not shutdown auth server: {e}")

        # Set a flag to indicate we've logged out and should force fresh OAuth
        state.force_fresh_oauth = True

        # Force clear any module-level caches
        import spotipy

        if hasattr(spotipy, "_cache"):
            spotipy._cache.clear()

        # Clear any OAuth manager instances that might be cached
        import spotipy.oauth2

        if hasattr(spotipy.oauth2, "_cache"):
            spotipy.oauth2._cache.clear()

        logger.info("All auth state cleared successfully")

    except Exception as e:
        logger.error(f"Error clearing auth state: {e}")


# Import the proper base class and create a compliant cache handler
try:
    from spotipy.cache_handler import CacheHandler

    class NoCacheHandler(CacheHandler):
        """A cache handler that doesn't cache anything - forces fresh OAuth every time."""

        def __init__(self, cache_path=None):
            self.cache_path = cache_path

        def get_cached_token(self):
            """Always return None to force fresh OAuth."""
            return None

        def save_token_to_cache(self, token_info):
            """Don't save anything."""
            pass

        def is_token_expired(self, token_info):
            """Check if token is expired (not cached)."""
            if not token_info:
                return True
            import time

            return token_info.get("expires_at", 0) < time.time()

except ImportError:
    # Fallback for older Spotipy versions
    class NoCacheHandler:
        """A cache handler that doesn't cache anything - forces fresh OAuth every time."""

        def __init__(self, cache_path=None):
            self.cache_path = cache_path

        def get_cached_token(self):
            """Always return None to force fresh OAuth."""
            return None

        def save_token_to_cache(self, token_info):
            """Don't save anything."""
            pass

        def is_token_expired(self, token_info):
            """Check if token is expired (not cached)."""
            if not token_info:
                return True
            import time

            return token_info.get("expires_at", 0) < time.time()


class LoginScreen(Screen):
    """Login screen for Spotify authentication."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.status_label: Label
        self.login_button: Button | None = None
        self.login_in_progress = False
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(15))

        title = Label(
            text="Spotify Playlist Exporter",
            font_size=dp(24),
            size_hint_y=None,
            height=dp(50),
        )
        layout.add_widget(title)

        layout.add_widget(Widget(size_hint_y=0.2))

        instructions = Label(
            text="Click below to login with your Spotify account\nand start exporting your playlists to Excel files.\n\nNow with enhanced audio analysis powered by ReccoBeats!",
            text_size=(None, None),
            halign="center",
            font_size=dp(16),
            size_hint_y=None,
            height=dp(100),
        )
        layout.add_widget(instructions)

        login_btn = Button(
            text="Login with Spotify",
            size_hint=(None, None),
            size=(dp(180), dp(45)),
            pos_hint={"center_x": 0.5},
            font_size=dp(16),
        )
        login_btn.bind(on_press=self.start_login)
        layout.add_widget(login_btn)
        self.login_button = login_btn

        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(35),
            font_size=dp(14),
        )
        layout.add_widget(self.status_label)

        layout.add_widget(Widget(size_hint_y=0.2))

        self.add_widget(layout)

    def start_login(self, instance) -> None:  # pragma: no cover - UI path
        logger.info("Login button pressed")

        if self.login_in_progress:
            self.status_label.text = "Login already in progress..."
            return

        if (
            CLIENT_ID == "YOUR_CLIENT_ID_HERE"
            or CLIENT_SECRET == "YOUR_CLIENT_SECRET_HERE"
        ):
            self.status_label.text = "Error: Spotify credentials not configured"
            self.status_label.color = (1, 0.3, 0.3, 1)
            return

        self.status_label.text = "Opening browser for authentication..."
        self.status_label.color = (1, 1, 1, 1)
        self._set_login_state(True)
        threading.Thread(target=self.login_worker, daemon=True).start()

    def login_worker(self) -> None:
        logger.info("Login worker thread started")

        # Ensure previous attempts are cleaned up before starting a new server
        if state.auth_server:
            try:
                state.auth_server.shutdown()
            except Exception:
                pass
            state.auth_server = None
        state.auth_token = None

        try:
            # Find an available port and update the redirect URI
            available_port = find_available_port()

            # Update the global REDIRECT_URI to use the available port
            from .. import config

            config.REDIRECT_URI = f"http://127.0.0.1:{available_port}/callback"
            logger.info(f"Using redirect URI: {config.REDIRECT_URI}")

            # Create server with the available port
            server = HTTPServer(("127.0.0.1", available_port), AuthHandler)
            state.auth_server = server

            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            # Create cache directory if it doesn't exist
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

            # Use standard cache handler for normal token persistence
            cache_handler = CacheFileHandler(cache_path=CACHE_PATH)
            sp_oauth = SpotifyOAuth(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=config.REDIRECT_URI,
                scope=SCOPE,
                cache_handler=cache_handler,
                show_dialog=True,  # Always show dialog to ensure fresh login
            )

            # Try to get cached token first (normal behavior)
            # But skip this check if we've logged out and want to force fresh OAuth
            if not getattr(state, "force_fresh_oauth", False):
                token_info = sp_oauth.get_cached_token()
                if token_info and not sp_oauth.is_token_expired(token_info):
                    logger.info("Found valid cached token - logging in automatically")
                    sp = spotipy.Spotify(auth=token_info["access_token"])
                    user = sp.current_user()
                    username = user.get("display_name", user.get("id", "User"))
                    user_id = user.get("id")
                    Clock.schedule_once(
                        lambda dt,
                        info=token_info,
                        name=username,
                        uid=user_id: self.login_success(info, name, uid),
                        0,
                    )
                    return
            else:
                # Reset the force_fresh_oauth flag since we're proceeding with fresh OAuth
                state.force_fresh_oauth = False
                logger.info("Force fresh OAuth requested - skipping cached token check")

            # If no valid cached token, proceed with OAuth flow
            auth_url = sp_oauth.get_authorize_url()
            webbrowser.open(auth_url)

            Clock.schedule_once(
                lambda dt: setattr(
                    self.status_label, "text", "Waiting for authorization..."
                ),
                0,
            )

            start_time = time.time()
            while state.auth_token is None and time.time() - start_time < 120:
                time.sleep(0.5)

            if state.auth_token is None:
                Clock.schedule_once(
                    lambda dt: self.login_failed("Timeout waiting for authorization"), 0
                )
                return

            if "error" in state.auth_token:
                Clock.schedule_once(
                    lambda dt: self.login_failed(
                        f"Authorization error: {state.auth_token['error']}"
                    ),
                    0,
                )
                return

            try:
                # This will automatically cache the token using our cache_handler
                token_info = sp_oauth.get_access_token(state.auth_token["code"])
                if not token_info:
                    raise Exception("Failed to get access token")

                sp = spotipy.Spotify(auth=token_info["access_token"])
                user = sp.current_user()
                username = user.get("display_name", user.get("id", "Unknown"))

                user_id = user.get("id")
                Clock.schedule_once(
                    lambda dt,
                    info=token_info,
                    name=username,
                    uid=user_id: self.login_success(info, name, uid),
                    0,
                )

            except Exception as exc:
                logger.error("Token exchange failed during OAuth callback")
                Clock.schedule_once(
                    lambda dt, err=str(exc): self.login_failed(
                        f"Token exchange failed: {err}"
                    ),
                    0,
                )

        except Exception as exc:
            logger.error("Login failed: %s", exc)
            Clock.schedule_once(
                lambda dt, err=str(exc): self.login_failed(f"Login failed: {err}"), 0
            )
        finally:
            if state.auth_server:
                try:
                    state.auth_server.shutdown()
                except Exception:
                    pass
                state.auth_server = None
            Clock.schedule_once(lambda dt: self._set_login_state(False), 0)

    @mainthread
    def login_success(self, token_info, username, user_id=None) -> None:
        self.status_label.text = f"Welcome, {username}! Loading playlists..."
        app = App.get_running_app()
        app.token_info = token_info
        app.username = username
        app.user_id = user_id

        # Save token to file for normal persistence (not NoCacheHandler)
        try:
            import json

            with open(CACHE_PATH, "w") as f:
                json.dump(token_info, f)
            logger.info("Token saved to cache file")
        except Exception as e:
            logger.error(f"Failed to save token to cache file: {e}")

        app.switch_to_main()

    @mainthread
    def login_failed(self, error_msg: str) -> None:
        self.status_label.text = f"Login failed: {error_msg}"

    def _set_login_state(self, in_progress: bool) -> None:
        self.login_in_progress = in_progress
        if self.login_button:
            self.login_button.disabled = in_progress


def create_spotify_client_with_refresh(
    token_info: dict | None,
) -> spotipy.Spotify | None:
    """Create a Spotify client with automatic token refresh capability.

    Args:
        token_info: Dictionary containing token information from Spotify OAuth

    Returns:
        Spotify client with automatic refresh, or None if token_info is invalid
    """
    if not token_info or not token_info.get("access_token"):
        return None

    try:
        # Create cache handler for token refresh
        cache_handler = CacheFileHandler(cache_path=CACHE_PATH)

        # Create SpotifyOAuth manager for automatic refresh
        sp_oauth = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_handler=cache_handler,
        )

        # Seed the OAuth cache and let auth_manager provide tokens so Spotipy can
        # refresh them automatically instead of pinning a stale access token.
        sp_oauth.cache_handler.save_token_to_cache(token_info)
        refreshed_token_info = sp_oauth.validate_token(token_info)
        if not refreshed_token_info:
            app = App.get_running_app()
            if not _is_backend_authenticated_app(app):
                notify_spotify_session_expired()
            return None

        app = App.get_running_app()
        if app is not None:
            app.token_info = refreshed_token_info

        # Create Spotify client with OAuth manager for automatic refresh.
        sp = spotipy.Spotify(auth_manager=sp_oauth)

        return sp

    except Exception as exc:
        logger.error("Error creating Spotify client with refresh: %s", exc)
        app = App.get_running_app()
        if not _is_backend_authenticated_app(app):
            notify_spotify_session_expired()
        return None


__all__ = ["LoginScreen", "create_spotify_client_with_refresh"]
