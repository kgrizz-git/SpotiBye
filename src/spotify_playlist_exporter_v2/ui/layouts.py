"""Reusable layout widgets for the Spotify exporter UI."""

from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.gridlayout import GridLayout

from ..logging_config import logger


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

        # Card sizing constraints
        self.min_card_width = dp(162)  # Minimum width for cards
        self.max_card_width = dp(210)  # Maximum width for cards
        self._last_width = 0
        self._last_card_width = self.min_card_width
        self._cached_cols = 1

    def recalculate_columns(self, *args):
        try:
            if self.width > 0 and abs(self.width - self._last_width) > dp(10):
                available_width = self.width - (self.padding[0] + self.padding[2])

                # Calculate maximum possible columns based on min width
                max_cols = max(
                    1, int(available_width / (self.min_card_width + self.spacing[0]))
                )

                # Calculate actual width per card
                card_width = (
                    available_width - ((max_cols - 1) * self.spacing[0])
                ) / max_cols

                # If cards would be too wide, reduce columns
                if card_width > self.max_card_width:
                    max_cols = max(
                        1,
                        int(available_width / (self.max_card_width + self.spacing[0])),
                    )
                    card_width = min(
                        self.max_card_width,
                        (available_width - ((max_cols - 1) * self.spacing[0]))
                        / max_cols,
                    )

                if (
                    max_cols != self._cached_cols
                    or abs(self._last_card_width - card_width) > 1
                ):
                    self.cols = max_cols
                    self._cached_cols = max_cols
                    self._last_width = self.width
                    self._last_card_width = card_width

                    # Update children's size hints
                    for child in self.children:
                        child.size_hint_x = None
                        child.width = card_width

                    Clock.schedule_once(lambda dt: self.do_layout(), 0)
        except Exception as exc:
            logger.warning("Error recalculating columns: %s", exc)

    def add_widget(self, widget, *args, **kwargs):
        super().add_widget(widget, *args, **kwargs)
        # When a widget is added, update its size hint based on current layout
        if hasattr(self, "_cached_cols"):
            available_width = self.width - (self.padding[0] + self.padding[2])
            if available_width > 0 and self._cached_cols > 0:
                card_width = (
                    available_width - ((self._cached_cols - 1) * self.spacing[0])
                ) / self._cached_cols
                widget.size_hint_x = None
                widget.width = min(card_width, self.max_card_width)


__all__ = ["ResponsiveGridLayout"]
