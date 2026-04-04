"""
core/ticker_cache.py
In-memory cache of tracked ticker symbols, loaded at startup.
Avoids a DB round-trip for the lightweight /api/tickers/symbols endpoint.
"""

import logging

log = logging.getLogger(__name__)

_tickers: list[str] = []


def load(tickers: list[str]) -> None:
    """Replace the cache with a fresh list from the DB (called at startup)."""
    global _tickers
    _tickers = sorted(tickers)
    log.info(f"Ticker cache loaded: {len(_tickers)} tickers")


def add(ticker: str) -> None:
    """Add a ticker to the cache (called when a new ticker is tracked)."""
    if ticker not in _tickers:
        _tickers.append(ticker)
        _tickers.sort()


def remove(ticker: str) -> None:
    """Remove a ticker from the cache (called when a ticker is deleted)."""
    global _tickers
    _tickers = [t for t in _tickers if t != ticker]


def get_all() -> list[str]:
    return list(_tickers)
