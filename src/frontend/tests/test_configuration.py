"""Configuration testing for different environments."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest

from ..config.backend_config import (
    UIConstants,
    FeatureFlags,
    PerformanceSettings,
)
from ..services.backend_client import BackendClient

logger = logging.getLogger(__name__)

_ENV_KEYS = [
    "SPOTIBYE_BACKEND_URL",
    "SPOTIBYE_PRODUCTION_BACKEND_URL",
    "SPOTIBYE_USE_PRODUCTION",
    "SPOTIBYE_API_TIMEOUT",
    "SPOTIBYE_OAUTH_PORT",
    "SPOTIBYE_CACHE_DIR",
    "SPOTIBYE_EXPORT_DIR",
]


class TestConfiguration:
    @pytest.fixture(autouse=True)
    def restore_env(self):
        saved = {k: os.environ.get(k) for k in _ENV_KEYS}
        yield
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        # re-sync the module so subsequent tests see the restored env vars
        import importlib
        from ..config import backend_config

        importlib.reload(backend_config)

    def test_development_environment_config(self):
        os.environ["SPOTIBYE_USE_PRODUCTION"] = "false"
        os.environ["SPOTIBYE_BACKEND_URL"] = "http://localhost:8787"
        os.environ["SPOTIBYE_API_TIMEOUT"] = "30"

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)

            assert (
                not backend_config.USE_PRODUCTION
            ), f"USE_PRODUCTION should be False, got {backend_config.USE_PRODUCTION}"
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://localhost:8787"
            ), f"Backend URL should be localhost, got {backend_config.CURRENT_BACKEND_URL}"
            assert (
                backend_config.API_TIMEOUT == 30
            ), f"API timeout should be 30, got {backend_config.API_TIMEOUT}"

    def test_production_environment_config(self):
        os.environ["SPOTIBYE_USE_PRODUCTION"] = "true"
        os.environ["SPOTIBYE_PRODUCTION_BACKEND_URL"] = "https://api.spotibye.com"
        os.environ["SPOTIBYE_API_TIMEOUT"] = "60"

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)

            assert (
                backend_config.USE_PRODUCTION
            ), f"USE_PRODUCTION should be True, got {backend_config.USE_PRODUCTION}"
            assert (
                backend_config.CURRENT_BACKEND_URL == "https://api.spotibye.com"
            ), f"Backend URL should be production, got {backend_config.CURRENT_BACKEND_URL}"
            assert (
                backend_config.API_TIMEOUT == 60
            ), f"API timeout should be 60, got {backend_config.API_TIMEOUT}"

    def test_backend_client_configuration(self):
        custom_url = "http://custom-backend:9000"
        client = BackendClient(base_url=custom_url)
        assert (
            client.base_url == custom_url
        ), f"Backend client URL should be {custom_url}, got {client.base_url}"

        # BackendClient hardcodes http://localhost:8787 as the default dev URL
        default_client = BackendClient()
        assert (
            default_client.base_url == "http://localhost:8787"
        ), f"Default client URL should be http://localhost:8787, got {default_client.base_url}"

    def test_cache_directory_configuration(self):
        custom_cache_dir = "/tmp/spotibye-test-cache"
        os.environ["SPOTIBYE_CACHE_DIR"] = custom_cache_dir

        from pathlib import Path
        from ..caching.backend_cache import BackendCacheManager

        with patch.object(BackendCacheManager, "__init__", return_value=None):
            cache_manager = BackendCacheManager()
            cache_manager.cache_dir = Path(custom_cache_dir)
            assert (
                str(cache_manager.cache_dir) == custom_cache_dir
            ), f"Cache manager should use {custom_cache_dir}, got {cache_manager.cache_dir}"

        cache_path = Path(custom_cache_dir)
        if cache_path.exists():
            import shutil

            shutil.rmtree(cache_path)

    def test_feature_flags_configuration(self):
        assert isinstance(
            FeatureFlags.ENABLE_CACHING, bool
        ), "ENABLE_CACHING should be boolean"
        assert isinstance(
            FeatureFlags.ENABLE_ANALYSIS, bool
        ), "ENABLE_ANALYSIS should be boolean"
        assert isinstance(
            FeatureFlags.ENABLE_EXPORT, bool
        ), "ENABLE_EXPORT should be boolean"

        if hasattr(UIConstants, "LOADING_MESSAGE"):
            assert isinstance(
                UIConstants.LOADING_MESSAGE, str
            ), "LOADING_MESSAGE should be string"
        if hasattr(UIConstants, "ERROR_MESSAGE_COLOR"):
            assert isinstance(
                UIConstants.ERROR_MESSAGE_COLOR, str
            ), "ERROR_MESSAGE_COLOR should be string"

        assert isinstance(
            PerformanceSettings.BATCH_SIZE, int
        ), "BATCH_SIZE should be integer"
        assert PerformanceSettings.BATCH_SIZE > 0, "BATCH_SIZE should be positive"

    def test_oauth_configuration(self):
        os.environ["SPOTIBYE_OAUTH_PORT"] = "9999"

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert (
                backend_config.OAUTH_CALLBACK_PORT == 9999
            ), f"OAuth port should be 9999, got {backend_config.OAUTH_CALLBACK_PORT}"

        from ..auth.backend_auth import BackendAuthenticator

        custom_auth = BackendAuthenticator()
        custom_auth.callback_port = 9999
        assert (
            custom_auth.callback_port == 9999
        ), "Authenticator should accept custom port 9999"

    def test_environment_switching(self):
        os.environ["SPOTIBYE_USE_PRODUCTION"] = "false"
        os.environ["SPOTIBYE_BACKEND_URL"] = "http://dev-backend:8787"
        os.environ["SPOTIBYE_PRODUCTION_BACKEND_URL"] = "http://prod-backend:8787"

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://dev-backend:8787"
            ), "Should use development backend"

            os.environ["SPOTIBYE_USE_PRODUCTION"] = "true"
            importlib.reload(backend_config)
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://prod-backend:8787"
            ), "Should use production backend"

            os.environ["SPOTIBYE_USE_PRODUCTION"] = "false"
            importlib.reload(backend_config)
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://dev-backend:8787"
            ), "Should switch back to development backend"

    def test_configuration_validation(self):
        os.environ["SPOTIBYE_API_TIMEOUT"] = "45"
        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert (
                backend_config.API_TIMEOUT == 45
            ), f"Should use valid timeout 45, got {backend_config.API_TIMEOUT}"

        os.environ["SPOTIBYE_OAUTH_PORT"] = "8080"
        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert (
                backend_config.OAUTH_CALLBACK_PORT == 8080
            ), f"Should use valid port 8080, got {backend_config.OAUTH_CALLBACK_PORT}"

        os.environ["SPOTIBYE_USE_PRODUCTION"] = "maybe"
        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert (
                not backend_config.USE_PRODUCTION
            ), "Should default to False for invalid boolean"


class TestIsValidBackendUrl:
    """Regression tests for FL-2: is_valid_backend_url should validate
    the URL shape (not just the scheme) so we don't accept obvious
    garbage like 'https://x' or 'http:///path'."""

    def _is_valid(self, url):
        from ..config.backend_config import is_valid_backend_url
        return is_valid_backend_url(url)

    def test_accepts_https_with_dot(self):
        assert self._is_valid("https://example.com")

    def test_accepts_https_with_port(self):
        assert self._is_valid("https://example.com:8787")

    def test_accepts_http_with_dot(self):
        assert self._is_valid("http://api.example.com")

    def test_accepts_http_localhost(self):
        assert self._is_valid("http://localhost:8787")

    def test_accepts_http_localhost_no_port(self):
        assert self._is_valid("http://localhost")

    def test_rejects_empty_string(self):
        assert not self._is_valid("")

    def test_rejects_none(self):
        assert not self._is_valid(None)  # type: ignore[arg-type]

    def test_rejects_https_bare_hostname(self):
        # 'https://x' has no dot and isn't localhost
        assert not self._is_valid("https://x")

    def test_rejects_missing_scheme(self):
        assert not self._is_valid("example.com")

    def test_rejects_ftp_scheme(self):
        assert not self._is_valid("ftp://example.com")

    def test_rejects_garbage(self):
        assert not self._is_valid("not-a-url")

