"""JWT token handling for session management."""

from __future__ import annotations

import datetime
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import get_settings
from ..logging_config import logger

settings = get_settings()

# Password context for potential future password-based auth
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    data: dict[str, Any], expires_delta: datetime.timedelta | None = None
) -> str:
    """Create JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time override

    Returns:
        JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    logger.debug(f"Created access token, expires at: {expire}")
    return encoded_jwt


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token data or None if invalid
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def create_refresh_token(user_id: str) -> str:
    """Create refresh token for user.

    Args:
        user_id: Spotify user ID

    Returns:
        Refresh token string
    """
    expires = datetime.datetime.utcnow() + datetime.timedelta(days=30)  # 30 days
    to_encode = {"sub": user_id, "exp": expires, "type": "refresh"}

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    logger.debug(f"Created refresh token for user: {user_id}")
    return encoded_jwt


def verify_refresh_token(token: str) -> str | None:
    """Verify refresh token and return user ID.

    Args:
        token: Refresh token string

    Returns:
        User ID or None if invalid
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        # Check if this is a refresh token
        if payload.get("type") != "refresh":
            logger.warning("Token is not a refresh token")
            return None

        user_id = payload.get("sub")
        if user_id:
            logger.debug(f"Refresh token verified for user: {user_id}")
            return user_id
        else:
            logger.warning("Refresh token missing user ID")
            return None

    except JWTError as e:
        logger.warning(f"Refresh token verification failed: {e}")
        return None


def hash_password(password: str) -> str:
    """Hash password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches hash
    """
    return pwd_context.verify(plain_password, hashed_password)


__all__ = [
    "create_access_token",
    "verify_token",
    "create_refresh_token",
    "verify_refresh_token",
    "hash_password",
    "verify_password",
]
