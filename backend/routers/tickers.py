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
from core.auth import get_current_user
from db.models import TrackedTicker

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/tickers",
    tags=["tickers"],
    dependencies=[Depends(get_current_user)],
)


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
