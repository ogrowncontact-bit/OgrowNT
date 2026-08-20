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

from packages.agents import chief as chief_decision
from packages.execution.adapters.base import ExecutionProvider
from packages.execution.order_manager import open_position
from packages.portfolio.manager import evaluate_allocation
from packages.portfolio.state import compute_state
from packages.quant.scoring.engine import OpportunityScore as ScoreResult
from packages.quant.strategies.base import AnalysisResult, MarketContext, Strategy, StrategySignal
from packages.risk.config import load_risk_limits
from packages.risk.engine import SignalForRisk, evaluate_signal
from packages.shared.models import Asset, Signal, SystemState, TradingEvent

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
    decision: chief_decision.Decision | None = None,
) -> str:
    """Returns 'skipped_tier', 'chief_blocked', 'chief_no_trade',
    'risk_rejected', 'portfolio_rejected', or 'executed' for the caller's
    tally."""
    if score.tier not in TIERS_ELIGIBLE_FOR_RISK_REVIEW:
        db.add(
            TradingEvent(
                event_type="no_trade", entity_type="signal", entity_id=signal_row.id,
                payload={"stage": "tier_filter", "tier": score.tier, "asset": asset.symbol, "strategy": strategy.code},
            )
        )
        db.commit()
        return "skipped_tier"

    # "PROMPT 9" §14, §68 -- Chief Decision Engine gate: an ADDITIONAL
    # pre-filter ahead of the sovereign Risk Engine below, never a
    # replacement for it. A favorable Decision never approves a trade on
    # its own -- evaluate_signal() still runs, unchanged, on every signal
    # that reaches this point. `decision is None` (e.g. the Critical Safety
    # Battery's direct maybe_execute() calls, which construct their own
    # kwargs without running the multi-agent cycle) is treated as "no
    # opinion", not as an implicit approval.
    if decision is not None and decision.decision_state in (chief_decision.BLOCKED, chief_decision.NO_TRADE):
        event_type = "risk_blocked" if decision.decision_state == chief_decision.BLOCKED else "no_trade"
        db.add(
            TradingEvent(
                event_type=event_type, entity_type="signal", entity_id=signal_row.id,
                payload={
                    "layer": "chief_decision_engine", "decision_state": decision.decision_state,
                    "reasoning": decision.reasoning_summary, "critical_agent_failure": decision.critical_agent_failure,
                    "asset": asset.symbol, "strategy": strategy.code,
                },
            )
        )
        db.commit()
        outcome = "chief_blocked" if decision.decision_state == chief_decision.BLOCKED else "chief_no_trade"
        logger.info("%s %s CHIEF DECISION %s reason=%s", asset.symbol, strategy.code, outcome, decision.reasoning_summary)
        return outcome

    system_state = _get_or_create_system_state(db)
    portfolio_state = compute_state(db)  # fresh each call: earlier signals this same cycle may have opened positions
    limits = load_risk_limits()

    signal_for_risk = SignalForRisk(
        signal_id=signal_row.id,
        asset_id=asset.id,
        strategy_id=signal_row.strategy_id,
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
        asset_class=asset.asset_class,
    )

    verdict = evaluate_signal(db, signal_for_risk, portfolio_state, system_state, limits=limits)

    if not verdict.approved:
        signal_row.status = "risk_rejected"
        db.add(
            TradingEvent(
                event_type="risk_blocked", entity_type="signal", entity_id=signal_row.id,
                payload={"layer": "risk_engine", "reason": verdict.reason, "asset": asset.symbol, "strategy": strategy.code},
            )
        )
        db.commit()
        logger.info("%s %s REJECTED reason=%s", asset.symbol, strategy.code, verdict.reason)
        return "risk_rejected"

    if verdict.approved_quantity is None:
        # Unreachable in practice: evaluate_signal only ever leaves
        # approved_quantity None on the (already-returned-above) rejected
        # path. Guarded explicitly anyway — this sizes a real order.
        logger.warning("%s %s approved with no sized quantity — treating as rejected", asset.symbol, strategy.code)
        return "risk_rejected"

    # Portfolio Manager gate (§12-17) — a second, distinct approval after
    # Risk Engine's, per the spec's "Risk APPROVED AND Portfolio APPROVED"
    # chain. Only ever caps the Risk-approved quantity further, same
    # "smallest of every applicable cap" discipline as Risk Engine's own
    # sizing (packages/risk/position_sizing.py).
    candidate_notional_pct = (
        (verdict.approved_quantity * signal.entry_price / portfolio_state.equity) * 100
        if portfolio_state.equity > 0 else 0.0
    )
    allocation = evaluate_allocation(
        strategy_id=signal_row.strategy_id,
        candidate_notional_pct=candidate_notional_pct,
        portfolio_state=portfolio_state,
        limits=limits,
    )
    if not allocation.approved:
        signal_row.status = "risk_rejected"
        db.add(
            TradingEvent(
                event_type="risk_blocked", entity_type="signal", entity_id=signal_row.id,
                payload={
                    "layer": "portfolio_manager", "reason": allocation.reason,
                    "strategy_allocation_pct": allocation.strategy_allocation_pct,
                    "asset": asset.symbol, "strategy": strategy.code,
                },
            )
        )
        db.commit()
        logger.info("%s %s PORTFOLIO REJECTED reason=%s", asset.symbol, strategy.code, allocation.reason)
        return "portfolio_rejected"

    approved_quantity = verdict.approved_quantity
    if allocation.reason == "approved_capped" and candidate_notional_pct > 0:
        approved_quantity = verdict.approved_quantity * (allocation.approved_notional_pct / candidate_notional_pct)

    signal_row.status = "approved"
    db.commit()

    position = open_position(db, provider, signal=signal_row, asset=asset, quantity=approved_quantity)
    if position is None:
        logger.warning("%s %s approved but fill failed (DATA_UNAVAILABLE at execution time)", asset.symbol, strategy.code)
        return "risk_rejected"

    logger.info(
        "%s %s EXECUTED qty=%.6f entry~%.4f belt=%s",
        asset.symbol, strategy.code, approved_quantity, signal.entry_price, verdict.safety_belt_level,
    )
    return "executed"
