"""Performance degradation analysis — docs/blueprint/10-backtesting-paper-trading.md
anti-overfitting technique #5: compare live paper performance against the
strategy's reference backtest; a sustained divergence raises a WARNING
Alert. This never forces a lifecycle change by itself — Strategy Quarantine
(packages/quant/learning/quarantine.py, Phase 5) already handles the severe
end automatically off the live Health Score; this is the earlier, softer
signal from the lifecycle diagram's PRODUCTION → WARNING → REDUCED →
QUARANTINED chain, surfaced as an Alert for a human to notice.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.quant.learning.promotion import load_promotion_criteria
from packages.shared.models import Alert, BacktestRun, StrategyPerformance, StrategyRow

# Don't re-alert on every subsequent trade close while the condition
# persists — one notification is enough; the strategy stays visibly flagged
# via strategy_performance vs. its reference backtest either way.
ALERT_COOLDOWN_HOURS = 24


def reference_backtest(db: Session, strategy_id: int) -> BacktestRun | None:
    """The backtest a live strategy's performance is judged against --
    shared with packages/backtest/reality_gap.py (packages/backtest is
    allowed to depend on packages/quant per
    docs/blueprint/01-repo-structure.md's dependency table; the reverse
    isn't, so this lookup lives here, not there)."""
    return (
        db.query(BacktestRun)
        .filter(BacktestRun.strategy_id == strategy_id, BacktestRun.kind == "backtest")
        .order_by(BacktestRun.created_at.desc())
        .first()
    )


def _recently_alerted(db: Session, strategy: StrategyRow) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ALERT_COOLDOWN_HOURS)
    return (
        db.query(Alert)
        .filter(Alert.category == "learning", Alert.ts >= cutoff, Alert.message.like(f"%'{strategy.code}'%degraded%"))
        .first()
        is not None
    )


def check_degradation(db: Session, strategy_id: int, *, tolerance_pct: float | None = None) -> bool:
    """Returns True iff a degradation warning was just raised (False for:
    no reference backtest on file, no live performance yet, degradation
    within tolerance, or already alerted recently)."""
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        return False

    reference = reference_backtest(db, strategy_id)
    if reference is None or reference.expectancy is None or reference.expectancy <= 0:
        return False  # nothing to compare against, or no positive baseline to degrade from

    perf = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    if perf is None or perf.expectancy is None:
        return False

    tolerance = tolerance_pct if tolerance_pct is not None else load_promotion_criteria().degradation_tolerance_pct
    degradation_pct = (reference.expectancy - perf.expectancy) / abs(reference.expectancy) * 100
    if degradation_pct <= tolerance:
        return False

    if _recently_alerted(db, strategy):
        return False

    db.add(
        Alert(
            severity="warning", category="learning",
            message=(
                f"Strategy '{strategy.code}' performance degraded {degradation_pct:.1f}% vs its reference "
                f"backtest (live expectancy {perf.expectancy} vs backtest {reference.expectancy})"
            ),
            meta={
                "strategy_id": strategy.id, "live_expectancy": perf.expectancy,
                "backtest_expectancy": reference.expectancy, "degradation_pct": round(degradation_pct, 2),
            },
        )
    )
    db.commit()
    return True
