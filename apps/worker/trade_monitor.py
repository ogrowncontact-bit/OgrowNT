"""Trade Monitor — docs/blueprint/04-agents-architecture.md#agent-12.

For every open position: has the stop or target been hit at the latest
known price? If not, does the entry thesis still hold — has the asset's
regime moved into this strategy's declared worst_regimes since entry? If
either is true, the Execution Engine closes the position. The system does
not stay married to "I was right when I entered."

Every close also drives the Phase 5 Learning Agent (docs/blueprint/04-
agents-architecture.md#agent-13), "a cada trade fechado": Pattern Memory,
Strategy Memory (rolling performance + health score), Strategy Quarantine,
and the Failure Memory journal entry (with an LLM hypothesis when the
result diverged from the win the strategy expected).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.execution.adapters.base import ExecutionProvider
from packages.execution.order_manager import close_position
from packages.llm.client import LLMClient
from packages.llm.learning import generate_trade_hypothesis
from packages.quant.learning.degradation import check_degradation
from packages.quant.learning.quarantine import evaluate_quarantine
from packages.quant.learning.strategy_stats import compute_strategy_performance
from packages.quant.patterns.performance import record_trade_outcome
from packages.quant.strategies import ALL_STRATEGIES
from packages.shared.market_data import get_latest_close
from packages.shared.models import Asset, MarketMemory, MarketRegime, OpportunityScore, Pattern, Position, Signal, StrategyRow, Trade, TradeJournal

logger = logging.getLogger("worker.trade_monitor")

TIMEFRAME = "1m"
_STRATEGY_BY_CODE = {s.code: s for s in ALL_STRATEGIES}


def _check_stop_or_target(position: Position, price: float) -> str | None:
    if position.direction == "long":
        if price <= position.current_stop:
            return "stop_hit"
        if position.target_price is not None and price >= position.target_price:
            return "target_hit"
    else:
        if price >= position.current_stop:
            return "stop_hit"
        if position.target_price is not None and price <= position.target_price:
            return "target_hit"
    return None


def _check_thesis_validity(db: Session, position: Position) -> str | None:
    strategy_row = db.get(StrategyRow, position.strategy_id)
    strategy = _STRATEGY_BY_CODE.get(strategy_row.code) if strategy_row else None
    if strategy is None:
        return None

    latest_regime = (
        db.query(MarketRegime)
        .filter(MarketRegime.asset_id == position.asset_id)
        .order_by(MarketRegime.ts.desc())
        .first()
    )
    if latest_regime is None:
        return None
    if latest_regime.regime in strategy.worst_regimes:
        return "thesis_invalidated"
    return None


def _record_pattern_performance(db: Session, position: Position, trade: Trade) -> None:
    """Pattern Memory writeback — docs/blueprint/06-memory-system.md. Only
    fires when the position's originating signal was actually linked to a
    detected pattern (apps/worker/strategy_runner.py sets pattern_id only
    when one aligned with the signal's direction)."""
    if position.signal_id is None:
        return
    signal = db.get(Signal, position.signal_id)
    if signal is None or signal.pattern_id is None or signal.regime_id is None:
        return
    pattern = db.get(Pattern, signal.pattern_id)
    regime = db.get(MarketRegime, signal.regime_id)
    if pattern is None or regime is None:
        return

    record_trade_outcome(
        db, pattern_type=pattern.pattern_type, regime=regime.regime,
        r_multiple=trade.r_multiple, is_win=(trade.outcome == "win"),
    )


def _entry_context(db: Session, position: Position) -> dict:
    """Best-effort reconstruction of what the strategy knew at entry — the
    same signal/regime/pattern rows Strategy Engine wrote in
    apps/worker/strategy_runner.py. News direction is read back from that
    signal's OpportunityScore.notes (Phase 4 scores the news alignment but
    doesn't persist a separate news_impact_id FK on signals — this is the
    one place that read survives to trade close)."""
    context = {"regime": None, "pattern_type": None, "news_direction": None}
    if position.signal_id is None:
        return context
    signal = db.get(Signal, position.signal_id)
    if signal is None:
        return context

    if signal.regime_id:
        regime = db.get(MarketRegime, signal.regime_id)
        context["regime"] = regime.regime if regime else None
    if signal.pattern_id:
        pattern = db.get(Pattern, signal.pattern_id)
        context["pattern_type"] = pattern.pattern_type if pattern else None

    score = db.query(OpportunityScore).filter(OpportunityScore.signal_id == signal.id).first()
    if score is not None and isinstance(score.notes, dict):
        news_note = score.notes.get("news")
        if isinstance(news_note, dict) and news_note.get("aligned") is not None:
            context["news_direction"] = "aligned" if news_note["aligned"] else "conflicting"

    return context


def _record_trade_journal(db: Session, position: Position, trade: Trade, llm_client: LLMClient) -> None:
    """Failure/Trade Journal Memory — docs/blueprint/06-memory-system.md.
    Every closed trade gets a journal row; a trade whose actual outcome
    wasn't the win the strategy expected additionally gets an LLM-generated
    hypothesis (null, never fabricated, when no LLM is configured)."""
    expected_outcome = "win"
    diverged = trade.outcome != expected_outcome

    hypothesis = None
    root_cause = None
    if diverged:
        context = _entry_context(db, position)
        asset = position.asset or db.get(Asset, position.asset_id)
        strategy = position.strategy or db.get(StrategyRow, position.strategy_id)
        result = generate_trade_hypothesis(
            llm_client,
            strategy_code=strategy.code if strategy else "unknown",
            asset_symbol=asset.symbol if asset else "unknown",
            direction=position.direction,
            regime=context["regime"],
            pattern_type=context["pattern_type"],
            news_direction=context["news_direction"],
            outcome=trade.outcome,
            pnl=trade.pnl,
            r_multiple=trade.r_multiple,
            exit_reason=position.exit_reason,
        )
        if result is not None:
            hypothesis, root_cause = result.hypothesis, result.root_cause

    db.add(
        TradeJournal(
            trade_id=trade.id, expected_outcome=expected_outcome, actual_outcome=trade.outcome,
            hypothesis=hypothesis, root_cause=root_cause,
        )
    )
    db.commit()


def _record_market_memory_outcome(db: Session, position: Position, trade: Trade) -> None:
    """Market Memory outcome backfill — docs/blueprint/06-memory-system.md.
    apps/worker/strategy_runner.py writes the context row when the signal
    is created; this is the only field filled in later, once the position
    it led to (if any) actually closes."""
    if position.signal_id is None:
        return
    memory = db.query(MarketMemory).filter(MarketMemory.signal_id == position.signal_id).first()
    if memory is None:
        return
    memory.outcome = trade.outcome
    db.add(memory)
    db.commit()


def _record_strategy_learning(db: Session, position: Position) -> None:
    """Strategy Memory + Quarantine + degradation check —
    docs/blueprint/04-agents-architecture.md#agent-13. Recomputed from the
    fresh trade history, not incrementally, then checked against the
    quarantine threshold (Phase 5) and the softer degradation-vs-backtest
    warning (Phase 6, docs/blueprint/10-backtesting-paper-trading.md)."""
    perf = compute_strategy_performance(db, position.strategy_id)
    if evaluate_quarantine(db, position.strategy_id, perf):
        strategy = db.get(StrategyRow, position.strategy_id)
        logger.warning("Strategy %s quarantined: health_score=%s", strategy.code if strategy else position.strategy_id, perf.health_score)
    elif check_degradation(db, position.strategy_id):
        strategy = db.get(StrategyRow, position.strategy_id)
        logger.warning("Strategy %s flagged for performance degradation vs. its reference backtest", strategy.code if strategy else position.strategy_id)


def run_trade_monitor_cycle(db: Session, provider: ExecutionProvider, llm_client: LLMClient | None = None) -> dict:
    llm_client = llm_client or LLMClient()
    open_positions = db.query(Position).filter(Position.status == "open").all()
    checked, closed, unavailable = 0, 0, 0

    for position in open_positions:
        checked += 1
        price = get_latest_close(db, position.asset_id, TIMEFRAME)
        if price is None:
            unavailable += 1
            logger.warning("DATA_UNAVAILABLE monitoring position %s", position.id)
            continue

        exit_reason = _check_stop_or_target(position, price) or _check_thesis_validity(db, position)
        if exit_reason is None:
            continue

        asset = db.get(Asset, position.asset_id)
        trade = close_position(db, provider, position, asset=asset, exit_reason=exit_reason)
        if trade is not None:
            closed += 1
            _record_pattern_performance(db, position, trade)
            _record_market_memory_outcome(db, position, trade)
            _record_strategy_learning(db, position)
            _record_trade_journal(db, position, trade, llm_client)
            logger.info(
                "Closed position %s (%s) reason=%s pnl=%.2f outcome=%s",
                position.id, asset.symbol, exit_reason, trade.pnl, trade.outcome,
            )

    summary = {"checked": checked, "closed": closed, "unavailable": unavailable}
    logger.info("Trade monitor cycle complete: %s", summary)
    return summary
