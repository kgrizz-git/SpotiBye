"""Authentication flow testing for backend integration."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from ..services.backend_client import BackendClient
from ..auth.backend_auth import BackendAuthenticator

logger = logging.getLogger(__name__)

TEST_REDIRECT_URI = "http://127.0.0.1:8788/callback"
TEST_OAUTH_STATE = "test_state_12345"


class TestAuthenticationFlow:
    @pytest.fixture(autouse=True)
    def setup_clients(self, mock_backend_server):
        backend_url = mock_backend_server.get_base_url()
        self.backend_client = BackendClient(backend_url)
        self.authenticator = BackendAuthenticator(self.backend_client)

    def test_spotify_login_initiation(self):
        auth_url = self.backend_client.initiate_spotify_login(TEST_REDIRECT_URI)
        assert auth_url, "No auth URL returned"
        assert auth_url.startswith("http"), "Invalid auth URL format"

    def test_spotify_callback_handling(self):
        token_response = self.backend_client.handle_spotify_callback(
            "test_code_12345", TEST_OAUTH_STATE
        )
        assert token_response, "No token response received"
        assert token_response.get("token"), "No JWT token in response"
        assert (
            self.backend_client.is_authenticated()
        ), "Client not authenticated after callback"

    def test_token_refresh(self):
        self.backend_client.handle_spotify_callback("test_code_12345", TEST_OAUTH_STATE)
        refresh_response = self.backend_client.refresh_token()
        assert refresh_response, "No refresh response received"
        assert refresh_response.get("token"), "No new token in refresh response"
        assert (
            self.backend_client.is_authenticated()
        ), "Client not authenticated after refresh"

    def test_logout(self):
        self.backend_client.handle_spotify_callback("test_code_12345", TEST_OAUTH_STATE)
        assert self.authenticator.logout(), "Logout returned False"
        assert (
            not self.backend_client.is_authenticated()
        ), "Client still authenticated after logout"

    def test_full_auth_flow(self):
        with (
            patch("webbrowser.open", return_value=True),
            patch.object(
                self.authenticator, "_start_callback_server", return_value=True
            ),
            patch.object(
                self.authenticator,
                "_wait_for_callback",
                return_value={"code": "test_code_12345", "state": TEST_OAUTH_STATE},
            ),
            patch.object(self.authenticator, "_stop_callback_server"),
        ):
            auth_success = self.authenticator.login()
        assert auth_success, "Login flow failed"
        assert (
            self.authenticator.is_authenticated()
        ), "Not authenticated after login flow"
        assert self.authenticator.logout(), "Logout in flow failed"
