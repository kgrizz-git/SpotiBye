"""Network utilities and error handling for frontend-backend communication."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps

from ..services.backend_client import BackendAPIError

logger = logging.getLogger(__name__)


class NetworkError(Exception):
    """Base class for network-related errors."""
    pass


class ConnectionError(NetworkError):
    """Raised when unable to connect to backend."""
    pass


class TimeoutError(NetworkError):
    """Raised when network request times out."""
    pass


class RateLimitError(NetworkError):
    """Raised when rate limit is exceeded."""
    pass


class ServerError(NetworkError):
    """Raised when server returns 5xx error."""
    pass


def retry_on_network_error(max_retries: int = 3, 
                          backoff_factor: float = 1.0,
                          retryable_errors: Optional[List[type]] = None) -> Callable:
    """
    Decorator to retry function on network errors.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for retry delays
        retryable_errors: List of error types to retry on
        
    Returns:
        Decorated function
    """
    if retryable_errors is None:
        retryable_errors = [ConnectionError, TimeoutError, ServerError]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(retryable_errors) as e:
                    last_error = e
                    
                    if attempt < max_retries:
                        delay = backoff_factor * (2 ** attempt)
                        logger.warning(f"Network error (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Max retries exceeded for network error: {e}")
                        break
                except Exception as e:
                    # Don't retry on non-network errors
                    raise e
            
            raise last_error
        
        return wrapper
    return decorator


def handle_network_errors(func: Callable) -> Callable:
    """
    Decorator to handle network errors and convert them to user-friendly messages.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BackendAPIError as e:
            logger.error(f"Backend API error: {e}")
            # Convert to appropriate network error
            if e.status_code:
                if e.status_code == 429:
                    raise RateLimitError(str(e))
                elif 500 <= e.status_code < 600:
                    raise ServerError(f"Server error: {e}")
                elif e.status_code == 0:
                    raise ConnectionError(str(e))
            raise NetworkError(str(e))
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError("Unable to connect to backend. Check your internet connection.")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error: {e}")
            raise TimeoutError("Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise NetworkError(f"Network error: {str(e)}")
    
    return wrapper


class NetworkStatusMonitor:
    """Monitor network connectivity and backend status."""
    
    def __init__(self, backend_client):
        """
        Initialize network status monitor.
        
        Args:
            backend_client: Backend client instance
        """
        self.backend_client = backend_client
        self.last_check_time: Optional[float] = None
        self.last_status: Optional[Dict[str, Any]] = None
        self.check_interval = 60  # Check every 60 seconds
    
    def is_connected(self) -> bool:
        """
        Check if connected to backend.
        
        Returns:
            True if connected, False otherwise
        """
        current_time = time.time()
        
        # Use cached status if recent
        if (self.last_check_time and 
            current_time - self.last_check_time < self.check_interval and 
            self.last_status is not None):
            return self.last_status.get('status') == 'healthy'
        
        try:
            self.last_status = self.backend_client.health_check()
            self.last_check_time = current_time
            return self.last_status.get('status') == 'healthy'
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.last_status = {'status': 'unhealthy', 'error': str(e)}
            self.last_check_time = current_time
            return False
    
    def get_status_message(self) -> str:
        """
        Get user-friendly status message.
        
        Returns:
            Status message string
        """
        if not self.last_check_time:
            return "Checking connection..."
        
        if self.last_status and self.last_status.get('status') == 'healthy':
            return "Connected to backend"
        elif self.last_status and 'error' in self.last_status:
            return f"Connection error: {self.last_status['error']}"
        else:
            return "Unable to connect to backend"
    
    def force_check(self) -> bool:
        """
        Force an immediate connectivity check.
        
        Returns:
            True if connected, False otherwise
        """
        self.last_check_time = None  # Reset cache
        return self.is_connected()


class ProgressTracker:
    """Track progress of long-running network operations."""
    
    def __init__(self, total_steps: int, description: str = "Processing"):
        """
        Initialize progress tracker.
        
        Args:
            total_steps: Total number of steps
            description: Description of the operation
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description
        self.start_time = time.time()
        self.callbacks: List[Callable[[int, int, str], None]] = []
    
    def add_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Add progress callback function."""
        self.callbacks.append(callback)
    
    def update(self, step: int = 1, message: str = "") -> None:
        """
        Update progress.
        
        Args:
            step: Number of steps completed (default: 1)
            message: Optional status message
        """
        self.current_step += step
        progress = min(100, int((self.current_step / self.total_steps) * 100))
        
        for callback in self.callbacks:
            try:
                callback(self.current_step, self.total_steps, message)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def complete(self, message: str = "Complete") -> None:
        """Mark operation as complete."""
        self.current_step = self.total_steps
        elapsed = time.time() - self.start_time
        
        for callback in self.callbacks:
            try:
                callback(self.total_steps, self.total_steps, f"{message} ({elapsed:.1f}s)")
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current progress information.
        
        Returns:
            Progress dictionary
        """
        progress = min(100, int((self.current_step / self.total_steps) * 100))
        elapsed = time.time() - self.start_time
        
        return {
            'current': self.current_step,
            'total': self.total_steps,
            'progress': progress,
            'description': self.description,
            'elapsed': elapsed,
            'eta': (elapsed / self.current_step * (self.total_steps - self.current_step)) if self.current_step > 0 else None
        }


def format_error_message(error: Exception) -> str:
    """
    Format error message for user display.
    
    Args:
        error: Exception to format
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, ConnectionError):
        return "Unable to connect to the backend. Please check your internet connection and try again."
    elif isinstance(error, TimeoutError):
        return "The request timed out. Please try again."
    elif isinstance(error, RateLimitError):
        return "Too many requests. Please wait a moment and try again."
    elif isinstance(error, ServerError):
        return "The server is experiencing issues. Please try again later."
    elif isinstance(error, NetworkError):
        return f"Network error: {str(error)}"
    else:
        return f"An error occurred: {str(error)}"


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    retryable_errors = (ConnectionError, TimeoutError, ServerError, RateLimitError)
    return isinstance(error, retryable_errors)


def create_progress_callback(progress_bar, status_label: Optional[str] = None) -> Callable:
    """
    Create a progress callback for UI components.
    
    Args:
        progress_bar: Progress bar widget
        status_label: Optional status label widget
        
    Returns:
        Progress callback function
    """
    def callback(current: int, total: int, message: str) -> None:
        try:
            if progress_bar:
                progress = min(100, int((current / total) * 100))
                progress_bar.value = progress
            
            if status_label and message:
                status_label.text = message
                
        except Exception as e:
            logger.error(f"Progress callback error: {e}")
    
    return callback


# Import requests here to avoid circular imports
import requests
