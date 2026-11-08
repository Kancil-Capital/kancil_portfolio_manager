"""
Token verification fails closed (issue #30): weak or missing config never
leads to accepted tokens, and every token needs exp, sub, aud and the
project's iss.
"""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

import core.auth as auth
from core.config import settings
from routers import tickers
from tests.helpers import (
    TEST_JWT_SECRET,
    TEST_SUPABASE_URL,
    auth_header,
    client_for,
    make_token,
)

ISS = f"{TEST_SUPABASE_URL}/auth/v1"


def _payload(**overrides):
    now = int(time.time())
    p = {"sub": "u-1", "aud": "authenticated", "iss": ISS, "iat": now, "exp": now + 3600}
    p.update(overrides)
    return {k: v for k, v in p.items() if v is not None}


def _hs256(secret=TEST_JWT_SECRET, **overrides):
    return jwt.encode(_payload(**overrides), secret, algorithm="HS256")


# ── HS256 secret handling ──────────────────────────────────────────────────────

def test_valid_hs256_token_is_accepted():
    assert auth.verify_token(_hs256())["sub"] == "u-1"


def test_empty_secret_never_verifies(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    # PyJWT alone would accept a token signed with "" when the key is ""
    with pytest.raises(jwt.InvalidAlgorithmError):
        auth.verify_token(_hs256(secret=""))


def test_short_secret_never_verifies(monkeypatch):
    short = "x" * 31
    monkeypatch.setattr(settings, "supabase_jwt_secret", short)
    with pytest.raises(jwt.InvalidAlgorithmError):
        auth.verify_token(_hs256(secret=short))


def test_32_byte_secret_is_enough(monkeypatch):
    secret = "x" * 32
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)
    assert auth.verify_token(_hs256(secret=secret))["sub"] == "u-1"


def test_hs256_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "jwt_allow_hs256", False)
    with pytest.raises(jwt.InvalidAlgorithmError):
        auth.verify_token(_hs256())


# ── Required claims and issuer ─────────────────────────────────────────────────

@pytest.mark.parametrize("claim", ["exp", "sub", "aud", "iss"])
def test_missing_required_claim_is_rejected(claim):
    with pytest.raises(jwt.MissingRequiredClaimError):
        auth.verify_token(_hs256(**{claim: None}))


@pytest.mark.parametrize("iss", [
    "https://some-other-project.supabase.co/auth/v1",
    TEST_SUPABASE_URL,
    "",
])
def test_wrong_issuer_is_rejected(iss):
    with pytest.raises(jwt.InvalidIssuerError):
        auth.verify_token(_hs256(iss=iss))


def test_trailing_slash_in_supabase_url_is_ignored(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", TEST_SUPABASE_URL + "/")
    assert auth.verify_token(_hs256())["sub"] == "u-1"


def test_wrong_audience_is_rejected():
    with pytest.raises(jwt.InvalidAudienceError):
        auth.verify_token(_hs256(aud="anon"))


def test_rejections_are_401_over_http():
    client = client_for(tickers.router)
    for token in (_hs256(sub=None), _hs256(iss="https://evil.example/auth/v1")):
        assert client.get("/api/tickers", headers=auth_header(token)).status_code == 401


def test_harness_tokens_still_pass():
    # make_token() is what every other test uses; it must satisfy the new rules
    assert auth.verify_token(make_token(sub="u-2"))["sub"] == "u-2"


# ── ES256 via JWKS ─────────────────────────────────────────────────────────────

@pytest.fixture
def es256_key(monkeypatch):
    """A local EC key standing in for the project's JWKS."""
    private = ec.generate_private_key(ec.SECP256R1())
    fake_jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    monkeypatch.setattr(auth, "_get_jwks_client", lambda: fake_jwks)
    return private


def test_es256_token_is_accepted(es256_key):
    token = jwt.encode(_payload(), es256_key, algorithm="ES256")
    assert auth.verify_token(token)["sub"] == "u-1"


def test_es256_token_needs_issuer_and_claims(es256_key):
    wrong_iss = jwt.encode(_payload(iss="https://x/auth/v1"), es256_key, algorithm="ES256")
    with pytest.raises(jwt.InvalidIssuerError):
        auth.verify_token(wrong_iss)
    with pytest.raises(jwt.MissingRequiredClaimError):
        auth.verify_token(jwt.encode(_payload(exp=None), es256_key, algorithm="ES256"))


def test_es256_still_works_with_hs256_disabled(es256_key, monkeypatch):
    monkeypatch.setattr(settings, "jwt_allow_hs256", False)
    token = jwt.encode(_payload(), es256_key, algorithm="ES256")
    assert auth.verify_token(token)["sub"] == "u-1"


def test_public_key_cannot_be_used_as_hs256_secret(es256_key):
    # Algorithm confusion: sign HS256 with the public key's PEM
    pem = es256_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    try:
        forged = jwt.encode(_payload(), pem, algorithm="HS256")
    except jwt.InvalidKeyError:
        return  # PyJWT refuses to even sign with a PEM key: also fine
    with pytest.raises(jwt.InvalidSignatureError):
        auth.verify_token(forged)


# ── Startup check ──────────────────────────────────────────────────────────────

def test_startup_check_passes_with_good_config():
    auth.check_auth_config()


def test_startup_check_passes_without_secret_jwks_only(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    auth.check_auth_config()


def test_startup_fails_on_short_secret(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "short")
    with pytest.raises(RuntimeError, match="shorter than 32 bytes"):
        auth.check_auth_config()


def test_short_secret_is_fine_if_hs256_disabled(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "short")
    monkeypatch.setattr(settings, "jwt_allow_hs256", False)
    auth.check_auth_config()


def test_startup_fails_without_supabase_url(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        auth.check_auth_config()
