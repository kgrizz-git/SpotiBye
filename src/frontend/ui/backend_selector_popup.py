"""Popup UI for selecting and validating backend URL before app login."""

from __future__ import annotations

import threading
from typing import Callable, Optional

from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from ..config.backend_config import BACKEND_PRESETS, is_valid_backend_url
from ..services.backend_client import BackendClient


class BackendSelectorPopup(Popup):
    """Prompt user to choose backend URL and test connectivity."""

    def __init__(
        self,
        default_url: str,
        on_apply: Callable[[str], None],
        on_cancel: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.title = "Choose Backend"
        self.size_hint = (0.8, 0.7)
        self.auto_dismiss = False

        self._default_url = default_url.rstrip("/")
        self._on_apply = on_apply
        self._on_cancel = on_cancel
        self._last_tested_url: str | None = None
        self._auto_test_event = None
        self._health_check_request_id = 0

        self._preset_names = list(BACKEND_PRESETS.keys()) + ["Custom"]
        self._build_ui()
        self._initialize_from_default_url()

    def _build_ui(self) -> None:
        layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        layout.add_widget(Label(text="Backend target", size_hint_y=None, height=dp(24)))

        self.preset_spinner = Spinner(
            text=self._preset_names[0],
            values=self._preset_names,
            size_hint_y=None,
            height=dp(40),
        )
        self.preset_spinner.bind(text=self._on_preset_changed)  # type: ignore[attr-defined]
        layout.add_widget(self.preset_spinner)

        layout.add_widget(Label(text="Backend URL", size_hint_y=None, height=dp(24)))

        self.url_input = TextInput(
            multiline=False,
            size_hint_y=None,
            height=dp(38),
        )
        self.url_input.bind(text=self._on_url_changed)  # type: ignore[attr-defined]
        layout.add_widget(self.url_input)

        self.status_label = Label(
            text="Choose a backend. Connection status updates automatically.",
            size_hint_y=None,
            height=dp(44),
            color=(0.7, 0.7, 0.7, 1),
        )
        layout.add_widget(self.status_label)

        buttons = BoxLayout(
            orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(42)
        )

        self.test_button = Button(text="Test Connection")
        self.test_button.bind(on_press=self._on_test_pressed)  # type: ignore[attr-defined]
        buttons.add_widget(self.test_button)

        self.continue_button = Button(text="Continue")
        self.continue_button.bind(on_press=self._on_continue_pressed)  # type: ignore[attr-defined]
        buttons.add_widget(self.continue_button)

        self.cancel_button = Button(text="Cancel")
        self.cancel_button.bind(on_press=self._on_cancel_pressed)  # type: ignore[attr-defined]
        buttons.add_widget(self.cancel_button)

        layout.add_widget(buttons)
        self.content = layout

    def _initialize_from_default_url(self) -> None:
        matched_preset = None
        for name, preset_url in BACKEND_PRESETS.items():
            if preset_url.rstrip("/") == self._default_url:
                matched_preset = name
                break

        if matched_preset:
            self.preset_spinner.text = matched_preset
            self.url_input.text = BACKEND_PRESETS[matched_preset]
            self.url_input.readonly = True
        else:
            self.preset_spinner.text = "Custom"
            self.url_input.text = self._default_url
            self.url_input.readonly = False

        self._schedule_auto_health_check(0.1)

    def _on_preset_changed(self, _instance, selected: str) -> None:
        if selected == "Custom":
            self.url_input.readonly = False
            if not self.url_input.text:
                self.url_input.text = self._default_url
            self._update_status(
                "Custom URL selected. Connection will be checked automatically.",
                (0.7, 0.7, 0.7, 1),
            )
            self._schedule_auto_health_check()
            return

        self.url_input.readonly = True
        self.url_input.text = BACKEND_PRESETS[selected]
        self._last_tested_url = None
        self._update_status(
            "Preset selected. Connection will be checked automatically.",
            (0.7, 0.7, 0.7, 1),
        )
        self._schedule_auto_health_check()

    def _on_url_changed(self, _instance, _text: str) -> None:
        self._last_tested_url = None
        if self._auto_test_event is not None:
            self._auto_test_event.cancel()
            self._auto_test_event = None

        url = self._get_selected_url()
        if not url:
            self._update_status(
                "Enter a backend URL.",
                (0.7, 0.7, 0.7, 1),
            )
            return

        if not is_valid_backend_url(url):
            self._update_status(
                "Invalid URL. Use http:// or https://",
                (1, 0.3, 0.3, 1),
            )
            return

        self._update_status(
            "Connection will be checked automatically. You can also test manually.",
            (0.7, 0.7, 0.7, 1),
        )
        self._schedule_auto_health_check()

    def _get_selected_url(self) -> str:
        return self.url_input.text.strip().rstrip("/")

    def _schedule_auto_health_check(self, delay: float = 0.5) -> None:
        if self._auto_test_event is not None:
            self._auto_test_event.cancel()

        self._auto_test_event = Clock.schedule_once(
            lambda _dt: self._start_health_check(manual=False), delay
        )

    def _set_busy(self, busy: bool) -> None:
        self.test_button.disabled = busy
        self.continue_button.disabled = busy
        self.cancel_button.disabled = busy
        self.preset_spinner.disabled = busy
        if self.preset_spinner.text == "Custom":
            self.url_input.readonly = busy

    def _on_test_pressed(self, _instance) -> None:
        self._start_health_check(manual=True)

    def _start_health_check(self, manual: bool) -> None:
        url = self._get_selected_url()
        if not is_valid_backend_url(url):
            if manual:
                self._update_status(
                    "Invalid URL. Use http:// or https://", (1, 0.3, 0.3, 1)
                )
            return

        self._health_check_request_id += 1
        request_id = self._health_check_request_id

        if manual:
            self._set_busy(True)
            self._update_status("Testing backend health...", (0.7, 0.7, 0.7, 1))
        else:
            self._update_status("Checking backend status...", (0.7, 0.7, 0.7, 1))

        def worker() -> None:
            try:
                health = BackendClient(url).health_check()
                if request_id != self._health_check_request_id:
                    return
                if health.get("status") == "healthy":
                    self._last_tested_url = url
                    success_text = (
                        "Connection successful."
                        if manual
                        else "Backend reachable. You can continue or connect now."
                    )
                    self._update_status(success_text, (0.3, 1, 0.3, 1))
                else:
                    error = health.get("error", "Unknown backend health error")
                    failure_text = (
                        f"Backend unhealthy: {error}"
                        if manual
                        else f"Backend unavailable right now: {error}"
                    )
                    self._update_status(failure_text, (1, 0.3, 0.3, 1))
            except Exception as exc:  # pragma: no cover - network path
                if request_id != self._health_check_request_id:
                    return
                failure_text = (
                    f"Connection failed: {exc}"
                    if manual
                    else "Backend unavailable right now. You can continue and retry on login."
                )
                self._update_status(failure_text, (1, 0.3, 0.3, 1))
            finally:
                if manual and request_id == self._health_check_request_id:
                    Clock.schedule_once(lambda _dt: self._set_busy(False), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_continue_pressed(self, _instance) -> None:
        url = self._get_selected_url()
        if not is_valid_backend_url(url):
            self._update_status(
                "Invalid URL. Use http:// or https://", (1, 0.3, 0.3, 1)
            )
            return

        self.dismiss()
        self._on_apply(url)

    def _on_cancel_pressed(self, _instance) -> None:
        self.dismiss()
        if self._on_cancel:
            self._on_cancel()

    @mainthread
    def _update_status(self, text: str, color: tuple[float, float, float, float]) -> None:
        self.status_label.text = text
        self.status_label.color = color
