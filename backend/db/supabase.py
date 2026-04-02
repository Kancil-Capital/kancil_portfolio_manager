"""
db/supabase.py
Supabase client singleton + typed query helpers for all tables.

Note: the existing `tickers` table uses `symbol` as the primary text column
(not `ticker`) — matching the original SentimentPulse schema.
"""

import logging
from datetime import datetime

from supabase import Client, create_client

from core.config import settings

log = logging.getLogger(__name__)

# ── Client singleton ───────────────────────────────────────────────────────────

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_secret_key)
    return _client


# ── tickers (existing SentimentPulse table) ────────────────────────────────────

def get_ticker(symbol: str) -> dict | None:
    """Return ticker metadata row or None."""
    rows = (
        get_client()
        .table("tickers")
        .select("*")
        .eq("symbol", symbol)
        .execute()
        .data
    )
    return rows[0] if rows else None


def upsert_ticker(symbol: str, name: str, sector: str, region: str, country: str) -> None:
    get_client().table("tickers").upsert(
        {"symbol": symbol, "name": name, "sector": sector, "region": region, "country": country},
        on_conflict="symbol",
    ).execute()


def get_all_tickers() -> list[dict]:
    return get_client().table("tickers").select("*").execute().data or []


# ── tracked_tickers ────────────────────────────────────────────────────────────

def get_tracked_ticker(ticker: str) -> dict | None:
    rows = (
        get_client()
        .table("tracked_tickers")
        .select("*")
        .eq("ticker", ticker)
        .execute()
        .data
    )
    return rows[0] if rows else None


def insert_tracked_ticker(ticker: str, added_by: str | None = None) -> None:
    get_client().table("tracked_tickers").insert(
        {
            "ticker": ticker,
            "added_by": added_by,
            "status": "tracking",
            "sentiment_ready": False,
        }
    ).execute()


def update_tracked_ticker(ticker: str, **fields) -> None:
    get_client().table("tracked_tickers").update(fields).eq("ticker", ticker).execute()


def get_all_tracked_tickers(exclude_untracked: bool = True) -> list[dict]:
    query = get_client().table("tracked_tickers").select("*")
    if exclude_untracked:
        query = query.neq("status", "untracked")
    return query.execute().data or []


# ── sentiments RPC ─────────────────────────────────────────────────────────────

def get_sentiments_rpc(
    keywords: list[str],
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """
    Call the existing get_sentiments Supabase RPC.
    Returns joined article+sentiment rows.
    """
    try:
        return (
            get_client()
            .rpc(
                "get_sentiments",
                {
                    "keywords": keywords,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )
            .execute()
            .data
        ) or []
    except Exception as e:
        log.error(f"get_sentiments RPC failed: {e}")
        return []


# ── articles (for news feed) ───────────────────────────────────────────────────

def get_articles_paginated(
    ticker: str | None = None,
    sentiment_filter: str | None = None,  # "positive" | "neutral" | "negative"
    source: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Return (articles, total_count) with optional filters.
    Articles include their ticker list from sentiments.
    """
    client = get_client()

    # Build query against sentiments joined with articles
    query = (
        client.table("sentiments")
        .select("*, articles!inner(id, title, url, source, timestamp)", count="exact")
    )

    if ticker:
        query = query.eq("affected", ticker)

    if source:
        query = query.eq("articles.source", source)

    if sentiment_filter:
        if sentiment_filter == "positive":
            query = query.gt("score", 0.1)
        elif sentiment_filter == "negative":
            query = query.lt("score", -0.1)
        else:  # neutral
            query = query.gte("score", -0.1).lte("score", 0.1)

    result = (
        query
        .order("articles.timestamp", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    rows = result.data or []
    total = result.count or 0

    # Group by article — collect all tickers per article
    articles_map: dict[str, dict] = {}
    for row in rows:
        article = row.get("articles", {})
        art_id = article.get("id")
        if not art_id:
            continue
        if art_id not in articles_map:
            articles_map[art_id] = {
                "id": art_id,
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "timestamp": article.get("timestamp", ""),
                "sentiment": row.get("score", 0.0),
                "confidence": row.get("confidence", 0.0),
                "tickers": [],
            }
        affected = row.get("affected", "")
        if affected and affected not in articles_map[art_id]["tickers"]:
            articles_map[art_id]["tickers"].append(affected)

    return list(articles_map.values()), total


def get_articles_for_ticker(ticker: str, limit: int = 20) -> list[dict]:
    """Return recent articles for a ticker (for deep-dive articles panel)."""
    rows = (
        get_client()
        .table("sentiments")
        .select("score, confidence, articles!inner(id, title, url, source, timestamp)")
        .eq("affected", ticker)
        .order("articles.timestamp", desc=True)
        .limit(limit)
        .execute()
        .data
    ) or []

    results = []
    for row in rows:
        article = row.get("articles", {})
        results.append({
            "id": article.get("id", ""),
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "timestamp": article.get("timestamp", ""),
            "sentiment": row.get("score", 0.0),
            "confidence": row.get("confidence", 0.0),
        })
    return results


def get_sentiment_article_count(ticker: str) -> int:
    result = (
        get_client()
        .table("sentiments")
        .select("id", count="exact")
        .eq("affected", ticker)
        .execute()
    )
    return result.count or 0


# ── pead_signals ───────────────────────────────────────────────────────────────

def get_latest_pead_signal(ticker: str) -> dict | None:
    rows = (
        get_client()
        .table("pead_signals")
        .select("*")
        .eq("ticker", ticker)
        .order("computed_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def upsert_pead_signal(data: dict) -> None:
    get_client().table("pead_signals").insert(data).execute()


def get_pead_signals_for_tickers(tickers: list[str]) -> list[dict]:
    """Return latest pead_signal per ticker for the calendar view."""
    if not tickers:
        return []
    rows = (
        get_client()
        .table("pead_signals")
        .select("*")
        .in_("ticker", tickers)
        .order("computed_at", desc=True)
        .execute()
        .data
    ) or []

    # Keep only the most recent per ticker
    seen: set[str] = set()
    latest: list[dict] = []
    for row in rows:
        t = row.get("ticker", "")
        if t not in seen:
            seen.add(t)
            latest.append(row)
    return latest


# ── eps_cache ──────────────────────────────────────────────────────────────────

def get_eps_cache(ticker: str) -> list[dict]:
    return (
        get_client()
        .table("eps_cache")
        .select("*")
        .eq("ticker", ticker)
        .order("fiscal_date", desc=True)
        .execute()
        .data
    ) or []


def upsert_eps_cache(records: list[dict]) -> None:
    if not records:
        return
    get_client().table("eps_cache").upsert(records, on_conflict="ticker,fiscal_date").execute()


# ── articles (insert) ──────────────────────────────────────────────────────────

def upsert_articles(articles: list[dict]) -> list[dict]:
    """Upsert articles, return inserted rows (with IDs)."""
    result = (
        get_client()
        .table("articles")
        .upsert(articles, on_conflict="url", ignore_duplicates=True)
        .execute()
    )
    return result.data or []


def delete_articles(article_ids: list[str]) -> None:
    if not article_ids:
        return
    get_client().table("articles").delete().in_("id", article_ids).execute()


def insert_sentiments(sentiments: list[dict]) -> None:
    if not sentiments:
        return
    get_client().table("sentiments").insert(sentiments).execute()
