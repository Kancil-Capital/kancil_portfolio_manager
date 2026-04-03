"""
routers/research.py
GET /api/research/{ticker}          — Aggregated deep-dive
GET /api/research/{ticker}/sentiment-status — Polling endpoint for new tickers
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException

import db.supabase as db
from core import ticker_cache
from core.auth import get_current_user
import services.market_service as market_service
import services.pead_service as pead_service
import services.sentiment_service as sentiment_service
from db.models import ArticleSummary, SentimentStatus, TickerDeepDive
from workers.scheduler import trigger_ondemand_scrape

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/research",
    tags=["research"],
    dependencies=[Depends(get_current_user)],
)


def _get_or_create_ticker(ticker: str) -> dict:
    """
    Return tracked_ticker row. If ticker is new, insert into tickers + tracked_tickers
    and trigger on-demand scrape.
    """
    tracked = db.get_tracked_ticker(ticker)
    if tracked:
        return tracked

    # New ticker — get metadata from yfinance
    info = market_service.get_ticker_info(ticker)
    if not info:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

    name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector") or ""
    region = info.get("financialCurrency") or info.get("region") or ""
    country = info.get("country") or ""

    # Insert into tracked_tickers with metadata
    db.insert_tracked_ticker(ticker=ticker, name=name, sector=sector, region=region, country=country)

    # Update in-memory cache
    ticker_cache.add(ticker)

    # Trigger background scrape
    trigger_ondemand_scrape(ticker)

    return {
        "ticker": ticker,
        "status": "tracking",
        "sentiment_ready": False,
        "added_by": None,
        "last_scraped": None,
    }


@router.get("/{ticker}", response_model=TickerDeepDive, operation_id="getResearch")
def get_research(ticker: str):
    ticker = ticker.upper()

    tracked = _get_or_create_ticker(ticker)

    name = tracked.get("name") or ticker
    sector = tracked.get("sector") or ""

    status = tracked.get("status", "tracking")
    # If just inserted and status is still 'tracking' but was new, reflect it
    if status == "tracking" and not tracked.get("sentiment_ready") and not tracked.get("last_scraped"):
        status = "new"

    sentiment_ready = bool(tracked.get("sentiment_ready", False))

    # Fetch price, sentiment, PEAD in parallel
    price_data = None
    sentiment_data = None
    pead_signal = None

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(market_service.get_price_data, ticker): "price",
        }
        if sentiment_ready:
            futures[executor.submit(sentiment_service.get_sentiment_data, ticker)] = "sentiment"
            futures[executor.submit(pead_service.get_pead_signal, ticker)] = "pead"

        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
                if key == "price":
                    price_data = result
                elif key == "sentiment":
                    sentiment_data = result
                elif key == "pead":
                    pead_signal = result
            except Exception as e:
                log.error(f"Failed fetching {key} for {ticker}: {e}")

    if price_data is None:
        raise HTTPException(status_code=502, detail=f"Could not fetch price data for {ticker}")

    # If model exists but sentiment_ready, also fetch pead (it doesn't require sentiment)
    if sentiment_ready and pead_signal is None:
        try:
            pead_signal = pead_service.get_pead_signal(ticker)
        except Exception as e:
            log.error(f"PEAD signal fetch failed for {ticker}: {e}")

    # Recent articles
    raw_articles = db.get_articles_for_ticker(ticker, limit=20)
    articles = [
        ArticleSummary(
            id=a["id"],
            title=a["title"],
            url=a["url"],
            source=a["source"],
            timestamp=a["timestamp"],
            sentiment=a["sentiment"],
            confidence=a["confidence"],
        )
        for a in raw_articles
    ]

    return TickerDeepDive(
        ticker=ticker,
        name=name,
        sector=sector,
        status=status,
        sentiment_ready=sentiment_ready,
        price=price_data,
        sentiment=sentiment_data,
        pead=pead_signal,
        articles=articles,
    )


@router.get("/{ticker}/sentiment-status", response_model=SentimentStatus, operation_id="getSentimentStatus")
def get_sentiment_status(ticker: str):
    ticker = ticker.upper()
    tracked = db.get_tracked_ticker(ticker)
    if not tracked:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not tracked")

    ready = bool(tracked.get("sentiment_ready", False))
    article_count = db.get_sentiment_article_count(ticker)

    # Rough estimate: ~2s per article for FinBERT, based on typical batch
    estimated_remaining: int | None = None
    if not ready:
        # If we know how many have been processed and how many total expected
        # Use a simple heuristic: 30 days of news ≈ 50 articles, ~100s total
        estimated_remaining = max(0, 100 - article_count * 2)

    return SentimentStatus(
        ready=ready,
        article_count=article_count,
        estimated_seconds_remaining=estimated_remaining if not ready else None,
    )
