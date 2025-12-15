"""Backend configuration for frontend integration with Cloudflare Workers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

# Backend API configuration
BACKEND_URL: Final[str] = os.environ.get("SPOTIBYE_BACKEND_URL", "https://spotibye-backend-development.kevin-grizzard.workers.dev")
PRODUCTION_BACKEND_URL: Final[str] = os.environ.get("SPOTIBYE_PRODUCTION_BACKEND_URL", "https://spotibye-api.your-domain.com")

# Determine which backend URL to use
USE_PRODUCTION: Final[bool] = os.environ.get("SPOTIBYE_USE_PRODUCTION", "false").lower() == "true"
CURRENT_BACKEND_URL: Final[str] = PRODUCTION_BACKEND_URL if USE_PRODUCTION else BACKEND_URL

# API timeout configuration
API_TIMEOUT: Final[int] = int(os.environ.get("SPOTIBYE_API_TIMEOUT", "30"))
ANALYSIS_TIMEOUT: Final[int] = int(os.environ.get("SPOTIBYE_ANALYSIS_TIMEOUT", "300"))  # 5 minutes

# OAuth configuration for backend integration
OAUTH_CALLBACK_PORT: Final[int] = int(os.environ.get("SPOTIBYE_OAUTH_PORT", "8080"))
OAUTH_TIMEOUT: Final[int] = int(os.environ.get("SPOTIBYE_OAUTH_TIMEOUT", "300"))  # 5 minutes

# Cache configuration
CACHE_DIR: Final[Path] = Path(os.path.expanduser("~")) / ".spotibye_cache"
TOKEN_CACHE_PATH: Final[str] = str(CACHE_DIR / "backend_token.json")

# Export configuration
EXPORT_DIR: Final[str] = os.environ.get("SPOTIBYE_EXPORT_DIR", os.path.expanduser("~/Downloads"))
TEMP_DIR: Final[str] = os.environ.get("SPOTIBYE_TEMP_DIR", "/tmp/spotibye_exports")

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
    ENABLE_ANALYSIS: Final[bool] = os.environ.get("SPOTIBYE_ENABLE_ANALYSIS", "true").lower() == "true"
    ENABLE_EXPORT: Final[bool] = os.environ.get("SPOTIBYE_ENABLE_EXPORT", "true").lower() == "true"
    ENABLE_CACHING: Final[bool] = os.environ.get("SPOTIBYE_ENABLE_CACHING", "true").lower() == "true"
    ENABLE_OFFLINE_MODE: Final[bool] = os.environ.get("SPOTIBYE_ENABLE_OFFLINE", "false").lower() == "true"
    
    # Debug flags
    DEBUG_NETWORK: Final[bool] = os.environ.get("SPOTIBYE_DEBUG_NETWORK", "false").lower() == "true"
    DEBUG_AUTH: Final[bool] = os.environ.get("SPOTIBYE_DEBUG_AUTH", "false").lower() == "true"

# Performance settings
class PerformanceSettings:
    """Performance settings for backend integration."""
    
    # Request batching
    BATCH_SIZE: Final[int] = int(os.environ.get("SPOTIBYE_BATCH_SIZE", "50"))
    MAX_CONCURRENT_REQUESTS: Final[int] = int(os.environ.get("SPOTIBYE_MAX_CONCURRENT", "3"))
    
    # Retry settings
    MAX_RETRIES: Final[int] = int(os.environ.get("SPOTIBYE_MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR: Final[float] = float(os.environ.get("SPOTIBYE_RETRY_BACKOFF", "1.0"))
    
    # Polling settings
    ANALYSIS_POLL_INTERVAL: Final[float] = float(os.environ.get("SPOTIBYE_ANALYSIS_POLL_INTERVAL", "2.0"))
    MAX_POLL_INTERVAL: Final[float] = float(os.environ.get("SPOTIBYE_MAX_POLL_INTERVAL", "10.0"))

# Ensure directories exist
def ensure_directories() -> None:
    """Create necessary directories if they don't exist."""
    CACHE_DIR.mkdir(exist_ok=True)
    Path(TOKEN_CACHE_PATH).parent.mkdir(exist_ok=True)
    Path(EXPORT_DIR).mkdir(exist_ok=True)
    Path(TEMP_DIR).mkdir(exist_ok=True)

# Configuration validation
def validate_config() -> list[str]:
    """
    Validate configuration and return list of issues.
    
    Returns:
        List of configuration issues
    """
    issues = []
    
    # Check backend URL
    if not CURRENT_BACKEND_URL:
        issues.append("Backend URL is not configured")
    elif not CURRENT_BACKEND_URL.startswith(('http://', 'https://')):
        issues.append("Backend URL must start with http:// or https://")
    
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
        Path(EXPORT_DIR).mkdir(exist_ok=True)
    except Exception as e:
        issues.append(f"Cannot create export directory: {e}")
    
    return issues

# Get configuration summary
def get_config_summary() -> dict:
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
        }
    }

# Initialize directories on import
ensure_directories()

# Export configuration constants
__all__ = [
    "CURRENT_BACKEND_URL",
    "BACKEND_URL", 
    "PRODUCTION_BACKEND_URL",
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
    "ensure_directories",
    "validate_config",
    "get_config_summary",
]
