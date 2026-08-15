"""Strategy Quarantine — docs/blueprint/12-roadmap.md Phase 5. Demoting an
underperforming live strategy out of new-signal generation mirrors the Kill
Switch precedent (docs/blueprint/08-risk-engine.md): automatic, DET-only,
and always in the risk-reducing direction. The reverse — restoring a
quarantined strategy — is never automatic; it's an explicit admin action
(docs/blueprint/04-agents-architecture.md's "Research Agent propõe, Risk
Engine + admin aprovam" governs any lifecycle promotion). Enforcement point:
apps/worker/strategy_runner.py skips strategies whose lifecycle_stage is
'quarantine' or 'retired' before generating a signal.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.shared.models import Alert, AuditLog, StrategyPerformance, StrategyRow

# Below this health score (0-100, packages/quant/learning/strategy_stats.py),
# a strategy with enough sample size to trust the number gets pulled from
# live signal generation. Conservative on purpose — capital preservation
# over letting a strategy "prove itself" further while it's bleeding.
HEALTH_SCORE_QUARANTINE_THRESHOLD = 35.0

# Quarantine is only meaningful for a strategy actually generating live
# (paper) signals — an idea/backtest/out_of_sample strategy isn't live yet,
# and a strategy already quarantined/retired needs no further action.
_QUARANTINABLE_STAGES = ("paper", "small_capital", "production")


def evaluate_quarantine(db: Session, strategy_id: int, perf: StrategyPerformance) -> bool:
    """Checks one strategy's freshly computed performance against the
    quarantine threshold and demotes it if warranted. Returns True iff this
    call just quarantined the strategy (False otherwise — healthy, already
    quarantined, not yet eligible, or sample too thin to judge).
    """
    if perf.health_score is None or perf.health_score >= HEALTH_SCORE_QUARANTINE_THRESHOLD:
        return False

    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None or strategy.lifecycle_stage not in _QUARANTINABLE_STAGES:
        return False

    previous_stage = strategy.lifecycle_stage
    strategy.lifecycle_stage = "quarantine"
    db.add(strategy)

    reason = (
        f"health_score {perf.health_score:.2f} < threshold {HEALTH_SCORE_QUARANTINE_THRESHOLD} "
        f"over last {perf.window_trades} trades (win_rate={perf.win_rate}, expectancy={perf.expectancy})"
    )
    db.add(
        Alert(
            severity="warning", category="learning",
            message=f"Strategy '{strategy.code}' quarantined: {reason}",
            meta={"strategy_id": strategy.id, "health_score": perf.health_score, "previous_stage": previous_stage},
        )
    )
    db.add(
        AuditLog(
            actor="learning_agent", action="quarantine_strategy", entity_type="strategy",
            entity_id=strategy.id, detail={"previous_stage": previous_stage, "reason": reason},
        )
    )
    db.commit()
    return True


def restore_from_quarantine(db: Session, strategy_id: int, *, to_stage: str = "paper", actor: str = "admin") -> StrategyRow:
    """Admin-only restoration — see apps/api/routers/learning.py. Never
    called by the worker; a quarantined strategy stays quarantined until a
    human puts it back."""
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        raise ValueError("strategy not found")
    if strategy.lifecycle_stage != "quarantine":
        raise ValueError("strategy is not in quarantine")
    if to_stage not in _QUARANTINABLE_STAGES:
        raise ValueError(f"to_stage must be one of {_QUARANTINABLE_STAGES}")

    strategy.lifecycle_stage = to_stage
    db.add(strategy)
    db.add(
        AuditLog(
            actor=actor, action="restore_strategy", entity_type="strategy",
            entity_id=strategy.id, detail={"to_stage": to_stage},
        )
    )
    db.commit()
    return strategy
