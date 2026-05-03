"""Authentication middleware for FastAPI."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..logging_config import logger
from .jwt_handler import verify_token

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict | None:
    """Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        User data from token or raises HTTPException

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        token = credentials.credentials
        payload = verify_token(token)

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract user information from token
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user information",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Return user data
        user_data = {
            "user_id": user_id,
            "username": payload.get("username"),
            "display_name": payload.get("display_name"),
            "token_info": payload.get("token_info"),
        }

        logger.debug(f"Authenticated user: {user_id}")
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """Get current user if token provided, but don't require authentication.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        User data if token valid, None if no token or invalid
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        # Return None instead of raising exception for optional auth
        return None


def get_token_info_from_user(user_data: dict) -> dict | None:
    """Extract Spotify token info from authenticated user data.

    Args:
        user_data: User data from get_current_user

    Returns:
        Spotify token information or None
    """
    return user_data.get("token_info")


# Dependency for endpoints that require Spotify token
async def get_spotify_token_info(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get Spotify token info for authenticated user.

    Args:
        current_user: Current authenticated user

    Returns:
        Spotify token information

    Raises:
        HTTPException: If no Spotify token info available
    """
    token_info = get_token_info_from_user(current_user)
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No Spotify authentication found",
        )

    return token_info


# Dependency for endpoints that optionally need Spotify token
async def get_spotify_token_info_optional(
    current_user: dict | None = Depends(get_current_user_optional),
) -> dict | None:
    """Get Spotify token info if available.

    Args:
        current_user: Current authenticated user (optional)

    Returns:
        Spotify token information or None
    """
    if not current_user:
        return None

    return get_token_info_from_user(current_user)


__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "get_spotify_token_info",
    "get_spotify_token_info_optional",
    "get_token_info_from_user",
]
