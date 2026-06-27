"""Core adapter infrastructure: init, callbacks, error formatting, transient retry."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from ....shared.logging_config import logger
from ...caching.backend_cache import get_cache_manager
from ...services.backend_client import BackendAPIError, BackendClient
from ...services.reccobeats_backend import ReccoBeatsBackendService
from ...utils.network_utils import NetworkStatusMonitor


class BackendMainScreenAdapterCore:
    """Shared state and helpers for BackendMainScreenAdapter mixins."""

    def __init__(self, backend_client: Optional[BackendClient] = None):
        """
        Initialize backend adapter.

        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client or BackendClient()
        self.reccobeats_service = ReccoBeatsBackendService(self.backend_client)
        self.cache_manager = get_cache_manager()
        self.network_monitor = NetworkStatusMonitor(self.backend_client)

        # Callbacks for UI updates
        self.playlists_loaded_callback: Optional[Callable[..., Any]] = None
        self.error_callback: Optional[Callable[..., Any]] = None
        self.progress_callback: Optional[Callable[..., Any]] = None
        self._export_circuit_open_until: float = 0.0
        self._export_circuit_reason: str = ""

    def set_callbacks(
        self,
        playlists_loaded: Optional[Callable[..., Any]] = None,
        error: Optional[Callable[..., Any]] = None,
        progress: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Set UI update callbacks.

        Args:
            playlists_loaded: Callback for when playlists are loaded
            error: Callback for error messages
            progress: Callback for progress updates
        """
        self.playlists_loaded_callback = playlists_loaded
        self.error_callback = error
        self.progress_callback = progress

    def set_trace_id(self, trace_id: Optional[str]) -> None:
        """Set per-export trace ID propagated by backend client."""
        self.backend_client.set_trace_id(trace_id)

    def _emit_progress(self, message: str) -> None:
        """Send progress to UI and terminal logs."""
        # MainScreen logs progress with trace context; avoid duplicate adapter-side logs.
        if self.progress_callback:
            self.progress_callback(message)

    def _format_backend_api_error(
        self, error: BackendAPIError, fallback_prefix: str
    ) -> str:
        """Build a user-visible message with backend error code/message/request id when available."""
        status = (
            f"HTTP {error.status_code}"
            if error.status_code is not None
            else "HTTP error"
        )
        message = str(error)

        error_payload = {}
        if isinstance(error.response_data, dict):
            maybe_error = error.response_data.get("error")
            if isinstance(maybe_error, dict):
                error_payload = maybe_error

        code = error_payload.get("code")
        request_id = error_payload.get("request_id")
        details_payload = (
            error_payload.get("details")
            if isinstance(error_payload.get("details"), dict)
            else {}
        )

        source = "backend" if error.status_code is not None else "transport"
        if isinstance(error.response_data, dict):
            source = str(error.response_data.get("origin", source))

        upstream = details_payload.get("upstream")
        upstream_status = details_payload.get("upstream_status")

        parts = [fallback_prefix, status]
        parts.append(f"source={source}")
        if code:
            parts.append(f"code={code}")
        if upstream:
            parts.append(f"upstream={upstream}")
        if upstream_status:
            parts.append(f"upstream_status={upstream_status}")
        parts.append(message)
        if request_id:
            parts.append(f"request_id={request_id}")

        return " | ".join(parts)

    def _run_with_transient_retry(
        self,
        operation_name: str,
        func: Callable[..., Any],
        max_attempts: int = 4,
        base_delay: float = 1.0,
    ):
        """Run an operation with retry/backoff for transient backend failures."""
        retryable_statuses = {429, 500, 502, 503, 504}
        last_error: Optional[Exception] = None
        consecutive_503 = 0

        is_export_operation = (
            "export" in operation_name.lower() or "download" in operation_name.lower()
        )

        now = time.time()
        if is_export_operation and now < self._export_circuit_open_until:
            wait_secs = int(self._export_circuit_open_until - now)
            msg = f"Backend export temporarily cooling down ({wait_secs}s remaining): {self._export_circuit_reason}"
            raise BackendAPIError(msg, 503)

        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except BackendAPIError as e:
                last_error = e
                status = e.status_code
                is_retryable = status in retryable_statuses

                if status == 503:
                    consecutive_503 += 1
                else:
                    consecutive_503 = 0

                if is_export_operation and consecutive_503 >= 3:
                    self._export_circuit_open_until = time.time() + 25.0
                    self._export_circuit_reason = "repeated HTTP 503 responses"
                    raise BackendAPIError(
                        "Backend export service is unstable (repeated 503). Cooling down for 25s before next attempt.",
                        503,
                        e.response_data,
                    )

                if not is_retryable or attempt >= max_attempts:
                    raise

                delay = base_delay * attempt
                logger.warning(
                    "%s failed with transient backend error (status=%s). Retrying in %.1fs (%s/%s)",
                    operation_name,
                    status,
                    delay,
                    attempt,
                    max_attempts,
                )
                if self.progress_callback:
                    self.progress_callback(
                        f"{operation_name} temporary backend error (HTTP {status}), retrying ({attempt}/{max_attempts})..."
                    )
                time.sleep(delay)
            except Exception as e:
                last_error = e
                if attempt >= max_attempts:
                    raise
                delay = base_delay * attempt
                logger.warning(
                    "%s failed with transient error. Retrying in %.1fs (%s/%s): %s",
                    operation_name,
                    delay,
                    attempt,
                    max_attempts,
                    e,
                )
                time.sleep(delay)

        if last_error:
            raise last_error
