-- =============================================================================
-- Kancil Capital Portfolio Manager — v1 Schema Migration
-- Run in: Supabase Dashboard → SQL Editor
-- =============================================================================

-- -----------------------------------------------------------------------------
-- EXISTING TABLES (from SentimentPulse)
-- These should already exist. Included here for reference only — do NOT re-run
-- the CREATE statements if the tables are already present.
-- -----------------------------------------------------------------------------

-- articles (
--   id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   url         TEXT UNIQUE,
--   title       TEXT,
--   body        TEXT,
--   source      TEXT,
--   author      TEXT,
--   timestamp   TIMESTAMPTZ
-- );

-- sentiments (
--   id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   article_id  UUID REFERENCES articles(id) ON DELETE CASCADE,
--   affected    TEXT,        -- ticker / sector / region
--   sentiment   FLOAT,       -- -1.0 to +1.0
--   confidence  FLOAT,       -- 0.0 to 1.0
--   timestamp   TIMESTAMPTZ
-- );

-- tickers (
--   id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   ticker      TEXT UNIQUE,
--   name        TEXT,
--   sector      TEXT,
--   region      TEXT,
--   country     TEXT
-- );


-- =============================================================================
-- NEW TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tracked_tickers
-- Lifecycle management for tickers the fund is actively watching.
-- Statuses: 'new' → 'tracking' → 'held' → 'untracked'
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tracked_tickers (
  ticker          TEXT PRIMARY KEY,
  added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  added_by        TEXT,                              -- user email
  status          TEXT NOT NULL DEFAULT 'tracking'
                  CHECK (status IN ('new', 'tracking', 'held', 'untracked')),
  sentiment_ready BOOLEAN NOT NULL DEFAULT FALSE,    -- FALSE while first FinBERT run is pending
  last_scraped    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tracked_tickers_status ON tracked_tickers (status);


-- -----------------------------------------------------------------------------
-- pead_signals
-- Pre-computed nightly PEAD features + XGBoost model outputs.
-- One row per (ticker, computed_at); query the latest row per ticker.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pead_signals (
  ticker              TEXT        NOT NULL,
  computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  earnings_date       DATE,
  days_to_earnings    INT,

  -- Pre-earnings price momentum
  ret_5d_pre          FLOAT,
  ret_10d_pre         FLOAT,
  ret_20d_pre         FLOAT,

  -- Volatility / volume features
  pre_earn_vol_20d    FLOAT,
  volume_ratio        FLOAT,

  -- Market / sector features
  rolling_beta_60d    FLOAT,
  sector_rs_20d       FLOAT,

  -- Earnings surprise features
  eps_surprise        FLOAT,
  sue                 FLOAT,       -- standardised unexpected earnings
  hist_beat_rate      FLOAT,
  beat_streak         INT,
  lagged_surprise     FLOAT,

  -- Macro regime flags
  rate_regime         SMALLINT CHECK (rate_regime IN (0, 1)),
  vix_regime          SMALLINT CHECK (vix_regime IN (0, 1)),
  tnx                 FLOAT,
  vix                 FLOAT,

  -- Model outputs
  outperform_prob_5d  FLOAT,
  outperform_prob_10d FLOAT,
  outperform_prob_20d FLOAT,
  best_horizon        SMALLINT CHECK (best_horizon IN (5, 10, 20)),

  PRIMARY KEY (ticker, computed_at)
);

-- Fast lookup: latest signal per ticker
CREATE INDEX IF NOT EXISTS idx_pead_signals_ticker_time
  ON pead_signals (ticker, computed_at DESC);

-- Fast lookup: upcoming earnings window (used by /api/calendar)
CREATE INDEX IF NOT EXISTS idx_pead_signals_earnings_date
  ON pead_signals (earnings_date)
  WHERE earnings_date IS NOT NULL;


-- -----------------------------------------------------------------------------
-- eps_cache
-- Alpha Vantage EPS / SUE data with strict 90-day TTL.
-- Never re-fetched unless fetched_at < NOW() - INTERVAL '90 days'.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eps_cache (
  ticker              TEXT  NOT NULL,
  fiscal_date         DATE  NOT NULL,
  earnings_date       DATE,
  reported_eps        FLOAT,
  estimated_eps       FLOAT,
  eps_surprise        FLOAT,
  eps_surprise_pct    FLOAT,
  sue                 FLOAT,
  fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  PRIMARY KEY (ticker, fiscal_date)
);

CREATE INDEX IF NOT EXISTS idx_eps_cache_ticker ON eps_cache (ticker);
CREATE INDEX IF NOT EXISTS idx_eps_cache_fetched_at ON eps_cache (fetched_at);


-- =============================================================================
-- ROW-LEVEL SECURITY
-- =============================================================================

ALTER TABLE tracked_tickers ENABLE ROW LEVEL SECURITY;
ALTER TABLE pead_signals     ENABLE ROW LEVEL SECURITY;
ALTER TABLE eps_cache        ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read everything
CREATE POLICY "authenticated read tracked_tickers"
  ON tracked_tickers FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "authenticated read pead_signals"
  ON pead_signals FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "authenticated read eps_cache"
  ON eps_cache FOR SELECT
  TO authenticated
  USING (true);

-- Only the service role (backend) can write
-- (No INSERT/UPDATE/DELETE policies for authenticated — backend uses service key)


-- =============================================================================
-- HELPER FUNCTION: latest PEAD signal per ticker
-- Usage: SELECT * FROM latest_pead_signals();
-- =============================================================================
CREATE OR REPLACE FUNCTION latest_pead_signals()
RETURNS SETOF pead_signals
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT ON (ticker) *
  FROM pead_signals
  ORDER BY ticker, computed_at DESC;
$$;


-- =============================================================================
-- HELPER FUNCTION: calendar view
-- Returns the latest PEAD signal for each tracked ticker with earnings
-- within the next `days_ahead` days.
-- =============================================================================
CREATE OR REPLACE FUNCTION get_calendar_signals(days_ahead INT DEFAULT 30)
RETURNS TABLE (
  ticker              TEXT,
  earnings_date       DATE,
  days_to_earnings    INT,
  sue                 FLOAT,
  eps_surprise        FLOAT,
  hist_beat_rate      FLOAT,
  ret_5d_pre          FLOAT,
  outperform_prob_5d  FLOAT,
  outperform_prob_10d FLOAT,
  outperform_prob_20d FLOAT,
  best_horizon        SMALLINT
)
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT ON (p.ticker)
    p.ticker,
    p.earnings_date,
    p.days_to_earnings,
    p.sue,
    p.eps_surprise,
    p.hist_beat_rate,
    p.ret_5d_pre,
    p.outperform_prob_5d,
    p.outperform_prob_10d,
    p.outperform_prob_20d,
    p.best_horizon
  FROM pead_signals p
  INNER JOIN tracked_tickers t ON t.ticker = p.ticker
  WHERE
    t.status IN ('tracking', 'held')
    AND p.earnings_date IS NOT NULL
    AND p.earnings_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + days_ahead)
  ORDER BY p.ticker, p.computed_at DESC;
$$;
