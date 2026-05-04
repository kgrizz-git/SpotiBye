"""Authentication flow testing for backend integration."""

from __future__ import annotations

import logging
import time
from typing import Dict, Any, Optional
from unittest.mock import patch

from ..services.backend_client import BackendClient
from ..auth.backend_auth import BackendAuthenticator
from .test_framework import BackendTestFramework

logger = logging.getLogger(__name__)


TEST_REDIRECT_URI = "http://127.0.0.1:8788/callback"
TEST_OAUTH_STATE = "test_state_12345"


class TestAuthenticationFlow:
    """Test authentication flow with mock backend."""

    def __init__(self, framework: BackendTestFramework):
        """
        Initialize authentication tests.

        Args:
            framework: Test framework instance
        """
        self.framework = framework
        self.backend_client: Optional[BackendClient] = None
        self.authenticator: Optional[BackendAuthenticator] = None

    def setup(self) -> bool:
        """Setup authentication test environment."""
        try:
            # Setup backend client with mock server URL
            if self.framework.mock_server:
                backend_url = self.framework.mock_server.get_base_url()
                self.backend_client = BackendClient(backend_url)
                self.authenticator = BackendAuthenticator(self.backend_client)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to setup auth tests: {e}")
            return False

    def test_spotify_login_initiation(self) -> bool:
        """Test Spotify login initiation."""
        self.framework.start_test("Spotify Login Initiation")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Test login initiation
            auth_url = self.backend_client.initiate_spotify_login(TEST_REDIRECT_URI)

            if not auth_url:
                self.framework.end_test(False, "No auth URL returned")
                return False

            if not auth_url.startswith("http"):
                self.framework.end_test(False, "Invalid auth URL format")
                return False

            self.framework.end_test(True, f"Auth URL generated: {auth_url}")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Login initiation failed: {e}")
            return False

    def test_spotify_callback_handling(self) -> bool:
        """Test Spotify OAuth callback handling."""
        self.framework.start_test("Spotify Callback Handling")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Test callback with mock authorization code
            mock_code = "test_code_12345"
            token_response = self.backend_client.handle_spotify_callback(
                mock_code, TEST_OAUTH_STATE
            )

            if not token_response:
                self.framework.end_test(False, "No token response received")
                return False

            token = token_response.get("token")
            if not token:
                self.framework.end_test(False, "No JWT token in response")
                return False

            # Verify token is set in client
            if not self.backend_client.is_authenticated():
                self.framework.end_test(
                    False, "Client not authenticated after callback"
                )
                return False

            self.framework.end_test(True, "OAuth callback handled successfully")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Callback handling failed: {e}")
            return False

    def test_token_refresh(self) -> bool:
        """Test JWT token refresh."""
        self.framework.start_test("Token Refresh")

        try:
            if not self.backend_client:
                self.framework.end_test(False, "Backend client not initialized")
                return False

            # Ensure we have a token first
            self.backend_client.handle_spotify_callback(
                "test_code_12345", TEST_OAUTH_STATE
            )

            # Test token refresh
            refresh_response = self.backend_client.refresh_token()

            if not refresh_response:
                self.framework.end_test(False, "No refresh response received")
                return False

            new_token = refresh_response.get("token")
            if not new_token:
                self.framework.end_test(False, "No new token in refresh response")
                return False

            # Verify client is still authenticated
            if not self.backend_client.is_authenticated():
                self.framework.end_test(False, "Client not authenticated after refresh")
                return False

            self.framework.end_test(True, "Token refresh successful")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Token refresh failed: {e}")
            return False

    def test_logout(self) -> bool:
        """Test logout functionality."""
        self.framework.start_test("Logout Functionality")

        try:
            if not self.authenticator:
                self.framework.end_test(False, "Authenticator not initialized")
                return False

            # Ensure we're authenticated first
            self.backend_client.handle_spotify_callback(
                "test_code_12345", TEST_OAUTH_STATE
            )

            # Test logout
            logout_success = self.authenticator.logout()

            if not logout_success:
                self.framework.end_test(False, "Logout returned False")
                return False

            # Verify client is no longer authenticated
            if self.backend_client.is_authenticated():
                self.framework.end_test(
                    False, "Client still authenticated after logout"
                )
                return False

            self.framework.end_test(True, "Logout successful")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Logout failed: {e}")
            return False

    def test_full_auth_flow(self) -> bool:
        """Test complete authentication flow."""
        self.framework.start_test("Full Authentication Flow")

        try:
            if not self.authenticator:
                self.framework.end_test(False, "Authenticator not initialized")
                return False

            # Simulate the browser and callback parts of the flow while exercising
            # the current authenticator contract end-to-end.
            with patch("webbrowser.open", return_value=True), patch.object(
                self.authenticator, "_start_callback_server", return_value=True
            ), patch.object(
                self.authenticator,
                "_wait_for_callback",
                return_value={"code": "test_code_12345", "state": TEST_OAUTH_STATE},
            ), patch.object(self.authenticator, "_stop_callback_server"):
                auth_success = self.authenticator.login()

            if not auth_success:
                self.framework.end_test(False, "Login flow failed")
                return False

            # Verify authentication state
            if not self.authenticator.is_authenticated():
                self.framework.end_test(False, "Not authenticated after login flow")
                return False

            # Test logout
            logout_success = self.authenticator.logout()

            if not logout_success:
                self.framework.end_test(False, "Logout in flow failed")
                return False

            self.framework.end_test(True, "Full auth flow completed successfully")
            return True

        except Exception as e:
            self.framework.end_test(False, f"Full auth flow failed: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all authentication tests."""
        logger.info("Starting authentication flow tests")

        if not self.setup():
            return {"success": False, "message": "Failed to setup test environment"}

        # Run individual tests
        tests = [
            self.test_spotify_login_initiation,
            self.test_spotify_callback_handling,
            self.test_token_refresh,
            self.test_logout,
            self.test_full_auth_flow,
        ]

        passed = 0
        total = len(tests)

        for test in tests:
            if test():
                passed += 1
            time.sleep(0.1)  # Small delay between tests

        logger.info(f"Authentication tests completed: {passed}/{total} passed")

        return {
            "success": True,
            "passed": passed,
            "total": total,
            "results": self.framework.get_test_results(),
        }
