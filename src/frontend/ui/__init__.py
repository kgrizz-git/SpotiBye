"""Frontend UI helpers and popup components."""

__all__ = [
    "BackendSelectorPopup",
]


def __getattr__(name: str):
    """Lazy load kivy-dependent components to avoid import errors when kivy is unavailable."""
    if name == "BackendSelectorPopup":
        from .backend_selector_popup import BackendSelectorPopup

        return BackendSelectorPopup
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
