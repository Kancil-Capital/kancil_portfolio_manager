"""
workers/pead_refresh.py
Nightly PEAD signal refresh — runs at 02:00 UTC.
Recomputes signals for all tracked tickers with upcoming earnings.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

import db.supabase as db
import services.pead_service as pead_service

log = logging.getLogger(__name__)


def refresh_pead_signals() -> None:
    """
    Recompute PEAD signals for all tracked (non-untracked) tickers.
    Skips tickers with no upcoming earnings date.
    """
    log.info("=== Nightly PEAD refresh started ===")

    tracked = db.get_all_tracked_tickers(exclude_untracked=True)
    if not tracked:
        log.info("No tracked tickers — refresh complete")
        return

    success = 0
    skipped = 0
    failed = 0

    for row in tracked:
        ticker = row["ticker"]
        try:
            signal = pead_service.compute_pead_signal(ticker)
            if signal is None:
                log.info(f"  {ticker}: skipped (no earnings date or missing data)")
                skipped += 1
            else:
                log.info(
                    f"  {ticker}: OK — earnings {signal.earnings_date}, "
                    f"best={signal.best_horizon}d @ {max(signal.outperform_prob_5d, signal.outperform_prob_10d, signal.outperform_prob_20d):.1%}"
                )
                success += 1
        except Exception as e:
            log.error(f"  {ticker}: FAILED — {e}")
            failed += 1

    log.info(
        f"=== PEAD refresh complete — {success} updated, {skipped} skipped, {failed} failed ==="
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    refresh_pead_signals()
