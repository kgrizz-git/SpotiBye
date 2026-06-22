"""Frontend module for SpotiBye backend integration."""

from .services.backend_client import BackendClient, get_backend_client
from .auth.backend_auth import BackendAuthenticator, get_authenticator
from .utils.network_utils import NetworkError, ConnectionError, NetworkTimeoutError
from .config.backend_config import CURRENT_BACKEND_URL, UIConstants, FeatureFlags

__all__ = [
    "BackendClient",
    "get_backend_client",
    "BackendAuthenticator",
    "get_authenticator",
    "BackendLoginScreen",
    "create_backend_login_screen",
    "NetworkError",
    "ConnectionError",
    "NetworkTimeoutError",
    "CURRENT_BACKEND_URL",
    "UIConstants",
    "FeatureFlags",
]


def __getattr__(name: str):
    """Lazy load kivy-dependent components to avoid import errors when kivy is unavailable."""
    if name == "BackendLoginScreen":
        from .auth.backend_login_screen import BackendLoginScreen

        return BackendLoginScreen
    if name == "create_backend_login_screen":
        from .auth.backend_login_screen import create_backend_login_screen

        return create_backend_login_screen
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
