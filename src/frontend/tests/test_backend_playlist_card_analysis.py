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


class _FakeWidget:
    """Stand-in for any Kivy widget: records children, no-ops everything else."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.children: list[Any] = []

    def add_widget(self, widget: Any) -> None:
        self.children.append(widget)

    def clear_widgets(self) -> None:
        self.children = []

    def bind(self, **_kwargs: Any) -> None:
        pass

    def setter(self, _name: str):
        return lambda *_a, **_k: None


def _fake_module(name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


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
finally:
    for _name, _orig in _original_modules.items():
        if _orig is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _orig


def _card(total_tracks: int = 5) -> BackendPlaylistCard:
    card = BackendPlaylistCard.__new__(BackendPlaylistCard)
    card.playlist_data = {"tracks": {"total": total_tracks}}
    return card


def _render(
    card: BackendPlaylistCard, analysis: dict[str, Any] | None, error: str | None = None
):
    container = _FakeWidget()
    duration_label = _FakeWidget(text="")
    card._update_analysis_ui(
        cast("BoxLayout", cast(Any, container)),
        cast("Label", cast(Any, duration_label)),
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
        assert _describe_error_source(
            "reccobeats:audio-features", "HTTP 429: rate limited"
        ) == "audio features unavailable (HTTP 429: rate limited)"

    def test_includes_timeout_message(self) -> None:
        assert _describe_error_source(
            "reccobeats:track-metadata", "Request timed out after 15000ms"
        ) == "track metadata unavailable (Request timed out after 15000ms)"

    def test_includes_invalid_shape_message(self) -> None:
        assert _describe_error_source(
            "reccobeats:audio-features",
            "Invalid ReccoBeats audio features response shape",
        ) == (
            "audio features unavailable "
            "(Invalid ReccoBeats audio features response shape)"
        )


class TestAnalysisPopupRendering:
    def test_renders_all_nine_audio_features_key_mode_and_metadata(self) -> None:
        card = _card(total_tracks=10)
        analysis = {
            "schema_version": "1.0",
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
            "schema_version": "1.0",
            "errors": [
                {"source": "spotify:artists", "message": "HTTP 429: rate limited"},
                {
                    "source": "reccobeats:track-metadata",
                    "message": "Request timed out after 15000ms",
                },
            ],
            "overview": {},
            "genre_distribution": {},
            "artists": {},
        }

        texts, _ = _render(card, analysis)
        joined = "\n".join(texts)

        assert (
            "Partial data: artist genres unavailable (HTTP 429: rate limited)"
            in joined
        )
        assert (
            "Partial data: track metadata unavailable "
            "(Request timed out after 15000ms)" in joined
        )

    def test_no_crash_without_audio_features(self) -> None:
        card = _card()
        analysis = {
            "schema_version": "1.0",
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
            "schema_version": "1.0",
            "errors": [],
            "overview": {},
            "genre_distribution": {},
            "artists": {},
            "audio_features": {"track_count": 0, "averages": {}},
        }

        texts, _ = _render(card, analysis)
        assert "Audio Features:" not in "\n".join(texts)
