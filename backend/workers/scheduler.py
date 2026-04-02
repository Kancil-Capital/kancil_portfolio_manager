"""
workers/scheduler.py
APScheduler job definitions.
BackgroundScheduler runs in a daemon thread alongside FastAPI.
Start/stop is handled via FastAPI lifespan in main.py.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from workers.pead_refresh import refresh_pead_signals
from workers.sentiment_pipeline import run_daily_sentiment_pipeline

log = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")

# Daily sentiment pipeline — 07:00 UTC (before US market open)
scheduler.add_job(
    func=run_daily_sentiment_pipeline,
    trigger="cron",
    hour=7,
    minute=0,
    id="daily_sentiment",
    replace_existing=True,
    misfire_grace_time=600,  # 10 minutes
)

# Nightly PEAD refresh — 02:00 UTC (after US close + after-hours settled)
scheduler.add_job(
    func=refresh_pead_signals,
    trigger="cron",
    hour=2,
    minute=0,
    id="pead_refresh",
    replace_existing=True,
    misfire_grace_time=600,
)


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
        log.info("APScheduler started (daily_sentiment @ 07:00 UTC, pead_refresh @ 02:00 UTC)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("APScheduler stopped")


def trigger_ondemand_scrape(ticker: str) -> None:
    """
    Immediately dispatch an on-demand scrape job for a newly added ticker.
    Runs in the scheduler's thread pool (non-blocking).
    """
    import threading
    from workers.sentiment_pipeline import run_ondemand_ticker_scrape

    thread = threading.Thread(
        target=run_ondemand_ticker_scrape,
        args=(ticker,),
        name=f"ondemand-scrape-{ticker}",
        daemon=True,
    )
    thread.start()
    log.info(f"On-demand scrape dispatched for {ticker}")
