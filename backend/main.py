import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db.supabase as db
from core.config import settings
from core import ticker_cache
from routers import calendar, news, research, tickers
from workers.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    log.info("Starting Kancil Portfolio Manager API")
    start_scheduler()
    rows = db.get_all_tracked_tickers(exclude_untracked=False)
    ticker_cache.load([r["ticker"] for r in rows])

    # Optionally warm up FinBERT + spaCy at startup (uncomment for production)
    # from core.sentiment import get_spacy_nlp, get_sentiment_analyzer
    # get_spacy_nlp()
    # get_sentiment_analyzer()

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    log.info("Shutting down")
    stop_scheduler()


app = FastAPI(
    title="Kancil Portfolio Manager API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(research.router)
app.include_router(calendar.router)
app.include_router(news.router)
app.include_router(tickers.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
