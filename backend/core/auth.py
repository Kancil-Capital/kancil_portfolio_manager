"""
core/auth.py
FastAPI dependency for Supabase JWT verification (HS256 symmetric secret).
"""

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()


def verify_token(token: str) -> dict:
    """
    Verify a raw JWT string and return its claims.
    Raises jwt.PyJWTError on failure — callers must handle it.
    Used for non-HTTP transports (e.g. WebSocket) where HTTPBearer can't be injected.
    """
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verify the Supabase JWT and return its claims.
    Raises 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    if token == "dev":
        # Development bypass — accepts
        return {}

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception
