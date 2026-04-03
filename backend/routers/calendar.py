"""
routers/calendar.py
GET /api/calendar?days_ahead=30
"""

import logging

from fastapi import APIRouter, Depends, Query

import db.supabase as db
from core.auth import get_current_user
import services.market_service as market_service
import services.sentiment_service as sentiment_service
from db.models import CalendarEvent, CalendarResponse

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=CalendarResponse, operation_id="getCalendar")
def get_calendar(days_ahead: int = Query(default=30, ge=1, le=365)):
    # Get all tracked tickers
    tracked = db.get_all_tracked_tickers(exclude_untracked=True)
    if not tracked:
        return CalendarResponse(events=[])

    tickers = [row["ticker"] for row in tracked]
    tracked_map = {row["ticker"]: row for row in tracked}

    # Get upcoming earnings
    earnings_events = market_service.get_upcoming_earnings(tickers, days_ahead=days_ahead)
    if not earnings_events:
        return CalendarResponse(events=[])

    # Get pre-computed PEAD signals
    pead_rows = db.get_pead_signals_for_tickers(tickers)
    pead_map = {row["ticker"]: row for row in pead_rows}

    # Get ticker metadata
    events: list[CalendarEvent] = []
    for ev in earnings_events:
        ticker = ev["ticker"]
        tracked_row = tracked_map.get(ticker, {})
        name = tracked_row.get("name") or ticker
        sector = tracked_row.get("sector") or ""
        status = tracked_map.get(ticker, {}).get("status", "tracking")

        # Sentiment score (7-day mean)
        sentiment_score = None
        try:
            sentiment_score = sentiment_service.get_latest_sentiment_score(ticker, days=7)
        except Exception as e:
            log.debug(f"Could not get sentiment for {ticker}: {e}")

        # PEAD signal fields
        pead = pead_map.get(ticker, {})
        sue = pead.get("sue")
        outperform_prob = None
        hist_beat_rate = pead.get("hist_beat_rate")
        ret_5d_pre = pead.get("ret_5d_pre")

        if pead:
            best_horizon = pead.get("best_horizon", 5)
            prob_key = f"outperform_prob_{best_horizon}d"
            outperform_prob = pead.get(prob_key)

        events.append(CalendarEvent(
            ticker=ticker,
            name=name,
            sector=sector,
            status=status,
            earnings_date=ev["earnings_date"],
            days_to_earnings=ev["days_to_earnings"],
            sentiment_score=round(sentiment_score, 4) if sentiment_score is not None else None,
            sue=round(float(sue), 4) if sue is not None else None,
            outperform_prob=round(float(outperform_prob), 4) if outperform_prob is not None else None,
            hist_beat_rate=round(float(hist_beat_rate), 4) if hist_beat_rate is not None else None,
            ret_5d_pre=round(float(ret_5d_pre), 4) if ret_5d_pre is not None else None,
        ))

    # Sort by days_to_earnings ascending
    events.sort(key=lambda e: e.days_to_earnings)

    return CalendarResponse(events=events)
