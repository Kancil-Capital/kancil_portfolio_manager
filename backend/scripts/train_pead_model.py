"""
scripts/train_pead_model.py
Offline PEAD model training script.
Run from the backend/ directory:
    uv run python scripts/train_pead_model.py

Downloads price + EPS data, engineers 28 features per earnings event,
trains XGBoost classifiers for 5d / 10d / 20d outperformance horizons,
and saves models/pead_model.joblib.

The serialised dict is:  {"5d": model_5d, "10d": model_10d, "20d": model_20d}
"""

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Ensure backend/ is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
import time
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier

from services.market_service import (
    get_macro_data,
    get_raw_price_df_range,
)
from services.pead_service import FEATURE_NAMES, compute_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Ticker universe ────────────────────────────────────────────────────────────

SP500_SAMPLE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
    "JNJ", "WMT", "PG", "MA", "UNH", "HD", "CVX", "ABBV", "MRK", "COST",
    "PEP", "AVGO", "CSCO", "ACN", "LIN", "ADBE", "TXN", "DHR", "VZ", "INTC",
    "CMCSA", "NEE", "PM", "BMY", "RTX", "T", "AMGN", "QCOM", "HON", "SBUX",
    "INTU", "LOW", "ELV", "GS", "AMD", "DE", "CAT", "SPGI", "AXP", "ISRG",
    "BLK", "MDLZ", "PLD", "CI", "NOW", "GILD", "ADP", "TMO", "SYK", "MO",
]

TRAIN_START = "2015-01-01"
TRAIN_END = datetime.now().strftime("%Y-%m-%d")
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "models" / "pead_model.joblib"

# Checkpoint paths — deleted automatically after successful training
CHECKPOINT_ROWS = Path(__file__).resolve().parent / ".checkpoint_rows.csv"
CHECKPOINT_DONE = Path(__file__).resolve().parent / ".checkpoint_done.txt"


# ── Data collection ────────────────────────────────────────────────────────────

def get_earnings_history_yf(ticker: str) -> pd.DataFrame | None:
    """Pull earnings dates + EPS from yfinance."""
    try:
        t = yf.Ticker(ticker)
        cal = t.get_earnings_dates(limit=40)
        if cal is None or cal.empty:
            return None

        cal = cal.copy()
        cal.index = pd.to_datetime(cal.index).tz_localize(None)
        cal = cal.sort_index()
        cal = cal.dropna(subset=["Reported EPS"])
        cal = cal.rename(columns={
            "Reported EPS": "eps_actual",
            "EPS Estimate": "eps_est",
        })

        cal["eps_surprise"] = cal["eps_actual"] - cal["eps_est"]
        cal["eps_std"] = cal["eps_surprise"].rolling(4, min_periods=2).std().shift(1)
        cal["sue"] = (cal["eps_surprise"] / (cal["eps_std"].abs() + 1e-9)).clip(-10, 10)
        cal["eps_surprise_pct"] = cal["eps_surprise"] / cal["eps_est"].abs().replace(0, np.nan)
        cal["beat"] = (cal["eps_actual"] > cal["eps_est"]).astype(int)
        cal["hist_beat_rate"] = cal["beat"].shift(1).rolling(4, min_periods=2).mean()

        def consec_streak(series):
            streaks, count = [], 0
            for v in series:
                count = count + 1 if v == 1 else 0
                streaks.append(count)
            return pd.Series(streaks, index=series.index)

        cal["beat_streak"] = consec_streak(cal["beat"].shift(1).fillna(0))
        return cal
    except Exception as e:
        log.debug(f"earnings_history failed for {ticker}: {e}")
        return None


def build_dataset_for_ticker(
    ticker: str,
    price_df: pd.DataFrame,
    eps_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    spx_df: pd.DataFrame,
    sector: str | None,
) -> list[dict]:
    """Build feature rows for every historical earnings date of a ticker."""
    rows = []

    if eps_df is None or eps_df.empty or price_df is None:
        return rows

    earnings_dates = eps_df.index.tolist()

    for i, ed in enumerate(earnings_dates):
        if ed < pd.Timestamp(TRAIN_START) or ed > pd.Timestamp(TRAIN_END):
            continue

        # Pre-earnings price window (up to 90 days before)
        pre_start = ed - timedelta(days=90)
        pre_prices = price_df[(price_df.index >= pre_start) & (price_df.index < ed)]
        if len(pre_prices) < 20:
            continue

        # Post-earnings returns (5d, 10d, 20d)
        post_prices = price_df[price_df.index >= ed]
        if len(post_prices) < 21:
            continue

        targets: dict[str, int] = {}
        for horizon in [5, 10, 20]:
            if len(post_prices) < horizon + 1:
                break
            stock_ret = post_prices["close"].iloc[horizon] / post_prices["close"].iloc[0] - 1
            spx_slice = spx_df[spx_df.index >= ed]
            if len(spx_slice) < horizon + 1:
                break
            spx_ret = spx_slice["close"].iloc[horizon] / spx_slice["close"].iloc[0] - 1
            targets[f"target_{horizon}d"] = int(stock_ret > spx_ret)

        if len(targets) < 3:
            continue

        # Build EPS sub-df for this event (all events up to and including this one)
        eps_sub = eps_df.iloc[: i + 1].copy()
        # Map earnings-prediction helper column names
        eps_sub["reported_eps"] = eps_sub["eps_actual"] if "eps_actual" in eps_sub.columns else None
        eps_sub["estimated_eps"] = eps_sub["eps_est"] if "eps_est" in eps_sub.columns else None
        eps_sub["fiscal_date"] = eps_sub.index

        # Macro slice around earnings date
        macro_slice = macro_df[macro_df.index <= ed].tail(5)

        # Compute features
        feats = compute_features(ticker, pre_prices, eps_sub, macro_slice, sector=sector)

        row = {**feats, **targets, "ticker": ticker, "earnings_date": str(ed.date())}
        rows.append(row)

    return rows


# ── Main training loop ─────────────────────────────────────────────────────────

def main():
    log.info(f"Training PEAD model on {len(SP500_SAMPLE)} tickers from {TRAIN_START}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Download macro data once
    log.info("Downloading macro data (TNX, VIX)...")
    macro_df = get_macro_data(start=TRAIN_START)
    if macro_df is None:
        log.error("Failed to get macro data — aborting")
        sys.exit(1)

    log.info("Downloading S&P 500 returns...")
    spx_df = get_raw_price_df_range("^GSPC", start=TRAIN_START)
    if spx_df is None:
        log.error("Failed to get SPX data — aborting")
        sys.exit(1)

    # Batch-download all price data in one request to avoid per-ticker rate limits
    log.info(f"Batch downloading price data for {len(SP500_SAMPLE)} tickers...")
    raw = yf.download(
        SP500_SAMPLE,
        start=TRAIN_START,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )

    def _extract_price_df(raw_data: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
        try:
            if isinstance(raw_data.columns, pd.MultiIndex):
                df = raw_data[ticker][["Open", "High", "Low", "Close", "Volume"]].copy()
            else:
                df = raw_data[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            df.index = pd.to_datetime(df.index)
            if df.index.tzinfo is not None:
                df.index = df.index.tz_localize(None)
            df = df.dropna(how="all")
            return df.sort_index() if not df.empty else None
        except Exception:
            return None

    # ── Checkpoint: resume from where we left off ──────────────────────────────
    done_tickers: set[str] = set()
    if CHECKPOINT_DONE.exists():
        done_tickers = set(CHECKPOINT_DONE.read_text().splitlines())
        log.info(f"Resuming — {len(done_tickers)} tickers already done: {sorted(done_tickers)}")

    remaining = [t for t in SP500_SAMPLE if t not in done_tickers]
    log.info(f"{len(remaining)} tickers left to process")

    # Collect all training rows
    for ticker in remaining:
        log.info(f"Processing {ticker}...")
        try:
            price_df = _extract_price_df(raw, ticker)
            eps_df = get_earnings_history_yf(ticker)
            time.sleep(0.5)  # avoid per-ticker rate limits on earnings endpoint

            if price_df is None or eps_df is None:
                log.info(f"  {ticker}: skipped (no data)")
            else:
                # Get sector for relative strength
                try:
                    info = yf.Ticker(ticker).info
                    sector = info.get("sector")
                    time.sleep(0.3)
                except Exception:
                    sector = None

                rows = build_dataset_for_ticker(ticker, price_df, eps_df, macro_df, spx_df, sector)
                log.info(f"  {ticker}: {len(rows)} earnings events")

                if rows:
                    rows_df = pd.DataFrame(rows)
                    rows_df.to_csv(
                        CHECKPOINT_ROWS,
                        mode="a",
                        header=not CHECKPOINT_ROWS.exists(),
                        index=False,
                    )

        except Exception as e:
            log.error(f"  {ticker}: failed — {e}")
            continue

        # Mark done regardless of outcome so we don't retry on restart
        with CHECKPOINT_DONE.open("a") as f:
            f.write(ticker + "\n")
        done_tickers.add(ticker)

    if not CHECKPOINT_ROWS.exists():
        log.error("No training data collected — aborting")
        sys.exit(1)

    df = pd.read_csv(CHECKPOINT_ROWS)
    log.info(f"\nTotal training rows: {len(df)}")
    log.info(f"Date range: {df['earnings_date'].min()} to {df['earnings_date'].max()}")

    # Fill missing features with median
    for col in FEATURE_NAMES:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())
        else:
            df[col] = 0.0

    X = df[FEATURE_NAMES].values

    models: dict = {}
    for horizon in ["5d", "10d", "20d"]:
        target_col = f"target_{horizon}"
        if target_col not in df.columns:
            log.warning(f"Target {target_col} missing — skipping")
            continue

        y = df[target_col].values
        log.info(f"\nTraining {horizon} model — {y.sum()}/{len(y)} positive ({y.mean():.1%})")

        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )

        # Time-series cross-validation (no data leakage)
        tscv = TimeSeriesSplit(n_splits=5)
        auc_scores = []
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_tr, X_val = X[train_idx], X[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            if len(np.unique(y_val)) < 2:
                continue
            m = XGBClassifier(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                use_label_encoder=False, eval_metric="logloss",
                random_state=42, n_jobs=-1,
            )
            m.fit(X_tr, y_tr)
            auc = roc_auc_score(y_val, m.predict_proba(X_val)[:, 1])
            auc_scores.append(auc)
            log.info(f"  Fold {fold + 1}: AUC = {auc:.4f}")

        if auc_scores:
            log.info(f"  Mean AUC: {np.mean(auc_scores):.4f} ± {np.std(auc_scores):.4f}")

        # Train final model on all data
        model.fit(X, y)
        models[horizon] = model
        log.info(f"  Final model trained on {len(X)} rows")

        # Feature importances
        importances = pd.Series(model.feature_importances_, index=FEATURE_NAMES)
        top5 = importances.nlargest(5)
        log.info(f"  Top 5 features: {top5.to_dict()}")

    # Save
    joblib.dump(models, OUTPUT_PATH)
    log.info(f"\nModels saved to {OUTPUT_PATH}")

    # Clean up checkpoints now that training succeeded
    CHECKPOINT_ROWS.unlink(missing_ok=True)
    CHECKPOINT_DONE.unlink(missing_ok=True)
    log.info("Checkpoints cleared. Done. Run the FastAPI server to use the model.")


if __name__ == "__main__":
    main()
