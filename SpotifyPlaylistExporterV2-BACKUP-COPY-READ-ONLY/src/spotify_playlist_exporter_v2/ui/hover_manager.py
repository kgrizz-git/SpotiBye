"""Global hover manager for playlist cards."""

from __future__ import annotations

from typing import List, Optional

from kivy.clock import Clock
from kivy.core.window import Window

from ..logging_config import logger


class PlaylistHoverManager:
    """Global manager for playlist card hover detection."""

    def __init__(self):
        self.cards: List = []
        self.current_hovered_card = None
        self.hover_timer: Optional = None
        self.start_checking()

    def register_card(self, card) -> None:
        if card not in self.cards:
            self.cards.append(card)

    def unregister_card(self, card) -> None:
        if card in self.cards:
            self.cards.remove(card)

        if not self.cards and self.hover_timer:
            self.hover_timer.cancel()
            self.hover_timer = None

    def start_checking(self) -> None:
        if not self.hover_timer:
            self.hover_timer = Clock.schedule_interval(self.check_hover, 0.15)

    def check_hover(self, dt) -> None:
        try:
            if not hasattr(Window, "mouse_pos") or not self.cards:
                return

            mouse_pos = Window.mouse_pos
            if not isinstance(mouse_pos, (list, tuple)) or len(mouse_pos) < 2:
                return

            mouse_x, mouse_y = mouse_pos
            hovered_card = None

            visible_cards = []
            for card in self.cards[:]:
                try:
                    if (
                        hasattr(card, "is_visible_in_window")
                        and card.is_visible_in_window()
                    ):
                        visible_cards.append(card)
                except Exception:
                    self.cards.remove(card)

            for card in visible_cards:
                try:
                    bounds = card.get_window_bounds()
                    if bounds:
                        if (
                            bounds["x"] <= mouse_x <= bounds["right"]
                            and bounds["y"] <= mouse_y <= bounds["top"]
                        ):
                            hovered_card = card
                            break
                except Exception as exc:
                    logger.warning("Error checking card bounds: %s", exc)

            if hovered_card != self.current_hovered_card:
                if self.current_hovered_card:
                    self.current_hovered_card.on_hover_end()

                if hovered_card:
                    hovered_card.on_hover_start(mouse_pos)

                self.current_hovered_card = hovered_card

        except Exception as exc:
            logger.warning("Error in hover manager check: %s", exc)


__all__ = ["PlaylistHoverManager"]
