"""
services/pead_service.py
Unified PEAD feature computation + XGBoost inference.
Adapted from pre-earning-drift-research/predictor.py and earnings-prediction/utils/helpers.py.
Model is loaded once at startup from models/pead_model.joblib.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import db.supabase as db_module
import services.eps_service as eps_service
import services.market_service as market_service
from core.config import settings
from db.models import (
    EarningsHistoryItem,
    PeadFeatures,
    PeadSignal,
)

log = logging.getLogger(__name__)

# ── Feature names (must match training order) ──────────────────────────────────
FEATURE_NAMES = [
    "ret_5d_pre", "ret_10d_pre", "ret_20d_pre",
    "pre_earn_vol_20d", "volume_ratio", "rolling_beta_60d", "sector_rs_20d",
    "eps_surprise", "sue", "hist_beat_rate", "beat_streak", "lagged_surprise",
    "rate_regime", "vix_regime", "tnx", "vix",
    "rsi_14", "pct_above_ma20", "pct_above_ma50",
    "rvol_10d", "rvol_pctile", "vol_term_ratio", "vol_ratio_5d", "atr_pct",
    "ticker_avg_abs_move", "ticker_avg_move", "ticker_move_std", "ticker_up_rate",
]

# ── Model singleton ────────────────────────────────────────────────────────────
_models: dict | None = None   # {"5d": model, "10d": model, "20d": model}


def get_models() -> dict | None:
    global _models
    if _models is not None:
        return _models

    model_path = Path(settings.pead_model_path)
    if not model_path.exists():
        log.warning(f"PEAD model not found at {model_path}. Run scripts/train_pead_model.py first.")
        return None

    try:
        import joblib
        _models = joblib.load(model_path)
        log.info(f"PEAD model loaded from {model_path}")
        return _models
    except Exception as e:
        log.error(f"Failed to load PEAD model: {e}")
        return None


# ── Feature computation helpers ────────────────────────────────────────────────

def _compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff().dropna()
    gain = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return float(100 - (100 / (1 + rs.iloc[-1])))


def _compute_rolling_beta(stock_returns: pd.Series, spy_returns: pd.Series, window: int = 60) -> float:
    aligned = pd.concat([stock_returns, spy_returns], axis=1).dropna()
    if len(aligned) < window // 2:
        return 1.0
    cov = aligned.iloc[-window:, 0].cov(aligned.iloc[-window:, 1])
    var = aligned.iloc[-window:, 1].var()
    return float(cov / (var + 1e-9)) if var else 1.0


def _compute_ticker_history_features(price_df: pd.DataFrame, past_earnings_dates: list) -> dict:
    feats: dict = {}
    past_moves = []
    for ed in past_earnings_dates[-8:]:
        ed_ts = pd.Timestamp(ed)
        future = price_df[price_df.index > ed_ts]
        prev = price_df[price_df.index <= ed_ts]
        if len(future) >= 1 and len(prev) >= 1:
            m = future.iloc[0]["close"] / prev.iloc[-1]["close"] - 1
            past_moves.append(float(m))
    if len(past_moves) >= 2:
        feats["ticker_avg_abs_move"] = float(np.mean(np.abs(past_moves)))
        feats["ticker_avg_move"] = float(np.mean(past_moves))
        feats["ticker_move_std"] = float(np.std(past_moves))
        feats["ticker_up_rate"] = float(np.mean([m > 0 for m in past_moves]))
    return feats


def compute_features(
    ticker: str,
    price_df: pd.DataFrame,
    eps_df: pd.DataFrame | None,
    macro_df: pd.DataFrame | None,
    sector: str | None = None,
) -> dict:
    """
    Compute all 28 PEAD features for the current state of ticker.
    Returns a dict with feature_name → value (None if uncomputable).
    """
    feats: dict = {name: None for name in FEATURE_NAMES}

    if price_df is None or len(price_df) < 5:
        return feats

    close = price_df["close"]
    volume = price_df["volume"]
    high = price_df["high"]
    low = price_df["low"]

    # ── Momentum ───────────────────────────────────────────────────────────────
    for n in [5, 10, 20]:
        if len(close) >= n + 1:
            feats[f"ret_{n}d_pre"] = float(close.iloc[-1] / close.iloc[-(n + 1)] - 1)

    # ── Realized volatility ────────────────────────────────────────────────────
    log_ret = np.log(close / close.shift(1)).dropna()
    if len(log_ret) >= 20:
        feats["pre_earn_vol_20d"] = float(log_ret.tail(20).std() * np.sqrt(252))
    if len(log_ret) >= 10:
        feats["rvol_10d"] = float(log_ret.tail(10).std() * np.sqrt(252))
    if len(log_ret) >= 60:
        roll_vol = log_ret.rolling(20).std() * np.sqrt(252)
        cur_vol = roll_vol.iloc[-1]
        feats["rvol_pctile"] = float((roll_vol < cur_vol).mean())
        st = log_ret.tail(10).std()
        lt = log_ret.tail(60).std()
        feats["vol_term_ratio"] = float(st / (lt + 1e-9))

    # ── Volume ratio ───────────────────────────────────────────────────────────
    if len(volume) >= 10:
        vol_base = volume.iloc[:-5].mean()
        feats["volume_ratio"] = float(volume.tail(5).mean() / (vol_base + 1))
        feats["vol_ratio_5d"] = feats["volume_ratio"]

    # ── RSI ────────────────────────────────────────────────────────────────────
    if len(close) >= 15:
        feats["rsi_14"] = _compute_rsi(close)

    # ── MA deviation ───────────────────────────────────────────────────────────
    if len(close) >= 20:
        feats["pct_above_ma20"] = float(close.iloc[-1] / close.tail(20).mean() - 1)
    if len(close) >= 50:
        feats["pct_above_ma50"] = float(close.iloc[-1] / close.tail(50).mean() - 1)

    # ── ATR ────────────────────────────────────────────────────────────────────
    if len(price_df) >= 14:
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        feats["atr_pct"] = float(tr.tail(14).mean() / (close.iloc[-1] + 1e-9))

    # ── Beta vs SPY ────────────────────────────────────────────────────────────
    try:
        start_date = str((datetime.now() - timedelta(days=120)).date())
        spy_df = market_service.get_raw_price_df_range("^GSPC", start=start_date)
        if spy_df is not None and len(spy_df) >= 30:
            stock_ret = close.pct_change().dropna()
            spy_ret = spy_df["close"].pct_change().dropna()
            feats["rolling_beta_60d"] = _compute_rolling_beta(stock_ret, spy_ret)
    except Exception:
        pass

    # ── Sector relative strength ───────────────────────────────────────────────
    if sector:
        try:
            start_date = str((datetime.now() - timedelta(days=30)).date())
            sector_ret_series = market_service.get_sector_etf_returns(sector, start=start_date)
            if sector_ret_series is not None:
                stock_20d = float(close.iloc[-1] / close.iloc[-min(21, len(close))] - 1)
                sector_20d = float((1 + sector_ret_series.tail(20)).prod() - 1)
                feats["sector_rs_20d"] = stock_20d - sector_20d
        except Exception:
            pass

    # ── EPS / SUE features ─────────────────────────────────────────────────────
    if eps_df is not None and not eps_df.empty:
        latest = eps_df.iloc[-1]
        feats["eps_surprise"] = float(latest["eps_surprise"]) if pd.notna(latest.get("eps_surprise")) else None
        feats["sue"] = float(latest["sue"]) if pd.notna(latest.get("sue")) else None

        if len(eps_df) >= 2:
            feats["lagged_surprise"] = float(eps_df.iloc[-2]["sue"]) if pd.notna(eps_df.iloc[-2].get("sue")) else None

        # Beat rate and streak
        if "reported_eps" in eps_df.columns and "estimated_eps" in eps_df.columns:
            beats = (eps_df["reported_eps"] > eps_df["estimated_eps"]).astype(int)
            if len(beats) >= 2:
                feats["hist_beat_rate"] = float(beats.iloc[:-1].tail(4).mean())
            # Consecutive beat streak (looking at history, excluding current)
            streak = 0
            for b in reversed(beats.iloc[:-1].tolist()):
                if b == 1:
                    streak += 1
                else:
                    break
            feats["beat_streak"] = streak

    # ── Macro features ─────────────────────────────────────────────────────────
    if macro_df is not None and not macro_df.empty:
        latest_macro = macro_df.iloc[-1]
        feats["tnx"] = float(latest_macro["tnx"]) if pd.notna(latest_macro.get("tnx")) else None
        feats["vix"] = float(latest_macro["vix"]) if pd.notna(latest_macro.get("vix")) else None
        feats["rate_regime"] = int(latest_macro["rate_regime"]) if pd.notna(latest_macro.get("rate_regime")) else None
        feats["vix_regime"] = int(latest_macro["vix_regime"]) if pd.notna(latest_macro.get("vix_regime")) else None

    # ── Ticker history ─────────────────────────────────────────────────────────
    if eps_df is not None and not eps_df.empty and "earnings_date" in eps_df.columns:
        past_dates = eps_df["earnings_date"].dropna().tolist()
        history_feats = _compute_ticker_history_features(price_df, past_dates)
        feats.update(history_feats)

    return feats


# ── Earnings date lookup ───────────────────────────────────────────────────────

def get_next_earnings_date(ticker: str) -> tuple[date | None, int]:
    """Return (next_earnings_date, days_to_earnings). (None, 0) if not found."""
    try:
        cal = yf.Ticker(ticker).get_earnings_dates(limit=8)
        if cal is None or cal.empty:
            return None, 0
        cal.index = pd.to_datetime(cal.index).tz_localize(None)
        future = cal[cal.index > datetime.now()]
        if future.empty:
            return None, 0
        next_dt = future.index.min()
        days = (next_dt.date() - date.today()).days
        return next_dt.date(), days
    except Exception:
        return None, 0


# ── Earnings history for display ───────────────────────────────────────────────

def build_earnings_history(eps_df: pd.DataFrame | None) -> list[EarningsHistoryItem]:
    if eps_df is None or eps_df.empty:
        return []
    items = []
    for _, row in eps_df.tail(8).iterrows():
        ed = row.get("earnings_date") or row.get("fiscal_date")
        items.append(EarningsHistoryItem(
            date=str(pd.Timestamp(ed).date()) if pd.notna(ed) else "",
            eps_surprise=float(row["eps_surprise"]) if pd.notna(row.get("eps_surprise")) else None,
            sue=float(row["sue"]) if pd.notna(row.get("sue")) else None,
            beat=bool(row.get("reported_eps", 0) > row.get("estimated_eps", 0))
            if pd.notna(row.get("reported_eps")) and pd.notna(row.get("estimated_eps"))
            else False,
        ))
    return list(reversed(items))  # most recent first


# ── Main service functions ─────────────────────────────────────────────────────

def get_pead_signal(ticker: str) -> PeadSignal | None:
    """Return cached signal if fresh (< 12h), otherwise recompute."""
    cached = db_module.get_latest_pead_signal(ticker)
    if cached:
        computed_at = datetime.fromisoformat(cached["computed_at"].replace("Z", "+00:00"))
        age = datetime.now(tz=timezone.utc) - computed_at
        if age.total_seconds() < 12 * 3600:
            return _row_to_pead_signal(cached, ticker)

    return compute_pead_signal(ticker)


def compute_pead_signal(ticker: str) -> PeadSignal | None:
    """Compute PEAD signal from scratch and persist it."""
    models = get_models()

    # Get next earnings date
    earnings_date, days_to_earnings = get_next_earnings_date(ticker)
    if earnings_date is None:
        log.info(f"No upcoming earnings date found for {ticker}")
        return None

    # Pull data
    start = str((datetime.now() - timedelta(days=180)).date())
    price_df = market_service.get_raw_price_df_range(ticker, start=start)
    if price_df is None or len(price_df) < 20:
        log.warning(f"Insufficient price data for {ticker}")
        return None

    eps_df = eps_service.get_eps_as_dataframe(ticker)

    macro_start = str((datetime.now() - timedelta(days=90)).date())
    macro_df = market_service.get_raw_price_df_range("^TNX", start=macro_start)
    macro_df_full = market_service.get_macro_data(start=macro_start)

    # Get sector for relative strength
    ticker_info = db_module.get_tracked_ticker(ticker)
    sector = ticker_info.get("sector") if ticker_info else None

    feats = compute_features(ticker, price_df, eps_df, macro_df_full, sector=sector)

    # ── ML inference ──────────────────────────────────────────────────────────
    probs: dict[str, float] = {}
    if models:
        feature_vec = [feats.get(f) for f in FEATURE_NAMES]
        # Replace None with 0 for inference
        feature_vec_clean = [v if v is not None else 0.0 for v in feature_vec]
        X = np.array([feature_vec_clean])

        for horizon, model in models.items():
            try:
                p = float(model.predict_proba(X)[0][1])
                probs[horizon] = round(p, 4)
            except Exception as e:
                log.error(f"Model inference failed for {ticker} horizon {horizon}: {e}")
                probs[horizon] = 0.5
    else:
        # No model — return None
        return None

    p5 = probs.get("5d", 0.5)
    p10 = probs.get("10d", 0.5)
    p20 = probs.get("20d", 0.5)
    best_horizon = max([(p5, 5), (p10, 10), (p20, 20)])[1]

    # ── Persist to pead_signals ────────────────────────────────────────────────
    signal_row = {
        "ticker": ticker,
        "computed_at": datetime.now().isoformat(),
        "earnings_date": str(earnings_date),
        "days_to_earnings": days_to_earnings,
        "ret_5d_pre": feats.get("ret_5d_pre"),
        "ret_10d_pre": feats.get("ret_10d_pre"),
        "ret_20d_pre": feats.get("ret_20d_pre"),
        "pre_earn_vol_20d": feats.get("pre_earn_vol_20d"),
        "volume_ratio": feats.get("volume_ratio"),
        "rolling_beta_60d": feats.get("rolling_beta_60d"),
        "sector_rs_20d": feats.get("sector_rs_20d"),
        "eps_surprise": feats.get("eps_surprise"),
        "sue": feats.get("sue"),
        "hist_beat_rate": feats.get("hist_beat_rate"),
        "beat_streak": feats.get("beat_streak"),
        "lagged_surprise": feats.get("lagged_surprise"),
        "rate_regime": feats.get("rate_regime"),
        "vix_regime": feats.get("vix_regime"),
        "tnx": feats.get("tnx"),
        "vix": feats.get("vix"),
        "outperform_prob_5d": p5,
        "outperform_prob_10d": p10,
        "outperform_prob_20d": p20,
        "best_horizon": best_horizon,
    }
    try:
        db_module.upsert_pead_signal(signal_row)
    except Exception as e:
        log.error(f"Failed to persist pead_signal for {ticker}: {e}")

    earnings_history = build_earnings_history(eps_df)

    return PeadSignal(
        earnings_date=str(earnings_date),
        days_to_earnings=days_to_earnings,
        outperform_prob_5d=p5,
        outperform_prob_10d=p10,
        outperform_prob_20d=p20,
        best_horizon=best_horizon,
        features=PeadFeatures(
            ret_5d_pre=feats.get("ret_5d_pre"),
            ret_10d_pre=feats.get("ret_10d_pre"),
            ret_20d_pre=feats.get("ret_20d_pre"),
            pre_earn_vol_20d=feats.get("pre_earn_vol_20d"),
            volume_ratio=feats.get("volume_ratio"),
            sue=feats.get("sue"),
            eps_surprise=feats.get("eps_surprise"),
            hist_beat_rate=feats.get("hist_beat_rate"),
            beat_streak=feats.get("beat_streak"),
            rate_regime=feats.get("rate_regime"),
            vix_regime=feats.get("vix_regime"),
            tnx=feats.get("tnx"),
            vix=feats.get("vix"),
        ),
        earnings_history=earnings_history,
    )


def _row_to_pead_signal(row: dict, ticker: str) -> PeadSignal:
    """Convert a pead_signals DB row back to PeadSignal model."""
    eps_df = eps_service.get_eps_as_dataframe(ticker)
    earnings_history = build_earnings_history(eps_df)

    return PeadSignal(
        earnings_date=row.get("earnings_date", ""),
        days_to_earnings=row.get("days_to_earnings", 0),
        outperform_prob_5d=row.get("outperform_prob_5d", 0.5),
        outperform_prob_10d=row.get("outperform_prob_10d", 0.5),
        outperform_prob_20d=row.get("outperform_prob_20d", 0.5),
        best_horizon=row.get("best_horizon", 5),
        features=PeadFeatures(
            ret_5d_pre=row.get("ret_5d_pre"),
            ret_10d_pre=row.get("ret_10d_pre"),
            ret_20d_pre=row.get("ret_20d_pre"),
            pre_earn_vol_20d=row.get("pre_earn_vol_20d"),
            volume_ratio=row.get("volume_ratio"),
            sue=row.get("sue"),
            eps_surprise=row.get("eps_surprise"),
            hist_beat_rate=row.get("hist_beat_rate"),
            beat_streak=row.get("beat_streak"),
            rate_regime=row.get("rate_regime"),
            vix_regime=row.get("vix_regime"),
            tnx=row.get("tnx"),
            vix=row.get("vix"),
        ),
        earnings_history=earnings_history,
    )
