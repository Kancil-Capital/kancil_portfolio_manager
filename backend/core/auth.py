"""
core/auth.py
FastAPI dependency for Supabase JWT verification (RS256 asymmetric keys).
Public keys are fetched from Supabase's JWKS endpoint on first use and cached.
"""

import logging
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm

from core.config import settings

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

# Cached JWKS public keys: kid -> RSA public key
_jwks_cache: dict[str, Any] = {}


def _fetch_jwks() -> dict[str, Any]:
    """Fetch and cache public keys from Supabase JWKS endpoint."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        _jwks_cache = {
            key["kid"]: RSAAlgorithm.from_jwk(key)
            for key in keys
            if key.get("kty") == "RSA"
        }
        log.info(f"Loaded {len(_jwks_cache)} JWKS key(s) from Supabase")
    except Exception as e:
        log.error(f"Failed to fetch JWKS from Supabase: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )

    return _jwks_cache


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Verify the Supabase JWT and return its claims.
    Raises 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Peek at the header to get the key ID
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        keys = _fetch_jwks()

        if kid and kid in keys:
            public_key = keys[kid]
        elif keys:
            # Fallback: try the only available key
            public_key = next(iter(keys.values()))
        else:
            raise credentials_exception

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
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
