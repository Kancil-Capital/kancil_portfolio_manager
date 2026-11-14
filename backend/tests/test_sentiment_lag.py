"""
Sentiment lag correlations: lags are TRADING DAYS, each comes with n (trading
days with both news and return) and an adjusted p-value, and the best lag is
only reported when it is significant. Prices, the exchange timezone and the DB
are faked.
"""

import numpy as np
import pandas as pd
import pytest

import services.market_service as market_service
import services.sentiment_service as sentiment_service

DAYS = pd.bdate_range("2026-01-05", periods=120)  # the fake exchange has no holidays
TRUE_LAG = 2


def make_articles(rng, news_probability=0.6):
    """One article at 12:00 UTC on a random subset of calendar days, weekends included."""
    calendar = pd.date_range(DAYS[0], DAYS[-1], freq="D", tz="UTC") + pd.Timedelta(hours=12)
    kept = calendar[rng.random(len(calendar)) < news_probability]
    return pd.DataFrame({"timestamp": kept, "sentiment": rng.uniform(-1, 1, len(kept))})


def make_prices(rng, articles=None):
    """Noise returns; with articles, returns follow sentiment TRUE_LAG trading days later."""
    ret = pd.Series(rng.normal(0, 0.01, len(DAYS)), index=DAYS)
    if articles is not None:
        # Weekend articles count for Monday: the same rule the service applies
        pos = DAYS.searchsorted(articles["timestamp"].dt.tz_localize(None).dt.normalize())
        daily = articles["sentiment"].groupby(DAYS[pos]).mean().reindex(DAYS)
        ret = ret.add(0.03 * daily.shift(TRUE_LAG), fill_value=0)
    close = 100 * (1 + ret).cumprod()
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1_000})


@pytest.fixture
def fake_market(monkeypatch):
    def install(prices, tz="UTC"):
        monkeypatch.setattr(market_service, "get_raw_price_df", lambda t, period="6mo": prices)
        monkeypatch.setattr(market_service, "get_exchange_timezone", lambda t: tz)
    return install


def test_lag_is_in_trading_days_with_n_and_adjusted_p(fake_market):
    rng = np.random.default_rng(1)
    articles = make_articles(rng)
    fake_market(make_prices(rng, articles))

    correlations, scatter = sentiment_service._compute_lag_correlations(articles, "TEST")

    assert [c.lag for c in correlations] == list(range(1, 9))
    by_lag = {c.lag: c for c in correlations}
    best = max(correlations, key=lambda c: abs(c.correlation))
    assert best.lag == TRUE_LAG
    assert best.correlation > 0.8
    assert best.p_value < 0.001
    # every other lag is noise once adjusted for the 8 tests
    assert all(c.p_value > 0.05 for c in correlations if c.lag != TRUE_LAG)
    # n counts trading days that have both news `lag` days earlier and a return
    assert all(10 <= c.n < len(DAYS) for c in correlations)
    assert len(scatter) == by_lag[1].n


def test_p_value_is_bonferroni_adjusted_by_max_lag(fake_market):
    rng = np.random.default_rng(2)
    articles = make_articles(rng)
    fake_market(make_prices(rng))  # pure noise, so p-values are well above 0

    eight, _ = sentiment_service._compute_lag_correlations(articles, "TEST", max_lag=8)
    four, _ = sentiment_service._compute_lag_correlations(articles, "TEST", max_lag=4)
    for a, b in zip(four, eight):
        assert a.correlation == b.correlation
        assert b.p_value == pytest.approx(min(a.p_value * 2, 1.0), abs=1e-5)


def test_exchange_timezone_decides_the_trading_day(fake_market):
    # All news lands at 23:30 UTC, which is already the next morning in Tokyo. Returns are
    # built from the UTC dates, so dating articles in Tokyo time moves the signal one lag
    # earlier: from TRUE_LAG to TRUE_LAG - 1.
    rng = np.random.default_rng(3)
    articles = make_articles(rng, news_probability=1.0)
    prices = make_prices(rng, articles)
    articles["timestamp"] += pd.Timedelta(hours=11, minutes=30)

    def best_lag(tz):
        fake_market(prices, tz=tz)
        correlations, _ = sentiment_service._compute_lag_correlations(articles, "TEST")
        return max(correlations, key=lambda c: abs(c.correlation)).lag

    assert best_lag("UTC") == TRUE_LAG
    assert best_lag("Asia/Tokyo") == TRUE_LAG - 1


def test_too_few_pairs_gives_no_correlations(fake_market):
    rng = np.random.default_rng(4)
    fake_market(make_prices(rng))
    articles = make_articles(rng).head(5)
    assert sentiment_service._compute_lag_correlations(articles, "TEST") == ([], [])


# ── best lag in get_sentiment_data ─────────────────────────────────────────────

@pytest.fixture
def fake_db(monkeypatch):
    def install(articles):
        rows = [{"affected": "TEST", "sentiment": s, "confidence": 0.9,
                 "a_timestamp": ts.isoformat(), "title": "Some headline"}
                for ts, s in zip(articles["timestamp"], articles["sentiment"])]
        monkeypatch.setattr(sentiment_service.db, "get_tracked_ticker", lambda t: None)
        monkeypatch.setattr(sentiment_service.db, "get_sentiments_rpc", lambda *a: rows)
    return install


def test_best_lag_is_the_strongest_significant_lag(fake_market, fake_db):
    rng = np.random.default_rng(5)
    articles = make_articles(rng)
    fake_market(make_prices(rng, articles))
    fake_db(articles)

    data = sentiment_service.get_sentiment_data("TEST")

    assert data.stats.best_lag == TRUE_LAG
    assert data.stats.best_lag_correlation == data.lag_correlations[TRUE_LAG - 1].correlation


def test_best_lag_is_none_when_no_lag_is_significant(fake_market, fake_db):
    rng = np.random.default_rng(6)
    articles = make_articles(rng)
    fake_market(make_prices(rng))  # returns unrelated to sentiment
    fake_db(articles)

    data = sentiment_service.get_sentiment_data("TEST")

    assert len(data.lag_correlations) == 8
    assert all(c.p_value >= 0.05 for c in data.lag_correlations)
    assert data.stats.best_lag is None
    assert data.stats.best_lag_correlation is None


# ── exchange timezone lookup ───────────────────────────────────────────────────

class FakeTicker:
    fast_info: dict = {}

    def __init__(self, symbol):
        pass


@pytest.mark.parametrize("fast_info, expected", [
    ({"timezone": "Europe/London"}, "Europe/London"),
    ({"timezone": "Not/AZone"}, "UTC"),
    ({"timezone": None}, "UTC"),
    ({}, "UTC"),
])
def test_exchange_timezone_falls_back_to_utc(monkeypatch, caplog, fast_info, expected):
    monkeypatch.setattr(market_service, "_exchange_tz_cache", {})
    monkeypatch.setattr(FakeTicker, "fast_info", fast_info)
    monkeypatch.setattr(market_service.yf, "Ticker", FakeTicker)

    assert market_service.get_exchange_timezone("TEST") == expected
    assert ("using UTC" in caplog.text) is (expected == "UTC")
    # only a real answer is cached, so a failed lookup is retried
    assert market_service._exchange_tz_cache == ({} if expected == "UTC" else {"TEST": expected})
