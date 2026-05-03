"""Spotify OAuth handler for backend API - extracted from Kivy LoginScreen."""

from __future__ import annotations

import os
import socket
import time
from typing import Any

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from ..config import get_settings
from ..logging_config import logger

settings = get_settings()


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
    """Find an available port from the configured OAuth ports."""
    for port in settings.OAUTH_PORTS:
        if is_port_available(port):
            logger.info(f"Found available port: {port}")
            return port
    raise RuntimeError("No available ports found for OAuth callback")


def clear_all_auth_state() -> None:
    """Clear all authentication state including cached tokens and OAuth managers."""
    try:
        # Clear token cache file
        cache_path = settings.CACHE_PATH
        if os.path.exists(cache_path):
            os.remove(cache_path)
            logger.info("Token cache file removed")

        # Clear any in-memory cache in cache handlers
        try:
            cache_handler = CacheFileHandler(cache_path=cache_path)
            if hasattr(cache_handler, "_cache"):
                cache_handler._cache.clear()
            logger.info("Cache handler memory cleared")
        except Exception as e:
            logger.warning(f"Could not clear cache handler memory: {e}")

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
            return

        def save_token_to_cache(self, token_info):
            """Don't save anything."""

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
            return

        def save_token_to_cache(self, token_info):
            """Don't save anything."""

        def is_token_expired(self, token_info):
            """Check if token is expired (not cached)."""
            if not token_info:
                return True
            import time

            return token_info.get("expires_at", 0) < time.time()


class SpotifyOAuthHandler:
    """Handles Spotify OAuth flow for the backend API."""

    def __init__(self):
        self.client_id = settings.SPOTIPY_CLIENT_ID
        self.client_secret = settings.SPOTIPY_CLIENT_SECRET
        self.redirect_uri = settings.SPOTIPY_REDIRECT_URI
        self.cache_path = settings.CACHE_PATH

    def get_auth_url(self, port: int | None = None) -> str:
        """Get the Spotify authorization URL.

        Args:
            port: Optional port to use for redirect URI. If None, uses default.

        Returns:
            Authorization URL for Spotify OAuth.
        """
        if port:
            redirect_uri = f"http://127.0.0.1:{port}/callback"
        else:
            redirect_uri = self.redirect_uri

        # Create cache directory if it doesn't exist
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

        # Use NoCacheHandler to prevent persistent token caching during auth flow
        cache_handler = NoCacheHandler(cache_path=self.cache_path)

        sp_oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=redirect_uri,
            scope=settings.SCOPE,
            cache_handler=cache_handler,
            show_dialog=True,
        )

        return sp_oauth.get_authorize_url()

    def exchange_code_for_token(
        self, code: str, port: int | None = None
    ) -> dict[str, Any] | None:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from Spotify callback
            port: Optional port that was used for redirect URI

        Returns:
            Token information dictionary or None if failed.
        """
        if port:
            redirect_uri = f"http://127.0.0.1:{port}/callback"
        else:
            redirect_uri = self.redirect_uri

        # Create cache directory if it doesn't exist
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

        # Use NoCacheHandler during token exchange
        cache_handler = NoCacheHandler(cache_path=self.cache_path)

        sp_oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=redirect_uri,
            scope=settings.SCOPE,
            cache_handler=cache_handler,
        )

        try:
            token_info = sp_oauth.get_access_token(code)
            if token_info:
                # Save token to file manually since we're using NoCacheHandler
                self._save_token_to_cache(token_info)
                logger.info("Token exchanged and saved successfully")
                return token_info
            else:
                logger.error("Failed to exchange code for token")
                return None

        except Exception as exc:
            logger.error(f"Token exchange failed: {exc}")
            return None

    def _save_token_to_cache(self, token_info: dict[str, Any]) -> None:
        """Save token information to cache file.

        Args:
            token_info: Token information to save
        """
        try:
            import json

            with open(self.cache_path, "w") as f:
                json.dump(token_info, f)
            logger.info("Token saved to cache file")
        except Exception as e:
            logger.error(f"Failed to save token to cache file: {e}")

    def get_cached_token(self) -> dict[str, Any] | None:
        """Get cached token information.

        Returns:
            Token information dictionary or None if not found/invalid.
        """
        try:
            import json

            if os.path.exists(self.cache_path):
                with open(self.cache_path) as f:
                    token_info = json.load(f)

                # Check if token is expired
                if not self._is_token_expired(token_info):
                    return token_info
                else:
                    logger.info("Cached token is expired")
                    return None
            else:
                logger.info("No cached token found")
                return None

        except Exception as e:
            logger.error(f"Error reading cached token: {e}")
            return None

    def _is_token_expired(self, token_info: dict[str, Any]) -> bool:
        """Check if token is expired.

        Args:
            token_info: Token information to check

        Returns:
            True if token is expired, False otherwise.
        """
        if not token_info:
            return True
        return token_info.get("expires_at", 0) < time.time()


def create_spotify_client_with_refresh(
    token_info: dict[str, Any] | None,
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
        cache_path = settings.CACHE_PATH

        # Create cache handler for token refresh
        cache_handler = CacheFileHandler(cache_path=cache_path)

        # Create SpotifyOAuth manager for automatic refresh
        sp_oauth = SpotifyOAuth(
            client_id=settings.SPOTIPY_CLIENT_ID,
            client_secret=settings.SPOTIPY_CLIENT_SECRET,
            redirect_uri=settings.SPOTIPY_REDIRECT_URI,
            scope=SCOPE,
            cache_handler=cache_handler,
        )

        # Create Spotify client with OAuth manager for automatic refresh
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=token_info["access_token"])

        # Manually set the token info for refresh
        sp_oauth.cache_handler.save_token_to_cache(token_info)

        return sp

    except Exception as exc:
        logger.error("Error creating Spotify client with refresh: %s", exc)
        # Fallback to basic client without refresh
        return spotipy.Spotify(auth=token_info["access_token"])


__all__ = [
    "SpotifyOAuthHandler",
    "create_spotify_client_with_refresh",
    "clear_all_auth_state",
    "find_available_port",
    "is_port_available",
]
