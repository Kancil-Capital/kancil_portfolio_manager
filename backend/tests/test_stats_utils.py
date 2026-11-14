"""
Trading-day alignment and correlation helpers behind the sentiment lag analysis.
"""

import numpy as np
import pandas as pd
import pytest

from services.stats_utils import align_to_trading_days, bonferroni, corr_with_significance

# Two weeks of trading days around a Monday holiday: 2026-01-19 (MLK day) is missing.
# Mon 12 .. Fri 16, Tue 20 .. Fri 23 January 2026.
DAYS = pd.bdate_range("2026-01-12", "2026-01-23").drop(pd.Timestamp("2026-01-19"))


def articles(*rows):
    return pd.DataFrame(rows, columns=["timestamp", "sentiment"])


def day(s):
    return pd.Timestamp(s)


# ── align_to_trading_days ──────────────────────────────────────────────────────

@pytest.mark.parametrize("timestamp, expected_day", [
    ("2026-01-14T15:00:00+00:00", "2026-01-14"),  # trading day stays put
    ("2026-01-17T12:00:00+00:00", "2026-01-20"),  # Saturday -> Tuesday (Monday is a holiday)
    ("2026-01-18T12:00:00+00:00", "2026-01-20"),  # Sunday
    ("2026-01-19T12:00:00+00:00", "2026-01-20"),  # the holiday itself
])
def test_articles_map_to_next_trading_day(timestamp, expected_day):
    out = align_to_trading_days(articles((timestamp, 0.5)), DAYS)
    assert out.dropna().to_dict() == {day(expected_day): 0.5}


@pytest.mark.parametrize("tz, expected_day", [
    ("UTC", "2026-01-14"),
    ("America/New_York", "2026-01-13"),  # 01:00 UTC Wednesday is 20:00 Tuesday in New York
    ("Asia/Tokyo", "2026-01-14"),
])
def test_date_is_taken_in_the_exchange_timezone(tz, expected_day):
    out = align_to_trading_days(articles(("2026-01-14T01:00:00+00:00", 0.5)), DAYS, tz=tz)
    assert out.dropna().index.tolist() == [day(expected_day)]


def test_timezone_can_move_an_article_across_a_weekend():
    # 23:30 UTC Friday is already Saturday in Tokyo, so it belongs to the next session
    out = align_to_trading_days(articles(("2026-01-16T23:30:00+00:00", 0.5)), DAYS, tz="Asia/Tokyo")
    assert out.dropna().index.tolist() == [day("2026-01-20")]


def test_daily_mean_and_no_news_days_are_nan():
    out = align_to_trading_days(articles(
        ("2026-01-13T10:00:00+00:00", 0.2),
        ("2026-01-13T18:00:00+00:00", 0.6),
        ("2026-01-17T09:00:00+00:00", -1.0),  # Saturday, joins Tuesday the 20th
        ("2026-01-20T09:00:00+00:00", 0.0),
    ), DAYS)
    assert out.index.equals(DAYS)
    assert out[day("2026-01-13")] == pytest.approx(0.4)
    assert out[day("2026-01-20")] == pytest.approx(-0.5)
    assert out.isna().sum() == len(DAYS) - 2  # every other day is NaN, never 0


def test_articles_outside_the_price_range_are_dropped():
    out = align_to_trading_days(articles(
        ("2026-01-05T12:00:00+00:00", 0.9),  # before the first trading day
        ("2026-01-24T12:00:00+00:00", 0.9),  # Saturday after the last one
    ), DAYS)
    assert out.isna().all()


def test_naive_timestamps_are_read_as_utc_and_tz_aware_index_is_accepted():
    out = align_to_trading_days(
        articles((pd.Timestamp("2026-01-14 01:00:00"), 0.5)),
        DAYS.tz_localize("America/New_York"),
        tz="America/New_York",
    )
    assert out.index.tz is None
    assert out.dropna().index.tolist() == [day("2026-01-13")]


def test_no_articles_gives_all_nan():
    out = align_to_trading_days(articles(), DAYS)
    assert out.index.equals(DAYS) and out.isna().all()


# ── corr_with_significance ─────────────────────────────────────────────────────

def test_correlation_uses_only_complete_pairs():
    idx = pd.RangeIndex(6)
    x = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0], index=idx)
    y = pd.Series([2.0, 4.0, 6.0, np.nan, 10.0, 12.0], index=idx)
    r, p, n = corr_with_significance(x, y)
    assert n == 4
    assert r == pytest.approx(1.0)
    assert p < 0.01


def test_correlation_matches_a_known_value():
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    y = pd.Series([2.0, 1.0, 4.0, 3.0, 5.0])
    r, p, n = corr_with_significance(x, y)
    assert (round(r, 4), round(p, 4), n) == (0.8, 0.1041, 5)


def test_shifted_series_recovers_the_lag():
    # returns follow sentiment two trading days later
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2026-01-01", periods=60)
    sent = pd.Series(rng.normal(size=60), index=idx)
    ret = sent.shift(2) * 0.01
    r, _, n = corr_with_significance(sent.shift(2), ret)
    assert r == pytest.approx(1.0) and n == 58
    r_wrong, _, _ = corr_with_significance(sent.shift(1), ret)
    assert abs(r_wrong) < 0.5


@pytest.mark.parametrize("x, y", [
    ([1.0, 2.0], [1.0, 3.0]),                       # n < 3
    ([1.0, np.nan, 3.0, np.nan], [1.0, 2.0, 3.0, 4.0]),  # n < 3 after dropping NaN
    ([1.0, 1.0, 1.0, 1.0], [1.0, 2.0, 3.0, 4.0]),   # constant x
    ([1.0, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 0.0]),   # constant y
    ([], []),
])
def test_undefined_correlation_returns_none(x, y):
    assert corr_with_significance(pd.Series(x, dtype=float), pd.Series(y, dtype=float)) is None


# ── bonferroni ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("p, k, expected", [
    (0.01, 8, 0.08), (0.2, 8, 1.0), (0.0, 8, 0.0), (0.03, 1, 0.03),
])
def test_bonferroni(p, k, expected):
    assert bonferroni(p, k) == pytest.approx(expected)
