"""
Checks the test harness itself (conftest.py) and the existing token check
that every HTTP route depends on.
"""

import jwt
import pytest

import db.supabase as db
from core.auth import verify_token
from core.config import settings
from routers import tickers
from tests.helpers import TEST_JWT_SECRET, auth_header, client_for, make_token

# ── Harness ────────────────────────────────────────────────────────────────────

def test_settings_never_point_at_real_services():
    assert settings.supabase_url == "http://supabase.invalid"
    assert settings.supabase_jwt_secret == TEST_JWT_SECRET
    assert settings.alpha_vantage_api_key == ""


def test_real_supabase_client_is_blocked():
    with pytest.raises(RuntimeError, match="must not reach Supabase"):
        db.get_tracked_ticker("NVDA")


def test_fake_db_behaves_like_the_table(fake_db):
    fake_db.insert_tracked_ticker("NVDA", added_by="a@kancil.test")
    assert db.get_tracked_ticker("NVDA")["added_by"] == "a@kancil.test"
    with pytest.raises(ValueError, match="duplicate key"):
        db.insert_tracked_ticker("NVDA")

    db.update_tracked_ticker("NVDA", status="untracked")
    assert db.get_all_tracked_tickers() == []
    assert len(db.get_all_tracked_tickers(exclude_untracked=False)) == 1

    db.delete_tracked_ticker("NVDA")
    assert db.get_tracked_ticker("NVDA") is None


def test_fake_db_returns_copies(fake_db):
    fake_db.add_ticker("NVDA")
    db.get_tracked_ticker("NVDA")["status"] = "held"
    assert fake_db.tracked_tickers["NVDA"]["status"] == "tracking"


def test_make_token_is_accepted_and_carries_claims():
    claims = verify_token(make_token(sub="u-1", email="pm@kancil.test",
                                     app_metadata={"role": "admin"}))
    assert claims["sub"] == "u-1"
    assert claims["email"] == "pm@kancil.test"
    assert claims["app_metadata"] == {"role": "admin"}
    assert claims["aud"] == "authenticated"


# ── Token check on HTTP routes (core.auth.get_current_user) ────────────────────

def test_valid_token_reaches_the_route(fake_db):
    fake_db.add_ticker("NVDA", added_by="analyst@kancil.test")
    r = client_for(tickers.router).get("/api/tickers", headers=auth_header(make_token()))
    assert r.status_code == 200
    assert [t["ticker"] for t in r.json()] == ["NVDA"]


def test_missing_token_is_401():
    r = client_for(tickers.router).get("/api/tickers")
    assert r.status_code == 401


@pytest.mark.parametrize("token, detail", [
    (make_token(expires_in=-60), "Token has expired"),
    (make_token(secret="some-other-secret-that-is-32-bytes-long"), "Invalid or expired token"),
    (make_token(aud="anon"), "Invalid or expired token"),
    ("not-a-jwt", "Invalid or expired token"),
])
def test_bad_tokens_are_401(token, detail):
    r = client_for(tickers.router).get("/api/tickers", headers=auth_header(token))
    assert r.status_code == 401
    assert r.json()["detail"] == detail


def test_unsupported_algorithm_is_rejected():
    token = jwt.encode({"sub": "x", "aud": "authenticated"}, "k" * 64, algorithm="HS512")
    r = client_for(tickers.router).get("/api/tickers", headers=auth_header(token))
    assert r.status_code == 401
