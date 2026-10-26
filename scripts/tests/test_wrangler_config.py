"""Tests for the tracked src/backend/wrangler.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

WRANGLER_TOML = Path(__file__).resolve().parents[2] / "src" / "backend" / "wrangler.toml"

# The desktop app's default OAuth callback: src/frontend/auth/backend_auth.py
# builds it from 127.0.0.1 and OAUTH_CALLBACK_PORT (default 8080).
DESKTOP_CALLBACK_URI = "http://127.0.0.1:8080/callback"

# Alternate SPOTIBYE_OAUTH_PORT values registered in the Spotify app.
ALTERNATE_CALLBACK_URIS = [
    f"http://127.0.0.1:{port}/callback"
    for port in (5000, 5001, 5002, 5003, 8001, 8101, 8202, 8303, 8888)
]


def _allowed_redirect_uris(env: str) -> list[str]:
    config = tomllib.loads(WRANGLER_TOML.read_text(encoding="utf-8"))
    raw = config["env"][env]["vars"]["ALLOWED_REDIRECT_URIS"]
    return [uri.strip() for uri in raw.split(",") if uri.strip()]


def test_production_allows_desktop_callback() -> None:
    assert DESKTOP_CALLBACK_URI in _allowed_redirect_uris("production")


def test_development_allows_desktop_callback() -> None:
    assert DESKTOP_CALLBACK_URI in _allowed_redirect_uris("development")


def test_every_environment_allows_the_alternate_callback_ports() -> None:
    for env in ("development", "production"):
        allowed = _allowed_redirect_uris(env)
        missing = [uri for uri in ALTERNATE_CALLBACK_URIS if uri not in allowed]
        assert not missing, f"{env} is missing {missing}"


def test_production_keeps_the_web_callback() -> None:
    assert "https://app.spotibye.com" in _allowed_redirect_uris("production")
