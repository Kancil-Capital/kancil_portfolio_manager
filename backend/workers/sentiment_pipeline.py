"""
workers/sentiment_pipeline.py
Daily sentiment pipeline — adapted from sentiment-analysis/app/data/pipeline.py.
Key change: reads tickers from tracked_tickers table instead of hardcoded list.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime, timedelta, timezone

import db.supabase as db
from core.sentiment import get_sentiment
from workers.scrapers import CNBCScraper, FinvizScraper, YFinanceScraper
from workers.scrapers.base import Article

log = logging.getLogger(__name__)


def _process_articles(articles: dict[str, dict]) -> tuple[list[str], list[dict]]:
    """
    Run FinBERT on a dict of {article_id: {title, body, source, author}}.
    Returns (ids_to_delete, sentiments_to_insert).
    """
    log.info(f"Processing {len(articles)} articles for sentiment")
    to_delete: list[str] = []
    sentiments: list[dict] = []

    for article_id, content in articles.items():
        results = get_sentiment(
            title=content["title"],
            body=content["body"],
            source=content["source"],
            author=content.get("author"),
        )
        log.info(f"Article {article_id}: {len(results)} sentiment(s)")

        if not results:
            to_delete.append(article_id)
            continue

        for affected, score, confidence in results:
            sentiments.append({
                "article_id": article_id,
                "affected": affected,
                "score": score,
                "confidence": confidence,
            })

    return to_delete, sentiments


def _insert_articles_and_sentiments(articles: list[Article]) -> None:
    """Upsert articles, run sentiment, persist sentiments."""
    if not articles:
        return

    log.info(f"Upserting {len(articles)} articles")
    inserted = db.upsert_articles([a.to_json() for a in articles])
    log.info(f"Inserted {len(inserted)} unique articles")

    articles_to_process = {
        row["id"]: {
            "title": row["title"],
            "body": row["body"],
            "source": row["source"],
            "author": row.get("author"),
        }
        for row in inserted
    }

    to_delete, sentiments = _process_articles(articles_to_process)

    if to_delete:
        log.info(f"Deleting {len(to_delete)} articles with no sentiment")
        db.delete_articles(to_delete)

    if sentiments:
        log.info(f"Inserting {len(sentiments)} sentiments")
        db.insert_sentiments(sentiments)


def run_daily_sentiment_pipeline() -> None:
    """
    Daily pipeline — runs at 07:00 UTC.
    Fetches news for all tracked (non-untracked) tickers + their sector/region keywords.
    """
    log.info("=== Daily sentiment pipeline started ===")

    tracked = db.get_all_tracked_tickers(exclude_untracked=True)
    if not tracked:
        log.info("No tracked tickers — pipeline complete")
        return

    # Collect ticker symbols and unique keywords
    tickers: list[str] = []
    keywords: set[str] = set()
    for row in tracked:
        ticker = row["ticker"]
        tickers.append(ticker)
        # Get metadata from tracked_tickers for keywords
        info = db.get_tracked_ticker(ticker)
        if info:
            for key in ("region", "sector", "country"):
                val = info.get(key)
                if val:
                    keywords.add(val)

    latest = db.get_latest_article_timestamp()
    from_ = latest if latest else datetime.now(tz=timezone.utc) - timedelta(days=2)

    cnbc = CNBCScraper()
    finviz = FinvizScraper()
    yf_scraper = YFinanceScraper()

    # Sector / region news from CNBC only
    all_articles: list[Article] = []
    for kw in keywords:
        log.info(f"Fetching keyword '{kw}' from CNBC")
        all_articles.extend(cnbc.scrape(kw, from_, is_ticker=False))

    # Ticker-specific news from all three sources
    for ticker in tickers:
        log.info(f"Fetching ticker '{ticker}'")
        for scraper in [cnbc, finviz, yf_scraper]:
            all_articles.extend(scraper.scrape(ticker, from_, is_ticker=True))

    _insert_articles_and_sentiments(all_articles)

    # Update last_scraped timestamp
    now = datetime.now(tz=timezone.utc).isoformat()
    for row in tracked:
        db.update_tracked_ticker(row["ticker"], last_scraped=now)

    log.info(f"=== Daily pipeline complete — {len(all_articles)} articles processed ===")


def run_ondemand_ticker_scrape(ticker: str, days_back: int = 30) -> None:
    """
    On-demand scrape triggered when a new ticker is added.
    Runs in a background thread; sets sentiment_ready=True when done.
    """
    log.info(f"On-demand scrape started for {ticker}")

    from_ = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    cnbc = CNBCScraper()
    finviz = FinvizScraper()
    yf_scraper = YFinanceScraper()

    all_articles: list[Article] = []

    # Also scrape sector/region keywords
    info = db.get_tracked_ticker(ticker)
    if info:
        for key in ("region", "sector", "country"):
            val = info.get(key)
            if val:
                log.info(f"Fetching keyword '{val}' for {ticker}")
                all_articles.extend(cnbc.scrape(val, from_, is_ticker=False))

    for scraper in [cnbc, finviz, yf_scraper]:
        all_articles.extend(scraper.scrape(ticker, from_, is_ticker=True))

    _insert_articles_and_sentiments(all_articles)

    # Mark ready
    db.update_tracked_ticker(
        ticker,
        sentiment_ready=True,
        last_scraped=datetime.now(tz=timezone.utc).isoformat(),
    )
    log.info(f"On-demand scrape complete for {ticker} — {len(all_articles)} articles")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        days_back = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        run_ondemand_ticker_scrape(ticker, days_back=days_back)
    else:
        run_daily_sentiment_pipeline()
