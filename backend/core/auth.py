"""
core/auth.py
FastAPI dependency for Supabase JWT verification.
Supports both Supabase signing schemes:
  - HS256 (legacy shared secret, SUPABASE_JWT_SECRET)
  - ES256 / RS256 (asymmetric signing keys, public keys fetched from the project's JWKS endpoint)
Local Supabase signs user tokens with ES256 by default.
"""

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """Lazily create the JWKS client; it caches the project's public keys."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def verify_token(token: str) -> dict:
    """
    Verify a raw JWT string and return its claims.
    Raises jwt.PyJWTError on failure — callers must handle it.
    Used for non-HTTP transports (e.g. WebSocket) where HTTPBearer can't be injected.
    """
    alg = jwt.get_unverified_header(token).get("alg")

    # Each algorithm family only ever gets its own key type, so a token can't
    # choose HS256 to be checked against a public key (algorithm confusion).
    if alg == "HS256":
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    if alg in ASYMMETRIC_ALGORITHMS:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ASYMMETRIC_ALGORITHMS,
            audience="authenticated",
        )
    raise jwt.InvalidAlgorithmError(f"Unsupported JWT algorithm: {alg}")


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
        return verify_token(token)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception
