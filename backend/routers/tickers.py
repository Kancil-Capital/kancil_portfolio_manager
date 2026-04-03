"""
routers/tickers.py
GET    /api/tickers              — list all tracked tickers
POST   /api/tickers              — add a new ticker to tracked list
PATCH  /api/tickers/{ticker}     — update status
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db.supabase as db
import services.market_service as market_service
from core import ticker_cache
from core.auth import get_current_user
from db.models import TrackedTicker
from workers.scheduler import trigger_ondemand_scrape

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/tickers",
    tags=["tickers"],
    dependencies=[Depends(get_current_user)],
)


class AddTickerRequest(BaseModel):
    ticker: str
    added_by: str | None = None


class UpdateTickerRequest(BaseModel):
    status: Literal["held", "tracking", "untracked"]


@router.get("/symbols", response_model=list[str], operation_id="getTrackedSymbols")
def get_tracked_symbols():
    return ticker_cache.get_all()


@router.get("", response_model=list[TrackedTicker], operation_id="listTickers")
def list_tickers():
    rows = db.get_all_tracked_tickers(exclude_untracked=False)
    return [
        TrackedTicker(
            ticker=row["ticker"],
            added_at=row.get("added_at") or "",
            added_by=row.get("added_by"),
            status=row.get("status", "tracking"),
            last_scraped=row.get("last_scraped"),
            sentiment_ready=bool(row.get("sentiment_ready", False)),
        )
        for row in rows
    ]


@router.post("", response_model=TrackedTicker, status_code=201, operation_id="addTicker")
def add_ticker(body: AddTickerRequest):
    ticker = body.ticker.upper()

    # Idempotent — if already tracked, just return it
    existing = db.get_tracked_ticker(ticker)
    if existing:
        return TrackedTicker(
            ticker=ticker,
            added_at=existing.get("added_at") or "",
            added_by=existing.get("added_by"),
            status=existing.get("status", "tracking"),
            last_scraped=existing.get("last_scraped"),
            sentiment_ready=bool(existing.get("sentiment_ready", False)),
        )

    # Validate ticker with yfinance
    info = market_service.get_ticker_info(ticker)
    if not info:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found on yfinance")

    # Insert into tracked_tickers with metadata
    db.insert_tracked_ticker(
        ticker=ticker,
        added_by=body.added_by,
        name=info.get("longName") or info.get("shortName") or ticker,
        sector=info.get("sector") or "",
        region=info.get("region") or "",
        country=info.get("country") or "",
    )

    # Update in-memory cache
    ticker_cache.add(ticker)

    # Trigger on-demand scrape
    trigger_ondemand_scrape(ticker)

    row = db.get_tracked_ticker(ticker) or {}
    return TrackedTicker(
        ticker=ticker,
        added_at=row.get("added_at") or "",
        added_by=row.get("added_by"),
        status=row.get("status", "tracking"),
        last_scraped=row.get("last_scraped"),
        sentiment_ready=False,
    )


@router.patch("/{ticker}", response_model=TrackedTicker, operation_id="updateTickerStatus")
def update_ticker_status(ticker: str, body: UpdateTickerRequest):
    ticker = ticker.upper()

    existing = db.get_tracked_ticker(ticker)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not tracked")

    db.update_tracked_ticker(ticker, status=body.status)

    row = db.get_tracked_ticker(ticker) or {}
    return TrackedTicker(
        ticker=ticker,
        added_at=row.get("added_at") or "",
        added_by=row.get("added_by"),
        status=row.get("status", "tracking"),
        last_scraped=row.get("last_scraped"),
        sentiment_ready=bool(row.get("sentiment_ready", False)),
    )
