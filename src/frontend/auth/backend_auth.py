"""Backend authentication handler for OAuth flow with Cloudflare Workers."""

from __future__ import annotations

import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict, Optional
import urllib.parse
import webbrowser

from ..services.backend_client import BackendClient, BackendAPIError
from ..config.backend_config import OAUTH_CALLBACK_PORT

logger = logging.getLogger(__name__)


class ReusableHTTPServer(HTTPServer):
    """HTTP server configured for quick restart on the same callback port."""

    allow_reuse_address = True


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP server handler for OAuth callback."""

    def __init__(self, auth_result_container: Dict[str, str], *args, **kwargs):
        self.auth_result_container = auth_result_container
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET request for OAuth callback."""
        try:
            # Parse the URL to extract the authorization code
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)

            if "code" in query_params and "state" in query_params:
                # Store the authorization code
                self.auth_result_container["code"] = query_params["code"][0]
                self.auth_result_container["state"] = query_params["state"][0]

                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                success_html = """
                <html>
                <head><title>Authentication Successful</title></head>
                <body>
                    <h1>Authentication Successful!</h1>
                    <p>You can return to the app now. The active session continues automatically.</p>
                    <script>
                        setTimeout(function() {
                            window.close();
                        }, 3000);
                    </script>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
                logger.info("OAuth callback received successfully")

            elif "error" in query_params:
                # Handle OAuth error
                error = query_params["error"][0]
                error_description = query_params.get(
                    "error_description", ["Unknown error"]
                )[0]

                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                error_html = f"""
                <html>
                <head><title>Authentication Failed</title></head>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>Description: {error_description}</p>
                    <p>You can now close this window and return to the application.</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
                logger.error(f"OAuth error: {error} - {error_description}")
                self.auth_result_container["error"] = f"{error}: {error_description}"

            else:
                # Missing authorization code
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                error_html = """
                <html>
                <head><title>Authentication Failed</title></head>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>No authorization code received.</p>
                    <p>You can now close this window and return to the application.</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
                logger.error("OAuth callback missing authorization code/state")
                self.auth_result_container["error"] = (
                    "Missing code or state in callback"
                )

        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            self.auth_result_container["error"] = str(e)
            self.send_response(500)
            self.end_headers()

    def log_message(self, format: str, *args):
        """Suppress default HTTP server logging."""
        pass


class BackendAuthenticator:
    """Handles authentication flow with Cloudflare Worker backend."""

    def __init__(self, backend_client: Optional[BackendClient] = None):
        """
        Initialize authenticator.

        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client or BackendClient()
        # Spotify no longer allows localhost redirect URIs; use loopback IP literal.
        self.callback_host = "127.0.0.1"
        self.callback_port = OAUTH_CALLBACK_PORT
        self.callback_timeout = 300  # 5 minutes
        self.server_thread: Optional[threading.Thread] = None
        self.http_server: Optional[HTTPServer] = None
        self.auth_result_container: Dict[str, str] = {}

    def login(
        self,
        on_success: Optional[Callable[[Dict[str, str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Initiate OAuth login flow.

        Args:
            on_success: Callback function called on successful authentication
            on_error: Callback function called on authentication error

        Returns:
            True if login flow initiated successfully, False otherwise
        """
        try:
            logger.info("Initiating OAuth login flow")

            # Get authorization URL from backend
            redirect_uri = f"http://{self.callback_host}:{self.callback_port}/callback"
            auth_url = self.backend_client.initiate_spotify_login(redirect_uri)
            logger.info(f"Got authorization URL: {auth_url}")

            # Start local HTTP server to handle callback
            if not self._start_callback_server():
                if on_error:
                    on_error("Failed to start callback server")
                return False

            # Open browser for authentication
            try:
                webbrowser.open(auth_url)
                logger.info("Opened browser for authentication")
            except Exception as e:
                logger.error(f"Failed to open browser: {e}")
                if on_error:
                    on_error("Failed to open browser for authentication")
                self._stop_callback_server()
                return False

            # Wait for callback
            auth_result = self._wait_for_callback()

            # Stop callback server
            self._stop_callback_server()

            if auth_result and "code" in auth_result and "state" in auth_result:
                # Exchange authorization code for JWT token
                try:
                    token_response = self.backend_client.handle_spotify_callback(
                        auth_result["code"], auth_result["state"]
                    )
                    logger.info(
                        "Successfully exchanged authorization code for JWT token"
                    )

                    if on_success:
                        on_success(token_response)
                    return True

                except BackendAPIError as e:
                    logger.error(f"Failed to exchange authorization code: {e}")
                    if on_error:
                        on_error(f"Authentication failed: {e}")
                    return False
            else:
                error_msg = (
                    auth_result.get("error", "Authentication failed")
                    if auth_result
                    else "Authentication timed out"
                )
                logger.error(f"Authentication failed: {error_msg}")
                if on_error:
                    on_error(error_msg)
                return False

        except Exception as e:
            logger.error(f"Login flow error: {e}")
            if on_error:
                on_error(f"Login error: {e}")
            return False

    def _start_callback_server(self) -> bool:
        """Start local HTTP server to handle OAuth callback."""
        try:
            # Ensure a stale server from a previous login attempt is fully released.
            self._stop_callback_server()

            # Container to store authorization code
            self.auth_result_container = {}

            # Create HTTP server
            def handler(*args, **kwargs):
                return CallbackHandler(self.auth_result_container, *args, **kwargs)

            self.http_server = ReusableHTTPServer(
                (self.callback_host, self.callback_port), handler
            )

            # Start server in separate thread
            self.server_thread = threading.Thread(target=self.http_server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()

            logger.info(
                f"Callback server started on {self.callback_host}:{self.callback_port}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start callback server: {e}")
            return False

    def _stop_callback_server(self) -> None:
        """Stop the callback server."""
        try:
            if self.http_server:
                self.http_server.shutdown()
                self.http_server.server_close()
                self.http_server = None

            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
                self.server_thread = None

            logger.info("Callback server stopped")

        except Exception as e:
            logger.error(f"Error stopping callback server: {e}")

    def _wait_for_callback(
        self, timeout: Optional[int] = None
    ) -> Optional[Dict[str, str]]:
        """
        Wait for OAuth callback.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Dictionary with authorization code or error, or None if timeout
        """
        timeout = timeout or self.callback_timeout
        start_time = time.time()

        logger.info(f"Waiting for OAuth callback (timeout: {timeout}s)")

        while time.time() - start_time < timeout:
            if hasattr(self, "auth_result_container"):
                if (
                    "code" in self.auth_result_container
                    and "state" in self.auth_result_container
                ):
                    return {
                        "code": self.auth_result_container["code"],
                        "state": self.auth_result_container["state"],
                    }
                if "error" in self.auth_result_container:
                    return {"error": self.auth_result_container["error"]}

            time.sleep(0.2)

        logger.warning("OAuth callback timeout")
        return None

    def logout(self) -> bool:
        """
        Logout user and clear authentication state.

        Returns:
            True if logout successful, False otherwise
        """
        try:
            # Clear authentication token
            self.backend_client.clear_auth_token()
            logger.info("Logged out successfully")
            return True

        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.backend_client.is_authenticated()

    def get_user_info(self) -> Optional[Dict[str, str]]:
        """
        Get current user information.

        Returns:
            User information dictionary or None if not authenticated
        """
        # This would typically call a backend endpoint to get user info
        # For now, return a placeholder
        if self.is_authenticated():
            return {"status": "authenticated"}
        return None

    def refresh_token(self) -> bool:
        """
        Refresh authentication token.

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            refresh_response = self.backend_client.refresh_token()
            app_token = refresh_response.get("token") or refresh_response.get(
                "access_token"
            )
            if app_token:
                app = None
                try:
                    from kivy.app import App

                    app = App.get_running_app()
                except Exception:
                    app = None

                cache_manager = getattr(app, "cache_manager", None) if app else None
                username = getattr(app, "username", None) if app else None
                if cache_manager:
                    cache_manager.save_auth_token(
                        {
                            "token": app_token,
                            "username": username or "User",
                            "saved_at": int(time.time()),
                        }
                    )
            logger.info("Token refreshed successfully")
            return True

        except BackendAPIError as e:
            logger.error(f"Token refresh failed: {e}")
            if e.error_code == "AUTH_REQUIRED":
                self.backend_client.clear_auth_token()
                app = None
                try:
                    from kivy.app import App

                    app = App.get_running_app()
                except Exception:
                    app = None

                cache_manager = getattr(app, "cache_manager", None) if app else None
                if cache_manager:
                    cache_manager.clear_auth_token()
                logger.warning(
                    "AUTH_REQUIRED detected: wiping cache and redirecting to login",
                    extra={"error_code": e.error_code, "status_code": e.status_code},
                )
                if app and hasattr(app, "prompt_reauthentication"):
                    from kivy.clock import Clock

                    Clock.schedule_once(
                        lambda _: app.prompt_reauthentication(
                            "Your Spotify session has expired. Please sign in again."
                        ),
                        0.2,
                    )
            return False
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False


# Global authenticator instance
_authenticator: Optional[BackendAuthenticator] = None


def get_authenticator() -> BackendAuthenticator:
    """Get or create global authenticator instance."""
    global _authenticator
    if _authenticator is None:
        _authenticator = BackendAuthenticator()
    return _authenticator


def set_backend_client(client: BackendClient) -> None:
    """Set backend client for authenticator."""
    global _authenticator
    _authenticator = BackendAuthenticator(client)
