"""Only absolute http(s) article URLs are stored (issue #18)."""

import queue
from datetime import datetime, timezone

import pytest

import workers.sentiment_pipeline as pipeline
from workers.scrapers.base import Article


def _article(url):
    return Article("title", "body", url, None, "test", datetime.now(timezone.utc))


@pytest.mark.parametrize("url", [
    "https://www.cnbc.com/2026/11/08/story.html",
    "http://finviz.com/news/1",
    "HTTPS://Example.com/path?q=1",
])
def test_http_urls_are_safe(url):
    assert _article(url).has_safe_url()


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "ftp://example.com/file",
    "/relative/path",
    "//example.com/no-scheme",
    "https:///no-host",
    "",
    "http://[::1",  # malformed: urlsplit raises ValueError
])
def test_other_urls_are_rejected(url):
    assert not _article(url).has_safe_url()


def test_scraper_pool_drops_unsafe_articles():
    good, bad = _article("https://example.com/a"), _article("javascript:alert(1)")

    class Scraper:
        name = "fake"

        def scrape(self, keyword, from_, **kwargs):
            return [good, bad]

    q: queue.Queue = queue.Queue()
    pipeline._run_scraper_pool([(Scraper(), "NVDA", True)], q, datetime.now(timezone.utc))

    queued = []
    while (item := q.get_nowait()) is not None:
        queued.append(item)
    assert queued == [good]
