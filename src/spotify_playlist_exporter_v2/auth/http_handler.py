"""Local HTTP handler used for Spotify OAuth callback."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from ..logging_config import logger
from .. import state


class AuthHandler(BaseHTTPRequestHandler):
    """HTTP handler for Spotify OAuth callback."""

    def do_GET(self) -> None:  # pragma: no cover - integration path
        try:
            if self.path.startswith('/callback'):
                parsed = urlparse(self.path)
                code = parse_qs(parsed.query).get('code')
                error = parse_qs(parsed.query).get('error')

                if error:
                    state.auth_token = {'error': error[0]}
                elif code:
                    state.auth_token = {'code': code[0]}
                else:
                    state.auth_token = {'error': 'No code received'}

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>Authorization Complete!</h2>
                    <p>You can now close this window and return to the Spotify Exporter.</p>
                </body></html>
                """)
        except Exception as exc:
            logger.error("Error in auth handler: %s", exc)
            state.auth_token = {'error': str(exc)}

    def log_message(self, format: str, *args) -> None:  # pragma: no cover - reduce noise
        return


__all__ = ["AuthHandler"]
