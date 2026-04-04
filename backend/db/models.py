"""
db/models.py
All Pydantic response models for the Kancil Portfolio Manager API.
"""

from pydantic import BaseModel


# ── Price ──────────────────────────────────────────────────────────────────────

class OHLCVPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class Technicals(BaseModel):
    rsi_14: float
    ma20: float
    ma50: float
    pct_above_ma20: float
    pct_above_ma50: float
    atr_pct: float


class PriceData(BaseModel):
    current: float
    change_pct: float
    ohlcv: list[OHLCVPoint]
    technicals: Technicals


# ── Sentiment ──────────────────────────────────────────────────────────────────

class SentimentDaily(BaseModel):
    date: str
    mean: float
    positive: int
    neutral: int
    negative: int
    count: int


class LagCorrelation(BaseModel):
    lag: int
    correlation: float


class SentimentStats(BaseModel):
    mean_30d: float
    net_sentiment: float
    total_articles: int
    sentiment_ratio: float   # positive / total
    best_lag: int
    best_lag_correlation: float


class KeywordCount(BaseModel):
    word: str
    count: int


class SentimentData(BaseModel):
    daily: list[SentimentDaily]
    lag_correlations: list[LagCorrelation]
    stats: SentimentStats
    keywords: list[KeywordCount]


# ── PEAD ───────────────────────────────────────────────────────────────────────

class PeadFeatures(BaseModel):
    ret_5d_pre: float | None = None
    ret_10d_pre: float | None = None
    ret_20d_pre: float | None = None
    pre_earn_vol_20d: float | None = None
    volume_ratio: float | None = None
    sue: float | None = None
    eps_surprise: float | None = None
    hist_beat_rate: float | None = None
    beat_streak: int | None = None
    rate_regime: int | None = None
    vix_regime: int | None = None
    tnx: float | None = None
    vix: float | None = None


class EarningsHistoryItem(BaseModel):
    date: str
    eps_surprise: float | None
    sue: float | None
    beat: bool


class PeadSignal(BaseModel):
    earnings_date: str
    days_to_earnings: int
    outperform_prob_5d: float
    outperform_prob_10d: float
    outperform_prob_20d: float
    best_horizon: int
    features: PeadFeatures
    earnings_history: list[EarningsHistoryItem]


# ── Articles ───────────────────────────────────────────────────────────────────

class ArticleSummary(BaseModel):
    id: str
    title: str
    url: str
    source: str
    timestamp: str
    sentiment: float
    confidence: float


class ArticleWithTickers(BaseModel):
    id: str
    title: str
    url: str
    source: str
    timestamp: str
    sentiment: float
    confidence: float
    tickers: list[str]


# ── Research deep-dive ─────────────────────────────────────────────────────────

class TickerDeepDive(BaseModel):
    ticker: str
    name: str
    sector: str
    status: str                     # "new" | "tracking" | "held" | "untracked"
    sentiment_ready: bool
    price: PriceData
    sentiment: SentimentData | None
    pead: PeadSignal | None
    articles: list[ArticleSummary]


class SentimentStatus(BaseModel):
    ready: bool
    article_count: int
    estimated_seconds_remaining: int | None


# ── Calendar ───────────────────────────────────────────────────────────────────

class CalendarEvent(BaseModel):
    ticker: str
    name: str
    sector: str
    status: str
    earnings_date: str
    days_to_earnings: int
    sentiment_score: float | None
    sue: float | None
    outperform_prob: float | None
    hist_beat_rate: float | None
    ret_5d_pre: float | None


class CalendarResponse(BaseModel):
    events: list[CalendarEvent]


# ── News ───────────────────────────────────────────────────────────────────────

class NewsResponse(BaseModel):
    articles: list[ArticleWithTickers]
    total: int


# ── Tickers ────────────────────────────────────────────────────────────────────

class TrackedTicker(BaseModel):
    ticker: str
    name: str
    added_at: str
    added_by: str | None
    status: str
    last_scraped: str | None
    sentiment_ready: bool


class EpsRecord(BaseModel):
    ticker: str
    fiscal_date: str
    earnings_date: str | None
    reported_eps: float | None
    estimated_eps: float | None
    eps_surprise: float | None
    eps_surprise_pct: float | None
    sue: float | None
    fetched_at: str
