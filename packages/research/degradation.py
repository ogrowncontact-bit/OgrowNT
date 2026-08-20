"""StrategyDegradationEngine — "PROMPT 10" §5, §7-10.

A 6-state taxonomy (HEALTHY/WATCH/DEGRADING/DEGRADED/FAILED/QUARANTINED)
for the Research Agent's own reasoning — distinct from, and never a
replacement for, `packages/risk/strategy_health.py`'s simpler 4-state
live Risk Engine gate (HEALTHY/WARNING/DEGRADED/QUARANTINED). That module
answers "should this strategy's next signal be sized down or blocked
right now" in the middle of the Risk Engine's decision pipeline; this one
answers "does this strategy's *trend* warrant opening a research
investigation" — a slower, richer question the trading path has no need
for. Both read the exact same underlying `health_score`
(`packages/quant/learning/strategy_stats.py`) and quarantine threshold
(`packages/quant/learning/quarantine.py`) — one source of truth, two
different consumers.

Also reuses `packages/quant/learning/degradation.py::reference_backtest`
(live-vs-backtest comparison) and `packages/research/significance.py`'s
change-point detector rather than re-deriving either.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.quant.learning.degradation import reference_backtest
from packages.quant.learning.promotion import load_promotion_criteria
from packages.quant.learning.quarantine import HEALTH_SCORE_QUARANTINE_THRESHOLD
from packages.research.significance import ChangePointResult, detect_change_point
from packages.shared.models import Position, StrategyPerformance, StrategyRow, Trade

HEALTHY = "HEALTHY"
WATCH = "WATCH"
DEGRADING = "DEGRADING"
DEGRADED = "DEGRADED"
FAILED = "FAILED"
QUARANTINED = "QUARANTINED"
DEGRADATION_STATES = (HEALTHY, WATCH, DEGRADING, DEGRADED, FAILED, QUARANTINED)

# Escalation thresholds on degradation_pct (vs the strategy's own reference
# backtest) -- WATCH reuses config/promotion_criteria.yaml's existing
# degradation_tolerance_pct (the same "vs backtest" number the existing
# Alert-raising check already uses) rather than a fourth new magic number;
# DEGRADED/FAILED escalate further from there.
DEGRADED_DEGRADATION_PCT = 40.0
FAILED_DEGRADATION_PCT = 70.0
# Rolling window size for change-point detection -- large enough to clear
# significance.py's MIN_SAMPLE_SIZE_FOR_SIGNIFICANCE on both sides.
CHANGE_POINT_WINDOW = 30

REDUCE_USAGE = "REDUCE_USAGE"
DISABLE_FOR_REGIME = "DISABLE_FOR_REGIME"
NO_REGIME_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class RegimeRecommendation:
    action: str  # REDUCE_USAGE | DISABLE_FOR_REGIME | NO_ACTION
    regime: str | None
    reason: str


@dataclass(frozen=True)
class DegradationVerdict:
    strategy_id: int
    state: str
    health_score: float | None
    degradation_pct: float | None
    change_point: ChangePointResult | None
    regime_recommendation: RegimeRecommendation
    reasons: list[str] = field(default_factory=list)


def _latest_performance(db: Session, strategy_id: int) -> StrategyPerformance | None:
    return (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )


def _trade_r_multiples(db: Session, strategy_id: int) -> list[float]:
    rows = (
        db.query(Trade.r_multiple)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.strategy_id == strategy_id, Trade.r_multiple.isnot(None))
        .order_by(Trade.closed_at.asc())
        .all()
    )
    return [r for (r,) in rows]


def check_change_point(db: Session, strategy_id: int, *, window: int = CHANGE_POINT_WINDOW) -> ChangePointResult:
    all_r = _trade_r_multiples(db, strategy_id)
    if len(all_r) < window * 2:
        return ChangePointResult(
            detected=False, z_score=None, recent_mean=None, baseline_mean=None,
            recent_n=max(0, len(all_r) - window), baseline_n=min(len(all_r), window),
            reason=f"insufficient trade history ({len(all_r)} closed trades, need >= {window * 2})",
        )
    return detect_change_point(all_r[-window:], all_r[:-window])


def _regime_recommendation(current_regime: str | None, strategy_row: StrategyRow, perf: StrategyPerformance | None) -> RegimeRecommendation:
    """§10: a regime the strategy's own declared risk profile calls
    "worst" recommends DISABLE_FOR_REGIME (stronger evidence -- the
    strategy was never expected to work here); a regime where its OWN
    recent live history shows it as the worst-performing regime
    recommends the softer REDUCE_USAGE. Neither is ever applied
    automatically -- packages/research/approval.py gates any real action.
    """
    if current_regime is None:
        return RegimeRecommendation(NO_REGIME_ACTION, None, "no current regime supplied")

    from packages.quant.strategies import STRATEGY_CLASSES

    strategy_class = STRATEGY_CLASSES.get(strategy_row.code)
    if strategy_class is not None:
        worst_regimes = strategy_class().get_risk_profile().worst_regimes
        if current_regime in worst_regimes:
            return RegimeRecommendation(
                DISABLE_FOR_REGIME, current_regime,
                f"{strategy_row.code}'s own declared risk profile lists {current_regime} as a worst-fit regime",
            )

    if perf is not None and perf.worst_regime == current_regime and (perf.window_trades or 0) >= 5:
        return RegimeRecommendation(
            REDUCE_USAGE, current_regime,
            f"live performance shows {current_regime} as this strategy's worst-performing regime over {perf.window_trades} recent trades",
        )

    return RegimeRecommendation(NO_REGIME_ACTION, current_regime, "no evidence this regime is a problem for this strategy")


def classify_degradation(db: Session, strategy_id: int, *, current_regime: str | None = None) -> DegradationVerdict:
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        raise ValueError(f"strategy {strategy_id} not found")

    perf = _latest_performance(db, strategy_id)
    health_score = perf.health_score if perf else None
    reasons: list[str] = []
    regime_rec = _regime_recommendation(current_regime, strategy, perf)

    if strategy.lifecycle_stage == "quarantine":
        return DegradationVerdict(
            strategy_id=strategy_id, state=QUARANTINED, health_score=health_score, degradation_pct=None,
            change_point=None, regime_recommendation=regime_rec,
            reasons=["strategy.lifecycle_stage is already 'quarantine' (packages/quant/learning/quarantine.py)"],
        )

    reference = reference_backtest(db, strategy_id)
    degradation_pct: float | None = None
    if reference is not None and reference.expectancy is not None and reference.expectancy > 0 and perf is not None and perf.expectancy is not None:
        degradation_pct = round((reference.expectancy - perf.expectancy) / abs(reference.expectancy) * 100, 2)

    change_point = check_change_point(db, strategy_id)
    watch_tolerance = load_promotion_criteria().degradation_tolerance_pct

    if health_score is not None and health_score < HEALTH_SCORE_QUARANTINE_THRESHOLD:
        state = FAILED
        reasons.append(f"health_score {health_score} is below the quarantine threshold {HEALTH_SCORE_QUARANTINE_THRESHOLD}")
    elif degradation_pct is not None and degradation_pct >= FAILED_DEGRADATION_PCT:
        state = FAILED
        reasons.append(f"expectancy degraded {degradation_pct}% vs reference backtest (>= {FAILED_DEGRADATION_PCT}%)")
    elif degradation_pct is not None and degradation_pct >= DEGRADED_DEGRADATION_PCT:
        state = DEGRADED
        reasons.append(f"expectancy degraded {degradation_pct}% vs reference backtest (>= {DEGRADED_DEGRADATION_PCT}%)")
    elif change_point.detected and change_point.z_score is not None and change_point.z_score < 0:
        state = DEGRADING
        reasons.append(f"possible negative change point detected (z={change_point.z_score}) -- {change_point.reason}")
    elif degradation_pct is not None and degradation_pct >= watch_tolerance:
        state = WATCH
        reasons.append(f"expectancy degraded {degradation_pct}% vs reference backtest (>= tolerance {watch_tolerance}%)")
    elif health_score is not None and health_score < 60.0:
        state = WATCH
        reasons.append(f"health_score {health_score} is trending toward the quarantine threshold")
    else:
        state = HEALTHY
        reasons.append("no degradation signal found")

    return DegradationVerdict(
        strategy_id=strategy_id, state=state, health_score=health_score, degradation_pct=degradation_pct,
        change_point=change_point, regime_recommendation=regime_rec, reasons=reasons,
    )
