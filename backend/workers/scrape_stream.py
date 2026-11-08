"""
workers/scrape_stream.py
Per-ticker event queues for streaming scrape progress to WebSocket clients.

A registry of in-progress on-demand scrapes.  The pipeline registers a queue
when it starts and unregisters when it finishes; the WebSocket endpoint
consumes events from that queue in real time.
"""

import queue
import threading
from dataclasses import dataclass


@dataclass
class ScrapeEvent:
    stage: str              # "analyzing" | "done" | "error"
    article_title: str | None = None
    sentiment: float | None = None   # score of top-confidence entity in article
    articles_done: int = 0
    articles_total: int | None = None  # unknown upfront; always None for now


# ── Registry ───────────────────────────────────────────────────────────────────

_scrape_queues: dict[str, "queue.Queue[ScrapeEvent]"] = {}
_lock = threading.Lock()


def try_register_scrape(ticker: str) -> "queue.Queue[ScrapeEvent] | None":
    """Register a new event queue for ticker and return it, or return None if a
    scrape for ticker is already running. Check and register happen under one lock,
    so two requests at once can't both start a scrape."""
    with _lock:
        if ticker in _scrape_queues:
            return None
        q: queue.Queue[ScrapeEvent] = queue.Queue()
        _scrape_queues[ticker] = q
        return q


def get_scrape_queue(ticker: str) -> "queue.Queue[ScrapeEvent] | None":
    with _lock:
        return _scrape_queues.get(ticker)


def unregister_scrape(ticker: str) -> None:
    with _lock:
        _scrape_queues.pop(ticker, None)
