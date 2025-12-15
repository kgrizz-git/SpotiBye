"""Integration tests for complete API workflows."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.spotibye_backend.api.main import app
from src.spotibye_backend.auth.jwt_handler import create_access_token, create_refresh_token

client = TestClient(app)


class TestAuthenticationWorkflow:
    """Test complete authentication workflow."""
    
    def test_oauth_login_redirect(self) -> None:
        """Test that OAuth login redirects to Spotify."""
        response = client.get("/auth/login", follow_redirects=False)
        assert response.status_code == 307
        assert "accounts.spotify.com" in response.headers["location"]
        assert "client_id=" in response.headers["location"]
    
    def test_protected_endpoints_without_auth(self) -> None:
        """Test that protected endpoints require authentication."""
        endpoints = [
            "/auth/verify",
            "/auth/me",
            "/api/playlists",
            "/api/user/profile",
            "/api/analysis/test_playlist/status",
            "/api/export/test_playlist/immediate"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403]
    
    def test_jwt_authentication_flow(self) -> None:
        """Test complete JWT authentication flow."""
        # Create test JWT token
        user_data = {
            "sub": "test_user",
            "username": "testuser",
            "display_name": "Test User"
        }
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token("test_user")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test token verification
        response = client.get("/auth/verify", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "valid"
        assert response.json()["user_id"] == "test_user"
        
        # Test user profile endpoint
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["user_id"] == "test_user"
        assert user_data["username"] == "testuser"
        
        # Test token refresh
        refresh_response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        assert "access_token" in refresh_response.json()
        
        # Test logout
        logout_response = client.post("/auth/logout", headers=headers)
        assert logout_response.status_code == 200
        assert logout_response.json()["message"] == "Successfully logged out"
    
    def test_invalid_jwt_token(self) -> None:
        """Test behavior with invalid JWT tokens."""
        invalid_tokens = [
            "invalid.token.here",
            "Bearer invalid.token.here",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
        ]
        
        for token in invalid_tokens:
            headers = {"Authorization": token}
            response = client.get("/auth/verify", headers=headers)
            assert response.status_code in [401, 403]
    
    def test_expired_jwt_token(self) -> None:
        """Test behavior with expired JWT token."""
        import datetime
        
        # Create expired token
        user_data = {"sub": "test_user", "username": "testuser"}
        expired_token = create_access_token(
            user_data, 
            expires_delta=datetime.timedelta(seconds=-1)  # Already expired
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/auth/verify", headers=headers)
        assert response.status_code in [401, 403]


class TestAPIEndpoints:
    """Test API endpoints functionality."""
    
    def test_health_check(self) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "spotibye-backend"}
    
    def test_api_documentation_available(self) -> None:
        """Test that API documentation is available."""
        # Test Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger-ui" in response.text.lower()
        
        # Test OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi_spec = response.json()
        
        # Verify required components
        assert "paths" in openapi_spec
        assert "components" in openapi_spec
        assert "info" in openapi_spec
        
        # Verify authentication endpoints exist
        paths = openapi_spec["paths"]
        assert "/auth/login" in paths
        assert "/auth/verify" in paths
        assert "/auth/refresh" in paths
        assert "/api/playlists" in paths
    
    def test_spotify_endpoints_require_spotify_auth(self) -> None:
        """Test that Spotify API endpoints require Spotify authentication."""
        # Create JWT token without Spotify token info
        user_data = {"sub": "test_user", "username": "testuser"}
        access_token = create_access_token(user_data)
        headers = {"Authorization": f"Bearer {access_token}"}
        
        spotify_endpoints = [
            "/api/playlists",
            "/api/user/profile",
            "/api/playlists/test_playlist/tracks",
            "/api/tracks/test_track/audio-features"
        ]
        
        for endpoint in spotify_endpoints:
            response = client.get(endpoint, headers=headers)
            assert response.status_code == 401
            assert "No Spotify authentication found" in response.json()["detail"]


class TestErrorHandling:
    """Test error handling across the API."""
    
    def test_404_not_found(self) -> None:
        """Test 404 error handling."""
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self) -> None:
        """Test method not allowed errors."""
        response = client.delete("/auth/login")
        assert response.status_code == 405
    
    def test_invalid_json_requests(self) -> None:
        """Test handling of invalid JSON requests."""
        response = client.post(
            "/auth/refresh",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestCORSConfiguration:
    """Test CORS configuration."""
    
    def test_cors_headers(self) -> None:
        """Test that CORS headers are properly set."""
        response = client.options("/health")  # Use health endpoint instead
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


if __name__ == "__main__":
    pytest.main([__file__])
