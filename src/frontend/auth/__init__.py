"""Frontend authentication module."""

from .backend_auth import BackendAuthenticator, get_authenticator

__all__ = [
    "BackendAuthenticator",
    "get_authenticator",
    "BackendLoginScreen",
    "create_backend_login_screen",
]


def __getattr__(name: str):
    """Lazy load kivy-dependent components to avoid import errors when kivy is unavailable."""
    if name == "BackendLoginScreen":
        from .backend_login_screen import BackendLoginScreen

        return BackendLoginScreen
    if name == "create_backend_login_screen":
        from .backend_login_screen import create_backend_login_screen

        return create_backend_login_screen
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
