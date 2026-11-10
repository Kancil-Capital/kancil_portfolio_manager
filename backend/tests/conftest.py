"""
Fixtures shared by every backend test. Helpers (make_token, client_for, FakeDB)
are in tests/helpers.py; importing it also points settings at test values.
"""

from collections.abc import Iterator

import pytest

import db.supabase as db
from tests.helpers import FakeDB


@pytest.fixture(autouse=True)
def _block_real_supabase(monkeypatch):
    """Fail loudly if code under test tries to build a real Supabase client."""

    def _blocked():
        raise RuntimeError(
            "Tests must not reach Supabase. Use the fake_db fixture or monkeypatch "
            "the db.supabase helper this code calls."
        )

    monkeypatch.setattr(db, "_client", None)
    monkeypatch.setattr(db, "get_client", _blocked)


@pytest.fixture
def fake_db(monkeypatch) -> Iterator[FakeDB]:
    """Replace the tracked_tickers helpers in db.supabase with an in-memory FakeDB."""
    fake = FakeDB()
    for name in (
        "get_tracked_ticker",
        "insert_tracked_ticker",
        "update_tracked_ticker",
        "delete_tracked_ticker",
        "get_all_tracked_tickers",
    ):
        monkeypatch.setattr(db, name, getattr(fake, name))
    yield fake
