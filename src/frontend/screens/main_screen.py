"""Main application screen (backend-mode-only) — no v2 standalone dependencies."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen

from ...shared.logging_config import logger
from . import main_screen_cache, main_screen_error_popup, main_screen_logout
from .main_screen_export import MainScreenExportOrchestrator
from .main_screen_filenames import (
    generate_default_filename,
    get_file_extension,
    increment_filename_suffix,
    sanitize_export_filename_component,
    selected_export_format,
)
from .main_screen_scheduler import KivyScheduler
from .main_screen_search_sort_ui import SearchSortUIHandler
from .main_screen_selection import SelectionManager
from .main_screen_ui import MainScreenUIBuilder

# Import backend cache explorer adapter if available.
# Prefer the runtime path used by the packaged launcher (`src.frontend...`),
# then fall back to `frontend...` for editable/local package layouts.
try:
    from src.frontend.screens.cache_explorer_adapter import create_cache_explorer

    BACKEND_CACHE_EXPLORER_AVAILABLE = True
except ImportError:
    try:
        from frontend.screens.cache_explorer_adapter import create_cache_explorer

        BACKEND_CACHE_EXPLORER_AVAILABLE = True
    except ImportError:
        BACKEND_CACHE_EXPLORER_AVAILABLE = False


class MainScreen(Screen):
    """Main screen with playlist selection and export (backend mode only)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend_adapter = None
        self.playlists: List[dict] = []
        self.playlist_widgets: List = []
        self._backend_error_phase = "idle"
        self._backend_error_step = ""
        self.trace_mode_enabled = os.getenv("SPOTIBYE_TRACE_MODE", "0").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._current_trace_id: str = ""
        self._backend_resume_popup: Optional[Popup] = None

        self.scheduler = KivyScheduler()
        self.export_orchestrator = MainScreenExportOrchestrator(self, self.scheduler)
        self.selection_manager = SelectionManager(self)
        self.search_sort = SearchSortUIHandler(self)

        self.build_ui()

    # ------------------------------------------------------------------
    # Selection facades
    # ------------------------------------------------------------------

    @property
    def selected_playlist_ids(self) -> Set[str]:
        return self.selection_manager.selected_playlist_ids

    def toggle_select_all(self, instance) -> None:
        self.selection_manager.toggle_select_all(instance)

    def update_selection_counter(self) -> None:
        self.selection_manager.update_selection_counter()

    def _on_playlist_checkbox_changed(self, playlist_id: str, is_active: bool) -> None:
        self.selection_manager._on_playlist_checkbox_changed(playlist_id, is_active)

    def deselect_all(self, *_args) -> None:
        self.selection_manager.deselect_all(*_args)

    # ------------------------------------------------------------------
    # Search / sort facades
    # ------------------------------------------------------------------

    @property
    def search_query(self) -> str:
        return self.search_sort.search_query

    @search_query.setter
    def search_query(self, value: str) -> None:
        self.search_sort.search_query = value

    @property
    def filtered_playlists(self) -> List[dict]:
        return self.search_sort.filtered_playlists

    @filtered_playlists.setter
    def filtered_playlists(self, value: List[dict]) -> None:
        self.search_sort.filtered_playlists = value

    @property
    def current_sort_key(self) -> str:
        return self.search_sort.current_sort_key

    @current_sort_key.setter
    def current_sort_key(self, value: str) -> None:
        self.search_sort.current_sort_key = value

    @property
    def current_sort_reverse(self) -> bool:
        return self.search_sort.current_sort_reverse

    @current_sort_reverse.setter
    def current_sort_reverse(self, value: bool) -> None:
        self.search_sort.current_sort_reverse = value

    def configure_dropdown(self, spinner) -> None:
        self.search_sort.configure_dropdown(spinner)

    def on_sort_change(self, spinner, text) -> None:
        self.search_sort.on_sort_change(spinner, text)

    def update_sort_controls_visibility(self) -> None:
        self.search_sort.update_sort_controls_visibility()

    def update_sort_direction_button(self) -> None:
        self.search_sort.update_sort_direction_button()

    def toggle_sort_direction(self, *_args) -> None:
        self.search_sort.toggle_sort_direction(*_args)

    def schedule_sort_refresh(self) -> None:
        self.search_sort.schedule_sort_refresh()

    def reset_sort_ui(self) -> None:
        self.search_sort.reset_sort_ui()

    def on_search_text(self, instance, value) -> None:
        self.search_sort.on_search_text(instance, value)

    def _perform_search(self, search_text: str) -> None:
        self.search_sort._perform_search(search_text)

    def clear_search(self, instance) -> None:
        self.search_sort.clear_search(instance)

    def _get_filtered_playlists(self) -> List[dict]:
        return self.search_sort.get_filtered_playlists()

    def _sort_playlists(self, playlists: List[dict]) -> List[dict]:
        return self.search_sort.sort_playlist_list(playlists)

    def _perform_sort(self) -> None:
        """Perform the actual sorting operation.

        Subclasses must override this to use their specific widget type.
        """
        raise NotImplementedError("_perform_sort must be implemented by subclass")

    # ------------------------------------------------------------------
    # Backend / lifecycle
    # ------------------------------------------------------------------

    def _set_backend_error_context(self, phase: str, step: str = "") -> None:
        """Track current backend operation phase so error popups include precise context."""
        self._backend_error_phase = phase
        self._backend_error_step = step

    def initialize_with_backend(self, backend_adapter) -> None:
        """Enable backend-integrated mode for playlist loading/export actions."""
        self.backend_adapter = backend_adapter
        if self.backend_adapter:
            self.backend_adapter.set_callbacks(
                playlists_loaded=self._on_backend_playlists_loaded,
                error=self._on_backend_error,
                progress=self._on_backend_progress,
            )

    @property
    def backend_mode_enabled(self) -> bool:
        """Return True when screen should use backend adapter APIs."""
        return self.backend_adapter is not None

    def build_ui(self) -> None:
        MainScreenUIBuilder(self).build_ui()

    def on_format_change(self, spinner, text):
        """Update filename extension when format changes."""
        current_filename = self.filename_input.text or ""
        if current_filename:
            base_name = os.path.splitext(current_filename)[0]
            extension = self._get_file_extension(text.lower())
            self.filename_input.text = f"{base_name}{extension}"
        else:
            self.filename_input.text = self._generate_default_filename(text.lower())

    def _get_file_extension(self, format_type: str) -> str:
        """Get file extension for export format."""
        return get_file_extension(format_type)

    def _selected_export_format(self) -> str:
        """Return the user-selected export format ('xlsx', 'csv', or 'json')."""
        spinner = getattr(self, "format_spinner", None)
        text = (spinner.text if spinner else "") or "xlsx"
        return selected_export_format(text)

    def on_enter(self):
        app = App.get_running_app()
        username = getattr(app, "username", "Unknown User")
        self.username_label.text = f"Logged in as: {username}"
        Clock.schedule_once(lambda _: self.update_sort_controls_visibility(), 0.2)

        if hasattr(self, "filename_input"):
            current_filename = self.filename_input.text or ""
            if "_user_" in current_filename or "_None_" in current_filename:
                self.filename_input.text = self._generate_default_filename()

        self.load_playlists_with_cache()

    def load_playlists_with_cache(self, *_args) -> None:
        self.reset_sort_ui()
        self.status_label.text = "Loading playlists..."
        self.playlist_layout.clear_widgets()
        self.playlist_widgets = []
        self.update_selection_counter()

        if self.backend_mode_enabled:
            self.filtered_playlists = []
            self.backend_adapter.load_playlists(force_refresh=False)
            return

        self.status_label.text = "Backend adapter not initialized"

    @mainthread
    def _on_backend_playlists_loaded(self, playlists: List[Dict[str, Any]]) -> None:
        """Callback for playlist data loaded via backend adapter."""
        self.playlists = playlists or []
        self.display_playlists_with_cache()

    @mainthread
    def _on_backend_error(self, error_msg: str) -> None:
        """Callback for backend loading errors."""
        logger.error("Backend request failed: %s", error_msg)
        message = str(error_msg or "")
        self.status_label.text = f"Backend error: {message}"
        self._show_backend_error_popup(message)

        lowered = message.lower()
        auth_related = (
            "session expired" in lowered
            or "session expired or invalid" in lowered
            or "token expired" in lowered
            or "unauthorized" in lowered
            or "http 401" in lowered
        )

        if auth_related:
            self.status_label.text = "Session expired. Please login again."
            app = App.get_running_app()
            if app and hasattr(app, "prompt_reauthentication"):
                Clock.schedule_once(
                    lambda _: app.prompt_reauthentication(
                        "Your Spotify session expired. Log out and log in again."
                    ),
                    0.2,
                )
            elif app and hasattr(app, "logout"):
                Clock.schedule_once(lambda _: app.logout(), 0.2)
            elif app and hasattr(app, "switch_to_login"):
                Clock.schedule_once(lambda _: app.switch_to_login(), 0.2)

    def _show_backend_error_popup(self, message: str) -> None:
        main_screen_error_popup.show_backend_error_popup(self, message)

    def _get_recoverable_backend_export_context(self) -> Optional[Dict[str, Any]]:
        return main_screen_error_popup.get_recoverable_backend_export_context(self)

    @mainthread
    def _on_backend_progress(self, status: str) -> None:
        """Callback for backend progress updates."""
        if status:
            trace = self._current_trace_id or "none"
            logger.info("[backend-progress][trace=%s] %s", trace, status)
            self.status_label.text = status

    def load_playlists_worker_with_cache(self) -> None:
        """Worker for loading playlists. In backend mode, delegates to backend adapter."""
        if self.backend_mode_enabled:
            self.backend_adapter.load_playlists(force_refresh=False)
            return

        Clock.schedule_once(
            lambda _: setattr(
                self.status_label, "text", "Backend adapter not initialized"
            ),
            0,
        )

    def display_playlists_with_cache(self) -> None:
        """Display playlists in the UI.

        Subclasses must override this to create the appropriate widget type.
        """
        raise NotImplementedError(
            "display_playlists_with_cache must be implemented by subclass"
        )

    def _make_playlist_widget(self, playlist: dict):
        """Create a playlist widget for a playlist row."""
        raise NotImplementedError("_make_playlist_widget must be implemented by subclass")

    def update_status_with_cache_info(self) -> None:
        """Update the status bar with current playlist information.

        Subclasses may override to add backend/cache-specific details.
        """
        try:
            total_playlists = len(self.playlists)

            if self.search_query:
                shown_playlists = len(self.filtered_playlists)
                if shown_playlists == 0:
                    self.status_label.text = f'No matches for "{self.search_query}"'
                else:
                    self.status_label.text = (
                        f"Showing {shown_playlists} of {total_playlists}"
                    )
            else:
                self.status_label.text = f"Loaded {total_playlists} playlists"

        except Exception as exc:
            logger.warning("Error updating status: %s", exc, exc_info=True)
            self.status_label.text = "Error updating status"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def start_export(self, *_args) -> None:
        try:
            if not self.backend_mode_enabled:
                self.status_label.text = "Backend adapter not initialized"
                return

            selected = [
                p for p in self.playlists if p.get("id") in self.selected_playlist_ids
            ]
            if not selected:
                Popup(
                    title="No Selection",
                    content=Label(
                        text="Please select at least one playlist to export."
                    ),
                    size_hint=(0.6, 0.4),
                ).open()
                return

            self._start_backend_export(selected)
        except Exception as exc:
            logger.error("Error starting export: %s", exc)
            self.status_label.text = f"Export error: {exc}"
            Clock.schedule_once(lambda _: self._refresh_filename_after_export(), 0)

    def _start_backend_export(self, playlists) -> None:
        """Start export flow using backend endpoints (no direct Spotify API calls)."""
        self.export_orchestrator._start_backend_export(playlists)

    def _show_backend_overwrite_confirmation(
        self, playlists, output_path, filename
    ) -> None:
        self.export_orchestrator._show_backend_overwrite_confirmation(
            playlists, output_path, filename
        )

    def _handle_backend_overwrite_confirmed(
        self, popup, playlists, output_path
    ) -> None:
        self.export_orchestrator._handle_backend_overwrite_confirmed(
            popup, playlists, output_path
        )

    def begin_backend_export(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Begin backend export worker for one or more playlists."""
        self.export_orchestrator.begin_backend_export(
            playlists, output_path, resume_saved_job
        )

    def _sanitize_export_filename_component(self, value: str) -> str:
        """Sanitize playlist/file name component for cross-platform safe filenames."""
        return sanitize_export_filename_component(value)

    def _build_backend_output_path(
        self, base_output_path: str, multiple: bool
    ) -> str:
        """Build output file path for backend export."""
        return self.export_orchestrator._build_backend_output_path(
            base_output_path, multiple
        )

    def backend_export_worker(
        self, playlists, output_path, resume_saved_job: bool = False
    ) -> None:
        """Worker that generates and downloads export(s) from backend API."""
        self.export_orchestrator.backend_export_worker(
            playlists, output_path, resume_saved_job
        )

    def _backend_export_fallback_sequential(
        self, playlists: List[Dict[str, Any]], base_output_path: str
    ) -> Dict[str, Any]:
        """Fallback export strategy: generate one backend export per playlist."""
        return self.export_orchestrator._backend_export_fallback_sequential(
            playlists, base_output_path
        )

    def cancel_export(self, *_args) -> None:
        self.export_orchestrator.cancel_export(*_args)

    def cleanup_after_export(self) -> None:
        self.export_orchestrator.cleanup_after_export()

    def handle_export_cancelled(self) -> None:
        """Handle the UI updates when an export is cancelled."""
        self.export_orchestrator.handle_export_cancelled()

    def logout(self, *_args) -> None:
        main_screen_logout.logout(self, *_args)

    def _show_logout_confirmation(self, selected_count: int) -> None:
        main_screen_logout.show_logout_confirmation(self, selected_count)

    def _handle_logout_confirmed(self, popup) -> None:
        main_screen_logout.handle_logout_confirmed(self, popup)

    def _perform_logout(self) -> None:
        main_screen_logout.perform_logout()

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def show_clear_cache_confirmation(self, *_args) -> None:
        main_screen_cache.show_clear_cache_confirmation(self, *_args)

    def clear_all_cache(self, popup) -> None:
        main_screen_cache.clear_all_cache(self, popup)

    def open_cache_explorer(self, *_args) -> None:
        main_screen_cache.open_cache_explorer(
            self, BACKEND_CACHE_EXPLORER_AVAILABLE, create_cache_explorer, *_args
        )

    # ------------------------------------------------------------------
    # Filename helpers
    # ------------------------------------------------------------------

    def _generate_default_filename(self, format_type: str = "xlsx") -> str:
        app = App.get_running_app()
        username = getattr(app, "username", None)
        return generate_default_filename(username, format_type)

    def _refresh_filename_after_export(self):
        if hasattr(self, "filename_input"):
            try:
                current_filename = self.filename_input.text or ""
                new_default = self._generate_default_filename()

                current_base = os.path.splitext(current_filename)[0]
                new_base = os.path.splitext(new_default)[0]

                if current_base == new_base:
                    self.filename_input.text = self._increment_filename_suffix(
                        new_default
                    )
                else:
                    self.filename_input.text = new_default
            except Exception:
                pass

    def _increment_filename_suffix(self, filename: str) -> str:
        """Increment filename suffix from _2 to _5 as needed."""
        return increment_filename_suffix(filename)
