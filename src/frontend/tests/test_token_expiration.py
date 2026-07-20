"""Tests for Spotify token expiration handling (AUTH_REQUIRED flow)."""

from __future__ import annotations

import base64
import json
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch

import pytest

from ..services.backend_client import BackendAPIError, BackendClient
from ..auth.backend_auth import BackendAuthenticator


def _valid_jwt(exp_offset_seconds: int = 3600) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"exp": int(time.time()) + exp_offset_seconds}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


class _FakeWidget:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def bind(self, **_kwargs):
        pass

    def add_widget(self, *_args, **_kwargs):
        pass


def _fake_module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _mainthread(func):
    return func


def _install_kivy_stubs() -> dict[str, types.ModuleType | None]:
    clock_module = _fake_module("kivy.clock", Clock=MagicMock(), mainthread=_mainthread)
    stubs = {
        "kivy": types.ModuleType("kivy"),
        "kivy.metrics": _fake_module("kivy.metrics", dp=lambda value: value),
        "kivy.clock": clock_module,
        "kivy.config": _fake_module("kivy.config", Config=MagicMock()),
        "kivy.app": _fake_module("kivy.app", App=MagicMock()),
        "kivy.uix": types.ModuleType("kivy.uix"),
        "kivy.uix.boxlayout": _fake_module("kivy.uix.boxlayout", BoxLayout=_FakeWidget),
        "kivy.uix.button": _fake_module("kivy.uix.button", Button=_FakeWidget),
        "kivy.uix.label": _fake_module("kivy.uix.label", Label=_FakeWidget),
        "kivy.uix.popup": _fake_module("kivy.uix.popup", Popup=_FakeWidget),
        "kivy.uix.screenmanager": _fake_module(
            "kivy.uix.screenmanager", ScreenManager=_FakeWidget, Screen=_FakeWidget
        ),
        "kivy.uix.widget": _fake_module("kivy.uix.widget", Widget=_FakeWidget),
        "kivy.uix.spinner": _fake_module("kivy.uix.spinner", Spinner=_FakeWidget),
        "kivy.uix.textinput": _fake_module("kivy.uix.textinput", TextInput=_FakeWidget),
        "kivy.uix.gridlayout": _fake_module(
            "kivy.uix.gridlayout", GridLayout=_FakeWidget
        ),
        "kivy.uix.scrollview": _fake_module(
            "kivy.uix.scrollview", ScrollView=_FakeWidget
        ),
        "kivy.core": types.ModuleType("kivy.core"),
        "kivy.core.window": _fake_module("kivy.core.window", Window=MagicMock()),
        "kivy.core.text": _fake_module("kivy.core.text", LabelBase=MagicMock()),
        "kivy.utils": _fake_module("kivy.utils", platform="linux"),
        "kivymd": types.ModuleType("kivymd"),
        "kivymd.app": _fake_module("kivymd.app", MDApp=type("MDApp", (), {})),
    }
    originals = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    return originals


def _import_backend_app_module():
    import importlib

    originals = _install_kivy_stubs()
    ui_mocks = {
        "src.frontend.auth.backend_login_screen": _fake_module(
            "src.frontend.auth.backend_login_screen",
            create_backend_login_screen=MagicMock(),
        ),
        "src.frontend.screens.backend_main_screen": _fake_module(
            "src.frontend.screens.backend_main_screen",
            BackendMainScreen=MagicMock,
        ),
        "src.frontend.screens.backend_main_screen_adapter": _fake_module(
            "src.frontend.screens.backend_main_screen_adapter",
            BackendMainScreenAdapter=MagicMock,
            create_backend_adapter=MagicMock(),
        ),
        "src.frontend.ui.backend_selector_popup": _fake_module(
            "src.frontend.ui.backend_selector_popup",
            BackendSelectorPopup=MagicMock,
        ),
    }
    ui_originals = {name: sys.modules.get(name) for name in ui_mocks}
    sys.modules.update(ui_mocks)

    module_name = "src.frontend.app.backend_app"
    for name in (module_name, "src.frontend.app"):
        sys.modules.pop(name, None)

    try:
        return importlib.import_module(module_name)
    finally:
        merged = {**originals, **ui_originals}
        for name, original in merged.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class TestBackendAPIErrorAuthRequired:
    def test_extracts_error_code_from_response_data(self) -> None:
        exc = BackendAPIError(
            "Unauthorized",
            401,
            {"error": {"code": "AUTH_REQUIRED", "message": "Refresh token expired"}},
        )
        assert exc.error_code == "AUTH_REQUIRED"

    def test_accepts_explicit_error_code_parameter(self) -> None:
        exc = BackendAPIError("Unauthorized", 401, error_code="AUTH_REQUIRED")
        assert exc.error_code == "AUTH_REQUIRED"

    def test_is_auth_required_error_helper(self) -> None:
        client = BackendClient("http://localhost:8787")
        exc = BackendAPIError("Unauthorized", 401, error_code="AUTH_REQUIRED")
        assert client.is_auth_required_error(exc) is True
        assert (
            client.is_auth_required_error(BackendAPIError("Unauthorized", 401)) is False
        )


class TestBackendClientDownloadAuthRequired:
    def test_download_file_surfaces_auth_required_error_code(self) -> None:
        client = BackendClient("http://localhost:8787")
        client.session = MagicMock()
        client.session.get.return_value = MagicMock(
            status_code=401,
            headers={"content-type": "application/json"},
            json=lambda: {
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Refresh token expired or revoked",
                }
            },
        )

        with pytest.raises(BackendAPIError) as exc_info:
            client.download_export("playlist-1")

        assert exc_info.value.error_code == "AUTH_REQUIRED"
        assert exc_info.value.status_code == 401


class TestBackendAuthenticatorRefreshToken:
    def test_wipes_caches_and_returns_false_on_auth_required(self) -> None:
        client = BackendClient("http://localhost:8787")
        authenticator = BackendAuthenticator(client)
        cache_manager = MagicMock()

        client.refresh_token = MagicMock(
            side_effect=BackendAPIError(
                "Unauthorized",
                401,
                {"error": {"code": "AUTH_REQUIRED"}},
            )
        )

        mock_app = MagicMock()
        mock_app.cache_manager = cache_manager

        with patch("kivy.app.App.get_running_app", return_value=mock_app):
            result = authenticator.refresh_token()

        assert result is False
        assert client.auth_token is None
        cache_manager.clear_auth_token.assert_called_once()


def _make_app_instance(backend_app_module):
    """Create an app instance without running Kivy/MDApp __init__."""
    app = object.__new__(backend_app_module.BackendSpotifyExporterApp)
    app.token_info = None
    app.username = None
    app.screen_manager = None
    return app


class TestHandleSessionExpired:
    def test_wipes_disk_cache_and_in_memory_token(self) -> None:
        backend_app_module = _import_backend_app_module()
        app = _make_app_instance(backend_app_module)
        app.backend_client = BackendClient("http://localhost:8787")
        app.backend_client.set_auth_token("cached-token")
        app.cache_manager = MagicMock()
        app.screen_manager = None

        app.handle_session_expired()

        assert app.backend_client.auth_token is None
        app.cache_manager.clear_auth_token.assert_called_once()


class TestFormatBackendApiError:
    def test_includes_auth_required_code_for_main_screen_detection(self) -> None:
        from ..screens.adapter_mixins.core import BackendMainScreenAdapterCore

        adapter = BackendMainScreenAdapterCore()
        exc = BackendAPIError(
            "Refresh token expired or revoked",
            401,
            {"error": {"code": "AUTH_REQUIRED", "message": "Refresh token expired"}},
        )

        formatted = adapter._format_backend_api_error(exc, "Backend request failed")

        assert "code=AUTH_REQUIRED" in formatted


class TestTryAutoLogin:
    def _build_app(self):
        backend_app_module = _import_backend_app_module()
        app = _make_app_instance(backend_app_module)
        app.cache_manager = MagicMock()
        app.backend_client = BackendClient("http://localhost:8787")
        app.login_screen = MagicMock()
        app.login_screen.status_label = MagicMock()
        app.switch_to_main = MagicMock()
        app._set_login_status = MagicMock()
        return app, backend_app_module

    def test_transport_error_proceeds_without_wiping_cache(self) -> None:
        app, backend_app_module = self._build_app()
        token = _valid_jwt()
        app.cache_manager.load_auth_token.return_value = {
            "token": token,
            "username": "Cached User",
        }

        def run_callbacks(callback, _dt=0, *_args) -> None:
            callback(0)

        with patch.object(
            backend_app_module.Clock,
            "schedule_once",
            side_effect=run_callbacks,
        ):
            app.backend_client.get_me = MagicMock(
                side_effect=BackendAPIError(
                    "Unable to connect",
                    None,
                    {"origin": "transport"},
                )
            )
            app._try_auto_login()
            for _ in range(20):
                if app.switch_to_main.called:
                    break
                threading.Event().wait(0.05)

        app.cache_manager.clear_auth_token.assert_not_called()
        app.switch_to_main.assert_called_once()
        app._set_login_status.assert_not_called()
        assert app.username == "Cached User"
        assert app.token_info == {"access_token": token}

    def test_auth_required_wipes_cache_and_keeps_user_on_login_screen(self) -> None:
        app, backend_app_module = self._build_app()
        token = _valid_jwt()
        app.cache_manager.load_auth_token.return_value = {"token": token}
        app.backend_client.set_auth_token(token)

        def run_callbacks(callback, _dt=0, *_args) -> None:
            callback(0)

        with patch.object(
            backend_app_module.Clock,
            "schedule_once",
            side_effect=run_callbacks,
        ):
            app.backend_client.get_me = MagicMock(
                side_effect=BackendAPIError(
                    "Unauthorized",
                    401,
                    {"error": {"code": "AUTH_REQUIRED"}},
                )
            )
            app._try_auto_login()
            for _ in range(20):
                if app._set_login_status.called:
                    break
                threading.Event().wait(0.05)
        assert app.backend_client.auth_token is None
        app.switch_to_main.assert_not_called()
        app._set_login_status.assert_called_once()
        assert "expired" in app._set_login_status.call_args[0][0].lower()
        assert app.username is None

    def test_get_me_success_hydrates_username_from_profile(self) -> None:
        app, backend_app_module = self._build_app()
        token = _valid_jwt()
        app.cache_manager.load_auth_token.return_value = {"token": token}

        def run_callbacks(callback, _dt=0, *_args) -> None:
            callback(0)

        with patch.object(
            backend_app_module.Clock,
            "schedule_once",
            side_effect=run_callbacks,
        ):
            app.backend_client.get_me = MagicMock(
                return_value={"id": "u1", "name": "Alice", "email": "a@example.com"}
            )
            app._try_auto_login()
            for _ in range(20):
                if app.switch_to_main.called:
                    break
                threading.Event().wait(0.05)

        app.switch_to_main.assert_called_once()
        assert app.username == "Alice"
        assert app.token_info == {"access_token": token}
        app.cache_manager.save_auth_token.assert_called()
        saved = app.cache_manager.save_auth_token.call_args[0][0]
        assert saved["username"] == "Alice"
        assert saved["token"] == token

    def test_get_me_success_falls_back_to_cached_username(self) -> None:
        app, backend_app_module = self._build_app()
        token = _valid_jwt()
        app.cache_manager.load_auth_token.return_value = {
            "token": token,
            "username": "From Cache",
        }

        def run_callbacks(callback, _dt=0, *_args) -> None:
            callback(0)

        with patch.object(
            backend_app_module.Clock,
            "schedule_once",
            side_effect=run_callbacks,
        ):
            # Empty / null-ish profile fields should fall through to cache.
            app.backend_client.get_me = MagicMock(
                return_value={"id": None, "name": None, "display_name": None}
            )
            app._try_auto_login()
            for _ in range(20):
                if app.switch_to_main.called:
                    break
                threading.Event().wait(0.05)

        assert app.username == "From Cache"
