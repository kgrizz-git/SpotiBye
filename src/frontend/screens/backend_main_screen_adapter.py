"""Backend integration adapter for existing MainScreen to use backend services."""

from __future__ import annotations

from typing import Optional

from ..services.backend_client import BackendClient
from ..services.reccobeats_backend import ReccoBeatsBackendService
from .adapter_mixins.core import BackendMainScreenAdapterCore
from .adapter_mixins.playlists import PlaylistsMixin
from .adapter_mixins.tracks import TracksMixin
from .adapter_mixins.analysis import AnalysisMixin
from .adapter_mixins.exports import ExportsMixin
from .adapter_mixins.exports_resumable import ExportsResumableMixin
from .adapter_mixins.exports_download import ExportsDownloadMixin
from .adapter_mixins.jobs import ExportJobsMixin
from .adapter_mixins.utilities import UtilitiesMixin


class BackendMainScreenAdapter(
    BackendMainScreenAdapterCore,
    PlaylistsMixin,
    TracksMixin,
    AnalysisMixin,
    ExportsMixin,
    ExportsResumableMixin,
    ExportsDownloadMixin,
    ExportJobsMixin,
    UtilitiesMixin,
):
    """Adapter to integrate backend services with existing MainScreen."""

    def __init__(self, backend_client: Optional[BackendClient] = None):
        BackendMainScreenAdapterCore.__init__(self, backend_client)


# Factory function
def create_backend_adapter(
    backend_client: Optional[BackendClient] = None,
) -> BackendMainScreenAdapter:
    """
    Create backend adapter instance.

    Args:
        backend_client: Optional backend client

    Returns:
        Backend adapter instance
    """
    return BackendMainScreenAdapter(backend_client)


# Legacy compatibility functions
def get_reccobeats_api():
    """Legacy compatibility function - returns backend service."""
    return ReccoBeatsBackendService()


def create_spotify_client_with_refresh(token_info: dict | None):
    """Legacy compatibility function - not used in backend mode."""
    return None


__all__ = [
    "BackendMainScreenAdapter",
    "create_backend_adapter",
    "get_reccobeats_api",
    "create_spotify_client_with_refresh",
]
