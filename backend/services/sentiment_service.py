"""
services/sentiment_service.py
Wraps SentimentPulse Supabase queries + computes analytics (daily aggregates,
lag correlations, stats, keyword cloud) from the articles/sentiments tables.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import db.supabase as db
import services.market_service as market_service
from db.models import (
    KeywordCount,
    LagCorrelation,
    ScatterPoint,
    SentimentDaily,
    SentimentData,
    SentimentStats,
)

log = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "for", "to", "of", "and", "or", "but",
    "is", "are", "was", "were", "its", "it", "by", "as", "from", "this", "that",
    "with", "be", "has", "have", "had", "will", "would", "could", "should", "may",
    "might", "not", "no", "new", "after", "before", "over", "up", "down", "out",
    "into", "than", "more", "also", "says", "said", "about", "amid", "how", "why",
    "what", "when", "where", "who", "can", "all", "just", "one", "two", "his",
    "her", "their", "its", "our", "we", "us", "they", "them", "s", "q", "vs",
    "amid", "still", "well", "back", "first", "last", "report", "reports",
}


# ── Keyword extraction ─────────────────────────────────────────────────────────

def _extract_keywords(titles: list[str], top_n: int = 30) -> list[KeywordCount]:
    word_counts: Counter = Counter()
    for title in titles:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())
        for word in words:
            if word not in STOPWORDS:
                word_counts[word] += 1
    return [KeywordCount(word=w, count=c) for w, c in word_counts.most_common(top_n)]


# ── Lag correlation ────────────────────────────────────────────────────────────

def _compute_lag_correlations(
    daily_sentiment: pd.Series,
    ticker: str,
    max_lag: int = 8,
) -> tuple[list[LagCorrelation], list[ScatterPoint]]:
    """Correlate daily sentiment[t] with price return[t+lag].
    Returns (correlations, scatter_points) where scatter_points are 1d lag pairs."""
    try:
        price_df = market_service.get_raw_price_df(ticker, period="1y")
        if price_df is None or len(price_df) < 20:
            return [], []

        price_returns = price_df["close"].pct_change().rename("ret")
        price_returns.index = price_returns.index.normalize()

        sent = daily_sentiment.copy()
        sent.index = pd.to_datetime(sent.index).tz_localize(None).normalize()

        correlations = []
        scatter_points: list[ScatterPoint] = []
        for lag in range(1, max_lag + 1):
            shifted = sent.shift(lag)
            merged = pd.concat([shifted, price_returns], axis=1).dropna()
            if len(merged) < 10:
                continue
            corr = merged.iloc[:, 0].corr(merged.iloc[:, 1])
            if not np.isnan(corr):
                correlations.append(LagCorrelation(lag=lag, correlation=round(float(corr), 4)))
            if lag == 1:
                for _, row in merged.iterrows():
                    scatter_points.append(ScatterPoint(
                        sentiment=round(float(row.iloc[0]), 4),
                        next_day_return=round(float(row.iloc[1]) * 100, 4),
                    ))

        return correlations, scatter_points
    except Exception as e:
        log.error(f"Lag correlation failed for {ticker}: {e}")
        return [], []


# ── Main service function ──────────────────────────────────────────────────────

def get_sentiment_data(
    ticker: str, days: int = 180, min_confidence: float | None = None
) -> SentimentData | None:
    """
    Build SentimentData for a ticker.
    Queries sentiments via Supabase RPC, aggregates daily stats, computes analytics.
    Returns None if no sentiment data exists.
    """
    # Get ticker metadata for keyword lookup
    ticker_info = db.get_tracked_ticker(ticker)
    if not ticker_info:
        keywords = [ticker]
    else:
        keywords = list(filter(None, [
            ticker_info.get("region"),
            ticker_info.get("sector"),
            ticker_info.get("country"),
        ]))
        if ticker not in keywords:
            keywords.insert(0, ticker)

    end_date = datetime.now(tz=timezone.utc)
    start_date = end_date - timedelta(days=days)

    rows = db.get_sentiments_rpc(keywords, start_date, end_date)
    if not rows:
        return None

    df = pd.DataFrame(rows)
    if df.empty:
        return None

    # Normalise column names (RPC aliases a_timestamp for article timestamp)
    if "a_timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["a_timestamp"])
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    else:
        return None

    df["date"] = df["timestamp"].dt.tz_convert(None).dt.normalize()

    # Filter to ticker-specific sentiment
    ticker_df = df[df["affected"] == ticker].copy()
    if ticker_df.empty:
        return None

    # Apply confidence filter
    if min_confidence is not None:
        ticker_df = ticker_df[ticker_df["confidence"] >= min_confidence]
        if ticker_df.empty:
            return None

    # ── Daily aggregation ──────────────────────────────────────────────────────
    daily_records: list[SentimentDaily] = []
    for dt, group in ticker_df.groupby("date"):
        scores = group["sentiment"].values
        pos = int((scores > 0.1).sum())
        neg = int((scores < -0.1).sum())
        neu = len(scores) - pos - neg
        daily_records.append(SentimentDaily(
            date=str(dt.date()),
            mean=round(float(scores.mean()), 4),
            positive=pos,
            neutral=neu,
            negative=neg,
            count=len(scores),
        ))
    daily_records.sort(key=lambda x: x.date)

    # ── Lag correlations ───────────────────────────────────────────────────────
    daily_mean = ticker_df.groupby("date")["sentiment"].mean()
    lag_correlations, scatter_points = _compute_lag_correlations(daily_mean, ticker)

    # ── Stats ──────────────────────────────────────────────────────────────────
    cutoff_30d = end_date - timedelta(days=30)
    recent_df = ticker_df[ticker_df["timestamp"] >= cutoff_30d.isoformat()]
    mean_30d = float(recent_df["sentiment"].mean()) if not recent_df.empty else 0.0
    median_30d = float(recent_df["sentiment"].median()) if not recent_df.empty else 0.0

    all_scores = ticker_df["sentiment"].values
    total = len(all_scores)
    positive_count = int((all_scores > 0.1).sum())
    negative_count = int((all_scores < -0.1).sum())
    neutral_count = total - positive_count - negative_count
    net_sentiment = float(all_scores.mean())
    sentiment_ratio = positive_count / total if total > 0 else 0.5

    best_lag = 0
    best_lag_corr = 0.0
    if lag_correlations:
        best = max(lag_correlations, key=lambda x: abs(x.correlation))
        best_lag = best.lag
        best_lag_corr = best.correlation

    stats = SentimentStats(
        mean_30d=round(mean_30d, 4),
        median_30d=round(median_30d, 4),
        net_sentiment=round(net_sentiment, 4),
        total_articles=total,
        positive_count=positive_count,
        neutral_count=neutral_count,
        negative_count=negative_count,
        sentiment_ratio=round(sentiment_ratio, 4),
        best_lag=best_lag,
        best_lag_correlation=round(best_lag_corr, 4),
    )

    # ── Keywords ───────────────────────────────────────────────────────────────
    titles = ticker_df["title"].dropna().tolist() if "title" in ticker_df.columns else []
    keywords_list = _extract_keywords(titles)

    scores = [round(float(s), 4) for s in all_scores.tolist()]

    return SentimentData(
        daily=daily_records,
        lag_correlations=lag_correlations,
        stats=stats,
        keywords=keywords_list,
        scores=scores,
        scatter_points=scatter_points,
    )


def get_latest_sentiment_score(ticker: str, days: int = 7) -> float | None:
    """Return the mean sentiment score for the last N days. Used in calendar."""
    ticker_info = db.get_tracked_ticker(ticker)
    keywords = [ticker]
    if ticker_info:
        keywords = list(filter(None, [
            ticker_info.get("region"),
            ticker_info.get("sector"),
            ticker_info.get("country"),
        ]))
        if ticker not in keywords:
            keywords.insert(0, ticker)

    end_date = datetime.now(tz=timezone.utc)
    start_date = end_date - timedelta(days=days)
    rows = db.get_sentiments_rpc(keywords, start_date, end_date)
    if not rows:
        return None

    df = pd.DataFrame(rows)
    ticker_df = df[df["affected"] == ticker] if "affected" in df.columns else df
    if ticker_df.empty:
        return None

    return round(float(ticker_df["sentiment"].mean()), 4)
