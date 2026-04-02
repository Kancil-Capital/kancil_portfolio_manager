# Kancil Capital Research Platform — Vision Document

*Version: 0.3 | Date: 2026-04-02 | Status: Approved for architecture planning*

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
- `tickers` — tracked tickers with metadata (extend)

**New tables** (v1):
```sql
-- Pre-computed PEAD signals, refreshed nightly
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
- **Adapt:** Extract feature computation functions into a reusable module; run nightly, cache to `pead_signals` Supabase table
- **New:** FastAPI route reads from cache and returns pre-computed signals

### Earnings Prediction → Merged into PEAD signal
- **Keep:** Regime analysis (rate_regime, vix_regime, TNX/VIX features), SHAP insights, 28-feature set
- **Merge:** Combine best features from both PEAD tools into a single unified signal model
- **New:** Single `pead_signals` table stores outputs from the unified model

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
| ML model inference (outperform probability) | On-demand once model is loaded | Fast; FinBERT worker stays resident |
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
| 3 | Is Alpha Vantage on a paid tier, or do we need an alternative EPS data source? | Team | Medium |
| 4 | What's the covered ticker universe for v1? (Kancil holdings + watchlist?) | CIO | Medium |
| 5 | Should the news scraper run on a cloud scheduler or a local machine? | Team | Medium |

---

## 10. What the Platform Is Not (v1)

- Not a trade execution system
- Not an ICOM voting/pitch tool (stays offline)
- Not a financial data terminal (no Bloomberg/FactSet replacement)
- Not a backtesting engine (PEAD models run offline; results are cached)
