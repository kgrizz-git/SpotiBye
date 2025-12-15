"""Authentication endpoints for Spotify OAuth."""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..auth.jwt_handler import create_access_token, create_refresh_token
from ..auth.middleware import get_current_user, get_spotify_token_info_optional
from ..auth.oauth_handler import SpotifyOAuthHandler, clear_all_auth_state
from ..config import get_settings
from ..logging_config import logger

router = APIRouter()
settings = get_settings()


# Pydantic models
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# OAuth handler instance
oauth_handler = SpotifyOAuthHandler()


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect to Spotify OAuth login."""
    try:
        # Find available port for callback
        from ..auth.oauth_handler import find_available_port
        port = find_available_port()
        
        # Get authorization URL
        auth_url = oauth_handler.get_auth_url(port)
        
        logger.info(f"Redirecting to Spotify OAuth with port: {port}")
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        logger.error(f"Error initiating OAuth flow: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate authentication")


@router.get("/callback")
async def auth_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None
) -> Response:
    """Handle Spotify OAuth callback."""
    try:
        if error:
            logger.error(f"OAuth error: {error}")
            return Response(
                content=f"<html><body><h1>Authentication Failed</h1><p>Error: {error}</p></body></html>",
                status_code=400
            )
        
        if not code:
            logger.error("No authorization code received")
            return Response(
                content="<html><body><h1>Authentication Failed</h1><p>No authorization code received</p></body></html>",
                status_code=400
            )
        
        # Exchange code for token
        # Note: In a real implementation, we'd need to track which port was used
        # For now, we'll use the default redirect URI
        token_info = oauth_handler.exchange_code_for_token(code)
        
        if not token_info:
            logger.error("Failed to exchange code for token")
            return Response(
                content="<html><body><h1>Authentication Failed</h1><p>Failed to exchange authorization code for token</p></body></html>",
                status_code=500
            )
        
        # Get user information
        from ..auth.oauth_handler import create_spotify_client_with_refresh
        sp = create_spotify_client_with_refresh(token_info)
        if not sp:
            logger.error("Failed to create Spotify client")
            return Response(
                content="<html><body><h1>Authentication Failed</h1><p>Failed to create Spotify client</p></body></html>",
                status_code=500
            )
        
        user = sp.current_user()
        user_data = {
            "id": user.get("id"),
            "display_name": user.get("display_name"),
            "email": user.get("email"),
            "country": user.get("country"),
            "product": user.get("product")
        }
        
        # Create JWT tokens
        access_token = create_access_token(
            data={
                "sub": user_data["id"],
                "username": user_data["display_name"],
                "display_name": user_data["display_name"],
                "token_info": token_info
            }
        )
        
        refresh_token = create_refresh_token(user_data["id"])
        
        # Return tokens in HTML response (in production, this would redirect to frontend)
        html_response = f"""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>Authentication Successful!</h2>
            <p>Welcome, {user_data['display_name']}!</p>
            <p>You can now close this window and return to the application.</p>
            <div style="background: #f0f0f0; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Your Tokens (for development):</h3>
                <p><strong>Access Token:</strong> {access_token[:50]}...</p>
                <p><strong>Refresh Token:</strong> {refresh_token[:50]}...</p>
            </div>
            <script>
                // In production, these would be sent to the frontend app
                localStorage.setItem('access_token', '{access_token}');
                localStorage.setItem('refresh_token', '{refresh_token}');
                setTimeout(() => window.close(), 5000);
            </script>
        </body>
        </html>
        """
        
        logger.info(f"Successfully authenticated user: {user_data['id']}")
        return Response(content=html_response)
        
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return Response(
            content=f"<html><body><h1>Authentication Failed</h1><p>Error: {str(e)}</p></body></html>",
            status_code=500
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(request: RefreshTokenRequest) -> RefreshTokenResponse:
    """Refresh access token using refresh token."""
    try:
        from ..auth.jwt_handler import verify_refresh_token
        
        user_id = verify_refresh_token(request.refresh_token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Create new access token
        access_token = create_access_token(data={"sub": user_id})
        
        logger.info(f"Refreshed access token for user: {user_id}")
        return RefreshTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)) -> Dict[str, str]:
    """Logout user and clear authentication state."""
    try:
        user_id = current_user["user_id"]
        
        # Clear Spotify auth state
        clear_all_auth_state()
        
        logger.info(f"Logged out user: {user_id}")
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        raise HTTPException(status_code=500, detail="Failed to logout")


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current authenticated user information."""
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "display_name": current_user["display_name"]
    }


@router.get("/verify")
async def verify_authentication(current_user: dict = Depends(get_current_user)) -> Dict[str, str]:
    """Verify if current authentication is valid."""
    return {"status": "valid", "user_id": current_user["user_id"]}


__all__ = ["router"]
