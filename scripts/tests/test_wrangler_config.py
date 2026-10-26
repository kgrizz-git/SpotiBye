"""Tests for the tracked src/backend/wrangler.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

WRANGLER_TOML = Path(__file__).resolve().parents[2] / "src" / "backend" / "wrangler.toml"

# The desktop app's default OAuth callback: src/frontend/auth/backend_auth.py
# builds it from 127.0.0.1 and OAUTH_CALLBACK_PORT (default 8080).
DESKTOP_CALLBACK_URI = "http://127.0.0.1:8080/callback"


def _allowed_redirect_uris(env: str) -> list[str]:
    config = tomllib.loads(WRANGLER_TOML.read_text())
    raw = config["env"][env]["vars"]["ALLOWED_REDIRECT_URIS"]
    return [uri.strip() for uri in raw.split(",") if uri.strip()]


def test_production_allows_desktop_callback() -> None:
    assert DESKTOP_CALLBACK_URI in _allowed_redirect_uris("production")


def test_development_allows_desktop_callback() -> None:
    assert DESKTOP_CALLBACK_URI in _allowed_redirect_uris("development")
