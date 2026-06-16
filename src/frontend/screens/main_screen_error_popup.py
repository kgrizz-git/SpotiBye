"""Backend error details popup and resume logic for MainScreen."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput


def show_backend_error_popup(screen, message: str) -> None:
    """Show backend error details with one-click copy for diagnostics sharing."""
    if not message:
        return

    phase = screen._backend_error_phase or "unknown"
    step = screen._backend_error_step or "n/a"
    trace_id = screen._current_trace_id or "n/a"
    details = (
        f"Time: {datetime.now().isoformat()}\n"
        f"Screen: MainScreen\n"
        f"TraceId: {trace_id}\n"
        f"Phase: {phase}\n"
        f"Step: {step}\n"
        f"Error: {message}"
    )
    resumable_export = get_recoverable_backend_export_context(screen)

    def _open_popup(_dt):
        if screen._backend_resume_popup:
            screen._backend_resume_popup.dismiss()

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

        if resumable_export:
            resume_summary = Label(
                text=resumable_export["summary"],
                size_hint_y=None,
                height=dp(72),
                halign="center",
                valign="middle",
                text_size=(dp(420), None),
            )
            content.add_widget(resume_summary)

        details_input = TextInput(
            text=details,
            readonly=True,
            multiline=True,
            size_hint_y=1,
            font_size=dp(13),
            background_color=(0.15, 0.15, 0.15, 1),
            foreground_color=(1, 1, 1, 1),
        )
        content.add_widget(details_input)

        if resumable_export:
            action_row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(42),
                spacing=dp(8),
            )
            resume_btn = Button(
                text="Resume Export", background_color=[0.2, 0.6, 0.35, 1]
            )
            discard_btn = Button(
                text="Discard Resume", background_color=[0.55, 0.35, 0.2, 1]
            )
            action_row.add_widget(resume_btn)
            action_row.add_widget(discard_btn)
            content.add_widget(action_row)

        button_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8)
        )
        copy_btn = Button(
            text="Copy Error Details", background_color=[0.2, 0.55, 0.85, 1]
        )
        close_btn = Button(text="Close", background_color=[0.45, 0.45, 0.45, 1])
        button_row.add_widget(copy_btn)
        button_row.add_widget(close_btn)
        content.add_widget(button_row)

        popup = Popup(
            title="Backend Error Details",
            content=content,
            size_hint=(0.86, 0.58),
            auto_dismiss=True,
        )
        screen._backend_resume_popup = popup

        def _copy_details(_instance):
            Clipboard.copy(details)
            screen.status_label.text = "Backend error details copied to clipboard"

        def _clear_resume_job(_instance):
            if screen.backend_adapter:
                screen.backend_adapter.clear_active_export_job()
            screen.status_label.text = "Discarded resumable export state"
            popup.dismiss()

        def _resume_export(_instance):
            popup.dismiss()
            screen.begin_backend_export(
                resumable_export["playlists"],
                resumable_export["output_path"],
                resume_saved_job=True,
            )

        copy_btn.bind(on_press=_copy_details)
        close_btn.bind(on_press=popup.dismiss)
        if resumable_export:
            resume_btn.bind(on_press=_resume_export)
            discard_btn.bind(on_press=_clear_resume_job)
        popup.bind(
            on_dismiss=lambda *_args: setattr(screen, "_backend_resume_popup", None)
        )
        popup.open()

    Clock.schedule_once(_open_popup, 0)


def get_recoverable_backend_export_context(screen) -> Optional[Dict[str, Any]]:
    """Return cached resumable export details when the current failure can be resumed."""
    if not screen.backend_adapter:
        return None

    if screen._backend_error_phase not in {
        "chunked-combined",
        "sequential-fallback",
        "failed",
    }:
        return None

    cached_job = screen.backend_adapter.get_active_export_job()
    if not isinstance(cached_job, dict):
        return None

    playlist_ids = cached_job.get("playlist_ids") or []
    playlist_names = cached_job.get("playlist_names") or []
    output_path = str(cached_job.get("output_path") or "")
    job_id = str(cached_job.get("job_id") or "")
    current_cursor = str(cached_job.get("current_cursor") or "")
    current_resume_token = str(cached_job.get("current_resume_token") or "")

    if (
        not isinstance(playlist_ids, list)
        or not playlist_ids
        or not output_path
        or not job_id
    ):
        return None

    if not current_cursor or not current_resume_token:
        return None

    playlists = []
    for index, playlist_id in enumerate(playlist_ids):
        playlist_name = (
            playlist_names[index]
            if isinstance(playlist_names, list) and index < len(playlist_names)
            else playlist_id
        )
        playlists.append({"id": playlist_id, "name": playlist_name})

    processed = int(cached_job.get("processed_count", 0) or 0)
    total = int(cached_job.get("playlist_count", len(playlists)) or len(playlists))
    phase = str(cached_job.get("phase") or "collect")
    summary = (
        f"A resumable export is still available.\n"
        f"Progress: {processed}/{total} playlists\n"
        f"Phase: {phase}\n"
        f"Output: {os.path.basename(output_path)}"
    )

    return {
        "playlists": playlists,
        "output_path": output_path,
        "summary": summary,
    }
