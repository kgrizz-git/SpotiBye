"""Shared mutable application state."""

from __future__ import annotations

from typing import Any, Dict, Optional

# OAuth/authentication shared data
auth_token: Optional[Dict[str, Any]] = None
auth_server = None
force_fresh_oauth: bool = False  # Flag to force fresh OAuth after logout

# Export job tracking
current_export_job: Optional[Dict[str, Any]] = None

# Analysis task tracking
analysis_cache: Dict[str, Any] = {}
active_analysis_tasks: Dict[str, Any] = {}
