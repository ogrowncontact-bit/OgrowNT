"""Risk Engine + Execution Engine, wired into the Strategy cycle.

Called once per newly-scored signal, right after packages/quant/scoring
produces its OpportunityScore — the MarketContext is still in memory, so
there's no need to reconstruct it from the DB just to run the risk check
(docs/blueprint/05-event-flow.md's SCORE -> RISK -> PORTFOLIO -> EXECUTION
pipeline, as one continuous flow per signal).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.execution.adapters.base import ExecutionProvider
from packages.execution.order_manager import open_position
from packages.portfolio.state import compute_state
from packages.quant.scoring.engine import OpportunityScore as ScoreResult
from packages.quant.strategies.base import AnalysisResult, MarketContext, Strategy, StrategySignal
from packages.risk.engine import SignalForRisk, evaluate_signal
from packages.shared.models import Asset, Signal, SystemState

logger = logging.getLogger("worker.risk_execution")

# Only these tiers are sent to the Risk Engine at all — docs/blueprint/
# 07-scoring-engine.md: watch/ignore are informational only.
TIERS_ELIGIBLE_FOR_RISK_REVIEW = {"possible", "high_quality", "exceptional"}

BASELINE_ATR_PCT = 0.01  # 1% of price treated as "normal" volatility for sizing


def _volatility_factor(ctx: MarketContext) -> float:
    atr, close = ctx.indicators.atr_14, ctx.indicators.close
    if not atr or not close:
        return 1.0
    return max(1.0, (atr / close) / BASELINE_ATR_PCT)


def _get_or_create_system_state(db: Session) -> SystemState:
    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
        db.add(state)
        db.commit()
    return state


def maybe_execute(
    db: Session,
    provider: ExecutionProvider,
    *,
    ctx: MarketContext,
    asset: Asset,
    strategy: Strategy,
    analysis: AnalysisResult,
    signal: StrategySignal,
    signal_row: Signal,
    score: ScoreResult,
) -> str:
    """Returns 'skipped_tier', 'risk_rejected', or 'executed' for the caller's tally."""
    if score.tier not in TIERS_ELIGIBLE_FOR_RISK_REVIEW:
        return "skipped_tier"

    system_state = _get_or_create_system_state(db)
    portfolio_state = compute_state(db)  # fresh each call: earlier signals this same cycle may have opened positions

    signal_for_risk = SignalForRisk(
        signal_id=signal_row.id,
        asset_id=asset.id,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        target_price=signal.target_price,
        risk_reward=signal.risk_reward,
        confidence=analysis.strength,
        volatility_factor=_volatility_factor(ctx),
        data_quality=ctx.candles[-1].data_quality,
        data_ts=ctx.candles[-1].ts,
        tier=score.tier,
    )

    verdict = evaluate_signal(db, signal_for_risk, portfolio_state, system_state)

    if not verdict.approved:
        signal_row.status = "risk_rejected"
        db.commit()
        logger.info("%s %s REJECTED reason=%s", asset.symbol, strategy.code, verdict.reason)
        return "risk_rejected"

    signal_row.status = "approved"
    db.commit()

    position = open_position(db, provider, signal=signal_row, asset=asset, quantity=verdict.approved_quantity)
    if position is None:
        logger.warning("%s %s approved but fill failed (DATA_UNAVAILABLE at execution time)", asset.symbol, strategy.code)
        return "risk_rejected"

    logger.info(
        "%s %s EXECUTED qty=%.6f entry~%.4f belt=%s",
        asset.symbol, strategy.code, verdict.approved_quantity, signal.entry_price, verdict.safety_belt_level,
    )
    return "executed"
