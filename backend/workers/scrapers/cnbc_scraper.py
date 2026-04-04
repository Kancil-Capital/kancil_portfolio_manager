"""
workers/scrapers/cnbc_scraper.py
CNBC news scraper — ticker-specific (GraphQL) and keyword (Queryly) endpoints.
Adapted from sentiment-analysis/app/data/scrapers/cnbc_scraper.py.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from workers.scrapers.base import Article, Scraper


class CNBCScraper(Scraper):
    def __init__(self):
        super().__init__("CNBC_Scraper")
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        self.queryly_url = "https://api.queryly.com/cnbc/json.aspx"
        self.queryly_params = {
            "queryly_key": "31a35d40a9a64ab3",
            "endindex": 0,
            "batchsize": 100,
            "timezoneoffset": "0",
            "sort": "date",
        }
        self.log("initialized")

    def _get_body(self, html: str, url: str, title: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        if "/video/" in url:
            ld = soup.find_all("script", {"type": "application/ld+json"})
            if not ld:
                return None
            try:
                return json.loads(ld[0].get_text())["description"]
            except Exception:
                return None

        # Regular article
        script = soup.find_all("script", {"charset": "UTF-8"})
        if script:
            text = script[0].get_text()
            idx = text.find("articleBodyText")
            if idx != -1:
                start = text.find(":", idx) + 2
                end = text.find('",', start + 1)
                if end > start:
                    return text[start:end]

        data = soup.find_all("span", {"class": "xyz-data"})
        if data:
            lines = [l.strip() for l in data[0].get_text().splitlines() if l.strip()]
            return " ".join(lines)

        return None

    def _get_ticker_articles(self, ticker: str, from_: datetime) -> list[tuple]:
        time_period = (datetime.now(tz=timezone.utc) - from_).days
        graphql_url = "https://webql-redesign.cnbcfm.com/graphql"
        variables = {
            "pageSize": 30,
            "contentType": ["blogpost", "cnbcvideo", "cnbcnewsstory", "livestory"],
            "symbol": ticker,
            "page": 1,
            "timePeriod": str(time_period),
            "sortBy": "dateline",
            "partner": "cnbc01",
        }
        params = {
            "operationName": "SymbolSearch",
            "variables": json.dumps(variables),
            "extensions": json.dumps({
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "45e411d8c5c566db6396ca67781b4c0f42a3c594e0e6e87c091333db6a9f5a55",
                }
            }),
        }

        articles = []
        while True:
            try:
                resp = requests.get(graphql_url, params=params, headers=self.headers, timeout=(10, 30))
                if not resp.ok:
                    self.error(f"GraphQL {resp.status_code} page {variables['page']}")
                    break
                results = resp.json()["data"]["search"]["results"]
                if not results:
                    break
                done = False
                for res in results:
                    if res["datePublished"] < from_.isoformat():
                        done = True
                        break
                    articles.append((
                        res["title"],
                        res["url"],
                        res["author"][0]["name"] if res.get("author") else "",
                        datetime.fromisoformat(res["datePublished"]),
                    ))
                if done:
                    break
                variables["page"] += 1
                params["variables"] = json.dumps(variables)
            except Exception as e:
                self.error(f"GraphQL fetch error: {e}")
                break
        return articles

    def _get_keyword_articles(self, keyword: str, from_: datetime) -> list[tuple]:
        params = dict(self.queryly_params)
        params["query"] = keyword
        params["endindex"] = 0

        articles = []
        seen_ids: set = set()

        while True:
            try:
                time.sleep(2)
                resp = requests.get(self.queryly_url, params=params, headers=self.headers, timeout=(10, 30))
                if not resp.ok:
                    self.error(f"Queryly {resp.status_code}")
                    break
                results = resp.json()["results"]
                prev_size = len(seen_ids)
                done = False
                for res in results:
                    if res["datePublished"] < from_.isoformat():
                        done = True
                        break
                    articles.append((
                        res["cn:title"],
                        res["url"],
                        res.get("author", ""),
                        datetime.fromisoformat(res["datePublished"]),
                    ))
                    seen_ids.add(res["_id"])
                if done or len(seen_ids) == prev_size:
                    break
                params["endindex"] += params["batchsize"]
            except Exception as e:
                self.error(f"Queryly fetch error: {e}")
                break
        return articles

    def _fetch_body(self, article_data: tuple) -> Article | None:
        title, url, author, timestamp = article_data
        try:
            resp = requests.get(url, headers=self.headers, timeout=(10, 30))
            if not resp.ok:
                return None
            body = self._get_body(resp.text, url, title)
            if not body:
                return None
            return Article(title=title, body=body, url=url, author=author,
                           source="CNBC", timestamp=timestamp)
        except Exception as e:
            self.error(f"Body fetch failed for {url}: {e}")
            return None

    def scrape(self, keyword: str, from_: datetime, **kwargs) -> list[Article]:
        self.keyword = keyword
        is_ticker = kwargs.get("is_ticker", False)
        self.log(f"Scraping {'ticker' if is_ticker else 'keyword'} '{keyword}' from {from_.strftime('%Y-%m-%d %H:%M UTC')}")
        raw = self._get_ticker_articles(keyword, from_) if is_ticker else self._get_keyword_articles(keyword, from_)
        self.log(f"Found {len(raw)} articles, fetching bodies...")

        groups = [raw[i: i + 50] for i in range(0, len(raw), 50)]

        def process_group(group_and_idx):
            group, idx = group_and_idx
            results = []
            for item in group:
                art = self._fetch_body(item)
                if art:
                    results.append(art)
            return results

        all_articles: list[Article] = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for batch in executor.map(process_group, [(g, i) for i, g in enumerate(groups)]):
                all_articles.extend(batch)

        self.log(f"Scraped {len(all_articles)} articles")
        return all_articles
