"""Cache Explorer Adapter - Backend-aware cache explorer integration."""

from __future__ import annotations

from typing import Any


from spotify_playlist_exporter_v2.logging_config import logger

try:
    from ..ui.backend_cache_explorer import BackendCacheExplorerPopup
    from ..config.backend_config import BackendConfig

    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False
    logger.debug("Backend cache explorer not available")

from spotify_playlist_exporter_v2.ui.cache_explorer import CacheExplorerPopup


class CacheExplorerAdapter:
    """Adapter that provides appropriate cache explorer based on backend availability."""

    def __init__(self):
        self.backend_available = BACKEND_AVAILABLE
        self.backend_config = None

        if self.backend_available:
            try:
                self.backend_config = BackendConfig()
                logger.info("Backend cache explorer adapter initialized")
            except Exception as exc:
                logger.warning("Backend config unavailable: %s", exc)
                self.backend_available = False

    def get_cache_explorer(self) -> CacheExplorerPopup:
        """Get appropriate cache explorer based on backend availability."""
        if self.backend_available and self.backend_config:
            try:
                return BackendCacheExplorerPopup()
            except Exception as exc:
                logger.error("Failed to create backend cache explorer: %s", exc)
                # Fallback to standard cache explorer
                logger.info("Falling back to standard cache explorer")

        # Return standard cache explorer
        return CacheExplorerPopup()

    def is_backend_enabled(self) -> bool:
        """Check if backend cache explorer is enabled."""
        return self.backend_available and self.backend_config is not None

    def get_cache_status_info(self) -> dict[str, Any]:
        """Get cache status information for display."""
        info = {
            "local_cache": True,
            "backend_cache": self.is_backend_enabled(),
            "backend_url": None,
        }

        if self.backend_config:
            info["backend_url"] = self.backend_config.backend_url

        return info


# Global instance for easy access
_cache_explorer_adapter = None


def get_cache_explorer_adapter() -> CacheExplorerAdapter:
    """Get global cache explorer adapter instance."""
    global _cache_explorer_adapter
    if _cache_explorer_adapter is None:
        _cache_explorer_adapter = CacheExplorerAdapter()
    return _cache_explorer_adapter


def create_cache_explorer() -> CacheExplorerPopup:
    """Create appropriate cache explorer popup."""
    adapter = get_cache_explorer_adapter()
    return adapter.get_cache_explorer()
