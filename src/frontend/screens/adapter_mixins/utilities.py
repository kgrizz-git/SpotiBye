"""Utility mixin for BackendMainScreenAdapter: network, cache, auth."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ....shared.logging_config import logger


class UtilitiesMixin:
    """Network status, cache management, and authentication helpers."""

    def get_network_status(self) -> Dict[str, Any]:
        """Get current network status."""
        return {
            "connected": self.network_monitor.is_connected(),
            "message": self.network_monitor.get_status_message(),
        }

    def refresh_connection(self) -> None:
        """Refresh network connection status."""
        self.network_monitor.force_check()

    def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """
        Clear cache.

        Args:
            cache_type: Type of cache to clear ('playlists', 'tracks', 'analysis', 'export', or None for all)
        """
        try:
            if cache_type == "playlists":
                self.cache_manager.clear_cache("playlists.json")
            elif cache_type == "tracks":
                self.cache_manager.clear_cache("tracks_*.json")
            elif cache_type == "analysis":
                self.cache_manager.clear_cache("analysis_*.json")
            elif cache_type == "export":
                self.cache_manager.clear_cache("export_*.json")
            else:
                self.cache_manager.clear_cache()

            logger.info(f"Cleared {cache_type or 'all'} cache")

        except Exception as e:
            logger.error("Error clearing cache: %s", e)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_cache_stats()

    def is_authenticated(self) -> bool:
        """Check if authenticated with backend."""
        return self.backend_client.is_authenticated()

    def logout(self) -> None:
        """Logout and clear authentication state."""
        try:
            # Clear backend client token
            self.backend_client.clear_auth_token()

            # Clear auth token cache
            self.cache_manager.clear_auth_token()

            # Clear all data cache
            self.cache_manager.clear_cache()

            logger.info("Backend logout completed")

        except Exception as e:
            logger.error("Error during logout: %s", e)
