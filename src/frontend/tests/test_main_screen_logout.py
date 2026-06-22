"""Tests for FM-1 (download_export signature) and FM-6 (missing logout)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


class TestDownloadExportSignature:
    """FM-1: download_export should no longer take an export_id argument."""

    def test_backend_client_download_export_signature(self):
        from ..services.backend_client import BackendClient

        client = BackendClient(base_url="http://localhost:8787")
        import inspect
        sig = inspect.signature(client.download_export)
        params = list(sig.parameters.keys())
        assert "export_id" not in params, (
            "download_export should not accept export_id (FM-1)"
        )
        assert "playlist_id" in params

    def test_adapter_download_export_signature(self):
        from ..screens.backend_main_screen_adapter import BackendMainScreenAdapter

        import inspect
        sig = inspect.signature(BackendMainScreenAdapter.download_export)
        params = list(sig.parameters.keys())
        assert "export_id" not in params, (
            "BackendMainScreenAdapter.download_export should not accept export_id (FM-1)"
        )
        assert "playlist_id" in params
        assert "save_path" in params

    def test_download_export_hits_new_endpoint(self):
        from ..services.backend_client import BackendClient

        client = BackendClient(base_url="http://localhost:8787")
        client.session = MagicMock()
        client.session.get.return_value = MagicMock(
            status_code=200,
            content=b"binary-data",
            headers={"content-type": "application/octet-stream"},
        )

        result = client.download_export("playlist-1")

        assert result == b"binary-data"
        call_url = client.session.get.call_args[0][0]
        assert call_url.endswith("/export/playlist/playlist-1/download")
        # export_id should not appear in the URL
        assert "export_id" not in call_url

    def test_download_export_raises_on_error(self):
        from ..services.backend_client import BackendClient, BackendAPIError

        client = BackendClient(base_url="http://localhost:8787")
        client.session = MagicMock()
        client.session.get.return_value = MagicMock(
            status_code=404,
            headers={"content-type": "application/json"},
            json=lambda: {"error": {"code": "NOT_FOUND", "message": "Not found"}},
        )

        with pytest.raises(BackendAPIError):
            client.download_export("playlist-1")


class TestPerformLogoutMissingMethod:
    """FM-6: perform_logout logs an error when the app lacks logout()."""

    def test_logs_error_when_app_missing_logout_method(self, caplog):
        from ..screens.main_screen_logout import perform_logout

        # Build a mock App that has no `logout` attribute
        mock_app = MagicMock(spec=[])  # spec=[] means no attributes

        with caplog.at_level(logging.ERROR, logger="src.frontend.screens.main_screen_logout"):
            with patch("src.frontend.screens.main_screen_logout.App") as MockApp:
                MockApp.get_running_app.return_value = mock_app
                # Should NOT raise
                perform_logout()

        # Verify an error was logged about missing logout method
        error_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("logout" in msg.lower() for msg in error_messages), (
            f"Expected error log about missing logout method, got: {error_messages}"
        )

    def test_calls_logout_when_method_exists(self):
        from ..screens.main_screen_logout import perform_logout

        mock_app = MagicMock()
        mock_app.logout = MagicMock()

        with patch("src.frontend.screens.main_screen_logout.App") as MockApp:
            MockApp.get_running_app.return_value = mock_app
            perform_logout()

        mock_app.logout.assert_called_once()

    def test_returns_silently_when_app_is_none(self):
        from ..screens.main_screen_logout import perform_logout

        with patch("src.frontend.screens.main_screen_logout.App") as MockApp:
            MockApp.get_running_app.return_value = None
            # Should not raise
            perform_logout()
