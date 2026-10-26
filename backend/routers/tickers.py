"""
routers/tickers.py
GET    /api/tickers              — list all tracked tickers
PATCH  /api/tickers/{ticker}     — update status
DELETE /api/tickers/{ticker}     — delete (owner or admin only)
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

import db.supabase as db
from core import ticker_cache
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


def _row_to_ticker(row: dict) -> TrackedTicker:
    return TrackedTicker(
        ticker=row["ticker"],
        name=row.get("name") or row["ticker"],
        added_at=row.get("added_at") or "",
        added_by=row.get("added_by"),
        status=row.get("status", "tracking"),
        last_scraped=row.get("last_scraped"),
        sentiment_ready=bool(row.get("sentiment_ready", False)),
    )


@router.get("/symbols", response_model=list[str], operation_id="getTrackedSymbols")
def get_tracked_symbols():
    return ticker_cache.get_all()


@router.get("", response_model=list[TrackedTicker], operation_id="listTickers")
def list_tickers():
    rows = db.get_all_tracked_tickers(exclude_untracked=False)
    return [_row_to_ticker(row) for row in rows]


@router.patch("/{ticker}", response_model=TrackedTicker, operation_id="updateTickerStatus")
def update_ticker_status(ticker: str, body: UpdateTickerRequest):
    ticker = ticker.upper()

    existing = db.get_tracked_ticker(ticker)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not tracked")

    db.update_tracked_ticker(ticker, status=body.status)

    row = db.get_tracked_ticker(ticker) or {}
    return _row_to_ticker(row)


@router.delete("/{ticker}", status_code=204, operation_id="deleteTicker")
def delete_ticker(ticker: str, user: dict = Depends(get_current_user)):
    ticker = ticker.upper()

    existing = db.get_tracked_ticker(ticker)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not tracked")

    user_email = user.get("email")
    is_owner = bool(user_email and user_email == existing.get("added_by"))
    # app_metadata is only writable server-side; user_metadata is user-editable
    is_admin = user.get("app_metadata", {}).get("role") == "admin"

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="You can only delete tickers you added",
        )

    db.delete_tracked_ticker(ticker)
    ticker_cache.remove(ticker)
    return Response(status_code=204)
