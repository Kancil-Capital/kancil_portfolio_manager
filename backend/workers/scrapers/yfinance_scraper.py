"""
workers/scrapers/yfinance_scraper.py
Yahoo Finance news scraper — ticker-specific only.
Adapted from sentiment-analysis/app/data/scrapers/yfinance_scraper.py.
Uses Selenium for cookie initialisation (headless Chrome required).
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from workers.scrapers.base import Article, Scraper


class YFinanceScraper(Scraper):
    def __init__(self):
        super().__init__("YFinance_Scraper")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        })
        self._init_cookies()
        self.log("initialized")

    def _init_cookies(self) -> None:
        """Accept Yahoo Finance consent via headless Chrome."""
        try:
            import selenium.webdriver as webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(options=options)
            driver.get("https://finance.yahoo.com/news/rocket-lab-q3-earnings-call-053227894.html")
            try:
                driver.find_element(By.ID, "scroll-down-btn").click()
                driver.find_element(By.CLASS_NAME, "accept-all").click()
                time.sleep(1)
            except Exception:
                pass
            cookies = driver.get_cookies()
            self.session.cookies.update({c["name"]: c["value"] for c in cookies})
            driver.quit()
        except Exception as e:
            self.warn(f"Cookie init failed (Selenium not available?): {e}")

    def _fetch_body(self, url: str) -> Article | None:
        try:
            resp = self.session.get(url, timeout=(10, 30))
            if not resp.ok:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")

            try:
                author = soup.find("div", {"class": "byline-attr-author"}).get_text(strip=True)
            except Exception:
                author = ""

            time_tag = soup.find("time", {"class": "byline-attr-meta-time"})
            if not time_tag:
                return None
            timestamp = datetime.fromisoformat(time_tag.get("datetime"))

            title_tag = soup.find("title")
            title = title_tag.get_text() if title_tag else ""

            body_div = soup.find("div", {"class": "bodyItems-wrapper"})
            if not body_div:
                return None
            body = body_div.get_text(separator=" ", strip=True)

            return Article(title=title, body=body, url=url, author=author,
                           source="Yahoo Finance", timestamp=timestamp)
        except Exception as e:
            self.error(f"Body fetch failed for {url}: {e}")
            return None

    def scrape(self, keyword: str, from_: datetime, **kwargs) -> list[Article]:
        self.keyword = keyword

        url = f"https://uk.finance.yahoo.com/quote/{keyword}/news/"
        try:
            resp = self.session.get(url, timeout=(10, 30))
            if not resp.ok:
                self.error(f"Initial fetch {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            scripts = soup.find_all("script", {"type": "application/json"})
            content = None
            for script in scripts:
                if "paginationString" in script.get_text():
                    content = script.get_text()
                    break

            if not content:
                self.error("paginationString not found in page")
                return []

            data = json.loads(json.loads(content)["body"])
        except Exception as e:
            self.error(f"Initial parse failed: {e}")
            return []

        scraped_urls: list[str] = []
        finished = False

        while not finished:
            try:
                stream = data["data"]["tickerStream"]["stream"]
                if not stream:
                    break

                stream_sorted = sorted(stream, key=lambda x: x["content"]["pubDate"], reverse=True)
                for article in stream_sorted:
                    if "yahoo" not in article["content"]["canonicalUrl"]["url"][:30]:
                        continue
                    if article["content"]["pubDate"] < from_.isoformat():
                        finished = True
                        break
                    scraped_urls.append(article["content"]["canonicalUrl"]["url"])

                if finished:
                    break

                # Paginate
                payload = {
                    "payload": {
                        "gqlVariables": {
                            "tickerStream": {
                                "pagination": {
                                    "uuids": data["data"]["tickerStream"]["pagination"]["uuids"]
                                }
                            }
                        }
                    },
                    "serviceConfig": {"count": 250, "snippetCount": 20},
                }
                next_url = (
                    f"https://uk.finance.yahoo.com/xhr/ncp"
                    f"?location=GB&queryRef=newsAll&serviceKey=ncp_fin"
                    f"&listName={keyword}-news&lang=en-GB&region=GB"
                )
                resp = self.session.post(next_url, json=payload, timeout=(10, 30))
                if not resp.ok:
                    break
                data = json.loads(resp.text)
            except Exception as e:
                self.error(f"Pagination error: {e}")
                break

        self.log(f"Found {len(scraped_urls)} article URLs, fetching bodies...")

        groups = [scraped_urls[i: i + 50] for i in range(0, len(scraped_urls), 50)]

        def process_group(group):
            return [art for url in group if (art := self._fetch_body(url)) is not None]

        all_articles: list[Article] = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for batch in executor.map(process_group, groups):
                all_articles.extend(batch)

        self.log(f"Scraped {len(all_articles)} articles")
        return all_articles
