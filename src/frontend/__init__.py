"""Frontend module for SpotiBye backend integration."""

from .services.backend_client import BackendClient, get_backend_client
from .auth.backend_auth import BackendAuthenticator, get_authenticator
from .auth.backend_login_screen import BackendLoginScreen, create_backend_login_screen
from .utils.network_utils import NetworkError, ConnectionError, TimeoutError
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
    "TimeoutError",
    "CURRENT_BACKEND_URL",
    "UIConstants",
    "FeatureFlags",
]
