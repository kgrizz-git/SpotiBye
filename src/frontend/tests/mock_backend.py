"""Mock backend server for testing frontend integration."""

from __future__ import annotations

import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

class MockBackendHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock backend server."""
    
    def __init__(self, test_data: Dict[str, Any], *args, **kwargs):
        self.test_data = test_data
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self._handle_health_check()
        elif parsed_path.path == '/spotify/playlists':
            self._handle_get_playlists()
        elif parsed_path.path.startswith('/spotify/playlists/') and '/tracks' in parsed_path.path:
            playlist_id = parsed_path.path.split('/')[3]
            self._handle_get_playlist_tracks(playlist_id)
        elif parsed_path.path.startswith('/spotify/playlists/'):
            playlist_id = parsed_path.path.split('/')[3]
            self._handle_get_playlist_details(playlist_id)
        elif parsed_path.path.startswith('/spotify/tracks/'):
            track_id = parsed_path.path.split('/')[3]
            self._handle_get_track_details(track_id)
        elif parsed_path.path.startswith('/analysis/playlist/') and '/status' in parsed_path.path:
            playlist_id = parsed_path.path.split('/')[3]
            self._handle_get_analysis_status(playlist_id)
        elif parsed_path.path.startswith('/analysis/playlist/') and '/results' in parsed_path.path:
            playlist_id = parsed_path.path.split('/')[3]
            self._handle_get_analysis_results(playlist_id)
        else:
            self._send_error(404, "Endpoint not found")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        if parsed_path.path == '/auth/spotify/login':
            self._handle_spotify_login()
        elif parsed_path.path == '/auth/spotify/callback':
            self._handle_spotify_callback(post_data)
        elif parsed_path.path == '/auth/spotify/refresh':
            self._handle_token_refresh()
        elif parsed_path.path.startswith('/analysis/playlist/'):
            playlist_id = parsed_path.path.split('/')[3]
            self._handle_start_analysis(playlist_id)
        elif parsed_path.path.startswith('/export/playlist/'):
            playlist_id = parsed_path.path.split('/')[3]
            self._handle_generate_export(playlist_id, post_data)
        else:
            self._send_error(404, "Endpoint not found")
    
    def _handle_health_check(self):
        """Handle health check endpoint."""
        response = {
            'status': 'healthy',
            'timestamp': time.time(),
            'version': 'mock-1.0.0'
        }
        self._send_json_response(200, response)
    
    def _handle_spotify_login(self):
        """Handle Spotify login initiation."""
        auth_url = f"http://localhost:8080/callback?mock_auth_code=test_code_12345"
        response = {'auth_url': auth_url}
        self._send_json_response(200, response)
    
    def _handle_spotify_callback(self, post_data: bytes):
        """Handle Spotify OAuth callback."""
        try:
            data = json.loads(post_data.decode('utf-8'))
            code = data.get('code')
            
            if code == 'test_code_12345':
                token_data = {
                    'token': 'mock_jwt_token_abcdef123456',
                    'refresh_token': 'mock_refresh_token_789012',
                    'expires_in': 3600,
                    'user': {
                        'id': 'test_user_123',
                        'display_name': 'Test User',
                        'email': 'test@example.com'
                    }
                }
                self._send_json_response(200, token_data)
            else:
                self._send_error(400, "Invalid authorization code")
        except Exception as e:
            self._send_error(400, f"Invalid request data: {e}")
    
    def _handle_token_refresh(self):
        """Handle token refresh."""
        token_data = {
            'token': 'mock_jwt_token_refreshed_789012',
            'refresh_token': 'mock_refresh_token_new_345678',
            'expires_in': 3600
        }
        self._send_json_response(200, token_data)
    
    def _handle_get_playlists(self):
        """Handle get playlists endpoint."""
        playlists = self.test_data.get('playlists', [
            {
                'id': 'playlist_1',
                'name': 'Test Playlist 1',
                'description': 'A test playlist',
                'tracks': {'total': 50},
                'images': [{'url': 'http://example.com/img1.jpg'}],
                'owner': {'id': 'test_user', 'display_name': 'Test User'}
            },
            {
                'id': 'playlist_2', 
                'name': 'Large Test Playlist',
                'description': 'A large test playlist for performance testing',
                'tracks': {'total': 1500},
                'images': [{'url': 'http://example.com/img2.jpg'}],
                'owner': {'id': 'test_user', 'display_name': 'Test User'}
            }
        ])
        response = {'playlists': playlists}
        self._send_json_response(200, response)
    
    def _handle_get_playlist_details(self, playlist_id: str):
        """Handle get playlist details endpoint."""
        # Check for invalid playlist IDs
        if playlist_id.startswith('invalid_id'):
            self._send_error(404, "Playlist not found")
            return
        
        playlist = self.test_data.get('playlist_details', {}).get(playlist_id, {
            'id': playlist_id,
            'name': f'Test Playlist {playlist_id}',
            'description': 'Test playlist description',
            'tracks': {'total': 50},
            'images': [{'url': f'http://example.com/{playlist_id}.jpg'}],
            'owner': {'id': 'test_user', 'display_name': 'Test User'}
        })
        self._send_json_response(200, playlist)
    
    def _handle_get_track_details(self, track_id: str):
        """Handle get track details endpoint."""
        # Check for invalid track IDs
        if track_id.startswith('invalid_track'):
            self._send_error(404, "Track not found")
            return
        
        track = {
            'id': track_id,
            'name': f'Test Track {track_id}',
            'artists': [{'name': f'Test Artist {track_id}'}],
            'album': {'name': f'Test Album {track_id}'},
            'duration_ms': 180000,
            'preview_url': None
        }
        self._send_json_response(200, track)
    
    def _handle_get_playlist_tracks(self, playlist_id: str):
        """Handle get playlist tracks endpoint."""
        tracks = self.test_data.get('playlist_tracks', {}).get(playlist_id, [])
        
        # Generate mock tracks if not provided
        if not tracks:
            track_count = 1500 if 'large' in playlist_id else 50
            tracks = [
                {
                    'id': f'track_{i}',
                    'name': f'Test Track {i}',
                    'artists': [{'name': f'Test Artist {i}'}],
                    'album': {'name': f'Test Album {i}'},
                    'duration_ms': 180000,
                    'preview_url': None,
                    'track_number': i + 1
                }
                for i in range(track_count)
            ]
        
        response = {'tracks': tracks}
        self._send_json_response(200, response)
    
    def _handle_start_analysis(self, playlist_id: str):
        """Handle start analysis endpoint."""
        job_id = f'analysis_job_{playlist_id}_{int(time.time())}'
        response = {
            'job_id': job_id,
            'status': 'pending',
            'playlist_id': playlist_id
        }
        self._send_json_response(200, response)
    
    def _handle_get_analysis_status(self, playlist_id: str):
        """Handle get analysis status endpoint."""
        # Simulate analysis progress
        job_id = f'analysis_job_{playlist_id}'
        
        # For testing, simulate completion after a few calls
        current_status = self.test_data.get('analysis_status', {}).get(playlist_id, 'running')
        
        # For large playlists, simulate progress towards completion
        if playlist_id == 'large_playlist':
            # Always return completed for testing to avoid infinite loops
            status = 'completed'
            progress = 100
        else:
            # Small playlists complete immediately
            status = current_status if current_status != 'running' else 'completed'
            progress = 100 if status == 'completed' else 50
        
        response = {
            'job_id': job_id,
            'status': status,
            'progress': progress,
            'playlist_id': playlist_id
        }
        self._send_json_response(200, response)
    
    def _handle_get_analysis_results(self, playlist_id: str):
        """Handle get analysis results endpoint."""
        results = self.test_data.get('analysis_results', {}).get(playlist_id, {
            'playlist_id': playlist_id,
            'analysis_type': 'audio_features',
            'results': {
                'average_danceability': 0.7,
                'average_energy': 0.8,
                'average_valence': 0.6,
                'track_analysis': [
                    {
                        'track_id': 'track_1',
                        'danceability': 0.8,
                        'energy': 0.9,
                        'valence': 0.7
                    }
                ]
            },
            'completed_at': time.time()
        })
        self._send_json_response(200, results)
    
    def _handle_generate_export(self, playlist_id: str, post_data: bytes):
        """Handle generate export endpoint."""
        try:
            data = json.loads(post_data.decode('utf-8'))
            export_format = data.get('format', 'xlsx')
            
            export_id = f'export_{playlist_id}_{int(time.time())}'
            response = {
                'export_id': export_id,
                'format': export_format,
                'status': 'ready',
                'download_url': f'/export/playlist/{playlist_id}/download',
                'playlist_id': playlist_id
            }
            self._send_json_response(200, response)
        except Exception as e:
            self._send_error(400, f"Invalid export request: {e}")
    
    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """Send error response."""
        error_data = {
            'error': message,
            'status_code': status_code,
            'timestamp': time.time()
        }
        self._send_json_response(status_code, error_data)
    
    def log_message(self, format: str, *args):
        """Suppress default HTTP server logging."""
        pass


class MockBackendServer:
    """Mock backend server for testing frontend integration."""
    
    def __init__(self, host: str = 'localhost', port: int = 8788):
        """
        Initialize mock backend server.
        
        Args:
            host: Server host
            port: Server port
        """
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.test_data: Dict[str, Any] = {}
        self.is_running = False
    
    def set_test_data(self, test_data: Dict[str, Any]) -> None:
        """
        Set test data for the mock server to use.
        
        Args:
            test_data: Dictionary containing test data for various endpoints
        """
        self.test_data = test_data
    
    def start(self) -> bool:
        """
        Start the mock backend server.
        
        Returns:
            True if server started successfully, False otherwise
        """
        try:
            def handler(*args, **kwargs):
                return MockBackendHandler(self.test_data, *args, **kwargs)
            
            self.server = HTTPServer((self.host, self.port), handler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.is_running = True
            print(f"Mock backend server started at http://{self.host}:{self.port}")
            return True
            
        except Exception as e:
            print(f"Failed to start mock backend server: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the mock backend server."""
        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
                self.server = None
            
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
                self.server_thread = None
            
            self.is_running = False
            print("Mock backend server stopped")
            
        except Exception as e:
            print(f"Error stopping mock backend server: {e}")
    
    def get_base_url(self) -> str:
        """
        Get the base URL of the mock server.
        
        Returns:
            Base URL string
        """
        return f"http://{self.host}:{self.port}"
    
    def is_server_running(self) -> bool:
        """
        Check if the server is running.
        
        Returns:
            True if server is running, False otherwise
        """
        return self.is_running and self.server is not None


# Default test data
DEFAULT_TEST_DATA = {
    'playlists': [
        {
            'id': 'small_playlist',
            'name': 'Small Test Playlist',
            'description': 'A small playlist for basic testing',
            'tracks': {'total': 10},
            'images': [{'url': 'http://example.com/small.jpg'}],
            'owner': {'id': 'test_user', 'display_name': 'Test User'}
        },
        {
            'id': 'large_playlist',
            'name': 'Large Test Playlist',
            'description': 'A large playlist for performance testing',
            'tracks': {'total': 1500},
            'images': [{'url': 'http://example.com/large.jpg'}],
            'owner': {'id': 'test_user', 'display_name': 'Test User'}
        }
    ],
    'analysis_status': {
        'small_playlist': 'completed',
        'large_playlist': 'running'
    },
    'analysis_results': {
        'small_playlist': {
            'playlist_id': 'small_playlist',
            'analysis_type': 'audio_features',
            'results': {
                'average_danceability': 0.7,
                'average_energy': 0.8,
                'average_valence': 0.6,
                'track_analysis': [
                    {
                        'track_id': 'track_1',
                        'danceability': 0.8,
                        'energy': 0.9,
                        'valence': 0.7
                    }
                ]
            },
            'completed_at': time.time()
        }
    }
}

__all__ = ["MockBackendServer", "MockBackendHandler", "DEFAULT_TEST_DATA"]
