"""Backend export orchestration for MainScreen."""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from ...shared.logging_config import logger
from ..state import (
    clear_current_export_job,
    get_current_export_job,
    mark_current_export_cancelled,
    set_current_export_job,
)


class MainScreenExportOrchestrator:
    """Orchestrates the export flow, including threading and UI state updates."""

    def __init__(self, screen, scheduler) -> None:
        self.screen = screen
        self.scheduler = scheduler

    def _get_file_extension(self, format_type: str) -> str:
        return self.screen._get_file_extension(format_type)

    def _selected_export_format(self) -> str:
        return self.screen._selected_export_format()

    def _generate_default_filename(self) -> str:
        return self.screen._generate_default_filename()

    def _sanitize_export_filename_component(self, value: str) -> str:
        return self.screen._sanitize_export_filename_component(value)

    def _refresh_filename_after_export(self) -> None:
        self.scheduler.call_soon(lambda: self.screen._refresh_filename_after_export())

    def _set_backend_error_context(self, phase: str, step: str = "") -> None:
        self.screen._set_backend_error_context(phase, step)

    def _show_backend_error_popup(self, message: str) -> None:
        self.scheduler.call_soon(lambda: self.screen._show_backend_error_popup(message))

    def _build_backend_output_path(
        self, base_output_path: str, multiple: bool
    ) -> str:
        """Build output file path for backend export."""
        if not multiple:
            return base_output_path

        base_dir = os.path.dirname(base_output_path)
        base_name = os.path.splitext(os.path.basename(base_output_path))[0]
        extension = self._get_file_extension(self._selected_export_format())
        return os.path.join(base_dir, f"{base_name}{extension}")

    def _start_backend_export(self, playlists) -> None:
        """Start export flow using backend endpoints (no direct Spotify API calls)."""
        if not self.screen.backend_adapter:
            self.screen.status_label.text = "Backend export unavailable"
            return

        filename = (
            (self.screen.filename_input.text or "").strip()
            if hasattr(self.screen, "filename_input")
            else ""
        )
        if not filename:
            filename = os.path.splitext(self._generate_default_filename())[0]

        extension = self._get_file_extension(self._selected_export_format())
        if not filename.lower().endswith(extension):
            filename = f"{os.path.splitext(filename)[0]}{extension}"

        from ..config.backend_config import EXPORT_DIR as SAVE_DIR
        output_path = os.path.join(SAVE_DIR, filename)

        if len(playlists) == 1 and os.path.exists(output_path):
            self._show_backend_overwrite_confirmation(playlists, output_path, filename)
        else:
            self.begin_backend_export(playlists, output_path)

    def _show_backend_overwrite_confirmation(
        self, playlists, output_path, filename
    ) -> None:
        popup_content = BoxLayout(
            orientation="vertical", spacing=dp(10), padding=dp(20)
        )
        popup_content.add_widget(Widget(size_hint_y=0.3))
        popup_content.add_widget(
            Label(
                text=f'The file "{filename}" already exists.\n\nDo you want to overwrite it?',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(80),
                halign="center",
                valign="center",
                text_size=(dp(400), dp(80)),
            )
        )
        popup_content.add_widget(Widget(size_hint_y=0.4))
        buttons = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(15)
        )
        cancel_btn = Button(
            text="Cancel",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.6, 0.6, 0.6, 1],
        )
        overwrite_btn = Button(
            text="Overwrite",
            size_hint_x=0.5,
            font_size=dp(16),
            background_color=[0.8, 0.3, 0.3, 1],
        )
        buttons.add_widget(cancel_btn)
        buttons.add_widget(overwrite_btn)
        popup_content.add_widget(buttons)
        popup = Popup(
            title="File Already Exists",
            content=popup_content,
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
        )
        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        overwrite_btn.bind(
            on_press=lambda *_: self._handle_backend_overwrite_confirmed(
                popup, playlists, output_path
            )
        )
        popup.open()

    def _handle_backend_overwrite_confirmed(
        self, popup, playlists, output_path
    ) -> None:
        popup.dismiss()
        self.begin_backend_export(playlists, output_path)

    def begin_backend_export(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Begin backend export worker for one or more playlists."""
        try:
            if self.screen.trace_mode_enabled:
                self.screen._current_trace_id = uuid.uuid4().hex[:12]
            else:
                self.screen._current_trace_id = ""

            if self.screen.backend_adapter:
                self.screen.backend_adapter.set_trace_id(self.screen._current_trace_id)

            self.screen.export_btn.disabled = True
            self.screen.cancel_btn.opacity = 1
            self.screen.cancel_btn.disabled = True
            total = len(playlists) if isinstance(playlists, list) else 1
            filename = os.path.basename(output_path)
            self.screen.status_label.text = (
                f"Exporting {total} playlist(s) via backend to: {filename}"
            )
            self.screen.progress_bar.value = 5

            # Initialize global job state for cancellation tracking
            job_id = self.screen._current_trace_id or uuid.uuid4().hex[:12]
            p_list = playlists if isinstance(playlists, list) else [playlists]
            playlist_ids = [p.get("id", "") for p in p_list if isinstance(p, dict)]
            set_current_export_job(
                job_id=job_id,
                playlist_ids=playlist_ids,
                export_format=self._selected_export_format(),
                output_path=output_path,
            )

            threading.Thread(
                target=self.backend_export_worker,
                args=(playlists, output_path, resume_saved_job),
                daemon=True,
            ).start()
        except Exception as exc:
            logger.error("Error beginning backend export: %s", exc)
            self.screen.export_btn.disabled = False
            self.screen.cancel_btn.opacity = 0
            self.screen.cancel_btn.disabled = True
            self.screen.status_label.text = f"Export error: {exc}"
            self._refresh_filename_after_export()

    def _check_cancelled(self) -> bool:
        """Check if the current job is cancelled and handle UI if so.

        Returns:
            True if cancelled, False otherwise.
        """
        job = get_current_export_job()
        if job and job.get("cancelled"):
            self.scheduler.call_soon(lambda: self.handle_export_cancelled())
            return True
        return False

    def backend_export_worker(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Worker that generates and downloads export(s) from backend API."""
        screen = self.screen
        adapter = screen.backend_adapter
        try:
            if not adapter:
                self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", "Backend export unavailable"))
                self.scheduler.call_soon(lambda: self.cleanup_after_export())
                return

            selected_playlists = (
                playlists if isinstance(playlists, list) else [playlists]
            )
            valid_playlists = [
                p for p in selected_playlists if isinstance(p, dict) and p.get("id")
            ]
            if not valid_playlists:
                self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", "No valid playlists selected for export"))
                self.scheduler.call_soon(lambda: self.cleanup_after_export())
                self._refresh_filename_after_export()
                return

            total = len(valid_playlists)
            playlist_ids = [p.get("id") for p in valid_playlists if p.get("id")]
            target_path = self._build_backend_output_path(
                output_path, total > 1
            )
            resume_context = {
                "allow_resume": resume_saved_job,
                "output_path": target_path,
                "playlist_names": [p.get("name", "") for p in valid_playlists],
            }
            self._set_backend_error_context(
                "chunked-combined", f"prepare ({total} playlists)"
            )

            self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Generating combined backend export for {total} playlist(s) (chunked)..."))
            self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 35))

            # Use chunked processing to avoid per-invocation subrequest caps on Cloudflare free plans.
            self._set_backend_error_context("chunked-combined", "generate")
            if self._check_cancelled():
                return

            export_info = adapter.generate_batch_export_chunked(
                playlist_ids,
                self._selected_export_format(),
                chunk_size=1,
                report_errors=False,
                resume_context=resume_context,
            )
            if not export_info:
                # Fallback: combined export can exceed Worker subrequest limits for larger selections.
                # Degrade gracefully to sequential per-playlist exports so the user still gets files.
                self._set_backend_error_context("sequential-fallback", "start")
                if self._check_cancelled():
                    return

                fallback_result = self._backend_export_fallback_sequential(
                    valid_playlists, output_path
                )
                if fallback_result.get("cancelled"):
                    return

                if (
                    fallback_result.get("success_count", 0) > 0
                    and fallback_result.get("failed_count", 0) == 0
                ):
                    adapter.clear_active_export_job()
                    self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Export complete ({total} playlist(s), sequential fallback)"))
                    self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 100))
                elif fallback_result.get("success_count", 0) > 0:
                    s = fallback_result.get("success_count", 0)
                    f = fallback_result.get("failed_count", 0)
                    self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Partial export complete ({s} saved, {f} failed)"))
                    self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 100))
                    self._show_backend_error_popup(
                        f"Sequential fallback partially succeeded. Saved {s}, failed {f}. Failed IDs: {', '.join(fallback_result.get('failed_playlist_ids', []))}"
                    )
                else:
                    self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", "Backend combined export generation failed"))
                    self._show_backend_error_popup(
                        "Combined export generation failed after retries and sequential fallback"
                    )
                self.scheduler.call_soon(lambda: self.cleanup_after_export())
                self._refresh_filename_after_export()
                return

            export_id = (
                export_info.get("job_id", "") if isinstance(export_info, dict) else ""
            )
            total_tracks = (
                int(export_info.get("track_count", 0))
                if isinstance(export_info, dict)
                else 0
            )
            if total_tracks >= 2400:
                self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Large export ({total_tracks} tracks): reliability mode active; combined file prioritized over heavy styling."))

            self._set_backend_error_context(
                "chunked-combined", f'download job={export_id or "unknown"}'
            )

            self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", "Downloading combined backend export..."))
            self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 80))

            if self._check_cancelled():
                return

            success = adapter.download_batch_export(
                export_id, target_path, report_errors=False
            )
            if not success:
                # Recovery pass: try to resume/reconcile combined job state and retry combined download once.
                self._set_backend_error_context(
                    "chunked-combined", "recover-and-redownload"
                )
                self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", "Combined download failed; retrying combined export recovery..."))
                
                if self._check_cancelled():
                    return

                recovered_info = adapter.generate_batch_export_chunked(
                    playlist_ids,
                    self._selected_export_format(),
                    chunk_size=1,
                    max_steps=240,
                    report_errors=False,
                    resume_context={
                        "allow_resume": True,
                        "output_path": target_path,
                        "playlist_names": [p.get("name", "") for p in valid_playlists],
                    },
                )
                recovered_export_id = (
                    recovered_info.get("job_id", "")
                    if isinstance(recovered_info, dict)
                    else ""
                ) or export_id

                if recovered_export_id:
                    if self._check_cancelled():
                        return
                    success = adapter.download_batch_export(
                        recovered_export_id, target_path, report_errors=False
                    )

            if not success:
                self._set_backend_error_context(
                    "sequential-fallback", "start-after-combined-failure"
                )
                # Combined path failed after retries/recovery; now degrade to sequential.
                for _ in range(12):
                    if self._check_cancelled():
                        return
                    time.sleep(0.5)

                if self._check_cancelled():
                    return

                fallback_result = self._backend_export_fallback_sequential(
                    valid_playlists, output_path
                )
                if fallback_result.get("cancelled"):
                    return

                if (
                    fallback_result.get("success_count", 0) > 0
                    and fallback_result.get("failed_count", 0) == 0
                ):
                    adapter.clear_active_export_job(export_id or None)
                    self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Export complete ({total} playlist(s), sequential fallback)"))
                    self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 100))
                elif fallback_result.get("success_count", 0) > 0:
                    s = fallback_result.get("success_count", 0)
                    f = fallback_result.get("failed_count", 0)
                    self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Partial export complete ({s} saved, {f} failed)"))
                    self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 100))
                    self._show_backend_error_popup(
                        f"Combined download failed; sequential fallback partially succeeded. Saved {s}, failed {f}. Failed IDs: {', '.join(fallback_result.get('failed_playlist_ids', []))}"
                    )
                else:
                    self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", "Backend combined export download failed"))
                    self._show_backend_error_popup(
                        "Combined export download failed after retries and sequential fallback"
                    )
                self.scheduler.call_soon(lambda: self.cleanup_after_export())
                self._refresh_filename_after_export()
                return

            self.scheduler.call_soon(lambda: setattr(screen.progress_bar, "value", 100))
            self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Export complete ({total} playlist(s))"))
            self._set_backend_error_context(
                "completed", f"combined success ({total} playlists)"
            )
            self.scheduler.call_soon(lambda: self.cleanup_after_export())
            self._refresh_filename_after_export()

        except Exception as exc:
            logger.error("Backend export failed: %s", exc)
            self.scheduler.call_soon(lambda: setattr(screen.status_label, "text", f"Backend export failed: {exc}"))
            self._set_backend_error_context("failed", "backend-export-worker")
            self._show_backend_error_popup(f"Backend export failed: {str(exc)}")
            self.scheduler.call_soon(lambda: self.cleanup_after_export())
            self._refresh_filename_after_export()

    def _backend_export_fallback_sequential(
        self, playlists: List[Dict[str, Any]], base_output_path: str
    ) -> Dict[str, Any]:
        """Fallback export strategy: generate one backend export per playlist."""
        screen = self.screen
        adapter = screen.backend_adapter
        if not adapter:
            return {
                "success_count": 0,
                "failed_count": len(playlists),
                "failed_playlist_ids": [
                    p.get("id", "") for p in playlists if p.get("id")
                ],
            }

        total = len(playlists)
        base_dir = os.path.dirname(base_output_path)
        base_name = os.path.splitext(os.path.basename(base_output_path))[0]
        export_format = self._selected_export_format()
        success_count = 0
        failed_playlist_ids: List[str] = []

        for index, playlist in enumerate(playlists, start=1):
            playlist_id = playlist.get("id")
            if not playlist_id:
                continue

            playlist_name = self._sanitize_export_filename_component(
                playlist.get("name", "playlist")
            )
            safe_id = self._sanitize_export_filename_component(playlist_id)
            extension = self._get_file_extension(export_format)
            target_file = f"{base_name} - {playlist_name} ({safe_id}){extension}"
            target_path = os.path.join(base_dir, target_file)

            self.scheduler.call_soon(lambda i=index, t=total, name=playlist_name: setattr(
                screen.status_label,
                "text",
                f"Fallback [{i}/{t}] Generating export for {name}...",
            ))
            self.scheduler.call_soon(lambda i=index, t=total: setattr(
                screen.progress_bar, "value", int(((i - 1) / t) * 100) + 10
            ))
            self._set_backend_error_context(
                "sequential-fallback",
                f"generate {index}/{total} playlist={playlist_id}",
            )

            if self._check_cancelled():
                return {"success_count": success_count, "failed_count": total - success_count, "cancelled": True}

            export_info = adapter.generate_export(
                playlist_id, export_format, report_errors=False
            )
            if not export_info:
                failed_playlist_ids.append(playlist_id)
                continue

            export_id = (
                export_info.get("job_id", "") if isinstance(export_info, dict) else ""
            )

            self.scheduler.call_soon(lambda i=index, t=total, name=playlist_name: setattr(
                screen.status_label,
                "text",
                f"Fallback [{i}/{t}] Downloading export for {name}...",
            ))
            self.scheduler.call_soon(lambda i=index, t=total: setattr(
                screen.progress_bar, "value", int(((i - 1) / t) * 100) + 60
            ))
            self._set_backend_error_context(
                "sequential-fallback",
                f"download {index}/{total} playlist={playlist_id}",
            )

            if self._check_cancelled():
                return {"success_count": success_count, "failed_count": total - success_count, "cancelled": True}

            success = adapter.download_export(
                playlist_id, target_path
            )
            if not success:
                failed_playlist_ids.append(playlist_id)
                continue

            success_count += 1

            # Pace long sequential runs slightly to reduce backend/upstream burst failures.
            if index < total:
                time.sleep(0.5)

        if success_count > 0 and not failed_playlist_ids:
            self._set_backend_error_context(
                "completed", f"sequential fallback success ({total} playlists)"
            )
        elif success_count > 0:
            self._set_backend_error_context(
                "completed",
                f"sequential fallback partial ({success_count}/{total} playlists)",
            )
        else:
            self._set_backend_error_context(
                "failed", f"sequential fallback failed ({total} playlists)"
            )

        return {
            "success_count": success_count,
            "failed_count": len(failed_playlist_ids),
            "failed_playlist_ids": failed_playlist_ids,
        }

    def cancel_export(self, *_args) -> None:
        """Cancel the active export job."""
        if mark_current_export_cancelled():
            if self.screen.backend_adapter:
                self.screen.backend_adapter.clear_active_export_job()
                self.screen.backend_adapter.set_trace_id(None)
            self.screen.cancel_btn.disabled = True
            self.screen.cancel_btn.text = "Cancelling..."
            self.screen.status_label.text = "Cancelling export..."
            self.scheduler.call_later(3.0, lambda: self.cleanup_after_export())
            self._refresh_filename_after_export()

    def cleanup_after_export(self) -> None:
        """Reset UI state after export complete or failure."""
        self.screen.export_btn.disabled = False
        self.screen.cancel_btn.opacity = 0
        self.screen.cancel_btn.disabled = True
        self.screen.cancel_btn.text = "Cancel Export"
        self.screen.progress_bar.value = 0
        if self.screen.backend_adapter:
            self.screen.backend_adapter.set_trace_id(None)
        clear_current_export_job()

    def handle_export_cancelled(self) -> None:
        """Handle the UI updates when an export is cancelled."""
        self.screen.status_label.text = "Export cancelled"
        self.cleanup_after_export()
        self._refresh_filename_after_export()
