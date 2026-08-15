"""Pattern Memory — docs/blueprint/06-memory-system.md. Updated by the Trade
Monitor (apps/worker/trade_monitor.py) whenever a position whose signal was
linked to a pattern closes. Incremental running averages, not a full
recompute from trade history each time — cheap, and correct for the
sample_size we're realistically dealing with in Phase 4.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.shared.models import PatternPerformance


def record_trade_outcome(db: Session, *, pattern_type: str, regime: str, r_multiple: float | None, is_win: bool) -> PatternPerformance:
    perf = db.get(PatternPerformance, (pattern_type, regime))
    if perf is None:
        perf = PatternPerformance(pattern_type=pattern_type, regime=regime, sample_size=0, win_rate=0.0, avg_r_multiple=0.0, expectancy=0.0)
        db.add(perf)

    n = perf.sample_size
    new_n = n + 1
    perf.win_rate = round(((perf.win_rate or 0.0) * n + (1.0 if is_win else 0.0)) / new_n, 4)
    if r_multiple is not None:
        perf.avg_r_multiple = round(((perf.avg_r_multiple or 0.0) * n + r_multiple) / new_n, 4)
    # Expectancy in R-multiple terms IS the mean R-multiple across trades —
    # no separate formula needed, avg_r_multiple already blends wins and losses.
    perf.expectancy = perf.avg_r_multiple
    perf.sample_size = new_n

    db.commit()
    return perf
