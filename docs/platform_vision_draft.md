# Kancil Capital Research Platform — Vision Document

*Version: 0.3 | Date: 2026-04-02 | Status: Approved for architecture planning*

> Decisions reversed since approval are marked **[Changed]**. For the current implementation see `CLAUDE.md` and the code.

---

## 1. Purpose

A web platform for Kancil Capital's investment team to run equity research, monitor both portfolios, and manage risk — built incrementally across investment cycles. v1 focuses entirely on the research terminal, adapting three existing Python tools into a unified interface.

---

## 2. Fund Context

| Attribute | Detail |
|-----------|--------|
| Organisation | Student-led fund, University of Manchester |
| Members | Malaysian students in the UK |
| Founded | March 2025 |
| Team size | 8 core (growing to 20–25) |
| Combined AUM | ~$14,845 USD (as of 2025 report) |
| Platform builders | Quant & Data team (Python-focused) |

**Two portfolios:**
| Fund | Style | AUM | Return (since inception) |
|------|-------|-----|--------------------------|
| SMF I (Portfolio Manager) | Concentrated PM sleeves, event-driven | ~$2,422 | +58.08% |
| SMF II (Sponsorship) | Committee-built, diversified 10–30 names | ~$12,298 | +21.84% |

**Investment universe:** Public equities + liquid ETFs, US / UK / Europe. Global long-only.

**Current held names:** ADSK, BE, META, NVDA, GE, CBRE, SPXE, NOVO-B, C, CJPU, JFJ

---

## 3. Platform Roadmap

| Version | Modules | Status |
|---------|---------|--------|
| **v1** | Research Terminal (sentiment + PEAD + earnings calendar) | Planning |
| **v2** | Portfolio Dashboard (SMF I + II tracking, NAV reporting) | Future |
| **v3** | Risk Dashboard (VaR, factor exposures, IPS alerts) | Future |
| **v4** | ICOM Workflow (optional — TBD) | Deferred |

*ICOM pitch/voting process stays outside the platform for now. Platform is a research & analytics tool.*

---

## 4. V1 Scope — Research Terminal

### 4.1 Ticker Deep-Dive Page `/research/[ticker]`

Single-stock view combining all three existing tools:

**Sentiment Panel** *(from SentimentPulse)*
- Price + sentiment score overlay (dual-axis, daily)
- Lag correlation heatmap (sentiment → returns, 0–7 day lags)
- Recent news feed with sentiment tags (positive/neutral/negative) and confidence
- Keyword cloud from recent articles
- Source breakdown (CNBC, Finviz, Yahoo Finance)
- Confidence threshold slider

**Earnings Signal Panel** *(from PEAD Research + Earnings Prediction)*
- Next earnings date + days remaining
- Pre-earnings momentum snapshot (ret_5d, ret_10d, ret_20d)
- Realized volatility + volume ratio
- EPS surprise history (last 4–8 quarters)
- SUE score + beat streak
- PEAD drift prediction: outperform probability + best horizon (5/10/20d)
- Macro regime context (rate regime, VIX level)

**Price Panel**
- Candlestick OHLC + volume
- Key technicals: RSI-14, MA20/MA50 deviation, ATR

---

### 4.2 Earnings Calendar Page `/calendar`

All upcoming earnings for covered/watchlist names, showing pre-computed signals:

| Column | Source |
|--------|--------|
| Ticker / Company | Supabase tickers table |
| Earnings date | yfinance earnings_dates() |
| Days to earnings | Computed |
| Current sentiment score | SentimentPulse |
| SUE (last quarter) | Alpha Vantage / yfinance |
| Pre-earnings momentum | yfinance (computed nightly) |
| PEAD outperform prob | PEAD model output |
| Historical beat rate | yfinance earnings history |

Sortable/filterable. Clicking a row opens the ticker deep-dive.

---

### 4.3 News Feed Page `/news`

Sentiment-tagged news stream across the entire covered universe:

- Real-time (latest scrape) articles ranked by recency
- Filter by ticker, sentiment (positive/negative/neutral), source, confidence
- Each article shows: headline, source, timestamp, ticker tags, sentiment score
- Powered by existing SentimentPulse scrapers + Supabase

---

### 4.4 Pipeline Refactor + WebSocket Streaming

#### Sentiment Pipeline — Producer-Consumer Refactor

**Problem:** The current pipeline is fully sequential: all scrapers finish → all articles upserted → FinBERT runs one-by-one. FinBERT is the bottleneck and doesn't start until scraping is completely done. On runs with 100+ articles this causes significant delay.

**Proposed approach:** Classic producer-consumer pattern using a queue.
- Scrapers (producers) feed articles into a shared queue as they arrive
- A FinBERT worker (consumer) pulls from the queue and starts inference immediately, overlapping with ongoing scraping
- Both sides are thread-safe: scrapers are I/O-bound (threads fine), PyTorch releases the GIL during inference (real parallelism)

**Design consideration:** Deduplication currently happens via a DB upsert before FinBERT runs, to avoid wasting inference on already-seen articles. In a streaming pipeline this check needs to happen per-article (more DB round trips) or duplicates get processed and discarded after the fact.

#### On-Demand Fetch — New Ticker Flow

**Entry point:** Tickers are not added via a dedicated `POST /api/tickers` — that endpoint was removed. The only entry point is `GET /api/research/{ticker}`, which calls `_get_or_create_ticker` inline. If the ticker is new, it inserts it and triggers the background scrape from there.

**Problem:** PEAD and EPS have no dependency on sentiment, but the original code gated them both behind `sentiment_ready`. This meant a newly tracked ticker had no PEAD or EPS data until the nightly run at 2am UTC, even though computing them takes seconds.

**Correct flow:**
1. User navigates to `/research/{ticker}`
2. `_get_or_create_ticker` inserts the ticker and fires the background sentiment scrape
3. PEAD + EPS are computed immediately (best-effort, non-blocking on failure) — fast since it's just math + one Alpha Vantage call + XGBoost inference
4. Research page returns with price + PEAD populated right away; sentiment fields are null with `sentiment_ready: false`
5. Frontend subscribes to the WebSocket scrape stream — shows a live feed of articles being analyzed instead of a spinner
6. When the stream closes, the sentiment panel populates

**WebSocket stream endpoint:** `WS /api/research/{ticker}/scrape-stream`
- Pushes events: `{ stage, article_title, sentiment, articles_done, articles_total }`
- Pairs naturally with the producer-consumer pipeline refactor — the WebSocket is a third consumer of the queue

#### Ticker Management — ~~Remaining TODOs~~ Done

All three are implemented: `added_by` comes from the JWT, `/research` lists recently tracked tickers, and `/tickers` enforces ownership on delete.

1. **`added_by` from auth:** When `_get_or_create_ticker` fires on a new ticker, extract the user's email from the JWT (already available via `get_current_user`) and pass it into `insert_tracked_ticker` as `added_by`. Currently always null.

2. **Recently Tracked section:** The homepage (`/research`) shows 4 hardcoded skeleton cards. Wire it up to `GET /api/tickers` and display the most recently added tickers with their status and sentiment_ready state.

3. **Ticker management page:** Analysts should be able to untrack tickers they added. Needs a `/tickers` management page that:
   - Lists all tracked tickers with metadata
   - Allows the current user to remove/untrack only tickers where `added_by` matches their email (enforced on both frontend and backend via auth + `added_by` check in the PATCH handler)
   - Admins (CIO) can untrack any ticker

---

## 5. Technical Architecture

### Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | Next.js (TypeScript) | Best-in-class web UX, scalable as team grows, component reuse |
| **Backend API** | FastAPI (Python) | Python-native for the Quant team; serves ML outputs cleanly |
| **Database** | Supabase (PostgreSQL) | Already in use for SentimentPulse; extend with new tables |
| **Charts** | Recharts or Tremor | React-native charting; Plotly.js is an alternative if parity with existing charts needed |
| **Auth** | Supabase Auth | Role-based: CIO / Analyst / Read-only |
| **Background workers** | Python (APScheduler or cron) | Daily scraping + FinBERT inference; nightly PEAD signal refresh |
| **Deployment** | TBD (Vercel for frontend, Railway/Render for FastAPI) | — |

---

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  Next.js Frontend (TypeScript / React)                           │
│  ├── /research/[ticker]  — Ticker deep-dive                     │
│  ├── /calendar           — Earnings calendar                    │
│  └── /news               — Sentiment news feed                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP (JSON)
┌──────────────────────────▼───────────────────────────────────────┐
│  FastAPI Backend (Python)                                        │
│  ├── GET /api/research/{ticker}   — aggregated deep-dive data   │
│  ├── GET /api/calendar            — earnings + signals          │
│  ├── GET /api/news                — paginated sentiment feed     │
│  ├── GET /api/sentiment/{ticker}  — sentiment history + stats   │
│  └── GET /api/pead/{ticker}       — PEAD signal for ticker      │
└──────┬──────────────────────────────┬────────────────────────────┘
       │                              │
┌──────▼──────┐              ┌────────▼────────────────────────────┐
│  Supabase   │              │  External Data                      │
│  PostgreSQL │              │  ├── yfinance (prices, earnings)    │
│             │              │  ├── Alpha Vantage (EPS/SUE)        │
│  Tables:    │              │  └── CNBC/Finviz/YF scrapers        │
│  articles   │              └────────────────────────────────────-┘
│  sentiments │
│  tickers    │   ◄─── Background Workers (Python, run nightly/daily)
│  pead_cache │           ├── SentimentPulse daily pipeline
│  (new)      │           │   (scrape → FinBERT → DB insert)
└─────────────┘           └── PEAD signal refresh
                              (yfinance → feature compute → DB cache)
```

---

### Database Changes Required

**Existing tables** (SentimentPulse, Supabase):
- `articles` — news articles (keep as-is)
- `sentiments` — sentiment scores per article+entity (keep as-is)
- `tickers` — tracked tickers with metadata (extend) — **[Changed]** replaced by `tracked_tickers`; the old table no longer exists

**New tables** (v1):
```sql
-- [Changed] Not built as stored state: signals are computed on demand and cached in memory
-- for 12h. The table existed briefly and was dropped.
pead_signals (
  ticker          TEXT,
  computed_at     TIMESTAMPTZ,
  earnings_date   DATE,
  ret_5d_pre      FLOAT,
  ret_10d_pre     FLOAT,
  ret_20d_pre     FLOAT,
  pre_earn_vol    FLOAT,
  volume_ratio    FLOAT,
  sue             FLOAT,
  eps_surprise    FLOAT,
  beat_streak     INT,
  outperform_prob_5d   FLOAT,
  outperform_prob_10d  FLOAT,
  outperform_prob_20d  FLOAT,
  rate_regime     INT,
  vix_regime      INT
)

-- v2: positions, trades tables
-- v3: risk_snapshots table
```

---

### API Design (v1 endpoints)

**`GET /api/research/{ticker}`**
Returns all data needed for the ticker deep-dive page in a single call:
```json
{
  "ticker": "NVDA",
  "price_data": [...],
  "sentiment_history": [...],
  "recent_articles": [...],
  "lag_correlations": {...},
  "pead_signal": {...},
  "earnings_history": [...],
  "technicals": {...}
}
```

**`GET /api/calendar`**
Returns upcoming earnings sorted by date with pre-computed signals for all covered tickers.

**`GET /api/news?ticker=&sentiment=&limit=`**
Paginated sentiment news feed with filters.

---

## 6. How Existing Code Gets Adapted

### SentimentPulse → Sentiment Panel + News Feed
- **Keep:** Supabase DB, scrapers, FinBERT pipeline, daily pipeline runner
- **Remove:** Dash app (replaced by Next.js frontend)
- **Adapt:** `app/data/main.py` functions (`get_articles`, `get_price_data`) become FastAPI route handlers
- **New:** FastAPI routes wrap existing data functions and return JSON

### PEAD Research → Earnings Signal Panel + Calendar
- **Keep:** Feature engineering logic, ML models (XGBoost/LightGBM), Alpha Vantage EPS pipeline
- **Remove:** Static script runner, CSV output, matplotlib plots
- **Adapt:** Extract feature computation functions into a reusable module; ~~run nightly, cache to `pead_signals` Supabase table~~ **[Changed]** compute on request, cache in memory for 12h
- **New:** FastAPI route returns signals (computed or cached)

### Earnings Prediction → Merged into PEAD signal
- **Keep:** Regime analysis (rate_regime, vix_regime, TNX/VIX features), SHAP insights, 28-feature set
- **Merge:** Combine best features from both PEAD tools into a single unified signal model
- **New:** Single unified model; outputs served on demand (**[Changed]** no `pead_signals` table)

---

## 7. Covered Ticker Universe

The platform needs a canonical covered ticker list. Currently:
- SentimentPulse: 8 tickers (ADSK, BABA, C, CBRE, GE, GRAB, META, NVDA)
- PEAD tools: 98 S&P 500 names
- Kancil holdings: ~13 names (US + international)

**Recommendation for v1:** Start with ~20–30 tickers — Kancil's current holdings + watchlist. Build a ticker management UI so the CIO/team can add/remove tickers without code changes.

---

## 8. Design Decision: Data Fetching Strategy

### Hybrid On-Demand + Stored Model

Different data types have different cost profiles and are handled differently:

| Data type | Strategy | Rationale |
|-----------|----------|-----------|
| Price data + technicals | Always on-demand (yfinance) | Fast (~200ms), no storage benefit |
| PEAD features (momentum, vol, volume ratio) | Always on-demand | Pure math on price data, computes in seconds |
| ML model inference (outperform probability) | On-demand once model is loaded, cached in memory for 12h | Fast; FinBERT worker stays resident |
| News articles + FinBERT sentiment | Async on first lookup, stored after | FinBERT is too slow for synchronous requests |
| EPS / SUE (Alpha Vantage) | Stored, refreshed quarterly | Rate-limited API — never re-fetch until next quarter |

### First-Lookup Flow (New Ticker)

```
Analyst searches new ticker
  ├─ Immediate response: price chart, technicals, PEAD signal
  ├─ DB check: return cached articles/sentiment if exists
  └─ If not cached: trigger background job
       → scrape news (CNBC, Finviz, Yahoo Finance)
       → queue FinBERT inference
       → write results to Supabase
       → notify frontend when ready (polling or websocket)
       → auto-add ticker to "tracked" list
```

### Tracked Ticker Lifecycle

| Phase | State | Behaviour |
|-------|-------|-----------|
| Analyst starts research | New → Tracked | First-lookup flow above; daily scrape begins |
| Active research cycle | Tracked | Daily news scrape + sentiment refresh |
| Position held post-pitch | Tracked (held flag) | Same refresh; surfaced in portfolio view (v2) |
| Coverage dropped | Untracked | Scraping stops; historical data stays in DB |

Analysts simply search any ticker — the system handles whether it's already tracked or not. No manual setup required.

### Alpha Vantage Rate Limit Note

> **Be conservative with Alpha Vantage calls.** The API is rate-limited. Always check the local cache before making a request. EPS/SUE data only needs re-fetching after a new earnings quarter — never on every page load or ticker lookup. If multiple analysts research new tickers simultaneously, batch the AV calls and process sequentially rather than firing concurrent requests.

---

## 9. Open Questions (Pending)

| # | Question | Owner | Priority |
|---|---------|-------|---------|
| 1 | How are SMF I positions currently tracked? | Ask CIO | High (v2) |
| 2 | Where will the platform be deployed? (Vercel + Railway? Self-hosted?) | Team | High (v1) |
| 3 | ~~Is Alpha Vantage on a paid tier, or do we need an alternative EPS data source?~~ Free tier: 25 calls/day, 1/second. Handled by the 90-day `eps_cache` plus a request throttle. | Team | Answered |
| 4 | What's the covered ticker universe for v1? (Kancil holdings + watchlist?) | CIO | Medium |
| 5 | Should the news scraper run on a cloud scheduler or a local machine? | Team | Medium |

---

## 10. What the Platform Is Not (v1)

- Not a trade execution system
- Not an ICOM voting/pitch tool (stays offline)
- Not a financial data terminal (no Bloomberg/FactSet replacement)
- Not a backtesting engine (PEAD models run offline; results are cached)

