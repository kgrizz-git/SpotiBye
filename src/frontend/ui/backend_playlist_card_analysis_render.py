"""Render helpers for the playlist analysis popup content area."""

from __future__ import annotations

from typing import Any, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar

from ..screens.adapter_mixins.analysis import EXPECTED_ANALYSIS_SCHEMA_VERSION
from ..services.enrichment_status import (
    format_enrichment_status_line,
    format_last_refreshed_line,
)
from .backend_playlist_card_utils import _describe_error_source, _mood_label


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


def _handle_error_state(
    analysis_container: BoxLayout,
    error: Optional[str],
    progress_bar: Optional[ProgressBar],
    status_label: Optional[Label],
    enrichment_label: Optional[Label],
) -> None:
    """Handle error state for analysis popup."""
    msg = f"Analysis unavailable: {error}" if error else "Analysis not available"
    if progress_bar is not None:
        progress_bar.value = 100
        progress_bar.height = 0
    if status_label is not None:
        status_label.text = msg
    if enrichment_label is not None:
        enrichment_label.text = ""
    analysis_container.add_widget(_small_label(msg, color=(0.65, 0.4, 0.4, 1)))


def _update_progress_widgets(
    progress_bar: Optional[ProgressBar],
    status_label: Optional[Label],
) -> None:
    """Update progress widgets for completed analysis."""
    if progress_bar is not None:
        progress_bar.value = 100
        progress_bar.height = 0
    if status_label is not None:
        status_label.text = "Analysis complete"


def _update_enrichment_label(
    enrichment_label: Optional[Label],
    results: dict[str, Any],
) -> None:
    """Update enrichment label with status information."""
    if enrichment_label is not None:
        enrichment_line = format_enrichment_status_line(
            results,
            expected_schema_version=EXPECTED_ANALYSIS_SCHEMA_VERSION,
        )
        refreshed_line = format_last_refreshed_line(results)
        enrichment_label.text = (
            f"{enrichment_line}\n{refreshed_line}".strip()
            if refreshed_line
            else enrichment_line
        )


def _render_partial_errors(
    analysis_container: BoxLayout,
    results: dict[str, Any],
) -> None:
    """Render partial data error messages."""
    for err in results.get("errors") or []:
        source = err.get("source", "unknown") if isinstance(err, dict) else "unknown"
        message = err.get("message") if isinstance(err, dict) else None
        analysis_container.add_widget(
            _small_label(
                f"Partial data: {_describe_error_source(source, message)}",
                color=(0.65, 0.4, 0.4, 1),
            )
        )


def _render_overview_section(
    duration_label: Label,
    playlist_data: dict[str, Any],
    results: dict[str, Any],
) -> None:
    """Render overview section with duration information."""
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
        track_count = (playlist_data.get("tracks") or {}).get("total", 0)
        duration_label.text = f"Tracks: {track_count} \u00b7 Duration: {duration_str}"


def _render_genre_distribution(
    analysis_container: BoxLayout,
    results: dict[str, Any],
) -> None:
    """Render genre distribution section."""
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


def _render_artist_analysis(
    analysis_container: BoxLayout,
    results: dict[str, Any],
) -> None:
    """Render artist analysis section."""
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


def _render_audio_features_percentage_row(
    analysis_container: BoxLayout,
    averages: dict[str, Any],
    features: list[tuple[str, str]],
) -> None:
    """Render a row of percentage-based audio features."""

    def _pct(label: str, key: str) -> Optional[str]:
        val = averages.get(key)
        return f"{label}: {val * 100:.0f}%" if val is not None else None

    row = [p for p in (_pct(label, key) for label, key in features) if p]
    if row:
        analysis_container.add_widget(_small_label(" \u00b7 ".join(row)))


def _render_audio_features_tempo_loudness(
    analysis_container: BoxLayout,
    averages: dict[str, Any],
) -> None:
    """Render tempo and loudness audio features."""
    row = []
    tempo = averages.get("tempo")
    if tempo is not None:
        row.append(f"Tempo: {int(tempo)} BPM")
    loudness = averages.get("loudness")
    if loudness is not None:
        row.append(f"Loudness: {loudness:.1f} dB")
    if row:
        analysis_container.add_widget(_small_label(" \u00b7 ".join(row)))


def _render_audio_features_mood(
    analysis_container: BoxLayout,
    averages: dict[str, Any],
) -> None:
    """Render mood/valence audio feature."""
    valence = averages.get("valence")
    if valence is not None:
        analysis_container.add_widget(
            _small_label(f"Mood: {_mood_label(valence)} (valence {valence * 100:.0f}%)")
        )


def _render_audio_features_key_mode(
    analysis_container: BoxLayout,
    audio_features: dict[str, Any],
) -> None:
    """Render key and mode distribution if available."""
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


def _render_audio_features_track_count(
    analysis_container: BoxLayout,
    audio_features: dict[str, Any],
) -> None:
    """Render track count disclaimer for audio features."""
    track_count = audio_features.get("track_count", 0)
    if track_count:
        analysis_container.add_widget(
            _small_label(
                f"Based on {track_count} tracks with available audio data",
                color=(0.55, 0.55, 0.55, 1),
            )
        )


def _render_audio_features(
    analysis_container: BoxLayout,
    results: dict[str, Any],
    has_current_schema: bool,
) -> None:
    """Render audio features section."""
    audio_features = results.get("audio_features") or {}
    averages = audio_features.get("averages") or {}
    if averages:
        analysis_container.add_widget(_section_header("Audio Features:"))

        _render_audio_features_percentage_row(
            analysis_container,
            averages,
            [
                ("Danceability", "danceability"),
                ("Energy", "energy"),
                ("Acousticness", "acousticness"),
            ],
        )

        _render_audio_features_percentage_row(
            analysis_container,
            averages,
            [
                ("Instrumentalness", "instrumentalness"),
                ("Liveness", "liveness"),
                ("Speechiness", "speechiness"),
            ],
        )

        _render_audio_features_tempo_loudness(analysis_container, averages)
        _render_audio_features_mood(analysis_container, averages)

        if has_current_schema:
            _render_audio_features_key_mode(analysis_container, audio_features)

        _render_audio_features_track_count(analysis_container, audio_features)


def _render_reccobeats_metadata(
    analysis_container: BoxLayout,
    results: dict[str, Any],
    playlist_data: dict[str, Any],
) -> None:
    """Render ReccoBeats metadata section."""
    reccobeats_metadata = results.get("reccobeats_metadata") or {}
    if reccobeats_metadata:
        analysis_container.add_widget(_section_header("ReccoBeats Metadata:"))
        isrc_available = reccobeats_metadata.get("isrc_available", 0)
        total_tracks = (playlist_data.get("tracks") or {}).get("total", 0)
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


def render_analysis_popup_content(
    *,
    analysis_container: BoxLayout,
    duration_label: Label,
    playlist_data: dict[str, Any],
    analysis: Optional[dict[str, Any]],
    error: Optional[str],
    progress_bar: Optional[ProgressBar] = None,
    status_label: Optional[Label] = None,
    enrichment_label: Optional[Label] = None,
) -> None:
    """Populate analysis popup widgets from backend analysis results."""
    analysis_container.clear_widgets()

    if error or not analysis:
        _handle_error_state(
            analysis_container, error, progress_bar, status_label, enrichment_label
        )
        return

    _update_progress_widgets(progress_bar, status_label)

    results = analysis.get("results", analysis)
    _update_enrichment_label(enrichment_label, results)

    has_current_schema = (
        results.get("schema_version") == EXPECTED_ANALYSIS_SCHEMA_VERSION
    )

    if has_current_schema:
        _render_partial_errors(analysis_container, results)

    _render_overview_section(duration_label, playlist_data, results)
    _render_genre_distribution(analysis_container, results)
    _render_artist_analysis(analysis_container, results)
    _render_audio_features(analysis_container, results, has_current_schema)

    if has_current_schema:
        _render_reccobeats_metadata(analysis_container, results, playlist_data)


__all__ = [
    "render_analysis_popup_content",
    "_handle_error_state",
    "_update_progress_widgets",
    "_update_enrichment_label",
    "_render_partial_errors",
    "_render_overview_section",
    "_render_genre_distribution",
    "_render_artist_analysis",
    "_render_audio_features",
    "_render_audio_features_percentage_row",
    "_render_audio_features_tempo_loudness",
    "_render_audio_features_mood",
    "_render_audio_features_key_mode",
    "_render_audio_features_track_count",
    "_render_reccobeats_metadata",
]
