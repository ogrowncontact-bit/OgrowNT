"""Promotion pipeline — docs/blueprint/10-backtesting-paper-trading.md
"Research Agent → Produção" and "Critério de promoção mínimo". A strategy
never promotes itself: `evaluate_promotion` only ever answers "does it
qualify right now, and why/why not" (DET, config-driven, same live-editable
pattern as packages/risk/config.py). Actually moving
`strategies.lifecycle_stage` is `apply_promotion`, called only from an
explicit admin action (apps/api/routers/strategies.py's
POST /{id}/promote) — never automatic, matching Strategy Quarantine's
"DET can only ever take away, a human gives back" precedent in reverse:
here DET can only ever gate, a human still has to pull the trigger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from packages.shared.models import Alert, AuditLog, Position, StrategyPerformance, StrategyRow, Trade

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "promotion_criteria.yaml"

# Only these two transitions are ever gated by DET criteria — 'idea',
# 'backtest' and 'out_of_sample' are research-pipeline stages this module
# doesn't touch, and 'quarantine'/'retired' have their own (one-way, admin
# restore only) path in packages/quant/learning/quarantine.py.
_NEXT_STAGE = {"paper": "small_capital", "small_capital": "production"}


@dataclass(frozen=True)
class PromotionCriteria:
    min_paper_trades: int
    min_paper_days: int
    max_drawdown_pct: float
    min_expectancy: float
    min_sharpe_like: float
    degradation_tolerance_pct: float


def load_promotion_criteria(path: Path = CONFIG_PATH) -> PromotionCriteria:
    raw = yaml.safe_load(path.read_text())
    return PromotionCriteria(**raw["promotion"])


@dataclass(frozen=True)
class PromotionVerdict:
    eligible: bool
    current_stage: str
    next_stage: str | None
    reasons: list[str] = field(default_factory=list)
    criteria: dict = field(default_factory=dict)
    actual: dict = field(default_factory=dict)


def _earliest_trade_closed_at(db: Session, strategy_id: int) -> datetime | None:
    row = (
        db.query(Trade.closed_at)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.strategy_id == strategy_id)
        .order_by(Trade.closed_at.asc())
        .first()
    )
    return row[0] if row else None


def evaluate_promotion(db: Session, strategy_id: int, criteria: PromotionCriteria | None = None) -> PromotionVerdict:
    criteria = criteria or load_promotion_criteria()
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        return PromotionVerdict(eligible=False, current_stage="unknown", next_stage=None, reasons=["strategy not found"])

    next_stage = _NEXT_STAGE.get(strategy.lifecycle_stage)
    if next_stage is None:
        return PromotionVerdict(
            eligible=False, current_stage=strategy.lifecycle_stage, next_stage=None,
            reasons=[f"lifecycle_stage '{strategy.lifecycle_stage}' is not eligible for promotion (only 'paper' and 'small_capital' are)"],
        )

    perf = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    reasons: list[str] = []
    actual: dict = {}

    total_trades = perf.total_trades if perf else 0
    actual["total_trades"] = total_trades
    if total_trades < criteria.min_paper_trades:
        reasons.append(f"only {total_trades} paper trades closed, need >= {criteria.min_paper_trades}")

    earliest = _earliest_trade_closed_at(db, strategy_id)
    days_trading = (datetime.now(timezone.utc) - earliest).days if earliest else 0
    actual["days_trading"] = days_trading
    if days_trading < criteria.min_paper_days:
        reasons.append(f"only {days_trading} days of paper trading, need >= {criteria.min_paper_days}")

    max_dd = perf.max_drawdown if perf else None
    actual["max_drawdown"] = max_dd
    if max_dd is None:
        reasons.append("no drawdown data yet")
    elif max_dd > criteria.max_drawdown_pct:
        reasons.append(f"max_drawdown {max_dd} exceeds {criteria.max_drawdown_pct}% limit")

    expectancy = perf.expectancy if perf else None
    actual["expectancy"] = expectancy
    if expectancy is None:
        reasons.append("no expectancy data yet")
    elif expectancy < criteria.min_expectancy:
        reasons.append(f"expectancy {expectancy} below required {criteria.min_expectancy}")

    sharpe = perf.sharpe if perf else None
    actual["sharpe"] = sharpe
    if sharpe is None:
        reasons.append("no sharpe_like data yet")
    elif sharpe < criteria.min_sharpe_like:
        reasons.append(f"sharpe_like {sharpe} below required {criteria.min_sharpe_like}")

    return PromotionVerdict(
        eligible=(len(reasons) == 0), current_stage=strategy.lifecycle_stage, next_stage=next_stage,
        reasons=reasons, criteria=vars(criteria), actual=actual,
    )


def apply_promotion(db: Session, strategy_id: int, *, actor: str, criteria: PromotionCriteria | None = None) -> StrategyRow:
    """Admin-only — see apps/api/routers/strategies.py. Re-checks eligibility
    server-side (never trusts a client-supplied verdict) and raises
    ValueError with the specific reasons if the strategy doesn't qualify."""
    verdict = evaluate_promotion(db, strategy_id, criteria)
    if not verdict.eligible:
        raise ValueError("; ".join(verdict.reasons) or "not eligible for promotion")

    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        # Unreachable in practice: evaluate_promotion already returned
        # eligible=False for a missing strategy, which raised above. Guarded
        # explicitly anyway rather than relying on that cross-function
        # invariant to hold forever — this mutates lifecycle_stage.
        raise ValueError("strategy not found")
    if verdict.next_stage is None:
        # Unreachable in practice: eligible=True is only ever returned by
        # evaluate_promotion alongside a real next_stage. Guarded explicitly
        # for the same reason as the strategy-not-found check above.
        raise ValueError("no next lifecycle stage to promote to")
    previous_stage = strategy.lifecycle_stage
    strategy.lifecycle_stage = verdict.next_stage
    db.add(strategy)
    db.add(
        AuditLog(
            actor=actor, action="promote_strategy", entity_type="strategy", entity_id=strategy.id,
            detail={"from": previous_stage, "to": verdict.next_stage, "criteria": verdict.criteria, "actual": verdict.actual},
        )
    )
    db.add(
        Alert(
            severity="info", category="learning",
            message=f"Strategy '{strategy.code}' promoted {previous_stage} -> {verdict.next_stage}",
            meta={"strategy_id": strategy.id, "from": previous_stage, "to": verdict.next_stage},
        )
    )
    db.commit()
    return strategy
