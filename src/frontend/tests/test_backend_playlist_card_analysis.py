"""Tests for the ReccoBeats-enriched analysis popup in BackendPlaylistCard.

Constructing real Kivy widgets under KIVY_WINDOW=headless aborts the process
(kivy.metrics.dp() resolves Window, which doesn't exist headless — see
test_backend_selector_popup.py's docstring for the same issue). Stub every
kivy name this module touches, import under the stub, then restore
sys.modules immediately so later test files in the same session see the
real kivy modules.
"""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.progressbar import ProgressBar


class _FakeWidget:
    """Stand-in for any Kivy widget: records children, no-ops everything else."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.children: list[Any] = []
        self.bound_events: dict[str, Any] = {}

    def add_widget(self, widget: Any) -> None:
        self.children.append(widget)

    def clear_widgets(self) -> None:
        self.children = []

    def bind(self, **_kwargs: Any) -> None:
        self.bound_events.update(_kwargs)

    def setter(self, _name: str):
        return lambda *_a, **_k: None

    @staticmethod
    def schedule_once(callback: Any, timeout: float = 0) -> Any:
        return callback(timeout)


def _fake_module(name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _as_box_layout(widget: _FakeWidget) -> BoxLayout:
    """Cast a headless test double at the Kivy UI boundary."""
    return cast("BoxLayout", cast(Any, widget))


def _as_label(widget: _FakeWidget) -> Label:
    """Cast a headless test double at the Kivy UI boundary."""
    return cast("Label", cast(Any, widget))


def _as_progress_bar(widget: _FakeWidget) -> ProgressBar:
    """Cast a headless test double at the Kivy UI boundary."""
    return cast("ProgressBar", cast(Any, widget))


_STUB_MODULES = {
    "kivy.app": _fake_module("kivy.app", App=_FakeWidget),
    # Real `mainthread` always defers via `Clock.schedule_once` and never
    # calls synchronously (see kivy.clock source) — no callback fires without
    # a running App event loop. Stub it as a pass-through so
    # `_update_analysis_ui` (decorated with `@mainthread`) runs synchronously.
    "kivy.clock": _fake_module(
        "kivy.clock", Clock=_FakeWidget, mainthread=lambda func: func
    ),
    "kivy.graphics": _fake_module(
        "kivy.graphics", Color=_FakeWidget, Rectangle=_FakeWidget
    ),
    "kivy.metrics": _fake_module("kivy.metrics", dp=lambda value: value),
    "kivy.uix.boxlayout": _fake_module("kivy.uix.boxlayout", BoxLayout=_FakeWidget),
    "kivy.uix.button": _fake_module("kivy.uix.button", Button=_FakeWidget),
    "kivy.uix.checkbox": _fake_module("kivy.uix.checkbox", CheckBox=_FakeWidget),
    "kivy.uix.image": _fake_module("kivy.uix.image", AsyncImage=_FakeWidget),
    "kivy.uix.label": _fake_module("kivy.uix.label", Label=_FakeWidget),
    "kivy.uix.popup": _fake_module("kivy.uix.popup", Popup=_FakeWidget),
    "kivy.uix.progressbar": _fake_module(
        "kivy.uix.progressbar", ProgressBar=_FakeWidget
    ),
    "kivy.uix.relativelayout": _fake_module(
        "kivy.uix.relativelayout", RelativeLayout=_FakeWidget
    ),
    "kivy.uix.scrollview": _fake_module("kivy.uix.scrollview", ScrollView=_FakeWidget),
    "kivy.uix.widget": _fake_module("kivy.uix.widget", Widget=_FakeWidget),
}
_original_modules = {name: sys.modules.get(name) for name in _STUB_MODULES}
sys.modules.update(_STUB_MODULES)
try:
    from ..ui.backend_playlist_card import (
        BackendPlaylistCard,
        _describe_error_source,
        _mood_label,
    )
    from ..ui import backend_playlist_card_analysis_popup as analysis_popup_module
finally:
    for _name, _orig in _original_modules.items():
        if _orig is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _orig


def _card(total_tracks: int = 5) -> BackendPlaylistCard:
    card = BackendPlaylistCard.__new__(BackendPlaylistCard)
    card.playlist_data = {
        "id": "playlist-1",
        "name": "Playlist",
        "tracks": {"total": total_tracks},
        "owner": {},
        "images": [],
        "external_urls": {},
    }
    return card


def _render(
    card: BackendPlaylistCard, analysis: dict[str, Any] | None, error: str | None = None
):
    container = _FakeWidget()
    duration_label = _FakeWidget(text="")
    card._update_analysis_ui(
        _as_box_layout(container),
        _as_label(duration_label),
        analysis,
        error,
    )
    return [w.text for w in container.children], container.children


AUDIO_FEATURES_AVERAGES = {
    "danceability": 0.6,
    "energy": 0.8,
    "acousticness": 0.3,
    "instrumentalness": 0.05,
    "liveness": 0.2,
    "speechiness": 0.08,
    "tempo": 120,
    "loudness": -6.0,
    "valence": 0.68,
}


class TestMoodLabelBoundaries:
    def test_lower_edge_is_melancholic(self) -> None:
        assert _mood_label(0.0) == "Melancholic"

    def test_just_below_somber_boundary_is_melancholic(self) -> None:
        assert _mood_label(0.1999) == "Melancholic"

    def test_somber_boundary_is_somber(self) -> None:
        assert _mood_label(0.20) == "Somber"

    def test_neutral_boundary_is_neutral(self) -> None:
        assert _mood_label(0.40) == "Neutral"

    def test_cheerful_boundary_is_cheerful(self) -> None:
        assert _mood_label(0.60) == "Cheerful"

    def test_euphoric_boundary_is_euphoric(self) -> None:
        assert _mood_label(0.80) == "Euphoric"

    def test_upper_edge_is_euphoric_inclusive(self) -> None:
        assert _mood_label(1.0) == "Euphoric"


class TestDescribeErrorSource:
    def test_describes_known_source_without_message(self) -> None:
        assert (
            _describe_error_source("reccobeats:audio-features")
            == "audio features unavailable"
        )

    def test_includes_http_429_message(self) -> None:
        assert (
            _describe_error_source(
                "reccobeats:audio-features", "HTTP 429: rate limited"
            )
            == "audio features unavailable (HTTP 429: rate limited)"
        )

    def test_includes_timeout_message(self) -> None:
        assert (
            _describe_error_source(
                "reccobeats:track-metadata", "Request timed out after 15000ms"
            )
            == "track metadata unavailable (Request timed out after 15000ms)"
        )

    def test_includes_invalid_shape_message(self) -> None:
        assert _describe_error_source(
            "reccobeats:audio-features",
            "Invalid ReccoBeats audio features response shape",
        ) == (
            "audio features unavailable "
            "(Invalid ReccoBeats audio features response shape)"
        )

    def test_simplifies_nested_spotify_404_message(self) -> None:
        assert (
            _describe_error_source(
                "spotify:artists",
                'HTTP 404: {"error": {"status": 404, "message": "Resource not found"}}',
            )
            == "artist genres unavailable (Spotify returned 404: Resource not found)"
        )


class TestAnalysisPopupRendering:
    def test_loading_state_exposes_progress_widgets(self) -> None:
        card = _card()

        content = card._build_analysis_popup_content()

        assert hasattr(content, "_analysis_progress_bar")
        assert hasattr(content, "_analysis_status_label")
        assert content._analysis_status_label.text == "Analyzing playlist..."

    def test_refresh_buttons_are_available_and_bound(self) -> None:
        card = _card()

        content = card._build_analysis_popup_content()

        assert hasattr(content, "_refresh_track_info_button")
        assert hasattr(content, "_refresh_playlist_tracks_button")
        assert content._refresh_track_info_button.text == "Refresh track info"
        assert content._refresh_playlist_tracks_button.text == "Refresh playlist tracks"
        assert (
            content._refresh_track_info_button.bound_events["on_release"]
            == card._refresh_track_info_analysis
        )
        assert (
            content._refresh_playlist_tracks_button.bound_events["on_release"]
            == card._refresh_playlist_tracks_analysis
        )

    def test_retry_enrichment_button_is_available_and_bound(self) -> None:
        """Legacy alias still bound for Track A compatibility."""
        card = _card()

        content = card._build_analysis_popup_content()

        assert hasattr(content, "_refresh_track_info_button")
        refresh_button = content._refresh_track_info_button
        assert refresh_button.text == "Refresh track info"
        assert (
            refresh_button.bound_events["on_release"]
            == card._refresh_track_info_analysis
        )

    def test_worker_passes_analysis_task_to_adapter(self, monkeypatch) -> None:
        card = _card()
        adapter = _FakeWidget()
        adapter.analyze_playlist = cast(
            Any, lambda *_args, **_kwargs: {"status": "completed"}
        )
        app = _FakeWidget(backend_adapter=adapter)
        monkeypatch.setattr(
            analysis_popup_module.App,
            "get_running_app",
            lambda: app,
            raising=False,
        )
        captured: dict[str, Any] = {}

        def analyze_playlist(
            playlist_id: str, analysis_task: Any = None
        ) -> dict[str, Any]:
            captured["playlist_id"] = playlist_id
            captured["analysis_task"] = analysis_task
            return {"status": "completed"}

        adapter.analyze_playlist = analyze_playlist
        container = _FakeWidget()
        duration_label = _FakeWidget(text="")
        progress_bar = _FakeWidget()
        status_label = _FakeWidget(text="")
        enrichment_label = _FakeWidget(text="")

        card._load_analysis_worker(
            "playlist-1",
            cast("BoxLayout", cast(Any, container)),
            cast("Label", cast(Any, duration_label)),
            cast(Any, progress_bar),
            cast(Any, status_label),
            cast(Any, enrichment_label),
        )

        assert captured["playlist_id"] == "playlist-1"
        assert captured["analysis_task"] is not None

    def test_show_binds_dismiss_to_cancel(self, monkeypatch) -> None:
        card = _card()
        opened: list[bool] = []

        class FakePopup(_FakeWidget):
            def open(self) -> None:
                opened.append(True)

        monkeypatch.setattr(analysis_popup_module, "Popup", FakePopup)
        monkeypatch.setattr(
            card, "_start_analysis_worker", lambda *args, **kwargs: None
        )

        card.show_detailed_playlist_window()

        assert opened == [True]
        assert (
            card._detailed_popup.bound_events["on_dismiss"]
            == card._cancel_analysis_task
        )

    def test_cancel_analysis_task_cancels_and_clears(self) -> None:
        card = _card()
        calls: list[bool] = []

        class FakeTask:
            def cancel(self) -> None:
                calls.append(True)

        card._analysis_task = FakeTask()
        card._cancel_analysis_task()

        assert calls == [True]
        assert card._analysis_task is None

    def test_cancel_analysis_task_without_task_is_noop(self) -> None:
        card = _card()

        card._cancel_analysis_task()

        assert card._analysis_task is None

    def test_worker_skips_ui_update_when_cancelled(self, monkeypatch) -> None:
        from src.frontend.utils.analysis_task import AnalysisTask

        card = _card()
        adapter = _FakeWidget()
        adapter.analyze_playlist = cast(
            Any, lambda *_args, **_kwargs: {"status": "completed"}
        )
        app = _FakeWidget(backend_adapter=adapter)
        monkeypatch.setattr(
            analysis_popup_module.App,
            "get_running_app",
            lambda: app,
            raising=False,
        )
        ui_updates: list[bool] = []
        monkeypatch.setattr(
            card,
            "_update_analysis_ui",
            lambda *args, **kwargs: ui_updates.append(True),
        )

        task = AnalysisTask(_FakeWidget(), _FakeWidget())
        task.cancel()
        card._load_analysis_worker(
            "playlist-1",
            cast("BoxLayout", cast(Any, _FakeWidget())),
            cast("Label", cast(Any, _FakeWidget(text=""))),
            cast(Any, _FakeWidget()),
            cast(Any, _FakeWidget(text="")),
            cast(Any, _FakeWidget(text="")),
            analysis_task=task,
        )

        assert ui_updates == []

    def test_worker_skips_no_backend_ui_when_cancelled(
        self, monkeypatch
    ) -> None:
        from src.frontend.utils.analysis_task import AnalysisTask

        card = _card()
        app = _FakeWidget()
        monkeypatch.setattr(
            analysis_popup_module.App,
            "get_running_app",
            lambda: app,
            raising=False,
        )
        ui_updates: list[bool] = []
        monkeypatch.setattr(
            card,
            "_update_analysis_ui",
            lambda *args, **kwargs: ui_updates.append(True),
        )

        task = AnalysisTask(_FakeWidget(), _FakeWidget())
        task.cancel()
        card._load_analysis_worker(
            "playlist-1",
            cast("BoxLayout", cast(Any, _FakeWidget())),
            cast("Label", cast(Any, _FakeWidget(text=""))),
            cast(Any, _FakeWidget()),
            cast(Any, _FakeWidget(text="")),
            cast(Any, _FakeWidget(text="")),
            analysis_task=task,
        )

        assert ui_updates == []

    def test_refresh_cancels_superseded_task(self, monkeypatch) -> None:
        card = _card()
        content = card._build_analysis_popup_content()
        cancelled: list[bool] = []

        class FakeTask:
            def cancel(self) -> None:
                cancelled.append(True)

            def is_cancelled(self) -> bool:
                return bool(cancelled)

        old_task = FakeTask()
        card._analysis_task = old_task
        monkeypatch.setattr(
            card, "_load_analysis_worker", lambda *args, **kwargs: None
        )

        card._start_analysis_worker("playlist-1", _as_box_layout(content))

        assert cancelled == [True]
        assert card._analysis_task is not old_task

    def test_worker_force_reanalyze_uses_force_adapter_method(
        self, monkeypatch
    ) -> None:
        card = _card()
        adapter = _FakeWidget()
        app = _FakeWidget(backend_adapter=adapter)
        monkeypatch.setattr(
            analysis_popup_module.App,
            "get_running_app",
            lambda: app,
            raising=False,
        )
        captured: dict[str, Any] = {}

        def force_reanalyze_playlist(
            playlist_id: str, analysis_task: Any = None
        ) -> dict[str, Any]:
            captured["playlist_id"] = playlist_id
            captured["analysis_task"] = analysis_task
            return {"status": "completed"}

        adapter.force_reanalyze_playlist = force_reanalyze_playlist
        adapter.analyze_playlist = cast(
            Any, lambda *_args, **_kwargs: {"status": "unexpected"}
        )
        container = _FakeWidget()
        duration_label = _FakeWidget(text="")
        progress_bar = _FakeWidget()
        status_label = _FakeWidget(text="")
        enrichment_label = _FakeWidget(text="")

        card._load_analysis_worker(
            "playlist-1",
            cast("BoxLayout", cast(Any, container)),
            cast("Label", cast(Any, duration_label)),
            cast(Any, progress_bar),
            cast(Any, status_label),
            cast(Any, enrichment_label),
            True,
            False,
        )

        assert captured["playlist_id"] == "playlist-1"
        assert captured["analysis_task"] is not None

    def test_renders_all_nine_audio_features_key_mode_and_metadata(self) -> None:
        card = _card(total_tracks=10)
        analysis = {
            "schema_version": "1.1",
            "errors": [],
            "overview": {"formatted_duration": "30m 0s"},
            "genre_distribution": {},
            "artists": {},
            "audio_features": {
                "track_count": 10,
                "averages": AUDIO_FEATURES_AVERAGES,
                "key_mode_distribution": {
                    "dominant_key": "C",
                    "dominant_mode": "major",
                    "dominant_key_percentage": 42.0,
                },
            },
            "reccobeats_metadata": {
                "isrc_available": 8,
                "popularity_min": 20,
                "popularity_max": 90,
            },
        }

        texts, _ = _render(card, analysis)
        joined = "\n".join(texts)

        assert "Danceability: 60%" in joined
        assert "Energy: 80%" in joined
        assert "Acousticness: 30%" in joined
        assert "Instrumentalness: 5%" in joined
        assert "Liveness: 20%" in joined
        assert "Speechiness: 8%" in joined
        assert "Tempo: 120 BPM" in joined
        assert "Loudness: -6.0 dB" in joined
        assert "Mood: Cheerful (valence 68%)" in joined
        assert "Key: C major (42% of tracks)" in joined
        assert "ISRC available for 8 of 10 tracks" in joined
        assert "Popularity range: 20–90" in joined

    def test_omits_key_mode_and_metadata_sections_without_current_schema_version(
        self,
    ) -> None:
        # A Phase-1-shaped result: no schema_version, no key_mode_distribution,
        # no reccobeats_metadata, no errors. Must render the base audio
        # features without crashing and without any Phase-2-only section.
        card = _card()
        analysis = {
            "overview": {"formatted_duration": "10m 0s"},
            "genre_distribution": {},
            "artists": {},
            "audio_features": {
                "track_count": 5,
                "averages": AUDIO_FEATURES_AVERAGES,
            },
        }

        texts, _ = _render(card, analysis)
        joined = "\n".join(texts)

        assert "Danceability: 60%" in joined
        assert "Key:" not in joined
        assert "ReccoBeats Metadata:" not in joined
        assert "Partial data:" not in joined

    def test_ignores_key_mode_and_metadata_even_if_present_without_schema_version(
        self,
    ) -> None:
        # Defensive case: fields present but schema_version missing/stale
        # still suppresses the new sections (belt-and-suspenders per the
        # exec plan, not just incidental key-absence).
        card = _card()
        analysis = {
            "schema_version": "0.9",
            "errors": [{"source": "reccobeats:audio-features", "message": "boom"}],
            "overview": {},
            "genre_distribution": {},
            "artists": {},
            "audio_features": {
                "track_count": 5,
                "averages": AUDIO_FEATURES_AVERAGES,
                "key_mode_distribution": {
                    "dominant_key": "C",
                    "dominant_mode": "major",
                    "dominant_key_percentage": 100.0,
                },
            },
            "reccobeats_metadata": {"isrc_available": 1},
        }

        texts, _ = _render(card, analysis)
        joined = "\n".join(texts)

        assert "Key:" not in joined
        assert "ReccoBeats Metadata:" not in joined
        assert "Partial data:" not in joined

    def test_renders_partial_failure_banner_from_errors(self) -> None:
        card = _card()
        analysis = {
            "schema_version": "1.1",
            "errors": [
                {"source": "spotify:artists", "message": "HTTP 429: rate limited"},
                {
                    "source": "reccobeats:track-metadata",
                    "message": "Request timed out after 15000ms",
                },
                {
                    "source": "reccobeats:coverage",
                    "message": "Audio features available for 0 of 30 tracks.",
                },
            ],
            "overview": {},
            "genre_distribution": {},
            "artists": {},
        }

        texts, _ = _render(card, analysis)
        joined = "\n".join(texts)

        assert (
            "Partial data: artist genres unavailable (HTTP 429: rate limited)" in joined
        )
        assert (
            "Partial data: track metadata unavailable "
            "(Request timed out after 15000ms)" in joined
        )
        assert (
            "Partial data: audio feature coverage note "
            "(Audio features available for 0 of 30 tracks.)" in joined
        )

    def test_no_crash_without_audio_features(self) -> None:
        card = _card()
        analysis = {
            "schema_version": "1.1",
            "errors": [],
            "overview": {},
            "genre_distribution": {},
            "artists": {},
        }

        texts, _ = _render(card, analysis)
        assert "Audio Features:" not in "\n".join(texts)

    def test_no_crash_with_missing_analysis(self) -> None:
        card = _card()
        texts, _ = _render(card, None, error="boom")
        assert any("Analysis unavailable: boom" in t for t in texts)

    def test_na_style_missing_averages_render_no_audio_features_section(self) -> None:
        card = _card()
        analysis = {
            "schema_version": "1.1",
            "errors": [],
            "overview": {},
            "genre_distribution": {},
            "artists": {},
            "audio_features": {"track_count": 0, "averages": {}},
        }

        texts, _ = _render(card, analysis)
        assert "Audio Features:" not in "\n".join(texts)


class TestRefactoredRenderFunctions:
    """Tests for extracted render functions after refactoring."""

    def test_handle_error_state_with_error_message(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        container = _FakeWidget()
        progress_bar = _FakeWidget()
        status_label = _FakeWidget()
        enrichment_label = _FakeWidget()

        render_module._handle_error_state(
            _as_box_layout(container),
            "test error",
            _as_progress_bar(progress_bar),
            _as_label(status_label),
            _as_label(enrichment_label),
        )

        assert len(container.children) == 1
        assert "Analysis unavailable: test error" in container.children[0].text
        assert progress_bar.value == 100
        assert progress_bar.height == 0
        assert status_label.text == "Analysis unavailable: test error"
        assert enrichment_label.text == ""

    def test_handle_error_state_without_error(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        container = _FakeWidget()
        progress_bar = _FakeWidget()
        status_label = _FakeWidget()
        enrichment_label = _FakeWidget()

        render_module._handle_error_state(
            _as_box_layout(container),
            None,
            _as_progress_bar(progress_bar),
            _as_label(status_label),
            _as_label(enrichment_label),
        )

        assert len(container.children) == 1
        assert "Analysis not available" in container.children[0].text

    def test_update_progress_widgets(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        progress_bar = _FakeWidget()
        status_label = _FakeWidget()

        render_module._update_progress_widgets(
            _as_progress_bar(progress_bar), _as_label(status_label)
        )

        assert progress_bar.value == 100
        assert progress_bar.height == 0
        assert status_label.text == "Analysis complete"

    def test_render_overview_section_with_formatted_duration(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        duration_label = _FakeWidget()
        playlist_data = {"tracks": {"total": 10}}
        results = {"overview": {"formatted_duration": "30m 0s"}}

        render_module._render_overview_section(
            _as_label(duration_label), playlist_data, results
        )

        assert "Tracks: 10 · Duration: 30m 0s" in duration_label.text

    def test_render_overview_section_with_duration_calculation(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        duration_label = _FakeWidget()
        playlist_data = {"tracks": {"total": 5}}
        results = {"overview": {"total_duration_ms": 180000}}  # 3 minutes

        render_module._render_overview_section(
            _as_label(duration_label), playlist_data, results
        )

        assert "Tracks: 5 · Duration: 3m 0s" in duration_label.text

    def test_render_genre_distribution_with_data(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        container = _FakeWidget()
        results = {
            "genre_distribution": {
                "Rock": {"percentage": 45, "count": 10},
                "Pop": {"percentage": 30, "count": 7},
            }
        }

        render_module._render_genre_distribution(_as_box_layout(container), results)

        texts = [w.text for w in container.children]
        assert "Genre Distribution:" in texts
        assert any("Rock: 45%" in t for t in texts)
        assert any("Pop: 30%" in t for t in texts)

    def test_render_artist_analysis_with_data(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        container = _FakeWidget()
        results = {
            "artists": {
                "unique_artists": 15,
                "diversity": 0.75,
                "top_artists": [
                    {"artist": "Artist1", "count": 5},
                    {"artist": "Artist2", "count": 3},
                ],
            }
        }

        render_module._render_artist_analysis(_as_box_layout(container), results)

        texts = [w.text for w in container.children]
        assert "Artist Analysis:" in texts
        assert any("Unique Artists: 15" in t for t in texts)
        assert any("Diversity: 75%" in t for t in texts)
        assert any("Top Artists:" in t for t in texts)

    def test_render_audio_features_percentage_row(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        container = _FakeWidget()
        averages = {
            "danceability": 0.6,
            "energy": 0.8,
            "acousticness": 0.3,
        }

        render_module._render_audio_features_percentage_row(
            _as_box_layout(container),
            averages,
            [
                ("Danceability", "danceability"),
                ("Energy", "energy"),
                ("Acousticness", "acousticness"),
            ],
        )

        assert len(container.children) == 1
        text = container.children[0].text
        assert "Danceability: 60%" in text
        assert "Energy: 80%" in text
        assert "Acousticness: 30%" in text

    def test_render_reccobeats_metadata(self) -> None:
        from ..ui import backend_playlist_card_analysis_render as render_module

        container = _FakeWidget()
        results = {
            "reccobeats_metadata": {
                "isrc_available": 8,
                "popularity_min": 20,
                "popularity_max": 90,
            }
        }
        playlist_data = {"tracks": {"total": 10}}

        render_module._render_reccobeats_metadata(
            _as_box_layout(container), results, playlist_data
        )

        texts = [w.text for w in container.children]
        assert "ReccoBeats Metadata:" in texts
        assert any("ISRC available for 8 of 10 tracks" in t for t in texts)
        assert any("Popularity range: 20–90" in t for t in texts)
