"""
db/supabase.py
Supabase client singleton + typed query helpers for all tables.
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


def insert_tracked_ticker(
    ticker: str,
    added_by: str | None = None,
    name: str = "",
    sector: str = "",
    region: str = "",
    country: str = "",
) -> None:
    get_client().table("tracked_tickers").insert(
        {
            "ticker": ticker,
            "added_by": added_by,
            "status": "tracking",
            "sentiment_ready": False,
            "name": name,
            "sector": sector,
            "region": region,
            "country": country,
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
    Uses the get_articles_paginated RPC to allow ordering by articles.timestamp.
    """
    rows = (
        get_client()
        .rpc(
            "get_articles_paginated",
            {
                "p_ticker": ticker,
                "p_sentiment": sentiment_filter,
                "p_source": source,
                "p_limit": limit,
                "p_offset": offset,
            },
        )
        .execute()
        .data
    ) or []

    total = int(rows[0]["total_count"]) if rows else 0
    articles = [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "timestamp": row["timestamp"],
            "sentiment": row["sentiment"],
            "confidence": row["confidence"],
            "tickers": row["tickers"] or [],
        }
        for row in rows
    ]
    return articles, total


def get_articles_for_ticker(ticker: str, limit: int = 20) -> list[dict]:
    """Return recent articles for a ticker (for deep-dive articles panel)."""
    rows = (
        get_client()
        .table("sentiments")
        .select("score, confidence, articles!inner(id, title, url, source, timestamp)")
        .eq("affected", ticker)
        .order("timestamp", desc=True, foreign_table="articles")
        .limit(limit)
        .execute()
        .data
    ) or []

    results = []
    for row in rows:
        article = row.get("articles", {})
        results.append({
            "id": str(article.get("id", "")),
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
        .select("article_id", count="exact")
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


# ── articles (read) ───────────────────────────────────────────────────────────

def get_latest_article_timestamp() -> datetime | None:
    """Return the timestamp of the most recent article, or None if table is empty."""
    from datetime import datetime
    rows = (
        get_client()
        .table("articles")
        .select("timestamp")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None
    raw = rows[0].get("timestamp")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


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
