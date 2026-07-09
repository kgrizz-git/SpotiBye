"""Main BackendPlaylistCard orchestrator — thin class wiring UI/interaction/popup mixins.

The heavy lifting lives in:
  - backend_playlist_card_utils.py          module-level helpers (no deps)
  - backend_playlist_card_ui.py             PlaylistCardUIMixin (layout, graphics, selection)
  - backend_playlist_card_interaction.py    PlaylistCardInteractionMixin (touch/click)
  - backend_playlist_card_analysis_popup.py PlaylistCardAnalysisPopupMixin (analysis window)
  - backend_playlist_card_tracks_popup.py   PlaylistCardTracksPopupMixin (tracks window)
"""

from __future__ import annotations

from typing import Any, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup

from .backend_playlist_card_analysis_popup import PlaylistCardAnalysisPopupMixin
from .backend_playlist_card_interaction import PlaylistCardInteractionMixin
from .backend_playlist_card_tracks_popup import PlaylistCardTracksPopupMixin
from .backend_playlist_card_ui import PlaylistCardUIMixin
from .backend_playlist_card_utils import _describe_error_source, _mood_label

__all__ = ["BackendPlaylistCard", "_mood_label", "_describe_error_source"]


class BackendPlaylistCard(  # pyright: ignore[reportUnsafeMultipleInheritance]
    PlaylistCardInteractionMixin,
    PlaylistCardUIMixin,
    PlaylistCardAnalysisPopupMixin,
    PlaylistCardTracksPopupMixin,
    BoxLayout,
):
    """Playlist card for backend mode — checkbox + cover image, no disk cache or ReccoBeats.

    Interactions:
      - Single click anywhere: toggle selection (checkbox + blue highlight)
      - Double click / long press: open Playlist Analysis popup
        -> "Show Tracks" button inside opens the track-list window

    BoxLayout (Kivy EventDispatcher metaclass) is last in the MRO to avoid
    metaclass conflicts. The mixins define no ``__init__``, so
    ``super().__init__(**kwargs)`` resolves through the MRO to ``BoxLayout``.
    """

    playlist_data: Any = None
    _graphics_update_scheduled: Any = None
    _detailed_popup: Optional[Popup] = None
    _tracks_popup: Optional[Popup] = None

    def __init__(self, playlist_data: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(190)
        self.padding = dp(8)
        self.spacing = dp(0)

        self.playlist_data = playlist_data
        self._graphics_update_scheduled = False
        self._detailed_popup: Optional[Popup] = None
        self._tracks_popup: Optional[Popup] = None

        self._build_card_ui()
        self._setup_interactions()
