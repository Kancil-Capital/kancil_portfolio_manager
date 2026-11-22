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
from services.stats_utils import corr_with_significance, exchange_dates

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


def lag_correlations(articles, prices, tz="UTC", **kwargs):
    """Run the lag analysis the way get_sentiment_data does: date articles in tz first."""
    dated = articles.assign(date=exchange_dates(articles["timestamp"], tz))
    return sentiment_service._compute_lag_correlations(
        dated[["date", "sentiment"]], prices, **kwargs
    )


@pytest.fixture
def fake_market(monkeypatch):
    def install(prices, tz="UTC"):
        monkeypatch.setattr(market_service, "get_raw_price_df", lambda t, period="6mo": prices)
        monkeypatch.setattr(market_service, "get_exchange_timezone", lambda t: tz)
    return install


def test_lag_is_in_trading_days_with_n_and_adjusted_p():
    rng = np.random.default_rng(1)
    articles = make_articles(rng)

    correlations, scatter = lag_correlations(articles, make_prices(rng, articles))

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


def test_p_value_is_bonferroni_adjusted_by_lags_tested():
    rng = np.random.default_rng(2)
    articles = make_articles(rng)
    prices = make_prices(rng)  # pure noise, so p-values are well above 0

    eight, _ = lag_correlations(articles, prices, max_lag=8)
    four, _ = lag_correlations(articles, prices, max_lag=4)
    assert (len(eight), len(four)) == (8, 4)  # every lag has enough pairs here
    for a, b in zip(four, eight):
        assert a.correlation == b.correlation
        assert b.p_value == pytest.approx(min(a.p_value * 2, 1.0), abs=1e-5)


def test_skipped_lag_does_not_count_towards_bonferroni():
    # News only on the last 17 trading days, so lag k has 17 - k pairs: lags 1-7 have
    # 10 or more and are tested, lag 8 has 9 and is skipped. The factor is 7, not 8.
    rng = np.random.default_rng(7)
    calendar = pd.DatetimeIndex(DAYS[-17:], tz="UTC") + pd.Timedelta(hours=12)
    articles = pd.DataFrame({"timestamp": calendar, "sentiment": rng.uniform(-1, 1, 17)})
    prices = make_prices(rng, articles)  # signal at TRUE_LAG, so not every p is capped at 1

    correlations, _ = lag_correlations(articles, prices)

    assert [c.lag for c in correlations] == list(range(1, 8))
    assert [c.n for c in correlations] == [17 - lag for lag in range(1, 8)]
    returns = prices["close"].pct_change()
    sent = pd.Series(articles["sentiment"].to_numpy(), index=DAYS[-17:]).reindex(DAYS)
    for c in correlations:
        _, raw_p, _ = corr_with_significance(sent.shift(c.lag), returns)
        assert c.p_value == pytest.approx(min(raw_p * 7, 1.0), abs=1e-6)
    assert min(c.p_value for c in correlations) < 1.0


def test_exchange_timezone_decides_the_trading_day():
    # All news lands at 23:30 UTC, which is already the next morning in Tokyo. Returns are
    # built from the UTC dates, so dating articles in Tokyo time moves the signal one lag
    # earlier: from TRUE_LAG to TRUE_LAG - 1.
    rng = np.random.default_rng(3)
    articles = make_articles(rng, news_probability=1.0)
    prices = make_prices(rng, articles)
    articles["timestamp"] += pd.Timedelta(hours=11, minutes=30)

    def best_lag(tz):
        correlations, _ = lag_correlations(articles, prices, tz=tz)
        return max(correlations, key=lambda c: abs(c.correlation)).lag

    assert best_lag("UTC") == TRUE_LAG
    assert best_lag("Asia/Tokyo") == TRUE_LAG - 1


def test_too_few_pairs_gives_no_correlations():
    rng = np.random.default_rng(4)
    prices = make_prices(rng)
    articles = make_articles(rng).head(5)
    assert lag_correlations(articles, prices) == ([], [])


def test_constant_sentiment_gives_no_lag_1_and_no_scatter():
    # Plenty of pairs, but every day's sentiment is equal, so r is undefined: the
    # heatmap has no lag-1 cell and the scatter must not show points either.
    rng = np.random.default_rng(8)
    articles = make_articles(rng).assign(sentiment=0.5)

    correlations, scatter = lag_correlations(articles, make_prices(rng))

    assert 1 not in [c.lag for c in correlations]
    assert scatter == []


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


def test_article_has_the_same_date_in_daily_records_and_correlation(
    fake_market, fake_db, monkeypatch
):
    # 01:00 UTC Wednesday 14 Jan is 20:00 Tuesday 13 Jan in New York: both the daily
    # chart and the lag correlation must put it on Tuesday, not the UTC Wednesday.
    rng = np.random.default_rng(9)
    fake_market(make_prices(rng), tz="America/New_York")
    fake_db(pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-01-14T01:00:00", tz="UTC")], "sentiment": [0.5],
    }))
    aligned = []
    real_align = sentiment_service.align_to_trading_days

    def spy_align(*args):
        aligned.append(real_align(*args))
        return aligned[-1]

    monkeypatch.setattr(sentiment_service, "align_to_trading_days", spy_align)

    data = sentiment_service.get_sentiment_data("TEST")

    assert [d.date for d in data.daily] == ["2026-01-13"]
    assert aligned[0].dropna().index.tolist() == [pd.Timestamp("2026-01-13")]


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

def history(tz=None, rows=10):
    """A yfinance-style history frame; tz is put on the index as yfinance does."""
    index = pd.date_range("2026-01-05", periods=rows, freq="B", tz=tz)
    return pd.DataFrame({c: 1.0 for c in ["Open", "High", "Low", "Close", "Volume"]},
                        index=index)


@pytest.fixture
def fake_yf(monkeypatch):
    """Replace yf.Ticker; history() returns the frame given (or raises it). Counts calls."""
    monkeypatch.setattr(market_service, "_exchange_tz_cache", {})
    calls = []

    def install(frame):
        class FakeTicker:
            def __init__(self, symbol):
                pass

            def history(self, **kwargs):
                calls.append(kwargs)
                if isinstance(frame, Exception):
                    raise frame
                return frame

        monkeypatch.setattr(market_service.yf, "Ticker", FakeTicker)
        return calls
    return install


@pytest.mark.parametrize("download", [
    lambda: market_service.get_raw_price_df("TEST", period="1y"),
    lambda: market_service.get_raw_price_df_range("TEST", start="2026-01-01"),
])
def test_price_download_records_the_exchange_timezone(fake_yf, download):
    calls = fake_yf(history(tz="America/New_York"))

    df = download()

    # the returned frame is unchanged: tz-naive index
    assert df.index.tz is None and list(df.columns) == ["open", "high", "low", "close", "volume"]
    # the timezone comes from that download: no second request
    assert market_service.get_exchange_timezone("TEST") == "America/New_York"
    assert len(calls) == 1


@pytest.mark.parametrize("frame", [
    history(tz=None),                    # no tz on the index
    history(tz="UTC").tz_convert(None),  # tz stripped
    history(tz="UTC").iloc[:0],          # unknown symbol: empty history
    RuntimeError("rate limited"),
])
def test_exchange_timezone_falls_back_to_utc(fake_yf, caplog, frame):
    fake_yf(frame)
    assert market_service.get_exchange_timezone("TEST") == "UTC"
    assert "using UTC" in caplog.text
    tz, _expires_at = market_service._exchange_tz_cache["TEST"]
    assert tz == "UTC"


def test_unknown_ticker_is_looked_up_once_per_ttl(fake_yf, caplog, monkeypatch):
    calls = fake_yf(history(tz="UTC").iloc[:0])
    now = [1000.0]
    monkeypatch.setattr(market_service.time, "monotonic", lambda: now[0])

    for _ in range(5):
        assert market_service.get_exchange_timezone("NOPE") == "UTC"
    assert len(calls) == 1
    assert caplog.text.count("using UTC") == 1

    now[0] += market_service._TZ_RETRY_SECONDS - 1  # still inside the TTL
    market_service.get_exchange_timezone("NOPE")
    assert len(calls) == 1

    now[0] += 2  # expired: one new lookup, one new warning
    for _ in range(3):
        market_service.get_exchange_timezone("NOPE")
    assert len(calls) == 2
    assert caplog.text.count("using UTC") == 2


def test_later_successful_download_replaces_the_utc_fallback(fake_yf):
    fake_yf(history(tz="UTC").iloc[:0])
    assert market_service.get_exchange_timezone("TEST") == "UTC"

    fake_yf(history(tz="Asia/Tokyo"))
    market_service.get_raw_price_df("TEST")
    assert market_service.get_exchange_timezone("TEST") == "Asia/Tokyo"
