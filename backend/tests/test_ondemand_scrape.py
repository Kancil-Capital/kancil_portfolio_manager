"""
On-demand scrape error handling (issue #19).

A failed scrape must send an "error" event, unregister its queue, leave the
ticker un-ready so the next visit retries, and never run twice at once.
Scrapers, FinBERT and the database are faked; nothing touches the network.
"""

import queue
import threading
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.research as research
import workers.scheduler as scheduler
import workers.scrape_stream as scrape_stream
import workers.sentiment_pipeline as pipeline
from workers.scrape_stream import ScrapeEvent
from workers.scrapers.base import Article


class FakeScraper:
    articles: list[Article] = []

    def __init__(self):
        self.name = "fake"

    def scrape(self, keyword, from_, **kwargs):
        return list(self.articles)


def _article(url="https://example.com/a"):
    return Article("NVDA beats", "body", url, None, "fake", datetime.now(timezone.utc))


@pytest.fixture(autouse=True)
def fake_world(monkeypatch):
    """Fake scrapers and DB; record ticker updates; clear the scrape registry."""
    FakeScraper.articles = [_article()]
    for name in ("CNBCScraper", "FinvizScraper", "YFinanceScraper"):
        monkeypatch.setattr(pipeline, name, FakeScraper)

    updates: list[dict] = []
    monkeypatch.setattr(pipeline.db, "get_tracked_ticker", lambda t: {"ticker": t})
    monkeypatch.setattr(pipeline.db, "update_tracked_ticker", lambda t, **kw: updates.append(kw))
    monkeypatch.setattr(
        pipeline.db, "upsert_articles", lambda rows: [{"id": 1, "url": r["url"]} for r in rows]
    )
    monkeypatch.setattr(pipeline.db, "insert_sentiments", lambda rows: None)
    monkeypatch.setattr(
        pipeline, "get_sentiment_batch", lambda batch: [[("NVDA", 0.8, 0.9)] for _ in batch]
    )
    scrape_stream._scrape_queues.clear()
    yield updates
    scrape_stream._scrape_queues.clear()


def _drain(q: queue.Queue) -> list[ScrapeEvent]:
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


# ── try_register_scrape ────────────────────────────────────────────────────────

def test_try_register_scrape_refuses_a_second_scrape_until_unregistered():
    first = scrape_stream.try_register_scrape("NVDA")
    assert first is not None
    assert scrape_stream.try_register_scrape("NVDA") is None
    assert scrape_stream.get_scrape_queue("NVDA") is first

    scrape_stream.unregister_scrape("NVDA")
    assert scrape_stream.try_register_scrape("NVDA") is not None


def test_try_register_scrape_is_atomic_under_concurrency():
    results = []
    barrier = threading.Barrier(20)

    def claim():
        barrier.wait()
        results.append(scrape_stream.try_register_scrape("NVDA"))

    threads = [threading.Thread(target=claim) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(r is not None for r in results) == 1


# ── run_ondemand_ticker_scrape ─────────────────────────────────────────────────

def test_successful_scrape_sends_done_marks_ready_and_unregisters(fake_world):
    q = scrape_stream.try_register_scrape("NVDA")
    pipeline.run_ondemand_ticker_scrape("NVDA", event_queue=q)

    # One article from each of the three scrapers, then done
    stages = [e.stage for e in _drain(q)]
    assert stages == ["analyzing"] * 3 + ["done"]
    assert fake_world[-1]["sentiment_ready"] is True
    assert scrape_stream.get_scrape_queue("NVDA") is None


def test_finbert_failure_sends_error_and_leaves_ticker_unready(fake_world, monkeypatch):
    def boom(batch):
        raise RuntimeError("model failed to load")

    monkeypatch.setattr(pipeline, "get_sentiment_batch", boom)
    q = scrape_stream.try_register_scrape("NVDA")
    pipeline.run_ondemand_ticker_scrape("NVDA", event_queue=q)

    events = _drain(q)
    assert events[-1].stage == "error"
    assert not any(e.stage == "done" for e in events)
    assert not any(u.get("sentiment_ready") for u in fake_world)
    assert scrape_stream.get_scrape_queue("NVDA") is None


def test_db_failure_before_pipeline_sends_error_and_unregisters(fake_world, monkeypatch):
    def boom(ticker):
        raise ConnectionError("supabase down")

    monkeypatch.setattr(pipeline.db, "get_tracked_ticker", boom)
    q = scrape_stream.try_register_scrape("NVDA")
    pipeline.run_ondemand_ticker_scrape("NVDA", event_queue=q)

    assert [e.stage for e in _drain(q)] == ["error"]
    assert fake_world == []
    assert scrape_stream.get_scrape_queue("NVDA") is None


def test_cli_path_registers_its_own_queue_and_skips_if_already_running(fake_world):
    pipeline.run_ondemand_ticker_scrape("NVDA")  # no queue passed, as from __main__
    assert fake_world[-1]["sentiment_ready"] is True
    assert scrape_stream.get_scrape_queue("NVDA") is None

    fake_world.clear()
    scrape_stream.try_register_scrape("NVDA")  # someone else is scraping
    pipeline.run_ondemand_ticker_scrape("NVDA")
    assert fake_world == []


# ── _run_pipeline / _run_scraper_pool ──────────────────────────────────────────

def test_run_pipeline_reraises_consumer_errors(monkeypatch):
    def boom(batch):
        raise RuntimeError("inference failed")

    monkeypatch.setattr(pipeline, "get_sentiment_batch", boom)
    with pytest.raises(RuntimeError, match="inference failed"):
        pipeline._run_pipeline([(FakeScraper(), "NVDA", True)], datetime.now(timezone.utc))


def test_scraper_pool_always_sends_sentinel(monkeypatch):
    class BrokenPool:
        def __init__(self, *a, **kw):
            raise RuntimeError("cannot start threads")

    monkeypatch.setattr(pipeline, "ThreadPoolExecutor", BrokenPool)
    q: queue.Queue = queue.Queue()
    with pytest.raises(RuntimeError):
        pipeline._run_scraper_pool([(FakeScraper(), "NVDA", True)], q, datetime.now(timezone.utc))
    assert q.get_nowait() is None


def test_a_failing_scraper_does_not_fail_the_pipeline(fake_world):
    class FailingScraper(FakeScraper):
        def scrape(self, keyword, from_, **kwargs):
            raise TimeoutError("site down")

    q: queue.Queue = queue.Queue()
    tasks = [(FailingScraper(), "NVDA", True), (FakeScraper(), "NVDA", True)]
    pipeline._run_pipeline(tasks, datetime.now(timezone.utc), event_queue=q)
    assert [e.stage for e in _drain(q)] == ["analyzing", "done"]


# ── trigger_ondemand_scrape ────────────────────────────────────────────────────

def test_trigger_registers_before_starting_and_refuses_duplicates(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    seen_queue = {}

    def fake_run(ticker, event_queue=None):
        seen_queue["q"] = event_queue
        started.set()
        release.wait(5)
        scrape_stream.unregister_scrape(ticker)

    monkeypatch.setattr(pipeline, "run_ondemand_ticker_scrape", fake_run)

    assert scheduler.trigger_ondemand_scrape("NVDA") is True
    # Registered synchronously, so the WebSocket can find it straight away
    assert scrape_stream.get_scrape_queue("NVDA") is not None
    assert started.wait(5)
    assert seen_queue["q"] is scrape_stream.get_scrape_queue("NVDA")
    assert scheduler.trigger_ondemand_scrape("NVDA") is False
    release.set()


# ── research router: retry and WebSocket ───────────────────────────────────────

@pytest.mark.parametrize(
    "row, should_retry",
    [
        ({"ticker": "NVDA", "sentiment_ready": False, "last_scraped": None}, True),
        ({"ticker": "NVDA", "sentiment_ready": True, "last_scraped": "2026-11-01"}, False),
        ({"ticker": "NVDA", "sentiment_ready": False, "last_scraped": "2026-11-01"}, False),
    ],
)
def test_existing_ticker_retries_only_if_never_scraped(monkeypatch, row, should_retry):
    triggered = []
    monkeypatch.setattr(research.db, "get_tracked_ticker", lambda t: row)
    monkeypatch.setattr(research, "trigger_ondemand_scrape", lambda t: triggered.append(t))

    assert research._get_or_create_ticker("NVDA") is row
    assert triggered == (["NVDA"] if should_retry else [])


def test_websocket_stops_on_error_event(monkeypatch):
    monkeypatch.setattr(research, "verify_token", lambda token: {"sub": "u"})
    monkeypatch.setattr(
        research.db, "get_tracked_ticker", lambda t: {"ticker": t, "sentiment_ready": False}
    )
    q = scrape_stream.try_register_scrape("NVDA")
    q.put(ScrapeEvent(stage="analyzing", article_title="a", articles_done=1))
    q.put(ScrapeEvent(stage="error"))
    q.put(ScrapeEvent(stage="analyzing", article_title="never sent", articles_done=2))

    app = FastAPI()
    app.include_router(research.router)
    with TestClient(app).websocket_connect("/api/research/NVDA/scrape-stream?token=t") as ws:
        assert ws.receive_json()["stage"] == "analyzing"
        assert ws.receive_json()["stage"] == "error"
    # The third event was never consumed: the server stopped at "error"
    assert q.qsize() == 1
