# Kancil Capital Platform — Technical Specification

*Version: 1.0 | Date: 2026-04-02 | Scope: v1 Research Terminal*

> **This is the original pre-build design (April 2026).** The code has moved on since, and where the two disagree the code wins. Current sources of truth:
> - **Schema:** `backend/supabase/migrations/` (workflow in `docs/database_workflow.md`)
> - **API:** `frontend/openapi.json`, or `localhost:8000/docs` with the backend running
> - **Conventions and gotchas:** `CLAUDE.md`
>
> Reversed decisions are marked inline with **[Changed]**.

---

## 1. Repository Structure

Monorepo with two top-level packages — `frontend` and `backend`. The three existing research tools (`sentiment-analysis`, `pre-earning-drift-research`, `earnings-prediction`) are **references only** — their logic is studied, adapted, and rewritten cleanly into the backend's service layer. No cross-repo imports. The backend owns all the code it runs.

```
kancil_portfolio_manager/
│
├── frontend/                          # Next.js app (TypeScript)
│   ├── app/
│   │   ├── layout.tsx                 # Root layout (sidebar + topbar)
│   │   ├── page.tsx                   # Redirect → /research
│   │   ├── research/
│   │   │   ├── page.tsx               # Ticker search / landing
│   │   │   └── [ticker]/
│   │   │       └── page.tsx           # Ticker deep-dive
│   │   ├── calendar/
│   │   │   └── page.tsx               # Earnings calendar
│   │   └── news/
│   │       └── page.tsx               # News feed
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   └── Topbar.tsx
│   │   ├── ui/                        # Primitives
│   │   │   ├── Badge.tsx              # Sentiment / return badges
│   │   │   ├── Card.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   └── TickerChip.tsx
│   │   ├── charts/
│   │   │   ├── PriceChart.tsx         # Candlestick + sentiment overlay
│   │   │   ├── SentimentBars.tsx      # Daily stacked sentiment
│   │   │   ├── LagHeatmap.tsx         # Correlation heatmap
│   │   │   └── KeywordCloud.tsx
│   │   ├── research/
│   │   │   ├── TickerHeader.tsx
│   │   │   ├── SentimentPanel.tsx
│   │   │   ├── PeadPanel.tsx
│   │   │   ├── NewsPanel.tsx
│   │   │   └── FetchingBanner.tsx     # "Computing sentiment..." state
│   │   ├── calendar/
│   │   │   └── CalendarTable.tsx
│   │   └── news/
│   │       └── ArticleCard.tsx
│   ├── lib/
│   │   ├── api.ts                     # Typed API client (fetch wrappers)
│   │   ├── types.ts                   # Shared TypeScript interfaces
│   │   ├── formatters.ts              # Number / date formatting utils
│   │   └── supabaseClient.ts          # Supabase client (auth only)
│   ├── hooks/
│   │   ├── useTickerData.ts           # SWR hook for deep-dive
│   │   ├── useCalendar.ts
│   │   └── useNews.ts
│   ├── public/
│   │   └── kancil-logo-white.svg
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── package.json
│
├── backend/                           # FastAPI app (Python)
│   ├── main.py                        # App entrypoint, CORS, router registration
│   ├── routers/
│   │   ├── research.py                # /api/research/{ticker}
│   │   ├── calendar.py                # /api/calendar
│   │   ├── news.py                    # /api/news
│   │   └── tickers.py                 # /api/tickers (tracked list management)
│   ├── services/
│   │   ├── sentiment_service.py       # Wraps SentimentPulse data functions
│   │   ├── pead_service.py            # Unified PEAD feature + signal computation
│   │   ├── market_service.py          # Price data, technicals (yfinance)
│   │   └── eps_service.py             # EPS/SUE with caching guard
│   ├── workers/
│   │   ├── sentiment_pipeline.py      # Adapted from SentimentPulse daily_pipeline
│   │   └── scheduler.py              # APScheduler job definitions
│   ├── db/
│   │   ├── supabase.py                # Supabase client + typed query helpers
│   │   └── models.py                  # Pydantic response models
│   ├── core/
│   │   └── config.py                  # Settings (env vars via pydantic-settings)
│   ├── supabase/                      # Supabase CLI: migrations/, seed.sql, config.toml
│   └── pyproject.toml
│
├── docs/                              # This folder
│   ├── tools_audit.md
│   ├── platform_vision_draft.md
│   ├── technical_spec.md              # This file
│   └── ui_design_spec.md
│
# Reference codebases — read for logic, not imported
# ../sentiment-analysis/
# ../pre-earning-drift-research/
# ../earnings-prediction/
```

---

## 2. Database Schema

> **[Changed]** The real schema is in `backend/supabase/migrations/`; the sketches below differ from it (e.g. `articles.id` is a `bigint` identity, not a UUID; the SentimentPulse `tickers` table no longer exists).

### Existing Tables (Supabase — keep as-is)

```sql
-- Already exists in SentimentPulse
articles (
  id          UUID PRIMARY KEY,
  url         TEXT UNIQUE,
  title       TEXT,
  body        TEXT,
  source      TEXT,
  author      TEXT,
  timestamp   TIMESTAMPTZ
)

sentiments (
  id          UUID PRIMARY KEY,
  article_id  UUID REFERENCES articles(id),
  affected    TEXT,        -- ticker / sector / region
  sentiment   FLOAT,       -- -1.0 to +1.0
  confidence  FLOAT,       -- 0.0 to 1.0
  timestamp   TIMESTAMPTZ
)

tickers (
  id          UUID PRIMARY KEY,
  ticker      TEXT UNIQUE,
  name        TEXT,
  sector      TEXT,
  region      TEXT,
  country     TEXT
)
```

### New Tables (v1)

```sql
-- Tracked tickers with lifecycle state
CREATE TABLE tracked_tickers (
  ticker          TEXT PRIMARY KEY,
  added_at        TIMESTAMPTZ DEFAULT NOW(),
  added_by        TEXT,                        -- user email / name
  status          TEXT DEFAULT 'tracking',     -- 'tracking' | 'held' | 'untracked'
  last_scraped    TIMESTAMPTZ,
  sentiment_ready BOOLEAN DEFAULT FALSE        -- FALSE while first FinBERT run pending
);

-- [Changed] Never needed: signals are cheap to compute, so pead_service computes them on demand
-- and caches them in memory for 12h. The table was dropped in migration 20261026001454.
CREATE TABLE pead_signals (
  ticker              TEXT,
  computed_at         TIMESTAMPTZ DEFAULT NOW(),
  earnings_date       DATE,
  days_to_earnings    INT,

  -- Pre-earnings features
  ret_5d_pre          FLOAT,
  ret_10d_pre         FLOAT,
  ret_20d_pre         FLOAT,
  pre_earn_vol_20d    FLOAT,
  volume_ratio        FLOAT,
  rolling_beta_60d    FLOAT,
  sector_rs_20d       FLOAT,

  -- Earnings surprise features
  eps_surprise        FLOAT,
  sue                 FLOAT,
  hist_beat_rate      FLOAT,
  beat_streak         INT,
  lagged_surprise     FLOAT,

  -- Macro regime
  rate_regime         INT,        -- 0 or 1
  vix_regime          INT,        -- 0 or 1
  tnx                 FLOAT,
  vix                 FLOAT,

  -- Model outputs
  outperform_prob_5d  FLOAT,
  outperform_prob_10d FLOAT,
  outperform_prob_20d FLOAT,
  best_horizon        INT,        -- 5, 10, or 20

  PRIMARY KEY (ticker, computed_at)
);

-- EPS / SUE cache — never re-fetch until staleness threshold
CREATE TABLE eps_cache (
  ticker              TEXT,
  fiscal_date         DATE,
  earnings_date       DATE,
  reported_eps        FLOAT,
  estimated_eps       FLOAT,
  eps_surprise        FLOAT,
  eps_surprise_pct    FLOAT,
  sue                 FLOAT,
  fetched_at          TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (ticker, fiscal_date)
);
```

### Supabase RPC (extend existing)

```sql
-- Extend existing get_sentiments() to accept single ticker
-- Add new RPC for calendar view ([Changed] dropped with pead_signals; the calendar computes signals on demand)
CREATE OR REPLACE FUNCTION get_calendar_signals(tickers TEXT[])
RETURNS TABLE (...) AS $$ ... $$;
```

---

## 3. API Contract

Base URL: `http://localhost:8000` (dev) / `https://api.kancilcapital.com` (prod)

All endpoints return JSON. Auth header: `Authorization: Bearer <supabase_jwt>`.

---

### `GET /api/research/{ticker}`

Aggregated deep-dive — single call for the entire ticker page. Calls sub-services in parallel internally.

**Response:**
```typescript
{
  ticker: string
  name: string
  sector: string
  status: "held" | "tracking" | "new"  // from tracked_tickers
  sentiment_ready: boolean              // false = FinBERT still running

  price: {
    current: number
    change_pct: number
    ohlcv: { date: string; open: number; high: number; low: number; close: number; volume: number }[]
    technicals: {
      rsi_14: number
      ma20: number; ma50: number
      pct_above_ma20: number; pct_above_ma50: number
      atr_pct: number
    }
  }

  sentiment: {
    daily: { date: string; mean: number; positive: number; neutral: number; negative: number; count: number }[]
    lag_correlations: { lag: number; correlation: number }[]
    stats: {
      mean_30d: number; net_sentiment: number
      total_articles: number; sentiment_ratio: number
      best_lag: number; best_lag_correlation: number
    }
    keywords: { word: string; count: number }[]
  } | null  // null if sentiment_ready = false

  pead: {
    earnings_date: string
    days_to_earnings: number
    outperform_prob_5d: number
    outperform_prob_10d: number
    outperform_prob_20d: number
    best_horizon: number
    features: {
      ret_5d_pre: number; ret_10d_pre: number; ret_20d_pre: number
      pre_earn_vol_20d: number; volume_ratio: number
      sue: number; eps_surprise: number; hist_beat_rate: number; beat_streak: number
      rate_regime: number; vix_regime: number; tnx: number; vix: number
    }
    earnings_history: { date: string; eps_surprise: number; sue: number; beat: boolean }[]
  } | null  // null if no earnings date found

  articles: {
    id: string; title: string; url: string
    source: string; timestamp: string
    sentiment: number; confidence: number
  }[]
}
```

**Behaviour for new (untracked) ticker:**
1. Returns `status: "new"`, `sentiment_ready: false`, `sentiment: null`
2. Triggers background job: scrape → FinBERT → write to DB → set `sentiment_ready = true`
3. Frontend polls `GET /api/research/{ticker}/sentiment-status` every 5s
4. Auto-inserts ticker into `tracked_tickers`

---

### `GET /api/research/{ticker}/sentiment-status`

Lightweight polling endpoint.

**Response:** `{ ready: boolean; article_count: number; estimated_seconds_remaining: number | null }`

---

### `GET /api/calendar`

**Query params:** `?days_ahead=30` (default 30)

**Response:**
```typescript
{
  events: {
    ticker: string; name: string; sector: string; status: string
    earnings_date: string; days_to_earnings: number
    sentiment_score: number | null      // latest 7d mean
    sue: number | null
    outperform_prob: number | null      // best horizon prob
    hist_beat_rate: number | null
    ret_5d_pre: number | null           // current pre-earnings momentum
  }[]
}
```

---

### `GET /api/news`

**Query params:** `?ticker=&sentiment=positive|neutral|negative&source=&limit=20&offset=0`

**Response:**
```typescript
{
  articles: {
    id: string; title: string; url: string; source: string
    timestamp: string; sentiment: number; confidence: number
    tickers: string[]  // all affected entities in this article
  }[]
  total: number
}
```

---

### `GET /api/tickers`

Returns all tracked tickers with status.

---

### `POST /api/tickers`

**Body:** `{ ticker: string }`

Adds ticker to tracked list, triggers first scrape + FinBERT job.

---

### `PATCH /api/tickers/{ticker}`

**Body:** `{ status: "held" | "tracking" | "untracked" }`

---

## 4. Backend Services

### `sentiment_service.py`

Rewritten from SentimentPulse's `app/data/main.py` and `app/model/main.py`. Adapts the core logic (Supabase queries, FinBERT inference, entity extraction) into clean async-compatible service functions that return Pydantic models instead of DataFrames.

Key adaptations from the original:
- `get_articles()` → async `get_sentiment_data()` returning `SentimentData`
- `get_price_data()` → moved to `market_service.py`
- `SentimentAnalyzer` class → reused as-is, instantiated once at app startup and injected via FastAPI dependency
- `get_sentiment()` entity pipeline → reused as-is, called from the background scrape job
- Source weights, confidence thresholds, entity type multipliers → extracted into `core/config.py`

```python
# backend/services/sentiment_service.py
from backend.core.sentiment import SentimentAnalyzer, extract_entities  # adapted from original
from backend.db.supabase import get_client

async def get_sentiment_data(ticker: str, from_date: date, confidence_min: float = 0.2) -> SentimentData:
    # Adapted from app/data/main.py::get_articles()
    # Same Supabase RPC call, same filtering logic
    # Returns Pydantic model instead of DataFrame
    ...
```

### `pead_service.py`

Unified signal engine — rewrites and merges the best parts of both PEAD tools into a single clean module:

- **Feature set:** 28 features from `earnings-prediction/utils/helpers.py` (broader, includes macro regime — `compute_technical_features`, `compute_ticker_history_features`, `compute_targets` rewritten as standalone functions)
- **Model:** XGBoost from `pre-earning-drift-research/predictor.py` (better evaluated, 98 tickers, 10yr data — `train_models_for_horizon` rewritten as a one-time training script, trained model serialised to disk with `joblib`)
- **Horizons:** 5d, 10d, 20d outputs

Key adaptations:
- Feature engineering functions rewritten from both tools into a single `compute_features(ticker, price_df, eps_df, macro_df) -> dict`
- Model training extracted into a separate `scripts/train_pead_model.py` — runs offline, saves `pead_model.joblib`; service only runs inference
- `simulate_long_short_strategy`, `threshold_optimization`, IC analysis, plotting — dropped (research artefacts, not needed at runtime)

```python
# backend/services/pead_service.py
import joblib
from backend.services.eps_service import get_eps_data
from backend.services.market_service import get_price_data, get_macro_data

MODEL = joblib.load("models/pead_model.joblib")  # loaded once at startup

# [Changed] The 12h cache below is an in-memory dict, not a DB table
async def get_pead_signal(ticker: str) -> PeadSignal | None:
    cached = await db.get_pead_signal(ticker)
    if cached and cached.computed_at > datetime.now() - timedelta(hours=12):
        return cached
    return await compute_pead_signal(ticker)

async def compute_pead_signal(ticker: str) -> PeadSignal:
    # 1. Pull price + macro data (yfinance)
    # 2. Pull EPS/SUE from eps_cache only — never Alpha Vantage on-demand
    # 3. Compute 28 features
    # 4. Run MODEL.predict_proba() for 5d/10d/20d
    # 5. Cache in memory for 12h  ([Changed] originally: write to pead_signals table)
    # 6. Return PeadSignal model
```

### `eps_service.py`

Strictly guarded Alpha Vantage wrapper:

```python
def get_eps_data(ticker: str) -> list[EpsRecord]:
    # 1. Check eps_cache — if most recent record is < 90 days old, return cache
    cached = db.get_eps_cache(ticker)
    if is_fresh(cached):
        return cached

    # 2. Only call Alpha Vantage if cache is stale
    # Log every call — alert if approaching daily limit
    log.info(f"AV API call for {ticker} — check daily quota")
    data = fetch_alpha_vantage_earnings(ticker)
    db.upsert_eps_cache(ticker, data)
    return data
```

### `market_service.py`

Pure yfinance wrapper. No caching needed — yfinance responses are fast and free.

```python
def get_price_data(ticker: str, period: str = "6mo") -> PriceData
def get_technicals(ticker: str) -> Technicals
def get_upcoming_earnings(tickers: list[str]) -> list[EarningsEvent]
```

---

## 5. Background Workers

### Daily Sentiment Pipeline (`workers/sentiment_pipeline.py`)

Adapted from SentimentPulse `app/data/pipeline.py`. Changes:
- Reads tracked tickers from `tracked_tickers` table (not hardcoded list)
- Filters to `status != 'untracked'`
- Runs at 07:00 UTC daily (before US market open)

```python
# Scheduler definition
scheduler.add_job(
    func=run_daily_sentiment_pipeline,
    trigger="cron", hour=7, minute=0,
    id="daily_sentiment"
)
```

### ~~Nightly PEAD Refresh~~ [Changed]

Removed. Signals are computed on request and cached in memory for 12h, so there is nothing to pre-compute.

### On-Demand Scrape Job (triggered by `POST /api/tickers`)

Runs immediately in a background thread when a new ticker is added:
1. Scrape last 30 days of news for the ticker
2. Run FinBERT on all articles
3. Write sentiments to DB
4. Set `sentiment_ready = True` in `tracked_tickers`

---

## 6. Frontend Component Architecture

### Data Fetching Strategy

Use **SWR** for all data fetching — handles caching, revalidation, and the polling pattern for the on-demand sentiment job.

```typescript
// hooks/useTickerData.ts
export function useTickerData(ticker: string) {
  const { data, error, isLoading } = useSWR(
    `/api/research/${ticker}`,
    fetcher,
    { refreshInterval: 0 }  // no auto-refresh on deep-dive
  )
  return { data, error, isLoading }
}

// Polling hook for new tickers
export function useSentimentStatus(ticker: string, enabled: boolean) {
  const { data } = useSWR(
    enabled ? `/api/research/${ticker}/sentiment-status` : null,
    fetcher,
    { refreshInterval: 5000 }  // poll every 5s while computing
  )
  return data
}
```

### Key Component Behaviours

**`FetchingBanner`** — shown when `sentiment_ready = false`:
```
┌──────────────────────────────────────────────────────────┐
│  ⟳  Analysing news sentiment for AAPL (new ticker)      │
│     ~25 seconds remaining · Price data is available now  │
└──────────────────────────────────────────────────────────┘
```
Disappears and triggers SWR revalidation when polling confirms `ready: true`.

**`PriceChart`** — renders immediately on page load (yfinance is fast). No waiting for sentiment.

**`PeadPanel`** — shows skeleton if PEAD signal not computed, otherwise renders conviction scores:
```
┌─ Earnings Signal ────────────────────────┐
│  Next earnings    14 days (May 12)       │
│                                          │
│  Outperform probability                  │
│  5d   ████████░░  62%                   │
│  10d  ██████████  71%  ← best horizon   │
│  20d  ███████░░░  58%                   │
│                                          │
│  SUE score      +1.8   Beat streak  3x  │
│  Pre-momentum   +4.2%  Vol ratio   1.3x │
│  Rate regime    High   VIX regime   Low  │
└──────────────────────────────────────────┘
```

---

## 7. Authentication

Use **Supabase Auth** — already have a Supabase instance.

**Roles** (set as JWT custom claims):
| Role | Access |
|------|--------|
| `admin` (CIO) | Full access + ticker management |
| `analyst` | Read all + can add tickers to tracked list |
| `readonly` | Read only (Advisory Board, sponsors) |

**Implementation:** Next.js middleware checks JWT on every route. FastAPI verifies the same JWT via Supabase's public key.

> **[Changed]** Only `admin` is enforced so far, read from `app_metadata.role` (ticker deletion). FastAPI accepts both HS256 (shared secret) and ES256 (public key via JWKS) tokens. A fuller model with teams, leads and coverage is proposed separately.

---

## 8. Key Dependencies

### Frontend (`package.json`)
```json
{
  "dependencies": {
    "next": "^15",
    "react": "^19",
    "typescript": "^5",
    "tailwindcss": "^4",
    "swr": "^2",
    "recharts": "^2",
    "@supabase/supabase-js": "^2",
    "react-table": "^8",
    "date-fns": "^3",
    "feather-icons-react": "^0.1"
  }
}
```

> **Charts note:** Recharts for most charts. For the candlestick specifically, use `lightweight-charts` (TradingView's open-source library) — it handles financial OHLC charts far better than Recharts.

### Backend (`pyproject.toml`)
```toml
[project]
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "supabase>=2.0",
  "pydantic-settings>=2.0",
  "apscheduler>=3.10",
  "yfinance>=1.0",
  "pandas>=2.0",
  "xgboost>=2.0",
  "lightgbm>=4.0",
  "scikit-learn>=1.5",
  "httpx>=0.27",        # async HTTP for Alpha Vantage
  # FinBERT / spaCy — inherited from sentiment-analysis tool
  "transformers>=4.40",
  "torch>=2.0",
  "spacy>=3.7",
]
```

> **⚠️ macOS libomp import-order gotcha:** `xgboost` and `torch` both ship their own copy of the OpenMP runtime (`libomp`/`libiomp5`). On macOS, whichever one gets imported **second** tries to load its libomp on top of the first one's, and xgboost's C runtime segfaults during `Booster.__setstate__` (i.e. during `joblib.load(pead_model.joblib)`). Because uvicorn installs its own signal handlers, it swallows the segfault and the process just appears to hang forever during startup.
>
> **Rule:** `xgboost` must be imported **before** `torch`. This is enforced by an explicit `import xgboost` at the top of `services/pead_service.py` (marked `# noqa: F401`). In `main.py`, the `from routers import ...` line (which transitively imports `pead_service`) must stay **above** the `from workers.scheduler import ...` line (which transitively imports `core/sentiment.py` → `torch`).
>
> If you ever see the server hang at `Loading models: PEAD...` with no further output, this is almost certainly the cause — check that nothing has reordered those imports or removed the `import xgboost` from `pead_service.py`.

---

## 9. Deployment Plan

| Service | Platform | Notes |
|---------|---------|-------|
| Frontend (Next.js) | Vercel | Free tier sufficient; auto-deploy from main branch |
| Backend (FastAPI) | Railway or Render | Free tier has cold starts — use paid ($5/mo) to keep FinBERT worker warm |
| Database | Supabase | Already provisioned |
| Background workers | Same Railway instance as FastAPI | APScheduler runs in-process |
| FinBERT model | Loaded once at FastAPI startup, kept in memory | ~1.5GB RAM — factor into Railway plan |

**Environment variables required:**
```
SUPABASE_URL
SUPABASE_SECRET_KEY
SUPABASE_JWT_SECRET       # for auth verification
ALPHA_VANTAGE_API_KEY
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_API_BASE_URL
```

---

## 10. Implementation Phases

> Original plan, kept for reference; checkboxes were not maintained. Progress lives in git history.

### Phase 0 — Foundation (1 week)
- [ ] Initialise Next.js app with Tailwind, TypeScript
- [ ] Initialise FastAPI app with project structure above
- [ ] Configure Supabase: create new tables (`tracked_tickers`, ~~`pead_signals`~~, `eps_cache`)
- [ ] Set up Supabase Auth with roles
- [ ] Build sidebar + topbar layout components
- [ ] Wire up Next.js auth middleware
- [ ] Configure FastAPI JWT verification
- [ ] Set up monorepo tooling (single `Makefile` or `justfile` for `make dev`)

### Phase 1 — Backend Services (1.5 weeks)
- [ ] `market_service.py` — price data + technicals from yfinance
- [ ] `sentiment_service.py` — wrap SentimentPulse data functions, test against existing DB
- [ ] `eps_service.py` — Alpha Vantage wrapper with cache guard + logging
- [ ] `pead_service.py` — unified feature computation + XGBoost inference
- [ ] `workers/sentiment_pipeline.py` — adapt existing daily pipeline to read from `tracked_tickers`
- [ ] ~~`workers/pead_refresh.py` — nightly PEAD signal refresh~~ (dropped)
- [ ] All four API routers with response models
- [ ] On-demand scrape job + `sentiment_ready` flag flow

### Phase 2 — Research Terminal (2 weeks)
- [ ] `PriceChart` with `lightweight-charts` (candlestick + sentiment line overlay)
- [ ] `SentimentPanel` — daily bars + lag heatmap + keyword cloud + stats
- [ ] `PeadPanel` — outperform probability bars + feature table
- [ ] `NewsPanel` — article list with sentiment badges
- [ ] `TickerHeader` — name, price, change, status badge
- [ ] `FetchingBanner` — polling flow for new tickers
- [ ] Full ticker deep-dive page assembled

### Phase 3 — Calendar + News Feed (1 week)
- [ ] `CalendarTable` — sortable, filterable, click → deep-dive
- [ ] `ArticleCard` — news feed card
- [ ] Calendar page assembled
- [ ] News feed page assembled (infinite scroll or pagination)

### Phase 4 — Polish + Deploy (1 week)
- [ ] Skeleton loading states on all panels
- [ ] Empty states with Kancil city skyline SVG
- [ ] Mobile-responsive layout (tablet minimum)
- [ ] Error boundaries + API error handling
- [ ] Deploy frontend to Vercel
- [ ] Deploy backend to Railway
- [ ] Smoke test full flow: add new ticker → sentiment pipeline → deep-dive renders

**Total estimate: ~6 weeks** for a single developer, less with parallel work across the Quant & Data team.

---

## 11. What Gets Rewritten vs Retired

The existing tools are the reference. This table maps each piece to its fate in the new architecture:

| Original | Fate | Rewritten into |
|----------|------|---------------|
| SentimentPulse `app/data/scrapers/` | Rewritten | `backend/workers/scrapers/` — same scraping logic, async-compatible, reads ticker list from DB |
| SentimentPulse `app/model/main.py` (FinBERT + entity extraction) | Rewritten | `backend/core/sentiment.py` — same model, same pipeline, adapted to Pydantic I/O |
| SentimentPulse `app/data/main.py` (Supabase queries) | Rewritten | `backend/services/sentiment_service.py` — same queries, async, returns Pydantic not DataFrame |
| SentimentPulse `app/data/pipeline.py` | Rewritten | `backend/workers/sentiment_pipeline.py` — same flow, reads `tracked_tickers` table |
| SentimentPulse `app/main.py` (Dash app) | **Retired** | Replaced by Next.js frontend entirely |
| SentimentPulse `app/figures.py` (Plotly charts) | **Retired** | Replaced by React chart components |
| PEAD `predictor.py` feature engineering | Rewritten | `backend/services/pead_service.py::compute_features()` |
| PEAD `predictor.py` model training | Rewritten | `backend/scripts/train_pead_model.py` — offline script, outputs `models/pead_model.joblib` |
| PEAD `predictor.py` main() pipeline runner | **Retired** | Replaced by on-demand compute in `pead_service.py` (12h in-memory cache) |
| PEAD `predictor.py` backtest / IC / plotting | **Retired** | Research artefacts — not needed at runtime |
| Earnings Prediction `utils/helpers.py` feature set | Rewritten | Merged into `pead_service.py::compute_features()` — adds macro regime, ticker history features |
| Earnings Prediction notebooks | **Retired** | Research artefacts — findings inform the feature set, notebooks themselves not ported |
| Hardcoded ticker lists in all three tools | **Retired** | Replaced by `tracked_tickers` Supabase table |
| All CSV file outputs | **Retired** | Data lives in Supabase; API serves it directly |
