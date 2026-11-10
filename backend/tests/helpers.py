"""
Test helpers shared by the backend tests (fixtures live in conftest.py).

- Importing this module overrides settings (conftest.py imports it before any
  test runs), so tests never use the real Supabase project or Alpha Vantage
  key from .env / .env.local.
- conftest.py blocks every test from reaching Supabase (`get_client` raises).
  Use the `fake_db` fixture, or monkeypatch the `db.supabase` helper a test needs.
- `make_token(...)` signs a Supabase-style access token with a test secret,
  which `core.auth.verify_token` accepts through its HS256 path.
- `client_for(*routers)` builds a minimal app from only the given routers.
  It skips main.py, so no ML models are loaded and the scheduler doesn't start.

Usage:
    from tests.helpers import auth_header, client_for, make_token

    def test_list(fake_db):
        fake_db.add_ticker("NVDA", added_by="analyst@kancil.test")
        client = client_for(tickers.router)
        r = client.get("/api/tickers", headers=auth_header(make_token()))
        assert r.status_code == 200
"""

import time
import uuid

import jwt
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from core.config import settings

# 32+ bytes, as HS256 needs; only ever used to sign test tokens
TEST_JWT_SECRET = "test-jwt-secret-for-pytest-only-0123456789"
TEST_SUPABASE_URL = "http://supabase.invalid"

settings.supabase_url = TEST_SUPABASE_URL
settings.supabase_secret_key = "test-service-role-key"
settings.supabase_jwt_secret = TEST_JWT_SECRET
settings.alpha_vantage_api_key = ""


# ── Tokens ─────────────────────────────────────────────────────────────────────

def make_token(
    sub: str | None = None,
    email: str = "analyst@kancil.test",
    *,
    secret: str = TEST_JWT_SECRET,
    expires_in: int = 3600,
    **claims,
) -> str:
    """Sign an HS256 token shaped like a Supabase access token.

    Extra keyword arguments become claims, e.g.
    `make_token(app_metadata={"role": "admin"})` or `make_token(aud="anon")`.
    A negative `expires_in` gives an expired token.
    """
    now = int(time.time())
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + expires_in,
        "app_metadata": {},
        "user_metadata": {},
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── App ────────────────────────────────────────────────────────────────────────

def client_for(*routers: APIRouter) -> TestClient:
    """A TestClient for a bare FastAPI app with only these routers (no lifespan)."""
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    return TestClient(app)


# ── Database ───────────────────────────────────────────────────────────────────

class FakeDB:
    """In-memory stand-in for the tracked_tickers helpers in db.supabase.

    Other helpers still hit the block in conftest.py; monkeypatch them in the test that
    needs them (or add them here once several tests do).
    """

    def __init__(self) -> None:
        self.tracked_tickers: dict[str, dict] = {}

    def add_ticker(self, ticker: str, **fields) -> dict:
        row = {
            "ticker": ticker,
            "name": ticker,
            "status": "tracking",
            "added_by": None,
            "added_at": "2026-11-01T00:00:00+00:00",
            "last_scraped": None,
            "sentiment_ready": False,
            **fields,
        }
        self.tracked_tickers[ticker] = row
        return row

    # The functions below match db.supabase's signatures

    def get_tracked_ticker(self, ticker: str) -> dict | None:
        row = self.tracked_tickers.get(ticker)
        return dict(row) if row else None

    def insert_tracked_ticker(self, ticker: str, **fields) -> None:
        # Like the real table: ticker is the primary key
        if ticker in self.tracked_tickers:
            raise ValueError(f'duplicate key value violates "tracked_tickers_pkey": {ticker}')
        self.add_ticker(ticker, **fields)

    def update_tracked_ticker(self, ticker: str, **fields) -> None:
        if ticker in self.tracked_tickers:
            self.tracked_tickers[ticker].update(fields)

    def delete_tracked_ticker(self, ticker: str) -> None:
        self.tracked_tickers.pop(ticker, None)

    def get_all_tracked_tickers(self, exclude_untracked: bool = True) -> list[dict]:
        rows = [dict(r) for r in self.tracked_tickers.values()]
        if exclude_untracked:
            rows = [r for r in rows if r.get("status") != "untracked"]
        return rows
