"""Local HTTP handler used for Spotify OAuth callback."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from ..logging_config import logger


class AuthHandler(BaseHTTPRequestHandler):
    """HTTP handler for Spotify OAuth callback."""

    def __init__(self, *args, auth_callback=None, **kwargs):
        """Initialize with optional callback function.
        
        Args:
            auth_callback: Function to call with auth result (code or error)
        """
        self.auth_callback = auth_callback
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # pragma: no cover - integration path
        try:
            if self.path.startswith('/callback'):
                parsed = urlparse(self.path)
                code = parse_qs(parsed.query).get('code')
                error = parse_qs(parsed.query).get('error')

                if error:
                    result = {'error': error[0]}
                elif code:
                    result = {'code': code[0]}
                else:
                    result = {'error': 'No code received'}

                # Call callback if provided
                if self.auth_callback:
                    self.auth_callback(result)

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>Authorization Complete!</h2>
                    <p>You can now close this window and return to the application.</p>
                </body></html>
                """)
        except Exception as exc:
            logger.error("Error in auth handler: %s", exc)
            if self.auth_callback:
                self.auth_callback({'error': str(exc)})

    def log_message(self, format: str, *args) -> None:  # pragma: no cover - reduce noise
        return


__all__ = ["AuthHandler"]
