"""Backend configuration for frontend integration with Cloudflare Workers."""

from __future__ import annotations

import json
import os
import time
from ipaddress import ip_address
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Final
from urllib.parse import urlparse

from ...shared.logging_config import logger


def is_valid_backend_url(url: str) -> bool:
    """Return whether ``url`` has a usable HTTP(S) backend URL shape.

    The check is intentionally local: endpoint reachability is verified by the
    selector, after the user has chosen a URL.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if port is not None and not 0 < port <= 65535:
        return False
    if parsed.hostname is None or parsed.hostname == "":
        return False
    try:
        ip_address(parsed.hostname)
        return True
    except ValueError:
        # A DNS hostname must be fully qualified (e.g. ``example.com``) or
        # the explicit local-development loopback hostname. This avoids
        # silently accepting accidental one-word URLs such as ``https://x``.
        hostname = parsed.hostname
        return hostname == "localhost" or (
            "." in hostname
            and not hostname.startswith(".")
            and not hostname.endswith(".")
        )


def _configured_backend_url(variable_name: str) -> str | None:
    """Return a valid, explicitly configured backend URL, else ``None``.

    Endpoint variables deliberately have no source-code fallback. This keeps a
    packaged app from selecting an account-specific Worker or localhost before
    its user has made a choice.
    """
    value = os.environ.get(variable_name, "").strip().rstrip("/")
    return value if is_valid_backend_url(value) else None


# Backend API configuration. Ordinary, development, and production endpoints
# are opt-in process settings; absence means the startup selector begins in
# its unconfigured Custom state. Localhost is only an explicit selector preset.
BACKEND_URL: Final[str | None] = _configured_backend_url("SPOTIBYE_BACKEND_URL")
PRODUCTION_BACKEND_URL: Final[str | None] = _configured_backend_url(
    "SPOTIBYE_PRODUCTION_BACKEND_URL"
)
DEV_BACKEND_URL: Final[str | None] = _configured_backend_url("SPOTIBYE_DEV_BACKEND_URL")
# Intentional loopback default for local Cloudflare Worker
LOCALHOST_BACKEND_URL: Final[str] = (
    _configured_backend_url("SPOTIBYE_LOCALHOST_BACKEND_URL")
    or "http://localhost:8787"  # NOSONAR(S5332)
)

# Determine which backend URL to use
USE_PRODUCTION: Final[bool] = (
    os.environ.get("SPOTIBYE_USE_PRODUCTION", "false").lower() == "true"
)
CURRENT_BACKEND_URL: Final[str | None] = (
    PRODUCTION_BACKEND_URL if USE_PRODUCTION else BACKEND_URL
)

# Feature flag for startup backend selector UI
ENABLE_BACKEND_SELECTOR: Final[bool] = (
    os.environ.get("SPOTIBYE_ENABLE_BACKEND_SELECTOR", "true").lower() == "true"
)

# API timeout configuration
API_TIMEOUT: Final[int] = int(os.environ.get("SPOTIBYE_API_TIMEOUT", "30"))
ANALYSIS_TIMEOUT: Final[int] = int(
    os.environ.get("SPOTIBYE_ANALYSIS_TIMEOUT", "300")
)  # 5 minutes

# OAuth configuration for backend integration
OAUTH_CALLBACK_PORT: Final[int] = int(os.environ.get("SPOTIBYE_OAUTH_PORT", "8080"))
OAUTH_TIMEOUT: Final[int] = int(
    os.environ.get("SPOTIBYE_OAUTH_TIMEOUT", "300")
)  # 5 minutes

# Cache configuration
CACHE_DIR: Final[Path] = Path(os.path.expanduser("~")) / ".spotibye_cache"
TOKEN_CACHE_PATH: Final[str] = str(CACHE_DIR / "backend_token.json")
BACKEND_SELECTION_PATH: Final[Path] = CACHE_DIR / "backend_selection.json"


def _build_backend_presets() -> dict[str, str]:
    """Build the selector's named presets from explicitly configured URLs.

    Localhost is always available as an intentional developer choice. Named
    Cloudflare presets appear only when their URL is valid and configured in
    the launch environment. Duplicate URLs are omitted so restoring a saved
    URL cannot silently select a different preset label.
    """
    presets = {"Localhost": LOCALHOST_BACKEND_URL}
    for name, url in (
        ("Cloudflare Dev", DEV_BACKEND_URL),
        ("Cloudflare Prod", PRODUCTION_BACKEND_URL),
    ):
        if url is not None and url not in presets.values():
            presets[name] = url
    return presets


# Custom is added by BackendSelectorPopup and is always available.
BACKEND_PRESETS: Final[dict[str, str]] = _build_backend_presets()

# Export configuration
EXPORT_DIR: Final[str] = os.environ.get(
    "SPOTIBYE_EXPORT_DIR", os.path.expanduser("~/Downloads")
)
# Keep staging/temp files under the user-private cache tree — never under
# world-writable ``/tmp`` (Sonar python:S5443 / CWE symlink-race risk).
TEMP_DIR: Final[str] = os.environ.get(
    "SPOTIBYE_TEMP_DIR", str(CACHE_DIR / "temp_exports")
)


# UI Configuration
class UIConstants:
    """UI metrics and constants for backend integration."""

    # Network status colors
    STATUS_CONNECTED = (0.3, 1, 0.3, 1)  # Green
    STATUS_DISCONNECTED = (1, 0.3, 0.3, 1)  # Red
    STATUS_CHECKING = (0.7, 0.7, 0.7, 1)  # Gray

    # Loading messages
    MSG_CONNECTING = "Connecting to backend..."
    MSG_AUTHENTICATING = "Authenticating..."
    MSG_LOADING_PLAYLISTS = "Loading playlists..."
    MSG_ANALYZING = "Analyzing playlist..."
    MSG_EXPORTING = "Exporting data..."

    # Error messages
    ERR_NO_CONNECTION = "Unable to connect to backend. Check your internet connection."
    ERR_AUTH_FAILED = "Authentication failed. Please try again."
    ERR_TIMEOUT = "Request timed out. Please try again."
    ERR_SERVER_ERROR = "Server error occurred. Please try again later."


# Feature flags
class FeatureFlags:
    """Feature flags for backend integration."""

    # Enable/disable features based on backend capabilities
    ENABLE_ANALYSIS: Final[bool] = (
        os.environ.get("SPOTIBYE_ENABLE_ANALYSIS", "true").lower() == "true"
    )
    ENABLE_EXPORT: Final[bool] = (
        os.environ.get("SPOTIBYE_ENABLE_EXPORT", "true").lower() == "true"
    )
    ENABLE_CACHING: Final[bool] = (
        os.environ.get("SPOTIBYE_ENABLE_CACHING", "true").lower() == "true"
    )
    ENABLE_OFFLINE_MODE: Final[bool] = (
        os.environ.get("SPOTIBYE_ENABLE_OFFLINE", "false").lower() == "true"
    )

    # Debug flags
    DEBUG_NETWORK: Final[bool] = (
        os.environ.get("SPOTIBYE_DEBUG_NETWORK", "false").lower() == "true"
    )
    DEBUG_AUTH: Final[bool] = (
        os.environ.get("SPOTIBYE_DEBUG_AUTH", "false").lower() == "true"
    )


# Performance settings
class PerformanceSettings:
    """Performance settings for backend integration."""

    # Request batching
    BATCH_SIZE: Final[int] = int(os.environ.get("SPOTIBYE_BATCH_SIZE", "50"))
    MAX_CONCURRENT_REQUESTS: Final[int] = int(
        os.environ.get("SPOTIBYE_MAX_CONCURRENT", "3")
    )

    # Retry settings
    MAX_RETRIES: Final[int] = int(os.environ.get("SPOTIBYE_MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR: Final[float] = float(
        os.environ.get("SPOTIBYE_RETRY_BACKOFF", "1.0")
    )

    # Polling settings
    ANALYSIS_POLL_INTERVAL: Final[float] = float(
        os.environ.get("SPOTIBYE_ANALYSIS_POLL_INTERVAL", "2.0")
    )
    MAX_POLL_INTERVAL: Final[float] = float(
        os.environ.get("SPOTIBYE_MAX_POLL_INTERVAL", "10.0")
    )


# Ensure directories exist
def _ensure_private_dir(path: Path) -> None:
    """Create ``path`` (and parents) with owner-only permissions when possible."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        # Windows / restricted filesystems may ignore or reject Unix modes.
        pass


def ensure_directories() -> None:
    """Create necessary directories if they don't exist."""
    _ensure_private_dir(CACHE_DIR)
    _ensure_private_dir(Path(TOKEN_CACHE_PATH).parent)
    Path(EXPORT_DIR).expanduser().mkdir(exist_ok=True)
    _ensure_private_dir(Path(TEMP_DIR).expanduser())


def get_default_backend_url() -> str | None:
    """Return the explicitly configured startup URL, if one exists."""
    return CURRENT_BACKEND_URL


def save_backend_url(url: str) -> bool:
    """Persist selected backend URL for future launches."""
    if not is_valid_backend_url(url):
        return False

    temporary_path: Path | None = None
    try:
        _ensure_private_dir(BACKEND_SELECTION_PATH.parent)
        payload = {
            "backend_url": url.rstrip("/"),
            "saved_at": int(time.time()),
        }
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=BACKEND_SELECTION_PATH.parent,
            prefix=f".{BACKEND_SELECTION_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as selection_file:
            temporary_path = Path(selection_file.name)
            json.dump(payload, selection_file, indent=2)
            selection_file.write("\n")
        os.replace(temporary_path, BACKEND_SELECTION_PATH)
        return True
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Unable to save backend selection: %s", exc)
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Unable to remove temporary backend selection: %s", exc)


def get_saved_backend_url() -> str | None:
    """Load previously selected backend URL if available."""
    try:
        if not BACKEND_SELECTION_PATH.exists():
            return None

        with open(BACKEND_SELECTION_PATH, "r", encoding="utf-8") as selection_file:
            payload = json.load(selection_file)

        if not isinstance(payload, dict):
            logger.warning("Ignoring backend selection with an invalid JSON shape")
            return None
        url = payload.get("backend_url")
        if not isinstance(url, str):
            logger.warning("Ignoring backend selection with a non-string URL")
            return None
        url = url.rstrip("/")
        if is_valid_backend_url(url):
            return url
        logger.warning("Ignoring backend selection with an invalid URL")
        return None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Unable to load backend selection: %s", exc)
        return None


def resolve_startup_backend_url() -> str | None:
    """Resolve startup URL, preferring a saved choice over environment config.

    ``None`` is a supported result. It instructs the application to wait for a
    user selection rather than creating a localhost client automatically.
    """
    return get_saved_backend_url() or get_default_backend_url()


# Configuration validation
def validate_config() -> list[str]:
    """
    Validate configuration and return list of issues.

    Returns:
        List of configuration issues
    """
    issues = []

    # A backend URL is selected interactively at startup, so an absent
    # environment default is valid. Configured values were shape-checked when
    # this module loaded.

    # Check timeouts
    if API_TIMEOUT <= 0:
        issues.append("API timeout must be positive")
    if ANALYSIS_TIMEOUT <= 0:
        issues.append("Analysis timeout must be positive")

    # Check directories
    try:
        CACHE_DIR.mkdir(exist_ok=True)
    except Exception as e:
        issues.append(f"Cannot create cache directory: {e}")

    try:
        Path(EXPORT_DIR).expanduser().mkdir(exist_ok=True)
    except Exception as e:
        issues.append(f"Cannot create export directory: {e}")

    return issues


# Get configuration summary
def get_config_summary() -> dict[str, Any]:
    """
    Get configuration summary for debugging.

    Returns:
        Configuration summary dictionary
    """
    return {
        "backend_url": CURRENT_BACKEND_URL,
        "use_production": USE_PRODUCTION,
        "api_timeout": API_TIMEOUT,
        "analysis_timeout": ANALYSIS_TIMEOUT,
        "oauth_port": OAUTH_CALLBACK_PORT,
        "cache_dir": str(CACHE_DIR),
        "export_dir": EXPORT_DIR,
        "temp_dir": TEMP_DIR,
        "feature_flags": {
            "analysis": FeatureFlags.ENABLE_ANALYSIS,
            "export": FeatureFlags.ENABLE_EXPORT,
            "caching": FeatureFlags.ENABLE_CACHING,
            "offline_mode": FeatureFlags.ENABLE_OFFLINE_MODE,
        },
        "debug_flags": {
            "network": FeatureFlags.DEBUG_NETWORK,
            "auth": FeatureFlags.DEBUG_AUTH,
        },
    }


# Initialize directories on import
ensure_directories()

# Export configuration constants
__all__ = [
    "CURRENT_BACKEND_URL",
    "BACKEND_URL",
    "LOCALHOST_BACKEND_URL",
    "PRODUCTION_BACKEND_URL",
    "DEV_BACKEND_URL",
    "BACKEND_PRESETS",
    "BACKEND_SELECTION_PATH",
    "ENABLE_BACKEND_SELECTOR",
    "API_TIMEOUT",
    "ANALYSIS_TIMEOUT",
    "OAUTH_CALLBACK_PORT",
    "OAUTH_TIMEOUT",
    "CACHE_DIR",
    "TOKEN_CACHE_PATH",
    "EXPORT_DIR",
    "TEMP_DIR",
    "UIConstants",
    "FeatureFlags",
    "PerformanceSettings",
    "is_valid_backend_url",
    "get_default_backend_url",
    "save_backend_url",
    "get_saved_backend_url",
    "resolve_startup_backend_url",
    "ensure_directories",
    "validate_config",
    "get_config_summary",
]
