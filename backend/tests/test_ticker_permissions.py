"""
PATCH and DELETE on /api/tickers/{ticker} share one rule: owner or admin (issue #12).
The DB and the auth dependency are faked.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.tickers as tickers
from core.auth import get_current_user

OWNER = {"email": "owner@kancil.test"}
ADMIN = {"email": "admin@kancil.test", "app_metadata": {"role": "admin"}}
OTHER = {"email": "other@kancil.test"}
# user_metadata is editable by the user, so it must never grant admin
SELF_PROMOTED = {"email": "sneaky@kancil.test", "user_metadata": {"role": "admin"}}
NO_EMAIL = {"sub": "123"}


@pytest.fixture
def rows(monkeypatch):
    rows = {"NVDA": {"ticker": "NVDA", "name": "Nvidia", "added_by": OWNER["email"],
                     "status": "tracking"}}
    monkeypatch.setattr(tickers.db, "get_tracked_ticker",
                        lambda t: dict(rows[t]) if t in rows else None)
    monkeypatch.setattr(tickers.db, "update_tracked_ticker", lambda t, **kw: rows[t].update(kw))
    monkeypatch.setattr(tickers.db, "delete_tracked_ticker", lambda t: rows.pop(t))
    monkeypatch.setattr(tickers.ticker_cache, "remove", lambda t: None)
    return rows


def client_as(user):
    app = FastAPI()
    app.include_router(tickers.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize("user, allowed", [
    (OWNER, True), (ADMIN, True), (OTHER, False), (SELF_PROMOTED, False), (NO_EMAIL, False),
])
def test_can_manage(user, allowed):
    assert tickers._can_manage({"added_by": OWNER["email"]}, user) is allowed


def test_can_manage_ticker_with_no_owner():
    assert tickers._can_manage({"added_by": None}, OTHER) is False
    assert tickers._can_manage({"added_by": None}, NO_EMAIL) is False
    assert tickers._can_manage({"added_by": None}, ADMIN) is True


@pytest.mark.parametrize("user, expected", [
    (OWNER, 200), (ADMIN, 200), (OTHER, 403), (SELF_PROMOTED, 403),
])
def test_patch_status(rows, user, expected):
    r = client_as(user).patch("/api/tickers/nvda", json={"status": "held"})
    assert r.status_code == expected
    assert rows["NVDA"]["status"] == ("held" if expected == 200 else "tracking")


@pytest.mark.parametrize("user, expected", [
    (OWNER, 204), (ADMIN, 204), (OTHER, 403), (SELF_PROMOTED, 403),
])
def test_delete(rows, user, expected):
    r = client_as(user).delete("/api/tickers/NVDA")
    assert r.status_code == expected
    assert ("NVDA" in rows) is (expected == 403)


def test_unknown_ticker_is_404_not_403(rows):
    assert client_as(OTHER).patch("/api/tickers/ZZZ", json={"status": "held"}).status_code == 404
    assert client_as(OTHER).delete("/api/tickers/ZZZ").status_code == 404


def test_invalid_status_rejected(rows):
    assert client_as(OWNER).patch("/api/tickers/NVDA", json={"status": "bogus"}).status_code == 422
