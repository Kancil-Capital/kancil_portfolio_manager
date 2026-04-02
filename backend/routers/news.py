"""
routers/news.py
GET /api/news?ticker=&sentiment=&source=&limit=20&offset=0
"""

from fastapi import APIRouter, Depends, Query

import db.supabase as db
from core.auth import get_current_user
from db.models import ArticleWithTickers, NewsResponse

router = APIRouter(
    prefix="/api/news",
    tags=["news"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=NewsResponse)
def get_news(
    ticker: str | None = Query(default=None),
    sentiment: str | None = Query(default=None, pattern="^(positive|neutral|negative)$"),
    source: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows, total = db.get_articles_paginated(
        ticker=ticker.upper() if ticker else None,
        sentiment_filter=sentiment,
        source=source,
        limit=limit,
        offset=offset,
    )

    articles = [
        ArticleWithTickers(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            source=row["source"],
            timestamp=row["timestamp"],
            sentiment=round(float(row["sentiment"]), 4),
            confidence=round(float(row["confidence"]), 4),
            tickers=row.get("tickers", []),
        )
        for row in rows
    ]

    return NewsResponse(articles=articles, total=total)
