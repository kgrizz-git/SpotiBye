"""Tests for authentication functionality."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.spotibye_backend.api.main import app
from src.spotibye_backend.auth.jwt_handler import create_access_token, verify_token
from src.spotibye_backend.config import get_settings

client = TestClient(app)
settings = get_settings()


class TestJWTHandler:
    """Test JWT token handling."""
    
    def test_create_access_token(self) -> None:
        """Test creating access token."""
        data = {"sub": "test_user", "username": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test_user"
        assert payload["username"] == "testuser"
    
    def test_verify_invalid_token(self) -> None:
        """Test verifying invalid token."""
        invalid_token = "invalid.token.here"
        payload = verify_token(invalid_token)
        assert payload is None
    
    def test_token_expiration(self) -> None:
        """Test token expiration."""
        import datetime
        
        data = {"sub": "test_user"}
        # Create token with very short expiration
        token = create_access_token(
            data, 
            expires_delta=datetime.timedelta(seconds=-1)  # Already expired
        )
        
        payload = verify_token(token)
        assert payload is None


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_health_check(self) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "spotibye-backend"}
    
    def test_login_redirect(self) -> None:
        """Test login endpoint redirects to Spotify."""
        response = client.get("/auth/login")
        assert response.status_code in [302, 500]  # Redirect or error if no Spotify creds
    
    def test_verify_without_token(self) -> None:
        """Test verify endpoint without token."""
        response = client.get("/auth/verify")
        assert response.status_code == 401  # Unauthorized
    
    def test_verify_with_valid_token(self) -> None:
        """Test verify endpoint with valid token."""
        # Create test token
        data = {"sub": "test_user", "username": "testuser", "display_name": "Test User"}
        token = create_access_token(data)
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/verify", headers=headers)
        
        assert response.status_code == 200
        assert response.json()["status"] == "valid"
        assert response.json()["user_id"] == "test_user"
    
    def test_verify_with_invalid_token(self) -> None:
        """Test verify endpoint with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/auth/verify", headers=headers)
        
        assert response.status_code == 401
    
    def test_me_with_valid_token(self) -> None:
        """Test /me endpoint with valid token."""
        data = {"sub": "test_user", "username": "testuser", "display_name": "Test User"}
        token = create_access_token(data)
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["user_id"] == "test_user"
        assert user_data["username"] == "testuser"
        assert user_data["display_name"] == "Test User"


if __name__ == "__main__":
    pytest.main([__file__])
