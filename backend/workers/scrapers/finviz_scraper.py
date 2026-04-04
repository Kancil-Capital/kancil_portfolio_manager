"""
workers/scrapers/finviz_scraper.py
Finviz news scraper — ticker-specific only.
Adapted from sentiment-analysis/app/data/scrapers/finviz_scraper.py.
"""

import json
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from workers.scrapers.base import Article, Scraper


class FinvizScraper(Scraper):
    def __init__(self):
        super().__init__("Finviz_Scraper")
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        self.log("initialized")

    def scrape(self, keyword: str, from_: datetime, **kwargs) -> list[Article]:
        self.keyword = keyword
        self.log(f"Scraping ticker '{keyword}' from {from_.strftime('%Y-%m-%d %H:%M UTC')}")

        try:
            resp = requests.get(
                f"https://finviz.com/api/quote-news/{keyword}",
                headers=self.headers, timeout=(10, 30),
            )
            if not resp.ok:
                self.error(f"Failed fetching: {resp.status_code}")
                return []

            soup = BeautifulSoup(json.loads(resp.text)["html"], "html.parser")
            anchors = soup.find_all("a")
            links = [a["href"] for a in anchors if a.get("href", "").startswith("/news")]
            self.log(f"Found {len(links)} article links")
        except Exception as e:
            self.error(f"List fetch error: {e}")
            return []

        articles: list[Article] = []
        for link in links:
            url = f"https://finviz.com{link}"
            try:
                resp = requests.get(url, headers=self.headers, timeout=(10, 30))
                if not resp.ok:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                title_tag = soup.find("title")
                title = title_tag.get_text() if title_tag else ""

                publish_info = soup.find("div", {"class": "grow self-center"})
                body_div = soup.find("div", {"class": "text-justify"})
                if not publish_info or not body_div:
                    continue

                publish_line = publish_info.get_text(separator=" ", strip=True).removeprefix("By ")
                parts = publish_line.split(" | ")
                if len(parts) < 2:
                    continue
                author, timestamp_str = parts[0], parts[1]
                timestamp = date_parser.parse(timestamp_str)

                if timestamp.replace(tzinfo=None) < from_.replace(tzinfo=None):
                    break

                body = body_div.get_text(separator=" ", strip=True)
                self.log(f"{title}: {timestamp.isoformat()}")
                articles.append(Article(
                    title=title, body=body, url=url,
                    author=author, source="Finviz", timestamp=timestamp,
                ))
            except Exception as e:
                self.error(f"Article fetch error for {url}: {e}")
                continue

        return articles
