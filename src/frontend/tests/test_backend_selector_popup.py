"""Tests for BackendSelectorPopup: preset switching and default-URL matching.

Constructing real Kivy widgets under KIVY_WINDOW=headless aborts the
process (kivy.metrics.dp() and any real widget's __init__ resolve Window,
which doesn't exist headless — see .github/workflows/ci.yml's comment on
kivy sys.exit(102)), and CI / scripts/verify-frontend.sh always run
headless. Stub every kivy name this module's _build_ui() touches, import
under the stub, then restore sys.modules immediately so later test files
in the same session see the real kivy modules.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock, patch


class _FakeWidget:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def bind(self, **_kwargs):
        pass

    def add_widget(self, *_args, **_kwargs):
        pass


class _FakePopup(_FakeWidget):
    def dismiss(self):
        pass


def _fake_module(name: str, **attrs) -> types.ModuleType:
    # A real ModuleType instance, not MagicMock: accessing any attribute
    # other than the ones set below correctly raises AttributeError instead
    # of silently auto-vivifying a mock, so a typo'd import from one of
    # these stubs fails loudly instead of masking a real bug.
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


_STUB_MODULES = {
    "kivy.metrics": _fake_module("kivy.metrics", dp=lambda value: value),
    "kivy.uix.popup": _fake_module("kivy.uix.popup", Popup=_FakePopup),
    "kivy.uix.spinner": _fake_module("kivy.uix.spinner", Spinner=_FakeWidget),
    "kivy.uix.textinput": _fake_module("kivy.uix.textinput", TextInput=_FakeWidget),
    "kivy.uix.button": _fake_module("kivy.uix.button", Button=_FakeWidget),
    "kivy.uix.label": _fake_module("kivy.uix.label", Label=_FakeWidget),
    "kivy.uix.boxlayout": _fake_module("kivy.uix.boxlayout", BoxLayout=_FakeWidget),
}
_original_modules = {name: sys.modules.get(name) for name in _STUB_MODULES}
sys.modules.update(_STUB_MODULES)
try:
    from ..ui.backend_selector_popup import BackendSelectorPopup
finally:
    for _name, _orig in _original_modules.items():
        if _orig is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _orig


class TestBackendSelectorPopup:
    """Selector tests for configured, custom, and unconfigured endpoints."""

    @patch.dict(
        "src.frontend.ui.backend_selector_popup.BACKEND_PRESETS",
        {
            "Localhost": "http://localhost:8787",
            "Cloudflare Dev": "https://dev.example.test",
        },
        clear=True,
    )
    @patch("src.frontend.ui.backend_selector_popup.BackendClient")
    def test_preset_switch_updates_url_input(self, mock_backend_client):
        mock_backend_client.return_value.health_check.return_value = {
            "status": "healthy"
        }
        popup = BackendSelectorPopup(
            default_url="http://localhost:8787", on_apply=Mock(), on_cancel=Mock()
        )
        popup._on_preset_changed(popup.preset_spinner, "Cloudflare Dev")
        assert popup.url_input.text == "https://dev.example.test"
        assert popup.url_input.text != "http://localhost:8787"

    @patch.dict(
        "src.frontend.ui.backend_selector_popup.BACKEND_PRESETS",
        {
            "Localhost": "http://localhost:8787",
            "Cloudflare Dev": "https://dev.example.test",
        },
        clear=True,
    )
    @patch("src.frontend.ui.backend_selector_popup.BackendClient")
    def test_initialize_from_default_url_matches_correct_preset(
        self, mock_backend_client
    ):
        mock_backend_client.return_value.health_check.return_value = {
            "status": "healthy"
        }
        popup = BackendSelectorPopup(
            default_url="https://dev.example.test",
            on_apply=Mock(),
            on_cancel=Mock(),
        )
        # This assertion depends on _initialize_from_default_url() being
        # called after _build_ui() inside __init__ (it mutates
        # preset_spinner.text after the initial self._preset_names[0]
        # default set during construction) — if a future refactor reorders
        # those two calls, this test's premise changes.
        assert popup.preset_spinner.text == "Cloudflare Dev"

    @patch("src.frontend.ui.backend_selector_popup.BackendClient")
    def test_unconfigured_startup_uses_blank_custom_field(self, mock_backend_client):
        mock_backend_client.return_value.health_check.return_value = {
            "status": "healthy"
        }
        popup = BackendSelectorPopup(
            default_url=None, on_apply=Mock(), on_cancel=Mock()
        )

        assert popup.preset_spinner.text == "Custom"
        assert popup.url_input.text == ""
        assert popup.url_input.readonly is False

    @patch("src.frontend.ui.backend_selector_popup.BackendClient")
    def test_localhost_remains_an_explicit_preset(self, mock_backend_client):
        mock_backend_client.return_value.health_check.return_value = {
            "status": "healthy"
        }
        popup = BackendSelectorPopup(
            default_url=None, on_apply=Mock(), on_cancel=Mock()
        )

        popup._on_preset_changed(popup.preset_spinner, "Localhost")

        assert popup.url_input.text == "http://localhost:8787"
        assert popup.url_input.readonly is True

    @patch("src.frontend.ui.backend_selector_popup.BackendClient")
    def test_custom_url_not_misidentified_as_preset(self, mock_backend_client):
        mock_backend_client.return_value.health_check.return_value = {
            "status": "healthy"
        }
        popup = BackendSelectorPopup(
            default_url="https://example.com/custom",
            on_apply=Mock(),
            on_cancel=Mock(),
        )
        assert popup.preset_spinner.text == "Custom"
        assert popup.url_input.readonly is False


# _schedule_auto_health_check goes through Clock.schedule_once, which needs
# the Kivy clock to be pumped (e.g. via App.run()) to actually fire — it
# does not crash headless (verified: kivy.clock.Clock.schedule_once works
# fine without a Window), it just won't invoke the callback synchronously
# in a test. The tests above don't depend on it firing. Don't extend these
# tests to assert on status_label.text without first pumping Clock or
# calling _start_health_check directly.
