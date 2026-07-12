from __future__ import annotations

from src.frontend.services.enrichment_errors import has_retriable_reccobeats_errors


def test_hard_reccobeats_errors_are_retriable() -> None:
    assert has_retriable_reccobeats_errors(
        {
            "errors": [
                {
                    "source": "reccobeats:audio-features",
                    "message": "HTTP 429: rate limited",
                }
            ]
        }
    )


def test_reccobeats_coverage_warning_is_not_retriable() -> None:
    assert not has_retriable_reccobeats_errors(
        {
            "errors": [
                {
                    "source": "reccobeats:coverage",
                    "message": "Audio features available for 1 of 2 tracks.",
                }
            ]
        }
    )


def test_non_reccobeats_errors_are_not_retriable() -> None:
    assert not has_retriable_reccobeats_errors(
        {
            "errors": [
                {
                    "source": "spotify:artists",
                    "message": "HTTP 403",
                }
            ]
        }
    )
