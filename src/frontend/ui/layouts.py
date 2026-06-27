"""Reusable layout widgets for the Spotify exporter UI."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.gridlayout import GridLayout

from ...shared.logging_config import logger

if TYPE_CHECKING:
    from kivy.properties import NumericProperty as _NumericProperty


def _padding_list(value: _NumericProperty) -> list[float]:
    """Kivy's padding/spacing are typed as float but act as a ReferenceList."""
    return cast("list[float]", value)


def _spacing_list(value: _NumericProperty) -> list[float]:
    """Kivy's spacing is typed as float but acts as a ReferenceList."""
    return cast("list[float]", value)


class ResponsiveGridLayout(GridLayout):
    """Grid layout that adapts columns based on available width with optimized performance."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 1
        self.spacing = dp(8)
        self.padding = dp(8)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter("height"))
        self.bind(width=self.recalculate_columns)

        self.min_card_width = dp(162)
        self.max_card_width = dp(210)
        self._last_width = 0
        self._last_card_width = self.min_card_width
        self._cached_cols = 1

    def recalculate_columns(self, *args):
        try:
            padding = _padding_list(self.padding)
            spacing = _spacing_list(self.spacing)
            if self.width > 0 and abs(self.width - self._last_width) > dp(10):
                available_width = self.width - (padding[0] + padding[2])

                max_cols = max(
                    1, int(available_width / (self.min_card_width + spacing[0]))
                )

                card_width = (
                    available_width - ((max_cols - 1) * spacing[0])
                ) / max_cols

                if card_width > self.max_card_width:
                    max_cols = max(
                        1,
                        int(available_width / (self.max_card_width + spacing[0])),
                    )
                    card_width = min(
                        self.max_card_width,
                        (available_width - ((max_cols - 1) * spacing[0])) / max_cols,
                    )

                if (
                    max_cols != self._cached_cols
                    or abs(self._last_card_width - card_width) > 1
                ):
                    self.cols = max_cols
                    self._cached_cols = max_cols
                    self._last_width = self.width
                    self._last_card_width = card_width

                    for child in self.children:
                        child.size_hint_x = None
                        child.width = card_width

                    Clock.schedule_once(lambda dt: self.do_layout(), 0)
        except Exception as exc:
            logger.warning("Error recalculating columns: %s", exc)

    def add_widget(self, widget, *args, **kwargs):
        super().add_widget(widget, *args, **kwargs)
        if hasattr(self, "_cached_cols"):
            padding = _padding_list(self.padding)
            spacing = _spacing_list(self.spacing)
            available_width = self.width - (padding[0] + padding[2])
            if available_width > 0 and self._cached_cols > 0:
                card_width = (
                    available_width - ((self._cached_cols - 1) * spacing[0])
                ) / self._cached_cols
                widget.size_hint_x = None
                widget.width = min(card_width, self.max_card_width)


__all__ = ["ResponsiveGridLayout"]
