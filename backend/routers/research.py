"""
routers/research.py
GET  /api/research/{ticker}                    — Aggregated deep-dive
GET  /api/research/{ticker}/sentiment-status   — Polling endpoint for new tickers
WS   /api/research/{ticker}/scrape-stream      — Live scrape progress stream
"""

import asyncio
import logging
import queue as stdlib_queue
from concurrent.futures import ThreadPoolExecutor, as_completed

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

import db.supabase as db
import services.market_service as market_service
import services.pead_service as pead_service
import services.sentiment_service as sentiment_service
from core import ticker_cache
from core.auth import get_current_user, verify_token
from db.models import ArticleSummary, SentimentData, SentimentStatus, TickerDeepDive
from workers.scheduler import trigger_ondemand_scrape

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/research",
    tags=["research"],
)


def _get_or_create_ticker(ticker: str, added_by: str | None = None) -> dict:
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

    db.insert_tracked_ticker(
        ticker=ticker, name=name, sector=sector, region=region, country=country,
        added_by=added_by,
    )
    ticker_cache.add(ticker)

    # Trigger background sentiment scrape (does NOT block this request)
    trigger_ondemand_scrape(ticker)

    return {
        "ticker": ticker,
        "status": "tracking",
        "sentiment_ready": False,
        "added_by": added_by,
        "last_scraped": None,
        "name": name,
        "sector": sector,
    }


@router.get("/{ticker}", response_model=TickerDeepDive, operation_id="getResearch")
def get_research(ticker: str, user: dict = Depends(get_current_user)):
    ticker = ticker.upper()

    tracked = _get_or_create_ticker(ticker, added_by=user.get("email"))

    name = tracked.get("name") or ticker
    sector = tracked.get("sector") or ""
    status = tracked.get("status", "tracking")
    never_scraped = not tracked.get("sentiment_ready") and not tracked.get("last_scraped")
    if status == "tracking" and never_scraped:
        status = "new"

    sentiment_ready = bool(tracked.get("sentiment_ready", False))

    # Always fetch price; fetch sentiment + pre-stored PEAD only when ready
    price_data = None
    sentiment_data = None
    pead_signal = None

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures: dict = {executor.submit(market_service.get_price_data, ticker): "price"}
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

    # For new tickers compute PEAD immediately — it doesn't depend on sentiment
    if not sentiment_ready and pead_signal is None:
        try:
            pead_signal = pead_service.compute_pead_signal(ticker)
        except Exception as e:
            log.error(f"PEAD compute failed for new ticker {ticker}: {e}")

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


@router.get(
    "/{ticker}/sentiment",
    response_model=SentimentData,
    operation_id="getTickerSentiment",
    dependencies=[Depends(get_current_user)],
)
def get_ticker_sentiment(
    ticker: str,
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    days: int = Query(default=180, ge=7, le=730),
):
    ticker = ticker.upper()
    data = sentiment_service.get_sentiment_data(ticker, days=days, min_confidence=min_confidence)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No sentiment data for '{ticker}'")
    return data


@router.get(
    "/{ticker}/sentiment-status",
    response_model=SentimentStatus,
    operation_id="getSentimentStatus",
    dependencies=[Depends(get_current_user)],
)
def get_sentiment_status(ticker: str):
    ticker = ticker.upper()
    tracked = db.get_tracked_ticker(ticker)
    if not tracked:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not tracked")

    ready = bool(tracked.get("sentiment_ready", False))
    article_count = db.get_sentiment_article_count(ticker)

    estimated_remaining: int | None = None
    if not ready:
        estimated_remaining = max(0, 100 - article_count * 2)

    return SentimentStatus(
        ready=ready,
        article_count=article_count,
        estimated_seconds_remaining=estimated_remaining if not ready else None,
    )


# ── WebSocket scrape stream ────────────────────────────────────────────────────

# The router has a global Depends(get_current_user) which does not apply to
# WebSocket routes (FastAPI skips non-HTTP dependencies on WS endpoints).
# We verify the JWT manually via the ?token= query parameter instead.

@router.websocket("/{ticker}/scrape-stream")
async def scrape_stream(websocket: WebSocket, ticker: str, token: str | None = None):
    """
    Stream scrape-and-inference progress for a newly tracked ticker.

    Client connects with: ws://.../api/research/{TICKER}/scrape-stream?token=<jwt>

    Events pushed as JSON:
        { stage, article_title, sentiment, articles_done, articles_total }

    stage values:
        "analyzing" — article just processed by FinBERT
        "done"      — pipeline finished; sentiment_ready is now true
        "error"     — auth failure or internal error
    """
    await websocket.accept()
    ticker = ticker.upper()

    # Verify JWT passed as query param
    if not token:
        await websocket.send_json({"stage": "error", "detail": "Missing token"})
        await websocket.close(code=4001)
        return

    try:
        verify_token(token)
    except pyjwt.PyJWTError:
        await websocket.send_json({"stage": "error", "detail": "Invalid or expired token"})
        await websocket.close(code=4001)
        return

    # If ticker is already ready, there's nothing to stream
    tracked = db.get_tracked_ticker(ticker)
    if not tracked or tracked.get("sentiment_ready"):
        await websocket.send_json({
            "stage": "done", "articles_done": 0,
            "article_title": None, "sentiment": None, "articles_total": None,
        })
        await websocket.close()
        return

    # The background scrape is triggered by _get_or_create_ticker (in get_research).
    # It registers a queue in scrape_stream.py just before starting work.
    # We poll for up to 3 seconds to let the thread get started.
    from workers.scrape_stream import get_scrape_queue

    event_queue = None
    for _ in range(30):
        event_queue = get_scrape_queue(ticker)
        if event_queue is not None:
            break
        await asyncio.sleep(0.1)

    if event_queue is None:
        # Scrape hasn't started or already finished — send done and exit
        await websocket.send_json({
            "stage": "done", "articles_done": 0,
            "article_title": None, "sentiment": None, "articles_total": None,
        })
        await websocket.close()
        return

    loop = asyncio.get_event_loop()

    try:
        while True:
            try:
                # Block in an executor thread so the event loop stays free
                event = await loop.run_in_executor(
                    None, lambda: event_queue.get(timeout=120)
                )
            except stdlib_queue.Empty:
                log.warning(f"scrape-stream timed out for {ticker}")
                break

            await websocket.send_json({
                "stage": event.stage,
                "article_title": event.article_title,
                "sentiment": event.sentiment,
                "articles_done": event.articles_done,
                "articles_total": event.articles_total,
            })

            if event.stage == "done":
                break

    except WebSocketDisconnect:
        log.info(f"scrape-stream client disconnected for {ticker}")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
