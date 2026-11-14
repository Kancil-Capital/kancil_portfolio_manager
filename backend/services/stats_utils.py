"""
services/stats_utils.py
Small statistics helpers for the sentiment analytics: putting articles on the
trading-day calendar and correlating two series with a significance test.
"""

import numpy as np
import pandas as pd
from scipy import stats


def align_to_trading_days(
    articles_df: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    tz: str = "UTC",
) -> pd.Series:
    """Daily mean sentiment on the trading-day calendar.

    articles_df needs `timestamp` (tz-aware; naive values are read as UTC) and
    `sentiment`. Each article is dated in `tz` (the exchange's timezone), then
    assigned to that day if it is a trading day, otherwise to the next trading
    day (weekends, holidays). price_index is the calendar: one entry per
    trading day, so no holiday table is needed.

    The result is indexed by price_index. Days without news are NaN, not 0:
    "no news" is missing data, not neutral sentiment. Articles dated outside
    the range price_index covers are dropped.

    TODO: articles published after the close still count for that day. Rolling
    them to the next session needs per-exchange close times.
    """
    days = pd.DatetimeIndex(price_index)
    if days.tz is not None:
        days = days.tz_localize(None)
    days = days.normalize()
    empty = pd.Series(np.nan, index=days, name="sentiment", dtype=float)
    if articles_df.empty or len(days) == 0:
        return empty

    ts = pd.to_datetime(articles_df["timestamp"], utc=True)
    local_date = ts.dt.tz_convert(tz).dt.tz_localize(None).dt.normalize()

    # First trading day on or after the article's local date
    pos = days.searchsorted(local_date.to_numpy(), side="left")
    in_range = (pos < len(days)) & (local_date >= days[0]).to_numpy()
    if not in_range.any():
        return empty

    trading_day = days[pos[in_range]]
    sentiment = articles_df["sentiment"].to_numpy(dtype=float)[in_range]
    daily = pd.Series(sentiment).groupby(trading_day).mean()
    return daily.reindex(days).rename("sentiment")


def corr_with_significance(x: pd.Series, y: pd.Series) -> tuple[float, float, int] | None:
    """Pearson correlation of x and y over the index entries where both are present.

    Returns (r, p, n) with the two-sided p-value, or None when the correlation
    is undefined: fewer than 3 pairs, or either side is constant.
    """
    pair = pd.concat([x, y], axis=1, join="inner").dropna()
    n = len(pair)
    if n < 3:
        return None
    a = pair.iloc[:, 0].to_numpy(dtype=float)
    b = pair.iloc[:, 1].to_numpy(dtype=float)
    if np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    r, p = stats.pearsonr(a, b)
    if np.isnan(r) or np.isnan(p):
        return None
    return float(r), float(p), n


def bonferroni(p: float, k: int) -> float:
    """Bonferroni-adjust a p-value for k tests."""
    return min(p * k, 1.0)
