# Tools Audit — Kancil Capital Existing Research Tools

*Audited: 2026-04-02*

---

## 1. SentimentPulse (`../sentiment-analysis`)

### What it does
Production-grade financial news sentiment analysis system. Scrapes news, runs FinBERT NLP to score each article's sentiment toward specific equities, and renders an interactive dashboard correlating sentiment with price movements.

### Tech stack
- **Backend**: Python, Dash/Flask, Gunicorn
- **Database**: Supabase (PostgreSQL)
- **ML**: FinBERT (HuggingFace), spaCy NER, NLTK
- **Data**: yfinance (prices), CNBC/Finviz/Yahoo Finance scrapers
- **Auth**: Basic HTTP auth (dash-auth)

### Inputs
| Input | Details |
|-------|---------|
| Tickers | ADSK, BABA, C, CBRE, GE, GRAB, META, NVDA (hardcoded, expandable) |
| Date range | User-selected, up to 1 year lookback |
| Confidence threshold | 0.0–1.0 slider (default 0.2) |
| Affected party | Filter by sector/region/company |

### Outputs
- Sentiment scores per article (−1.0 to +1.0) with confidence
- Daily mean/median sentiment aggregates
- 8 interactive Plotly charts:
  - Price & sentiment overlay (dual-axis)
  - Candlestick OHLC
  - Sentiment histogram
  - Sentiment stacked bars (positive/neutral/negative)
  - Lag correlation scatter (sentiment → next-day returns)
  - Lag correlation heatmap (0–7 day lags)
  - Keyword cloud
  - Statistics panel (net sentiment, best lag, sentiment ratio)

### Data pipeline
```
News scrapers (CNBC, Finviz, Yahoo Finance)
  → Articles table (Supabase)
    → FinBERT sentiment + spaCy entity extraction
      → Sentiments table (Supabase)
        → Dashboard API (Supabase RPC)
          → Plotly dashboard
```

### Key characteristics
- Entity-aware: extracts which ticker/sector/region each article is actually about (not just keyword match)
- Source-weighted: Reuters/Bloomberg (1.0) down to Seeking Alpha (0.8)
- Position-aware: title mentions weighted higher than body mentions
- Daily pipeline trigger for fresh data ingestion

---

## 2. PEAD Research Framework (`../pre-earning-drift-research`)

### What it does
Quantitative research framework that predicts abnormal stock returns following earnings announcements. Tests whether Post-Earnings Announcement Drift (PEAD) is predictable with ML across ~100 S&P 500 stocks over 2014–2024.

### Tech stack
- **Language**: Python (single script, 1,492 lines)
- **ML**: XGBoost, LightGBM, Logistic Regression, Gradient Boosting, Ridge
- **Data**: yfinance (prices, earnings dates), Alpha Vantage (EPS/SUE)
- **Output**: JSON + static PNG charts

### Inputs
| Input | Details |
|-------|---------|
| Tickers | 98 S&P 500 constituents |
| Date range | 2014–2024 (train: 2014–2021, test: 2022–2024) |
| Horizons | 5, 10, 20 days post-earnings |
| Transaction costs | 10 bps round-trip |

### Features (14 total)
| Category | Features |
|----------|---------|
| Momentum | ret_5d/10d/20d pre-earnings |
| Volatility | 20-day realized vol, earnings vol spike |
| Volume | 5d/60d volume ratio |
| Market structure | log market cap, 60-day beta, sector relative strength |
| Earnings surprise | EPS surprise %, SUE (standardized), lagged surprise |
| Interactions | surprise × momentum, surprise × volatility |

### Outputs
- `output/results.json`: Full metrics (AUC, IC, Sharpe, max DD, hit rate, threshold optimization)
- `output/earnings_dataset.csv`: 4,169 events × 22 cols feature matrix
- PNG charts: IC heatmap, horizon comparison, cumulative P&L

### Models trained
- 4 classifiers: XGBoost, LightGBM, Logistic Regression, Gradient Boosting → AUC metric
- 3 regressors: XGBoost, LightGBM, Ridge → Spearman IC metric
- Long-short backtest: top/bottom quintile, quarterly rebalancing, 10bps cost

### Key results
- Best IC ~0.03–0.05 (weak but non-zero signal)
- Trading Sharpe ~0.34 on test set
- PEAD signal strongest at 10-day horizon

---

## 3. Earnings Prediction (`../earnings-prediction`)

### What it does
Complementary PEAD study that predicts whether a stock will outperform the S&P 500 in the 5 trading days following earnings. Also studies how macro regimes (rates, VIX) affect the PEAD effect.

### Tech stack
- **Format**: Jupyter notebooks (5 sequential notebooks)
- **ML**: LightGBM, Logistic Regression
- **Interpretation**: SHAP values
- **Data**: yfinance (prices, earnings, macro)

### Inputs
| Input | Details |
|-------|---------|
| Tickers | 69 S&P 500 stocks |
| Date range | 2019–2024 |
| Hold period | 5 trading days |
| Pre-earnings window | 30 trading days |

### Features (28 total)
| Category | Features |
|----------|---------|
| Earnings surprise | SUE, raw surprise %, hist beat rate, beat streak |
| Technical | ret_5d/10d/14d/20d, RSI-14, MA deviation, realized vol, ATR |
| Volume | vol_ratio_5d, vol_ratio_1d |
| Macro regime | TNX, VIX, rate_regime (binary), vix_regime (binary), rate/VIX change |
| Ticker history | avg earnings move, move std, up rate |

### Outputs
- `data/panel_dataset.csv`: 1,611 events, 35 columns
- `data/logit_predictions.csv`: Cross-validated probabilities
- `data/lgbm_predictions.csv`: Binary + 3-class predictions
- 14 visualization PNGs (EDA, calibration, SHAP, backtest P&L)

### Key findings
| Finding | Detail |
|---------|--------|
| PEAD signal exists | Top SUE quintile outperforms 54.7% vs 44.0% for bottom — 10.7pp spread |
| ML can't beat baseline | Both models ~50.2–50.7% accuracy (vs 49.2% naive) |
| Regime matters | Rate regime is top-10 feature; models differ between 2019–21 vs 2022+ |
| Costs kill edge | 20bps transaction cost wipes small alpha; naive long-all strategy (+0.17%) beats ML |

---

## Cross-Tool Comparison

| Dimension | SentimentPulse | PEAD Research | Earnings Prediction |
|-----------|---------------|--------------|-------------------|
| **Maturity** | Production (dashboard) | Research script | Research notebooks |
| **Signal type** | News sentiment | Earnings drift | Earnings drift + macro |
| **Horizon** | Intraday to weekly | 5/10/20 days post-earnings | 5 days post-earnings |
| **Universe** | 8 tickers (expandable) | 98 S&P 500 | 69 S&P 500 |
| **Persistence** | Supabase DB | CSV files | CSV files |
| **Interactivity** | Full dashboard | CLI/script | Jupyter |
| **Auth** | Basic HTTP auth | None | None |
| **API dependencies** | Supabase, HuggingFace | Alpha Vantage | yfinance only |

---

## Signal Stack (Combined View)

When integrated into a single platform, these tools provide a layered signal stack for equity research:

```
Pre-earnings (T-20 to T-0):
  → Sentiment trend (SentimentPulse)
  → Momentum + volatility features (PEAD Research / Earnings Prediction)
  → Volume anomalies (both PEAD tools)

Earnings event (T-0):
  → EPS surprise vs consensus (both PEAD tools)
  → SUE score (both PEAD tools)
  → Beat streak / historical beat rate (Earnings Prediction)

Post-earnings (T+1 to T+20):
  → PEAD drift prediction (PEAD Research: 5/10/20d)
  → Outperform probability (Earnings Prediction: 5d)
  → Ongoing sentiment monitoring (SentimentPulse)
```
