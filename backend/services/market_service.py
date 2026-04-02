"""
services/market_service.py
yfinance wrapper for price data, technicals, macro, and earnings calendar.
No caching needed — yfinance is fast and free.
"""

import logging
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from db.models import OHLCVPoint, PriceData, Technicals

log = logging.getLogger(__name__)

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Financial Services": "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Materials": "XLB",
    "Basic Materials": "XLB",
}


# ── Raw price download ─────────────────────────────────────────────────────────

def get_raw_price_df(ticker: str, period: str = "6mo") -> pd.DataFrame | None:
    """
    Download OHLCV DataFrame from yfinance.
    Returns None on failure or insufficient data.
    """
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if df.empty or len(df) < 5:
            return None
        df.index = pd.to_datetime(df.index)
        if df.index.tzinfo is not None:
            df.index = df.index.tz_localize(None)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        return df.sort_index()
    except Exception as e:
        log.error(f"Failed to download price data for {ticker}: {e}")
        return None


def get_raw_price_df_range(ticker: str, start: str, end: str | None = None) -> pd.DataFrame | None:
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start, end=end, auto_adjust=True)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        if df.index.tzinfo is not None:
            df.index = df.index.tz_localize(None)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        return df.sort_index()
    except Exception as e:
        log.error(f"Failed to download price data for {ticker} ({start}→{end}): {e}")
        return None


# ── Technicals ─────────────────────────────────────────────────────────────────

def _compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return float(100 - (100 / (1 + rs.iloc[-1])))


def _compute_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.tail(period).mean() / (close.iloc[-1] + 1e-9))


def compute_technicals(df: pd.DataFrame) -> Technicals:
    close = df["close"]
    current = close.iloc[-1]

    rsi = _compute_rsi(close) if len(close) >= 15 else 50.0
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else current
    ma50 = float(close.tail(50).mean()) if len(close) >= 50 else current
    pct_above_ma20 = float(current / ma20 - 1) if len(close) >= 20 else 0.0
    pct_above_ma50 = float(current / ma50 - 1) if len(close) >= 50 else 0.0
    atr_pct = _compute_atr_pct(df) if len(df) >= 14 else 0.0

    return Technicals(
        rsi_14=round(rsi, 2),
        ma20=round(ma20, 4),
        ma50=round(ma50, 4),
        pct_above_ma20=round(pct_above_ma20, 4),
        pct_above_ma50=round(pct_above_ma50, 4),
        atr_pct=round(atr_pct, 6),
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def get_price_data(ticker: str, period: str = "6mo") -> PriceData | None:
    """Full price data + technicals for the research deep-dive."""
    df = get_raw_price_df(ticker, period=period)
    if df is None:
        return None

    current = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else current
    change_pct = (current - prev_close) / prev_close if prev_close else 0.0

    ohlcv = [
        OHLCVPoint(
            date=str(idx.date()),
            open=round(float(row["open"]), 4),
            high=round(float(row["high"]), 4),
            low=round(float(row["low"]), 4),
            close=round(float(row["close"]), 4),
            volume=int(row["volume"]),
        )
        for idx, row in df.iterrows()
    ]

    technicals = compute_technicals(df)

    return PriceData(
        current=round(current, 4),
        change_pct=round(change_pct, 6),
        ohlcv=ohlcv,
        technicals=technicals,
    )


def get_ticker_info(ticker: str) -> dict:
    """Return basic info dict from yfinance (name, sector, country, etc.)."""
    try:
        info = yf.Ticker(ticker).info
        if info == {"trailingPegRatio": None}:
            return {}
        return info
    except Exception as e:
        log.error(f"Failed to get info for {ticker}: {e}")
        return {}


def get_upcoming_earnings(tickers: list[str], days_ahead: int = 90) -> list[dict]:
    """
    Return upcoming earnings dates for a list of tickers.
    Each dict: {ticker, earnings_date, days_to_earnings}
    """
    results = []
    cutoff = datetime.now() + timedelta(days=days_ahead)

    for ticker in tickers:
        try:
            cal = yf.Ticker(ticker).get_earnings_dates(limit=8)
            if cal is None or cal.empty:
                continue

            cal.index = pd.to_datetime(cal.index).tz_localize(None)
            future = cal[cal.index > datetime.now()]
            if future.empty:
                continue

            next_date = future.index[-1]  # yfinance returns newest first; last = soonest future
            # Actually yfinance returns in desc order, so min is the soonest
            next_date = future.index.min()
            if next_date > cutoff:
                continue

            days_to = (next_date.date() - date.today()).days
            results.append({
                "ticker": ticker,
                "earnings_date": str(next_date.date()),
                "days_to_earnings": days_to,
            })
        except Exception as e:
            log.debug(f"Could not get earnings date for {ticker}: {e}")
            continue

    return results


def get_macro_data(start: str = "2019-01-01", end: str | None = None) -> pd.DataFrame | None:
    """
    Download TNX (10Y yield) and VIX. Returns daily DataFrame with regime flags.
    """
    tnx = get_raw_price_df_range("^TNX", start=start, end=end)
    vix = get_raw_price_df_range("^VIX", start=start, end=end)

    if tnx is None or vix is None:
        return None

    macro = pd.DataFrame({"tnx": tnx["close"], "vix": vix["close"]}).ffill()
    macro["rate_regime"] = (macro["tnx"] >= 2.0).astype(int)
    macro["vix_regime"] = (macro["vix"] >= 20.0).astype(int)
    macro["tnx_1m_chg"] = macro["tnx"].pct_change(21)
    macro["vix_5d_chg"] = macro["vix"].pct_change(5)
    return macro


def get_spx_returns(start: str = "2019-01-01", end: str | None = None) -> pd.DataFrame | None:
    df = get_raw_price_df_range("^GSPC", start=start, end=end)
    if df is None:
        return None
    df["spx_ret"] = df["close"].pct_change()
    return df[["close", "spx_ret"]].rename(columns={"close": "spx_close"})


def get_sector_etf_returns(sector: str, start: str, end: str | None = None) -> pd.Series | None:
    etf = SECTOR_ETF_MAP.get(sector)
    if not etf:
        return None
    df = get_raw_price_df_range(etf, start=start, end=end)
    if df is None:
        return None
    return df["close"].pct_change().rename(f"{etf}_ret")
