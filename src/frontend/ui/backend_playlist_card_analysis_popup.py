"""Analysis-popup mixin for BackendPlaylistCard.

Defines PlaylistCardAnalysisPopupMixin — playlist analysis window,
analysis-content builder, async worker that calls the backend adapter,
and the @mainthread UI updater. Calls self._get_playlist_image_url()
from PlaylistCardUIMixin and self._open_tracks_window() from
PlaylistCardTracksPopupMixin via self.* — no direct imports needed.

Thread-safety: _load_analysis_worker runs on a daemon thread and passes
content widgets (analysis_container, duration_label) as arguments, never
re-reading them off self.content at runtime. The @mainthread-decorated
_update_analysis_ui marshals all widget mutations back to the Kivy main
thread. The popup content attributes exist before the worker runs because
_show_detailed_playlist_window creates them synchronously before spawning
the thread. The AnalysisTask is constructed on the UI thread in
_start_analysis_worker; dismissing the popup calls task.cancel() from the UI
thread while the worker only reads is_cancelled() (plain bool flag store,
atomic under the GIL). A cancelled worker returns before any UI update;
refresh supersedes the running task (old task cancelled in
_start_analysis_worker), so only the latest worker can reach UI updates.

Depends on kivy, threading, .backend_playlist_card_utils,
..screens.adapter_mixins.analysis.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from kivy.app import App
from kivy.clock import mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from ...shared.logging_config import logger
from ..utils.analysis_task import AnalysisTask
from .backend_playlist_card_analysis_render import render_analysis_popup_content


class PlaylistCardAnalysisPopupMixin:
    """Analysis-popup mixin for BackendPlaylistCard.

    Provides the double-click/long-press analysis popup with genre
    distribution, artist diversity, audio features, and ReccoBeats metadata.
    The "Show Tracks" button calls self._open_tracks_window() on the
    TracksPopupMixin.
    """

    playlist_data: Any = None
    _detailed_popup: Optional[Any] = None
    _analysis_task: Optional[Any] = None

    def show_detailed_playlist_window(self) -> None:
        if self._detailed_popup and self._detailed_popup.parent:
            return

        content = self._build_analysis_popup_content()
        self._detailed_popup = Popup(
            title="Playlist Analysis",
            title_size=dp(16),
            title_color=(1, 1, 1, 1),
            size_hint=(0.75, 0.88),
            background_color=(0.15, 0.15, 0.15, 0.97),
            auto_dismiss=True,
            overlay_color=(0, 0, 0, 0.5),
            content=content,
        )
        self._detailed_popup.bind(on_dismiss=self._cancel_analysis_task)
        self._detailed_popup.open()

        playlist_id = self.playlist_data.get("id")
        if playlist_id:
            self._start_analysis_worker(playlist_id, content)

    def _cancel_analysis_task(self, *_args: Any) -> None:
        """Stop local analysis polling when the popup is dismissed.

        Only stops frontend waiting/polling: the backend Worker job keeps
        running server-side and may later write status and results to KV.
        """
        task = self._analysis_task
        self._analysis_task = None
        if task is not None:
            task.cancel()

    def _build_analysis_popup_content(self) -> BoxLayout:
        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

        # ── main area: left technical panel + right scrollable details ──
        main = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=1)

        # Left panel — cover image + technical details
        left = BoxLayout(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(170),
            spacing=dp(4),
        )

        image_url = self._get_playlist_image_url()
        left.add_widget(
            AsyncImage(
                source=image_url,
                size_hint=(1, None),
                height=dp(155),
                allow_stretch=True,
                keep_ratio=True,
            )
        )

        # Image dimension info from the API payload
        images = self.playlist_data.get("images") or []
        if images:
            first = images[0]
            w = first.get("width") or "?"
            h = first.get("height") or "?"
            available = ", ".join(
                f"{i.get('width', '?')}x{i.get('height', '?')}"
                for i in images
                if i.get("width")
            )
            img_text = f"Image: {w}x{h}"
            if available:
                img_text += f"\n(Available: {available})"
            left.add_widget(
                Label(
                    text=img_text,
                    font_size=dp(9),
                    color=(0.55, 0.55, 0.55, 1),
                    halign="left",
                    valign="top",
                    text_size=(dp(165), None),
                    size_hint_y=None,
                    height=dp(32),
                )
            )

        left.add_widget(
            Label(
                text="Technical Details:",
                font_size=dp(10),
                bold=True,
                color=(0.8, 0.8, 0.8, 1),
                halign="left",
                text_size=(dp(165), None),
                size_hint_y=None,
                height=dp(16),
            )
        )

        owner_id = (self.playlist_data.get("owner") or {}).get("id", "Unknown")
        playlist_id = self.playlist_data.get("id", "Unknown")
        snapshot_id = self.playlist_data.get("snapshot_id", "")
        snap_short = (
            (snapshot_id[:18] + "...") if len(snapshot_id) > 18 else snapshot_id
        )

        for label_text in (
            f"Owner ID:\n{owner_id}",
            f"Playlist ID:\n{playlist_id}",
            f"Version:\n{snap_short}",
        ):
            left.add_widget(
                Label(
                    text=label_text,
                    font_size=dp(9),
                    color=(0.6, 0.6, 0.6, 1),
                    halign="left",
                    valign="top",
                    text_size=(dp(165), None),
                    size_hint_y=None,
                    height=dp(30),
                )
            )

        left.add_widget(Widget())  # vertical spacer
        main.add_widget(left)

        # Right panel — scrollable playlist info + analysis
        scroll = ScrollView(size_hint=(1, 1))
        right = BoxLayout(
            orientation="vertical",
            spacing=dp(3),
            size_hint_y=None,
            padding=[0, 0, dp(6), 0],
        )
        right.bind(minimum_height=right.setter("height"))

        name = self.playlist_data.get("name", "Unknown Playlist")
        track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
        owner_display = (self.playlist_data.get("owner") or {}).get(
            "display_name", "Unknown"
        )
        playlist_url = (self.playlist_data.get("external_urls") or {}).get(
            "spotify", ""
        )
        owner_url = (
            (self.playlist_data.get("owner") or {}).get("external_urls") or {}
        ).get("spotify", "")
        is_public = self.playlist_data.get("public", True)

        def info_label(
            text,
            bold=False,
            color=(0.88, 0.88, 0.88, 1),
            font_size=dp(12),
            height=dp(20),
        ):
            right.add_widget(
                Label(
                    text=text,
                    font_size=font_size,
                    bold=bold,
                    color=color,
                    halign="left",
                    valign="top",
                    text_size=(dp(420), None),
                    size_hint_y=None,
                    height=height,
                )
            )

        info_label(name, bold=True, font_size=dp(17), height=dp(32))
        info_label(f"Created by: {owner_display}", color=(0.75, 0.75, 0.75, 1))
        if playlist_url:
            info_label(
                f"Playlist URL: {playlist_url}", color=(0.4, 0.6, 1.0, 1), height=dp(18)
            )
        if owner_url:
            info_label(
                f"Owner URL: {owner_url}", color=(0.4, 0.6, 1.0, 1), height=dp(18)
            )
        info_label(
            f"Type: {'Public' if is_public else 'Private'}", color=(0.75, 0.75, 0.75, 1)
        )

        # Duration label — updated after analysis loads
        duration_label = Label(
            text=f"Tracks: {track_count}",
            font_size=dp(12),
            color=(0.88, 0.88, 0.88, 1),
            halign="left",
            valign="top",
            text_size=(dp(420), None),
            size_hint_y=None,
            height=dp(20),
        )
        right.add_widget(duration_label)

        progress_bar = ProgressBar(
            max=100,
            value=0,
            size_hint_y=None,
            height=dp(10),
        )
        status_label = Label(
            text="Analyzing playlist...",
            font_size=dp(11),
            color=(0.75, 0.55, 0.15, 1),
            halign="left",
            text_size=(dp(420), None),
            size_hint_y=None,
            height=dp(20),
        )
        enrichment_label = Label(
            text="",
            font_size=dp(10),
            color=(0.65, 0.65, 0.65, 1),
            halign="left",
            text_size=(dp(420), None),
            size_hint_y=None,
            height=dp(18),
        )
        right.add_widget(progress_bar)
        right.add_widget(status_label)
        right.add_widget(enrichment_label)

        # Analysis container — replaced by _update_analysis_ui when data arrives
        analysis_container = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2)
        )
        analysis_container.bind(minimum_height=analysis_container.setter("height"))
        analysis_container.add_widget(
            Label(
                text="Genre Distribution:",
                font_size=dp(12),
                bold=True,
                color=(0.88, 0.88, 0.88, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(22),
            )
        )
        right.add_widget(analysis_container)

        scroll.add_widget(right)

        # Right column wrapper: Show Tracks button pinned top-right, scroll below
        right_col = BoxLayout(orientation="vertical", spacing=dp(4))

        btn_row = BoxLayout(size_hint_y=None, height=dp(42))
        btn_row.add_widget(Widget())  # pushes buttons to the right
        refresh_tracks_btn = Button(
            text="Refresh playlist tracks",
            size_hint=(None, 1),
            width=dp(170),
            background_color=(0.28, 0.38, 0.22, 1),
            color=(1, 1, 1, 1),
        )
        refresh_tracks_btn.bind(on_release=self._refresh_playlist_tracks_analysis)
        btn_row.add_widget(refresh_tracks_btn)
        refresh_info_btn = Button(
            text="Refresh track info",
            size_hint=(None, 1),
            width=dp(150),
            background_color=(0.46, 0.34, 0.16, 1),
            color=(1, 1, 1, 1),
        )
        refresh_info_btn.bind(on_release=self._refresh_track_info_analysis)
        btn_row.add_widget(refresh_info_btn)

        show_tracks_btn = Button(
            text="Show Tracks",
            size_hint=(None, 1),
            width=dp(150),
            background_color=(0.22, 0.42, 0.72, 1),
            color=(1, 1, 1, 1),
        )
        show_tracks_btn.bind(on_release=self._open_tracks_window)
        btn_row.add_widget(show_tracks_btn)

        right_col.add_widget(btn_row)
        right_col.add_widget(scroll)

        main.add_widget(right_col)
        root.add_widget(main)

        root._analysis_container = analysis_container
        root._duration_label = duration_label
        root._analysis_progress_bar = progress_bar
        root._analysis_status_label = status_label
        root._enrichment_status_label = enrichment_label
        root._refresh_track_info_button = refresh_info_btn
        root._refresh_playlist_tracks_button = refresh_tracks_btn
        return root

    def _start_analysis_worker(
        self,
        playlist_id: str,
        content: BoxLayout,
        *,
        force_reanalyze: bool = False,
        refresh_tracks: bool = False,
    ) -> None:
        progress_bar = content._analysis_progress_bar
        status_label = content._analysis_status_label
        enrichment_label = content._enrichment_status_label
        analysis_container = content._analysis_container
        duration_label = content._duration_label

        progress_bar.height = dp(10)
        progress_bar.value = 0
        enrichment_label.text = ""
        if refresh_tracks:
            status_label.text = "Refreshing playlist tracks..."
        elif force_reanalyze:
            status_label.text = "Refreshing track info..."
        else:
            status_label.text = "Analyzing playlist..."
        analysis_container.clear_widgets()
        analysis_container.add_widget(
            Label(
                text=status_label.text,
                font_size=dp(11),
                color=(0.75, 0.55, 0.15, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(18),
            )
        )

        analysis_task = AnalysisTask(progress_bar, status_label)
        # Owned by the UI thread and reachable from _cancel_analysis_task;
        # the worker only reads is_cancelled() (bool store is GIL-atomic).
        # Refresh flows supersede the running task: cancel it so the old
        # worker returns before any UI update instead of racing the new one.
        previous_task = self._analysis_task
        self._analysis_task = analysis_task
        if previous_task is not None:
            previous_task.cancel()
        threading.Thread(
            target=self._load_analysis_worker,
            args=(
                playlist_id,
                analysis_container,
                duration_label,
                progress_bar,
                status_label,
                enrichment_label,
                force_reanalyze,
                refresh_tracks,
                analysis_task,
            ),
            daemon=True,
        ).start()

    def _refresh_track_info_analysis(self, *_args: Any) -> None:
        playlist_id = self.playlist_data.get("id")
        popup = self._detailed_popup
        content = getattr(popup, "content", None)
        if not playlist_id or content is None:
            return
        self._start_analysis_worker(playlist_id, content, force_reanalyze=True)

    def _refresh_playlist_tracks_analysis(self, *_args: Any) -> None:
        playlist_id = self.playlist_data.get("id")
        popup = self._detailed_popup
        content = getattr(popup, "content", None)
        if not playlist_id or content is None:
            return
        self._start_analysis_worker(playlist_id, content, refresh_tracks=True)

    def _retry_enrichment_analysis(self, *_args: Any) -> None:
        """Legacy alias for refresh track info (Track A compatibility)."""
        self._refresh_track_info_analysis()

    def _load_analysis_worker(
        self,
        playlist_id: str,
        analysis_container: BoxLayout,
        duration_label: Label,
        progress_bar: ProgressBar,
        status_label: Label,
        enrichment_label: Label,
        force_reanalyze: bool = False,
        refresh_tracks: bool = False,
        analysis_task: Optional[Any] = None,
    ) -> None:
        task = (
            analysis_task
            if analysis_task is not None
            else AnalysisTask(progress_bar, status_label)
        )
        try:
            app = App.get_running_app()
            adapter = getattr(app, "backend_adapter", None)
            if adapter is None:
                if task.is_cancelled():
                    return
                self._update_analysis_ui(
                    analysis_container,
                    duration_label,
                    None,
                    "No backend connection",
                    progress_bar,
                    status_label,
                    enrichment_label,
                )
                return

            if refresh_tracks and hasattr(adapter, "refresh_playlist_tracks"):
                analysis = adapter.refresh_playlist_tracks(
                    playlist_id, analysis_task=task
                )
            elif force_reanalyze and hasattr(adapter, "force_reanalyze_playlist"):
                analysis = adapter.force_reanalyze_playlist(
                    playlist_id, analysis_task=task
                )
            else:
                analysis = adapter.analyze_playlist(
                    playlist_id, analysis_task=task
                )
            if task.is_cancelled():
                # Dismissed while working: skip UI updates on detached widgets.
                # Backend job keeps running server-side (see _cancel_analysis_task).
                logger.debug("BackendPlaylistCard: analysis cancelled, skipping UI update")
                return
            self._update_analysis_ui(
                analysis_container,
                duration_label,
                analysis,
                None,
                progress_bar,
                status_label,
                enrichment_label,
            )
        except Exception as exc:
            if task.is_cancelled():
                # Dismissed while failing: no error UI on detached widgets.
                logger.debug("BackendPlaylistCard: analysis cancelled during error: %s", exc)
                return
            logger.warning("BackendPlaylistCard: analysis load error: %s", exc)
            self._update_analysis_ui(
                analysis_container,
                duration_label,
                None,
                str(exc),
                progress_bar,
                status_label,
                enrichment_label,
            )

    @mainthread
    def _update_analysis_ui(
        self,
        analysis_container: BoxLayout,
        duration_label: Label,
        analysis: Optional[dict[str, Any]],
        error: Optional[str],
        progress_bar: Optional[ProgressBar] = None,
        status_label: Optional[Label] = None,
        enrichment_label: Optional[Label] = None,
    ) -> None:
        render_analysis_popup_content(
            analysis_container=analysis_container,
            duration_label=duration_label,
            playlist_data=self.playlist_data,
            analysis=analysis,
            error=error,
            progress_bar=progress_bar,
            status_label=status_label,
            enrichment_label=enrichment_label,
        )


__all__ = ["PlaylistCardAnalysisPopupMixin"]
