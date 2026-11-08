"""
workers/scrapers/base.py
Base Article dataclass and Scraper ABC.
Adapted from sentiment-analysis/app/data/scrapers/base.py.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

SAFE_URL_SCHEMES = ("http", "https")


@dataclass
class Article:
    title: str
    body: str
    url: str
    author: str | None
    source: str
    timestamp: datetime

    def to_json(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "author": self.author,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }

    def has_safe_url(self) -> bool:
        """True if the URL is an absolute http(s) link. The frontend renders it as
        a link, so anything else (javascript:, data:, relative paths) is rejected here."""
        try:
            parts = urlsplit(self.url)
        except ValueError:
            return False
        return parts.scheme.lower() in SAFE_URL_SCHEMES and bool(parts.netloc)

    def __repr__(self) -> str:
        ts = self.timestamp.isoformat()
        return f"Article(title={self.title!r}, source={self.source}, ts={ts})"


class Scraper(ABC):
    def __init__(self, name: str):
        self.name = name
        self.keyword = ""

    @abstractmethod
    def scrape(self, keyword: str, from_: datetime, **kwargs) -> list[Article]:
        pass

    def log(self, msg: str) -> None:
        kw = f" ({self.keyword})" if self.keyword else ""
        logging.info(f"{self.name}{kw}: {msg}")

    def error(self, msg: str) -> None:
        kw = f" ({self.keyword})" if self.keyword else ""
        logging.error(f"{self.name}{kw} ERROR: {msg}")

    def warn(self, msg: str) -> None:
        logging.warning(f"{self.name} ({self.keyword}) WARNING: {msg}")
