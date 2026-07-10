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
the thread.

Depends on kivy, threading, .backend_playlist_card_utils,
..screens.adapter_mixins.analysis.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from ...shared.logging_config import logger
from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION
from .backend_playlist_card_utils import _describe_error_source, _mood_label


class PlaylistCardAnalysisPopupMixin:
    """Analysis-popup mixin for BackendPlaylistCard.

    Provides the double-click/long-press analysis popup with genre
    distribution, artist diversity, audio features, and ReccoBeats metadata.
    The "Show Tracks" button calls self._open_tracks_window() on the
    TracksPopupMixin.
    """

    playlist_data: Any = None
    _detailed_popup: Optional[Any] = None

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
        self._detailed_popup.open()

        playlist_id = self.playlist_data.get("id")
        if playlist_id:
            threading.Thread(
                target=self._load_analysis_worker,
                args=(
                    playlist_id,
                    content._analysis_container,
                    content._duration_label,
                ),
                daemon=True,
            ).start()

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
        analysis_container.add_widget(
            Label(
                text="Analyzing playlist...",
                font_size=dp(11),
                color=(0.75, 0.55, 0.15, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(20),
            )
        )
        right.add_widget(analysis_container)

        scroll.add_widget(right)

        # Right column wrapper: Show Tracks button pinned top-right, scroll below
        right_col = BoxLayout(orientation="vertical", spacing=dp(4))

        btn_row = BoxLayout(size_hint_y=None, height=dp(42))
        btn_row.add_widget(Widget())  # pushes button to the right
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
        return root

    def _load_analysis_worker(
        self, playlist_id: str, analysis_container: BoxLayout, duration_label: Label
    ) -> None:
        try:
            app = App.get_running_app()
            adapter = getattr(app, "backend_adapter", None)
            if adapter is None:
                self._update_analysis_ui(
                    analysis_container, duration_label, None, "No backend connection"
                )
                return

            analysis = adapter.analyze_playlist(playlist_id)
            self._update_analysis_ui(analysis_container, duration_label, analysis, None)
        except Exception as exc:
            logger.warning("BackendPlaylistCard: analysis load error: %s", exc)
            self._update_analysis_ui(analysis_container, duration_label, None, str(exc))

    @mainthread
    def _update_analysis_ui(
        self,
        analysis_container: BoxLayout,
        duration_label: Label,
        analysis: Optional[dict[str, Any]],
        error: Optional[str],
    ) -> None:
        analysis_container.clear_widgets()

        def _small_label(text, color=(0.75, 0.75, 0.75, 1), height=dp(18)):
            return Label(
                text=text,
                font_size=dp(11),
                color=color,
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=height,
            )

        def _section_header(text):
            return Label(
                text=text,
                font_size=dp(12),
                bold=True,
                color=(0.88, 0.88, 0.88, 1),
                halign="left",
                text_size=(dp(420), None),
                size_hint_y=None,
                height=dp(22),
            )

        if error or not analysis:
            msg = (
                f"Analysis unavailable: {error}" if error else "Analysis not available"
            )
            analysis_container.add_widget(_small_label(msg, color=(0.65, 0.4, 0.4, 1)))
            return

        # Normalise nested result wrapper
        results = analysis.get("results", analysis)

        # Results from a pre-schema-versioned (Phase 1) backend lack
        # schema_version, errors, key_mode_distribution, and
        # reccobeats_metadata entirely. Gate every Phase-2-and-later section
        # on schema_version matching so the popup renders identically to
        # today for those results instead of guessing at partial data.
        has_current_schema = (
            results.get("schema_version") == EXPECTED_ANALYSIS_SCHEMA_VERSION
        )

        # Partial-failure banner — shown first so a user scanning top-down
        # learns the analysis may be incomplete before reading the numbers.
        if has_current_schema:
            for err in results.get("errors") or []:
                source = (
                    err.get("source", "unknown") if isinstance(err, dict) else "unknown"
                )
                message = err.get("message") if isinstance(err, dict) else None
                analysis_container.add_widget(
                    _small_label(
                        f"Partial data: {_describe_error_source(source, message)}",
                        color=(0.65, 0.4, 0.4, 1),
                    )
                )

        # Duration
        overview = results.get("overview") or {}
        duration_str = overview.get("formatted_duration", "")
        if not duration_str:
            total_ms = overview.get("total_duration_ms", 0) or 0
            if total_ms:
                hrs = total_ms // 3_600_000
                mins = (total_ms % 3_600_000) // 60_000
                secs = (total_ms % 60_000) // 1000
                duration_str = f"{hrs}h {mins}m {secs}s" if hrs else f"{mins}m {secs}s"
        if duration_str:
            track_count = (self.playlist_data.get("tracks") or {}).get("total", 0)
            duration_label.text = f"Tracks: {track_count} \u00b7 Duration: {duration_str}"

        # Genre distribution
        genre_dist = results.get("genre_distribution") or results.get("genres") or {}
        analysis_container.add_widget(_section_header("Genre Distribution:"))
        if genre_dist and isinstance(genre_dist, dict):
            entries = []
            for genre, val in genre_dist.items():
                if isinstance(val, dict):
                    pct = float(val.get("percentage", 0))
                    count = int(val.get("count", 0))
                elif isinstance(val, (int, float)):
                    pct = float(val) * 100 if float(val) <= 1 else float(val)
                    count = 0
                else:
                    continue
                entries.append((genre, pct, count))
            entries.sort(key=lambda x: x[1], reverse=True)
            for genre, pct, count in entries[:7]:
                line = (
                    f"{genre}: {pct:.0f}% ({count} tracks)"
                    if count
                    else f"{genre}: {pct:.0f}%"
                )
                analysis_container.add_widget(_small_label(line))
        else:
            analysis_container.add_widget(
                _small_label("No genre data available", color=(0.55, 0.55, 0.55, 1))
            )

        # Artist analysis
        artists_data = results.get("artists") or {}
        if artists_data:
            analysis_container.add_widget(_section_header("Artist Analysis:"))

            unique_artists = artists_data.get("unique_artists", 0)
            diversity = artists_data.get("diversity", 0) or 0
            diversity_pct = diversity * 100 if diversity <= 1 else diversity
            analysis_container.add_widget(
                _small_label(
                    f"Unique Artists: {unique_artists} \u00b7 Diversity: {diversity_pct:.0f}%"
                )
            )

            top_artists = artists_data.get("top_artists") or []
            if top_artists:
                top_str = ", ".join(
                    f"{a.get('artist') or a.get('name', '?')} ({a.get('count', 0)})"
                    for a in top_artists[:5]
                )
                analysis_container.add_widget(_small_label(f"Top Artists: {top_str}"))

        # Audio features (from ReccoBeats, best-effort)
        audio_features = results.get("audio_features") or {}
        averages = audio_features.get("averages") or {}
        if averages:
            analysis_container.add_widget(_section_header("Audio Features:"))

            def _pct(label: str, key: str) -> Optional[str]:
                val = averages.get(key)
                return f"{label}: {val * 100:.0f}%" if val is not None else None

            row1 = [
                p
                for p in (
                    _pct("Danceability", "danceability"),
                    _pct("Energy", "energy"),
                    _pct("Acousticness", "acousticness"),
                )
                if p
            ]
            if row1:
                analysis_container.add_widget(_small_label(" \u00b7 ".join(row1)))

            row2 = [
                p
                for p in (
                    _pct("Instrumentalness", "instrumentalness"),
                    _pct("Liveness", "liveness"),
                    _pct("Speechiness", "speechiness"),
                )
                if p
            ]
            if row2:
                analysis_container.add_widget(_small_label(" \u00b7 ".join(row2)))

            row3 = []
            tempo = averages.get("tempo")
            if tempo is not None:
                row3.append(f"Tempo: {int(tempo)} BPM")
            loudness = averages.get("loudness")
            if loudness is not None:
                row3.append(f"Loudness: {loudness:.1f} dB")
            if row3:
                analysis_container.add_widget(_small_label(" \u00b7 ".join(row3)))

            valence = averages.get("valence")
            if valence is not None:
                analysis_container.add_widget(
                    _small_label(
                        f"Mood: {_mood_label(valence)} (valence {valence * 100:.0f}%)"
                    )
                )

            if has_current_schema:
                key_mode = audio_features.get("key_mode_distribution") or {}
                dominant_key = key_mode.get("dominant_key")
                dominant_mode = key_mode.get("dominant_mode")
                if dominant_key and dominant_mode:
                    key_pct = key_mode.get("dominant_key_percentage", 0)
                    analysis_container.add_widget(
                        _small_label(
                            f"Key: {dominant_key} {dominant_mode} ({key_pct:.0f}% of tracks)"
                        )
                    )

            track_count = audio_features.get("track_count", 0)
            if track_count:
                analysis_container.add_widget(
                    _small_label(
                        f"Based on {track_count} tracks with available audio data",
                        color=(0.55, 0.55, 0.55, 1),
                    )
                )

        # ReccoBeats metadata aggregates (ISRC coverage, popularity range)
        if has_current_schema:
            reccobeats_metadata = results.get("reccobeats_metadata") or {}
            if reccobeats_metadata:
                analysis_container.add_widget(_section_header("ReccoBeats Metadata:"))
                isrc_available = reccobeats_metadata.get("isrc_available", 0)
                total_tracks = (self.playlist_data.get("tracks") or {}).get("total", 0)
                analysis_container.add_widget(
                    _small_label(
                        f"ISRC available for {isrc_available} of {total_tracks} tracks"
                    )
                )
                pop_min = reccobeats_metadata.get("popularity_min")
                pop_max = reccobeats_metadata.get("popularity_max")
                if pop_min is not None and pop_max is not None:
                    analysis_container.add_widget(
                        _small_label(f"Popularity range: {pop_min}\u2013{pop_max}")
                    )


__all__ = ["PlaylistCardAnalysisPopupMixin"]
