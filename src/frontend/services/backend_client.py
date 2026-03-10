"""Backend client for Cloudflare Worker API communication."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
import webbrowser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class BackendAPIError(Exception):
    """Custom exception for backend API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class BackendClient:
    """HTTP client for Cloudflare Worker backend communication."""
    
    def __init__(self, base_url: str = "http://localhost:8787"):
        """
        Initialize backend client.
        
        Args:
            base_url: Base URL of the Cloudflare Worker backend
        """
        self.base_url = base_url.rstrip('/')
        self.session = self._create_session()
        self.auth_token: Optional[str] = None
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic and proper configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            # Retry only idempotent read operations; do not retry POST exports.
            allowed_methods=["GET", "HEAD", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'SpotiBye-Desktop/2.0'
        })
        
        return session
    
    def _make_request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Make HTTP request to backend API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests
            
        Returns:
            Response JSON data
            
        Raises:
            BackendAPIError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        
        # Add authentication header if token is available
        if self.auth_token:
            headers = kwargs.pop('headers', {})
            headers['Authorization'] = f'Bearer {self.auth_token}'
            kwargs['headers'] = headers
        
        try:
            logger.debug(f"Making {method} request to {url}")
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            # Log response for debugging
            logger.debug(f"Response status: {response.status_code}")
            
            # Handle different response types
            if response.headers.get('content-type', '').startswith('application/json'):
                response_data = response.json()
            else:
                response_data = {'data': response.text}
            
            # Check for error responses
            if response.status_code >= 400:
                error_payload = response_data.get('error', {}) if isinstance(response_data, dict) else {}
                if isinstance(error_payload, dict):
                    error_message = error_payload.get('message', error_payload.get('code', f'HTTP {response.status_code}'))
                else:
                    error_message = str(error_payload) or f'HTTP {response.status_code}'
                raise BackendAPIError(error_message, response.status_code, response_data)

            # Most backend routes return { data: ... }, where data can be dict or list.
            if isinstance(response_data, dict) and 'data' in response_data:
                return response_data['data']

            return response_data
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise BackendAPIError("Unable to connect to backend. Check your internet connection.")
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise BackendAPIError("Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise BackendAPIError(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise BackendAPIError("Invalid response from backend.")
    
    # Authentication endpoints
    def initiate_spotify_login(self, redirect_uri: str) -> str:
        """
        Initiate Spotify OAuth login flow.
        
        Returns:
            Authorization URL for user to visit
        """
        response = self._make_request('POST', '/auth/spotify/login', json={'redirect_uri': redirect_uri})
        auth_url = response.get('auth_url')
        if not auth_url:
            raise BackendAPIError("No authorization URL received from backend")
        return auth_url
    
    def handle_spotify_callback(self, code: str, state: str) -> Dict[str, Any]:
        """
        Handle Spotify OAuth callback.
        
        Args:
            code: Authorization code from Spotify
            
        Returns:
            JWT token and user information
        """
        response = self._make_request('GET', f'/auth/spotify/callback?code={code}&state={state}')
        token = response.get('token')
        if not token:
            raise BackendAPIError("No token received from backend")
        
        self.auth_token = token
        return response
    
    def refresh_token(self) -> Dict[str, Any]:
        """Refresh JWT token."""
        response = self._make_request('POST', '/auth/spotify/refresh')
        token = response.get('access_token')
        if not token:
            raise BackendAPIError("No refreshed token received from backend")
        
        self.auth_token = token
        return response
    
    # Spotify data endpoints
    def get_playlists(self) -> List[Dict[str, Any]]:
        """Get user's Spotify playlists."""
        response = self._make_request('GET', '/spotify/playlists')
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            data = response.get('data')
            if isinstance(data, list):
                return data
            return response.get('playlists', response.get('items', []))
        return []
    
    def get_playlist_details(self, playlist_id: str) -> Dict[str, Any]:
        """Get detailed information about a playlist."""
        response = self._make_request('GET', f'/spotify/playlists/{playlist_id}')
        return response
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get tracks from a playlist."""
        response = self._make_request('GET', f'/spotify/playlists/{playlist_id}/items')
        return response.get('items', response.get('tracks', []))
    
    def get_track_details(self, track_id: str) -> Dict[str, Any]:
        """Get detailed information about a track."""
        response = self._make_request('GET', f'/spotify/tracks/{track_id}')
        return response
    
    def get_track_audio_features(self, track_id: str) -> Dict[str, Any]:
        """Get audio features for a track."""
        response = self._make_request('GET', f'/spotify/tracks/{track_id}/audio-features')
        return response
    
    # Analysis endpoints
    def analyze_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Start playlist analysis."""
        response = self._make_request('POST', f'/analysis/playlist/{playlist_id}')
        return response
    
    def get_analysis_status(self, playlist_id: str) -> Dict[str, Any]:
        """Get analysis status for a playlist."""
        response = self._make_request('GET', f'/analysis/playlist/{playlist_id}/status')
        return response
    
    def get_analysis_results(self, playlist_id: str) -> Dict[str, Any]:
        """Get analysis results for a playlist."""
        response = self._make_request('GET', f'/analysis/playlist/{playlist_id}/results')
        return response
    
    # Export endpoints
    def generate_export(self, playlist_id: str, format: str = 'xlsx') -> Dict[str, Any]:
        """Generate export for a playlist."""
        response = self._make_request('POST', f'/export/playlist/{playlist_id}', 
                                    json={'format': format})
        return response

    def generate_batch_export(self, playlist_ids: List[str], format: str = 'xlsx') -> Dict[str, Any]:
        """Generate a combined export for multiple playlists."""
        response = self._make_request(
            'POST',
            '/export/playlists',
            json={'playlist_ids': playlist_ids, 'format': format}
        )
        return response
    
    def download_export(self, playlist_id: str, export_id: str) -> bytes:
        """Download generated export file."""
        url = f"{self.base_url}/export/playlist/{playlist_id}/download"
        headers = {'Authorization': f'Bearer {self.auth_token}'} if self.auth_token else {}
        
        response = self.session.get(url, headers=headers, timeout=60)
        if response.status_code >= 400:
            raise BackendAPIError(f"Export download failed: HTTP {response.status_code}")
        
        return response.content

    def download_batch_export(self, job_id: str) -> bytes:
        """Download generated combined export file."""
        url = f"{self.base_url}/export/playlists/{job_id}/download"
        headers = {'Authorization': f'Bearer {self.auth_token}'} if self.auth_token else {}

        response = self.session.get(url, headers=headers, timeout=120)
        if response.status_code >= 400:
            raise BackendAPIError(f"Batch export download failed: HTTP {response.status_code}")

        return response.content
    
    # Utility methods
    def health_check(self) -> Dict[str, Any]:
        """Check backend health."""
        try:
            response = self._make_request('GET', '/health')
            return response
        except BackendAPIError:
            return {'status': 'unhealthy', 'error': 'Backend not reachable'}
    
    def set_auth_token(self, token: str) -> None:
        """Set authentication token for subsequent requests."""
        self.auth_token = token
    
    def clear_auth_token(self) -> None:
        """Clear authentication token."""
        self.auth_token = None
    
    def is_authenticated(self) -> bool:
        """Check if client has valid authentication token."""
        return self.auth_token is not None


# Global backend client instance
_backend_client: Optional[BackendClient] = None


def get_backend_client() -> BackendClient:
    """Get or create global backend client instance."""
    global _backend_client
    if _backend_client is None:
        _backend_client = BackendClient()
    return _backend_client


def set_backend_url(url: str) -> None:
    """Set backend URL for new client instances."""
    global _backend_client
    _backend_client = BackendClient(url)
