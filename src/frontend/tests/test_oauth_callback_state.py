"""OAuth callback server must accept only the state its own login started with."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator, Tuple
from unittest.mock import MagicMock, patch

import pytest

from ..auth.backend_auth import BackendAuthenticator, CallbackHandler
from ..services.backend_client import BackendAPIError, BackendClient

EXPECTED_STATE = "state-from-this-login"


@pytest.fixture
def callback_server() -> Iterator[Tuple[BackendAuthenticator, str]]:
    authenticator = BackendAuthenticator()
    authenticator.callback_port = 0  # let the OS pick a free port
    assert authenticator._start_callback_server(EXPECTED_STATE)
    assert authenticator.http_server is not None
    port = authenticator.http_server.server_address[1]
    try:
        yield authenticator, f"http://127.0.0.1:{port}/callback"
    finally:
        authenticator._stop_callback_server()


def _get(url: str, **params: str) -> Tuple[int, str]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=5) as response:  # nosec B310
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def test_ignores_callback_with_wrong_state(callback_server) -> None:
    authenticator, url = callback_server
    status, _ = _get(url, code="attacker-code", state="attacker-state")
    assert status == 400
    assert authenticator.auth_result_container == {}


def test_ignores_callback_without_state(callback_server) -> None:
    authenticator, url = callback_server
    status, _ = _get(url, code="attacker-code")
    assert status == 400
    assert authenticator.auth_result_container == {}


def test_accepts_matching_state_after_a_forged_callback(callback_server) -> None:
    authenticator, url = callback_server
    _get(url, code="attacker-code", state="attacker-state")
    status, _ = _get(url, code="real-code", state=EXPECTED_STATE)
    assert status == 200
    assert authenticator._wait_for_callback(timeout=1) == {
        "code": "real-code",
        "state": EXPECTED_STATE,
    }


def test_forged_error_does_not_end_the_login(callback_server) -> None:
    authenticator, url = callback_server
    status, _ = _get(url, error="access_denied", state="attacker-state")
    assert status == 400
    assert "error" not in authenticator.auth_result_container


def test_escapes_error_details_in_the_callback_page(callback_server) -> None:
    authenticator, url = callback_server
    status, body = _get(
        url,
        error="<script>alert(1)</script>",
        error_description="<b>x</b>",
        state=EXPECTED_STATE,
    )
    assert status == 400
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "<b>x</b>" not in body
    assert "&lt;b&gt;x&lt;/b&gt;" in body
    assert "error" in authenticator.auth_result_container


def test_start_spotify_login_fails_closed_without_state() -> None:
    client = BackendClient("http://localhost:8787")
    with patch.object(
        BackendClient, "_make_request", return_value={"auth_url": "https://x"}
    ):
        with pytest.raises(BackendAPIError, match="No OAuth state"):
            client.start_spotify_login("http://127.0.0.1:8080/callback")


def test_start_spotify_login_returns_auth_url_and_state() -> None:
    client = BackendClient("http://localhost:8787")
    with patch.object(
        BackendClient,
        "_make_request",
        return_value={"auth_url": "https://x", "state": "s1"},
    ):
        assert client.start_spotify_login("http://127.0.0.1:8080/callback") == {
            "auth_url": "https://x",
            "state": "s1",
        }


def test_write_failure_on_forged_callback_records_nothing() -> None:
    """A sender that hangs up mid-response must not end the login."""
    handler = CallbackHandler.__new__(CallbackHandler)  # skip socket setup
    handler.auth_result_container = {}
    handler.expected_state = EXPECTED_STATE
    handler.path = "/callback?code=attacker-code&state=forged"
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = MagicMock()
    handler.wfile.write.side_effect = BrokenPipeError()

    handler.do_GET()

    handler.wfile.write.assert_called_once()
    assert handler.auth_result_container == {}

