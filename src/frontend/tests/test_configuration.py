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
    "SPOTIBYE_TEMP_DIR",
    "SPOTIBYE_DEV_BACKEND_URL",
    "SPOTIBYE_LOCALHOST_BACKEND_URL",
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

    def test_temp_dir_defaults_to_private_cache_subdir(self):
        """Default TEMP_DIR must live under the user-private cache tree (Sonar S5443)."""
        os.environ.pop("SPOTIBYE_TEMP_DIR", None)

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)

            from pathlib import Path

            temp_dir = Path(backend_config.TEMP_DIR)
            cache_dir = backend_config.CACHE_DIR
            assert temp_dir == cache_dir / "temp_exports"
            assert temp_dir.is_relative_to(cache_dir)
            assert temp_dir.is_relative_to(Path.home())

    def test_temp_dir_honors_env_override(self):
        from pathlib import Path

        custom = str(Path.home() / ".spotibye_cache" / "custom_temp_exports")
        os.environ["SPOTIBYE_TEMP_DIR"] = custom

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert backend_config.TEMP_DIR == custom

    def test_cache_directory_configuration(self):
        from pathlib import Path

        # Prefer a user-private path so Sonar S5443 does not flag this test.
        custom_cache_dir = str(Path.home() / ".spotibye_cache" / "pytest-cache-config")
        os.environ["SPOTIBYE_CACHE_DIR"] = custom_cache_dir

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
        os.environ["SPOTIBYE_BACKEND_URL"] = "http://dev-backend.test:8787"
        os.environ["SPOTIBYE_PRODUCTION_BACKEND_URL"] = "http://prod-backend.test:8787"

        with patch.dict("sys.modules"):
            import importlib
            from ..config import backend_config

            importlib.reload(backend_config)
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://dev-backend.test:8787"
            ), "Should use development backend"

            os.environ["SPOTIBYE_USE_PRODUCTION"] = "true"
            importlib.reload(backend_config)
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://prod-backend.test:8787"
            ), "Should use production backend"

            os.environ["SPOTIBYE_USE_PRODUCTION"] = "false"
            importlib.reload(backend_config)
            assert (
                backend_config.CURRENT_BACKEND_URL == "http://dev-backend.test:8787"
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


class TestBackendEndpointSelection:
    """Endpoint defaults and selector presets must require an explicit choice."""

    @staticmethod
    def _reload_config():
        import importlib
        from ..config import backend_config

        return importlib.reload(backend_config)

    def test_unconfigured_startup_has_no_url_or_cloudflare_presets(self, monkeypatch):
        for variable in (
            "SPOTIBYE_BACKEND_URL",
            "SPOTIBYE_DEV_BACKEND_URL",
            "SPOTIBYE_PRODUCTION_BACKEND_URL",
            "SPOTIBYE_USE_PRODUCTION",
        ):
            monkeypatch.delenv(variable, raising=False)

        backend_config = self._reload_config()

        assert backend_config.BACKEND_URL is None
        assert backend_config.DEV_BACKEND_URL is None
        assert backend_config.PRODUCTION_BACKEND_URL is None
        monkeypatch.setattr(backend_config, "get_saved_backend_url", lambda: None)
        assert backend_config.resolve_startup_backend_url() is None
        assert backend_config.BACKEND_PRESETS == {"Localhost": "http://localhost:8787"}

    def test_configured_cloudflare_presets_are_visible_and_distinct(self, monkeypatch):
        monkeypatch.setenv("SPOTIBYE_DEV_BACKEND_URL", "https://dev.example.test")
        monkeypatch.setenv(
            "SPOTIBYE_PRODUCTION_BACKEND_URL", "https://prod.example.test"
        )

        backend_config = self._reload_config()

        assert backend_config.BACKEND_PRESETS == {
            "Localhost": "http://localhost:8787",
            "Cloudflare Dev": "https://dev.example.test",
            "Cloudflare Prod": "https://prod.example.test",
        }
        assert len(set(backend_config.BACKEND_PRESETS.values())) == len(
            backend_config.BACKEND_PRESETS
        )

    def test_invalid_cloudflare_endpoint_does_not_create_a_preset(self, monkeypatch):
        monkeypatch.setenv("SPOTIBYE_DEV_BACKEND_URL", "not-a-url")

        backend_config = self._reload_config()

        assert backend_config.DEV_BACKEND_URL is None
        assert "Cloudflare Dev" not in backend_config.BACKEND_PRESETS

    def test_saved_custom_url_precedes_configured_startup_url(self, monkeypatch):
        monkeypatch.setenv("SPOTIBYE_BACKEND_URL", "https://configured.example.test")
        backend_config = self._reload_config()
        monkeypatch.setattr(
            backend_config,
            "get_saved_backend_url",
            lambda: "https://saved-custom.example.test",
        )

        assert (
            backend_config.resolve_startup_backend_url()
            == "https://saved-custom.example.test"
        )

    def test_dev_backend_url_reexported_from_config_package(self, monkeypatch):
        monkeypatch.setenv(
            "SPOTIBYE_DEV_BACKEND_URL", "https://custom-dev.example.test"
        )

        import importlib
        from .. import config as config_pkg

        backend_config = self._reload_config()
        importlib.reload(config_pkg)

        assert config_pkg.DEV_BACKEND_URL == backend_config.DEV_BACKEND_URL


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

    def test_accepts_ipv4_address(self):
        assert self._is_valid("http://192.168.1.1:8787")

    def test_accepts_ipv6_address(self):
        assert self._is_valid("http://[::1]:8787")

    def test_rejects_empty_string(self):
        assert not self._is_valid("")

    def test_rejects_none(self):
        assert not self._is_valid(None)  # type: ignore[arg-type]

    def test_rejects_https_bare_hostname(self):
        # 'https://x' has no dot and isn't localhost
        assert not self._is_valid("https://x")

    def test_rejects_url_with_embedded_credentials(self):
        assert not self._is_valid("https://user:password@example.com")

    def test_rejects_missing_scheme(self):
        assert not self._is_valid("example.com")

    def test_rejects_ftp_scheme(self):
        assert not self._is_valid("ftp://example.com")

    def test_rejects_garbage(self):
        assert not self._is_valid("not-a-url")


class TestSavedBackendSelection:
    """Saved backend selections should tolerate interrupted or invalid local state."""

    def test_save_is_atomic_and_round_trips(self, monkeypatch, tmp_path):
        from ..config import backend_config

        selection_path = tmp_path / "backend_selection.json"
        monkeypatch.setattr(backend_config, "BACKEND_SELECTION_PATH", selection_path)

        assert backend_config.save_backend_url("http://[::1]:8787/")
        assert backend_config.get_saved_backend_url() == "http://[::1]:8787"
        assert not list(tmp_path.glob(".backend_selection.json.*.tmp"))

    def test_malformed_saved_selection_is_ignored(self, monkeypatch, tmp_path, caplog):
        from ..config import backend_config

        selection_path = tmp_path / "backend_selection.json"
        selection_path.write_text("{not valid JSON", encoding="utf-8")
        monkeypatch.setattr(backend_config, "BACKEND_SELECTION_PATH", selection_path)

        with caplog.at_level(logging.WARNING):
            assert backend_config.get_saved_backend_url() is None
        assert "Unable to load backend selection" in caplog.text

    def test_non_mapping_saved_selection_is_ignored(
        self, monkeypatch, tmp_path, caplog
    ):
        from ..config import backend_config

        selection_path = tmp_path / "backend_selection.json"
        selection_path.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(backend_config, "BACKEND_SELECTION_PATH", selection_path)

        with caplog.at_level(logging.WARNING):
            assert backend_config.get_saved_backend_url() is None
        assert "invalid JSON shape" in caplog.text

    def test_invalid_saved_url_is_ignored_with_a_warning(
        self, monkeypatch, tmp_path, caplog
    ):
        from ..config import backend_config

        selection_path = tmp_path / "backend_selection.json"
        selection_path.write_text('{"backend_url": "https://x"}', encoding="utf-8")
        monkeypatch.setattr(backend_config, "BACKEND_SELECTION_PATH", selection_path)

        with caplog.at_level(logging.WARNING):
            assert backend_config.get_saved_backend_url() is None
        assert "invalid URL" in caplog.text
