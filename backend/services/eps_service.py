"""
services/eps_service.py
Alpha Vantage EPS/SUE cache with strict 90-day TTL.
Never re-fetches unless cache is stale. Logs every API call.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np
import pandas as pd

import db.supabase as db
from core.config import settings
from db.models import EpsRecord

log = logging.getLogger(__name__)

CACHE_TTL_DAYS = 90
AV_BASE_URL = "https://www.alphavantage.co/query"


# ── Cache freshness check ──────────────────────────────────────────────────────

def _is_fresh(records: list[dict]) -> bool:
    """Cache is fresh if the most recently fetched record is < 90 days old."""
    if not records:
        return False
    latest_fetched = max(
        datetime.fromisoformat(r["fetched_at"].replace("Z", "+00:00"))
        for r in records
        if r.get("fetched_at")
    )
    threshold = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
    return latest_fetched > threshold


# ── Alpha Vantage fetch ────────────────────────────────────────────────────────

def _fetch_from_alpha_vantage(ticker: str) -> list[dict]:
    """
    Call Alpha Vantage EARNINGS endpoint.
    Returns list of EPS records ready for upsert into eps_cache.
    """
    if not settings.alpha_vantage_api_key:
        log.warning(f"Alpha Vantage API key not set — cannot fetch EPS for {ticker}")
        return []

    log.info(f"[AV API CALL] Fetching earnings for {ticker} — check daily quota")
    url = f"{AV_BASE_URL}?function=EARNINGS&symbol={ticker}&apikey={settings.alpha_vantage_api_key}"

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"Alpha Vantage request failed for {ticker}: {e}")
        return []

    if "quarterlyEarnings" not in data:
        log.warning(f"No quarterly earnings in AV response for {ticker}: {data.get('Note', data.get('Information', ''))}")
        return []

    quarterly = data["quarterlyEarnings"]
    if not quarterly:
        return []

    df = pd.DataFrame(quarterly)
    df["ticker"] = ticker
    df["reportedDate"] = pd.to_datetime(df["reportedDate"], errors="coerce")
    df["fiscalDateEnding"] = pd.to_datetime(df["fiscalDateEnding"], errors="coerce")
    df["reportedEPS"] = pd.to_numeric(df["reportedEPS"], errors="coerce")
    df["estimatedEPS"] = pd.to_numeric(df["estimatedEPS"], errors="coerce")
    df = df.dropna(subset=["reportedEPS", "fiscalDateEnding"])

    # Compute EPS surprise
    df["surprise"] = df["reportedEPS"] - df["estimatedEPS"]
    df["eps_surprise_pct"] = df["surprise"] / df["estimatedEPS"].abs().replace(0, np.nan)

    # SUE: surprise / rolling std of past 8Q forecast errors
    df = df.sort_values("fiscalDateEnding")
    df["rolling_std"] = df["surprise"].rolling(8, min_periods=4).std().shift(1)
    df["sue"] = (df["surprise"] / (df["rolling_std"].abs() + 1e-9)).clip(-10, 10)

    now_iso = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in df.iterrows():
        records.append({
            "ticker": ticker,
            "fiscal_date": str(row["fiscalDateEnding"].date()),
            "earnings_date": str(row["reportedDate"].date()) if pd.notna(row["reportedDate"]) else None,
            "reported_eps": float(row["reportedEPS"]) if pd.notna(row["reportedEPS"]) else None,
            "estimated_eps": float(row["estimatedEPS"]) if pd.notna(row["estimatedEPS"]) else None,
            "eps_surprise": float(row["surprise"]) if pd.notna(row["surprise"]) else None,
            "eps_surprise_pct": float(row["eps_surprise_pct"]) if pd.notna(row.get("eps_surprise_pct")) else None,
            "sue": float(row["sue"]) if pd.notna(row["sue"]) else None,
            "fetched_at": now_iso,
        })
    return records


# ── Public API ─────────────────────────────────────────────────────────────────

def get_eps_data(ticker: str) -> list[EpsRecord]:
    """
    Return EPS records for ticker, using cache when fresh.
    Never calls Alpha Vantage if cache is < 90 days old.
    """
    cached = db.get_eps_cache(ticker)

    if _is_fresh(cached):
        log.debug(f"EPS cache hit for {ticker} ({len(cached)} records)")
        return [EpsRecord(**r) for r in cached]

    # Cache stale or empty — fetch from AV
    raw = _fetch_from_alpha_vantage(ticker)

    if raw:
        db.upsert_eps_cache(raw)
        return [EpsRecord(**r) for r in raw]

    # AV failed — return stale cache if we have it
    if cached:
        log.warning(f"AV fetch failed for {ticker} — returning stale cache ({len(cached)} records)")
        return [EpsRecord(**r) for r in cached]

    return []


def get_eps_as_dataframe(ticker: str) -> pd.DataFrame | None:
    """Return EPS records as a DataFrame sorted by fiscal_date ascending."""
    records = get_eps_data(ticker)
    if not records:
        return None
    data = [r.model_dump() for r in records]
    df = pd.DataFrame(data)
    df["fiscal_date"] = pd.to_datetime(df["fiscal_date"])
    df["earnings_date"] = pd.to_datetime(df["earnings_date"], errors="coerce")
    return df.sort_values("fiscal_date").reset_index(drop=True)
