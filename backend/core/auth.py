"""
core/auth.py
FastAPI dependency for Supabase JWT verification.
Supports both Supabase signing schemes:
  - HS256 (legacy shared secret, SUPABASE_JWT_SECRET; refused if shorter than
    32 bytes or JWT_ALLOW_HS256=false)
  - ES256 / RS256 (asymmetric signing keys, public keys fetched from the project's JWKS endpoint)
Local Supabase signs user tokens with ES256 by default.
Every token must carry exp, sub, aud="authenticated" and iss="{SUPABASE_URL}/auth/v1".
"""

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
# HS256 needs a key at least as long as its output; a short or empty secret
# would let anyone sign tokens
MIN_HS256_SECRET_BYTES = 32
REQUIRED_CLAIMS = ["exp", "sub", "aud", "iss"]

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """Lazily create the JWKS client; it caches the project's public keys."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"{_issuer()}/.well-known/jwks.json")
    return _jwks_client


def _issuer() -> str:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


def _hs256_usable() -> bool:
    secret = settings.supabase_jwt_secret.encode()
    return settings.jwt_allow_hs256 and len(secret) >= MIN_HS256_SECRET_BYTES


def check_auth_config() -> None:
    """Raise at startup if tokens can't be verified safely. Called from main.py."""
    secret = settings.supabase_jwt_secret.encode()
    if settings.jwt_allow_hs256 and secret and len(secret) < MIN_HS256_SECRET_BYTES:
        raise RuntimeError(
            f"SUPABASE_JWT_SECRET is shorter than {MIN_HS256_SECRET_BYTES} bytes; "
            "fix it or set JWT_ALLOW_HS256=false"
        )
    if not settings.supabase_url:
        # JWKS lives under the project URL, and every token's issuer is checked against it
        raise RuntimeError("SUPABASE_URL is not set, so no token can be verified")
    if not _hs256_usable():
        log.info("HS256 tokens not accepted (disabled or no secret); using JWKS only")


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
        if not _hs256_usable():
            raise jwt.InvalidAlgorithmError("HS256 tokens are disabled or the secret is too short")
        key = settings.supabase_jwt_secret
        algorithms = ["HS256"]
    elif alg in ASYMMETRIC_ALGORITHMS:
        key = _get_jwks_client().get_signing_key_from_jwt(token).key
        algorithms = ASYMMETRIC_ALGORITHMS
    else:
        raise jwt.InvalidAlgorithmError(f"Unsupported JWT algorithm: {alg}")

    return jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience="authenticated",
        issuer=_issuer(),
        options={"require": REQUIRED_CLAIMS},
    )


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
