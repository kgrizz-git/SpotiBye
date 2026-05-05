"""Shared export-domain exception hierarchy."""

from __future__ import annotations


class ExportError(Exception):
    """Base exception for export-related errors."""

    pass


class InsufficientDiskSpaceError(ExportError):
    """Raised when there's not enough disk space for export."""

    def __init__(self, free_space: int, required_space: int):
        self.free_space = free_space
        self.required_space = required_space
        super().__init__(
            f"Insufficient disk space: {required_space // (1024*1024)}MB required, "
            f"{free_space // (1024*1024)}MB available"
        )


class PermissionError(ExportError):
    """Raised when there are file permission issues during export."""

    pass


class NetworkError(ExportError):
    """Raised when network-related errors occur during export."""

    pass


class ExportFormatError(ExportError):
    """Raised when there are format-specific export errors."""

    pass


class ValidationError(ExportError):
    """Raised when export parameters fail validation."""

    pass
