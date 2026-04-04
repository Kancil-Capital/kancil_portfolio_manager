"""
workers/sentiment_pipeline.py
Daily sentiment pipeline — adapted from sentiment-analysis/app/data/pipeline.py.
Key change: reads tickers from tracked_tickers table instead of hardcoded list.

Architecture: producer-consumer pattern.
  Producers  — scraper threads (I/O-bound) push Article objects into a shared queue.
  Consumer   — single FinBERT thread pulls from the queue and starts inference
               immediately, overlapping with ongoing scraping.
For on-demand scrapes, the consumer also emits ScrapeEvents so the WebSocket
endpoint can stream progress to the frontend in real time.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import db.supabase as db
from core.sentiment import get_sentiment
from workers.scrapers import CNBCScraper, FinvizScraper, YFinanceScraper
from workers.scrapers.base import Article

log = logging.getLogger(__name__)


# ── Shared producer / consumer helpers ────────────────────────────────────────

def _run_scraper_pool(
    scrape_tasks: list[tuple],
    article_queue: "queue.Queue[Article | None]",
    from_: datetime,
) -> None:
    """
    Run (scraper, keyword, is_ticker) tasks in parallel.
    Pushes Article objects to article_queue, then a None sentinel when done.
    """
    def _scrape(scraper, keyword, is_ticker):
        try:
            articles = scraper.scrape(keyword, from_, is_ticker=is_ticker)
            for a in articles:
                article_queue.put(a)
        except Exception as e:
            log.error(f"Scraper {scraper.name} ({keyword}) failed: {e}")

    with ThreadPoolExecutor(max_workers=min(len(scrape_tasks), 6)) as pool:
        futs = [pool.submit(_scrape, s, k, t) for s, k, t in scrape_tasks]
        for f in as_completed(futs):
            f.result()  # re-raise unexpected errors so they surface in logs

    article_queue.put(None)  # sentinel — tells the consumer we're done


def _run_finbert_consumer(
    article_queue: "queue.Queue[Article | None]",
    event_queue: "queue.Queue | None" = None,
) -> int:
    """
    Pull Articles from article_queue, upsert to DB, run FinBERT, persist sentiments.
    Returns the count of newly-processed (non-duplicate) articles.
    If event_queue is provided, emits ScrapeEvents for each article and a final 'done'.
    """
    from workers.scrape_stream import ScrapeEvent

    articles_done = 0

    while True:
        try:
            item = article_queue.get(timeout=120)
        except queue.Empty:
            log.warning("FinBERT consumer: timed out waiting for articles — stopping")
            break

        if item is None:  # sentinel
            break

        # Upsert single article — returns [] if URL already in DB (duplicate)
        inserted = db.upsert_articles([item.to_json()])
        if not inserted:
            continue

        row = inserted[0]
        results = get_sentiment(
            title=row["title"],
            body=row["body"],
            source=row["source"],
            author=row.get("author"),
        )

        if not results:
            db.delete_articles([row["id"]])
        else:
            db.insert_sentiments([
                {"article_id": row["id"], "affected": e, "score": s, "confidence": c}
                for e, s, c in results
            ])
            articles_done += 1

            if event_queue is not None:
                event_queue.put(ScrapeEvent(
                    stage="analyzing",
                    article_title=row["title"],
                    sentiment=results[0][1],   # score of the highest-confidence entity
                    articles_done=articles_done,
                ))

    if event_queue is not None:
        event_queue.put(ScrapeEvent(stage="done", articles_done=articles_done))

    return articles_done


def _run_pipeline(
    scrape_tasks: list[tuple],
    from_: datetime,
    event_queue: "queue.Queue | None" = None,
) -> int:
    """
    Spin up producer + consumer threads and wait for both to finish.
    Returns total articles processed.
    """
    article_queue: queue.Queue[Article | None] = queue.Queue()

    producer = threading.Thread(
        target=_run_scraper_pool,
        args=(scrape_tasks, article_queue, from_),
        daemon=True,
    )
    consumer = threading.Thread(
        target=_run_finbert_consumer,
        args=(article_queue, event_queue),
        daemon=True,
    )

    producer.start()
    consumer.start()
    producer.join()
    consumer.join()

    return 0  # count is internal to consumer; callers don't need it


# ── Public pipeline functions ──────────────────────────────────────────────────

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

    tickers: list[str] = [row["ticker"] for row in tracked]
    keywords: set[str] = set()
    for row in tracked:
        info = db.get_tracked_ticker(row["ticker"])
        if info:
            for key in ("region", "sector", "country"):
                val = info.get(key)
                if val:
                    keywords.add(val)

    latest = db.get_latest_article_timestamp()
    from_ = latest if latest else datetime.now(tz=timezone.utc) - timedelta(days=2)

    # Build task list — new scraper instance per task to avoid shared state
    scrape_tasks: list[tuple] = []
    for kw in keywords:
        scrape_tasks.append((CNBCScraper(), kw, False))
    for ticker in tickers:
        scrape_tasks.append((CNBCScraper(), ticker, True))
        scrape_tasks.append((FinvizScraper(), ticker, True))
        scrape_tasks.append((YFinanceScraper(), ticker, True))

    _run_pipeline(scrape_tasks, from_)

    now = datetime.now(tz=timezone.utc).isoformat()
    for row in tracked:
        db.update_tracked_ticker(row["ticker"], last_scraped=now)

    log.info(f"=== Daily pipeline complete — {len(tickers)} tickers, {len(keywords)} keywords ===")


def run_ondemand_ticker_scrape(ticker: str, days_back: int = 30) -> None:
    """
    On-demand scrape triggered when a new ticker is first visited.
    Runs in a background thread; registers a ScrapeEvent queue so the WebSocket
    endpoint can stream progress to the frontend, then sets sentiment_ready=True.
    """
    from workers.scrape_stream import register_scrape, unregister_scrape

    log.info(f"On-demand scrape started for {ticker}")
    event_queue = register_scrape(ticker)

    from_ = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    scrape_tasks: list[tuple] = []

    # Sector/region context keywords from CNBC
    info = db.get_tracked_ticker(ticker)
    if info:
        for key in ("region", "sector", "country"):
            val = info.get(key)
            if val:
                scrape_tasks.append((CNBCScraper(), val, False))

    # Ticker-specific from all three sources
    scrape_tasks.append((CNBCScraper(), ticker, True))
    scrape_tasks.append((FinvizScraper(), ticker, True))
    scrape_tasks.append((YFinanceScraper(), ticker, True))

    _run_pipeline(scrape_tasks, from_, event_queue=event_queue)

    db.update_tracked_ticker(
        ticker,
        sentiment_ready=True,
        last_scraped=datetime.now(tz=timezone.utc).isoformat(),
    )
    unregister_scrape(ticker)
    log.info(f"On-demand scrape complete for {ticker}")


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
