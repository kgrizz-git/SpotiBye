"""Per-session guard for automatic enrichment coverage miss-fill retries."""

from __future__ import annotations

from typing import Set


class EnrichmentRetryLedger:
    """Tracks automatic miss-fill attempts for the current frontend app session."""

    def __init__(self) -> None:
        self._attempted_keys: Set[str] = set()

    def has_attempted(self, ledger_key: str) -> bool:
        return ledger_key in self._attempted_keys

    def record_attempt(self, ledger_key: str) -> None:
        self._attempted_keys.add(ledger_key)

    def clear(self) -> None:
        self._attempted_keys.clear()


_ledger: EnrichmentRetryLedger | None = None


def get_enrichment_retry_ledger() -> EnrichmentRetryLedger:
    global _ledger
    if _ledger is None:
        _ledger = EnrichmentRetryLedger()
    return _ledger


def reset_enrichment_retry_ledger() -> None:
    """Test helper and manual refresh bypass hook."""
    get_enrichment_retry_ledger().clear()


__all__ = [
    "EnrichmentRetryLedger",
    "get_enrichment_retry_ledger",
    "reset_enrichment_retry_ledger",
]
