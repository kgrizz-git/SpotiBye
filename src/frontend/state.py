"""Shared mutable state for the backend-integrated frontend."""

from __future__ import annotations

from typing import Any, Dict, Optional

current_export_job: Optional[Dict[str, Any]] = None
