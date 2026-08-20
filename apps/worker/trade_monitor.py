"""Trade Monitor — docs/blueprint/04-agents-architecture.md#agent-12.

For every open position: has the stop or target been hit at the latest
known price? Those are unconditional — a strategy's own declared risk
boundary, always honored the instant it's crossed. Everything else that
could end a position early (a regime shift into the strategy's declared
worst_regimes, critical news breaking, a portfolio emergency) is NOT
decided here: it's routed through packages/risk/position_policy.py's
configurable HOLD/REDUCE/CLOSE ("PROMPT 8" §28-30) so the Risk Engine
stays the sole authority over closing a position early, never whichever
module first noticed the trigger (§29: "Nunca permitir que News Engine
feche diretamente").

Every full close also drives the Phase 5 Learning Agent (docs/blueprint/04-
agents-architecture.md#agent-13), "a cada trade fechado": Pattern Memory,
Strategy Memory (rolling performance + health score), Strategy Quarantine,
and the Failure Memory journal entry (with an LLM hypothesis when the
result diverged from the win the strategy expected). A REDUCE only
realizes P&L on part of the position — it isn't a strategy-driven exit, so
it deliberately skips those learning side effects (see reduce_position()'s
own docstring in packages/execution/order_manager.py).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.execution.adapters.base import ExecutionProvider
from packages.execution.order_manager import close_position, reduce_position
from packages.llm.client import LLMClient
from packages.llm.learning import generate_trade_hypothesis
from packages.quant.exits.trailing_stop import compute_trailing_stop
from packages.quant.learning.degradation import check_degradation
from packages.quant.learning.quarantine import evaluate_quarantine
from packages.quant.learning.strategy_stats import compute_strategy_performance
from packages.quant.patterns.performance import record_trade_outcome
from packages.quant.strategies import ALL_STRATEGIES
from packages.risk.config import load_risk_limits
from packages.risk.news_guard import evaluate_news_risk
from packages.risk.position_policy import PositionRiskDecision, evaluate_position_risk_event
from packages.shared.market_data import get_latest_close, get_recent_candles
from packages.shared.models import Asset, MarketMemory, MarketRegime, OpportunityScore, Pattern, Position, Signal, StrategyRow, SystemState, Trade, TradeJournal, TradingEvent

logger = logging.getLogger("worker.trade_monitor")

TIMEFRAME = "1m"
ATR_HISTORY_LIMIT = 20  # >= atr()'s 14-period requirement, matching apps/worker/strategy_runner.py's own margin
_STRATEGY_BY_CODE = {s.code: s for s in ALL_STRATEGIES}

# Which position.exit_reason a CLOSE action maps to for the regime_change/
# news_risk triggers — kept inside Position.exit_reason's own closed
# vocabulary (packages/shared/models.py's ck_positions_exit_reason) rather
# than growing it further for this one purpose. portfolio_emergency is
# handled separately by _check_portfolio_emergency() above, since it needs
# to distinguish kill_switch_close from portfolio_emergency_close.
_CLOSE_EXIT_REASON_BY_TRIGGER = {
    "regime_change": "regime_change_exit",
    "news_risk": "portfolio_emergency_close",
}


def _update_trailing_stop(db: Session, position: Position, price: float) -> None:
    """"PROMPT 8" §27-29 — mutates position.current_stop/favorable_extreme_price
    in place when the position has a trailing_stop_config; a no-op
    otherwise (the Phase 3 static-stop behavior). Never widens a stop —
    packages/quant/exits/trailing_stop.py's own invariant."""
    if position.trailing_stop_config is None:
        return

    recent_candles = None
    if position.trailing_stop_config.get("type") == "atr_based":
        recent_candles = get_recent_candles(db, position.asset_id, TIMEFRAME, ATR_HISTORY_LIMIT)

    update = compute_trailing_stop(
        direction=position.direction,
        current_price=price,
        current_stop=position.current_stop,
        favorable_extreme_price=position.favorable_extreme_price,
        config=position.trailing_stop_config,
        recent_candles=recent_candles,
    )
    position.favorable_extreme_price = update.favorable_extreme_price
    if update.moved:
        position.current_stop = update.new_stop


def _check_stop_or_target(position: Position, price: float) -> str | None:
    stop_reason = "trailing_stop_hit" if position.trailing_stop_config is not None else "stop_hit"
    if position.direction == "long":
        if price <= position.current_stop:
            return stop_reason
        if position.target_price is not None and price >= position.target_price:
            return "target_hit"
    else:
        if price >= position.current_stop:
            return stop_reason
        if position.target_price is not None and price <= position.target_price:
            return "target_hit"
    return None


def _check_regime_shift(db: Session, position: Position) -> str | None:
    """Has the asset's regime moved into this strategy's declared
    worst_regimes since entry? Returns a detail string for
    position_policy.evaluate_position_risk_event() to act on — never
    decides HOLD/REDUCE/CLOSE itself (§28)."""
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
        return f"regime_shifted_to:{latest_regime.regime}"
    return None


def _check_portfolio_emergency(system_state: SystemState | None) -> tuple[str, str] | None:
    """Returns (detail, kill_switch_close|portfolio_emergency_close) when
    the Kill Switch is active or the safety belt is at EMERGENCY — the two
    read differently in the decision trace even though both route through
    the same 'portfolio_emergency' policy trigger."""
    if system_state is None:
        return None
    if not system_state.trading_enabled:
        return "kill_switch_active", "kill_switch_close"
    if system_state.safety_belt_level == "emergency":
        return "safety_belt_emergency", "portfolio_emergency_close"
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


def _entry_context(db: Session, position: Position) -> dict[str, str | None]:
    """Best-effort reconstruction of what the strategy knew at entry — the
    same signal/regime/pattern rows Strategy Engine wrote in
    apps/worker/strategy_runner.py. News direction is read back from that
    signal's OpportunityScore.notes (Phase 4 scores the news alignment but
    doesn't persist a separate news_impact_id FK on signals — this is the
    one place that read survives to trade close)."""
    context: dict[str, str | None] = {"regime": None, "pattern_type": None, "news_direction": None}
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


def _position_risk_decision(db: Session, position: Position, *, limits, system_state: SystemState | None, news_level: str) -> tuple[PositionRiskDecision, str] | None:
    """Checks the three §28-30 triggers in severity order (a live Kill
    Switch/EMERGENCY belt outranks a mere regime shift, which outranks
    nothing else being wrong) and returns the first applicable one's policy
    decision, paired with the exit_reason a CLOSE would use. None if no
    trigger fired this cycle."""
    emergency = _check_portfolio_emergency(system_state)
    if emergency is not None:
        detail, close_reason = emergency
        return evaluate_position_risk_event("portfolio_emergency", limits=limits, detail=detail), close_reason

    if news_level == "critical":
        decision = evaluate_position_risk_event("news_risk", limits=limits, detail=f"news_risk_level={news_level}")
        return decision, _CLOSE_EXIT_REASON_BY_TRIGGER["news_risk"]

    regime_detail = _check_regime_shift(db, position)
    if regime_detail is not None:
        decision = evaluate_position_risk_event("regime_change", limits=limits, detail=regime_detail)
        return decision, _CLOSE_EXIT_REASON_BY_TRIGGER["regime_change"]

    return None


def run_trade_monitor_cycle(db: Session, provider: ExecutionProvider, llm_client: LLMClient | None = None) -> dict:
    llm_client = llm_client or LLMClient()
    limits = load_risk_limits()
    system_state = db.get(SystemState, True)
    news_level = evaluate_news_risk(db, limits).level  # global, computed once per cycle — packages/risk/news_guard.py

    open_positions = db.query(Position).filter(Position.status == "open").all()
    checked, closed, unavailable = 0, 0, 0

    for position in open_positions:
        checked += 1
        price = get_latest_close(db, position.asset_id, TIMEFRAME)
        if price is None:
            unavailable += 1
            logger.warning("DATA_UNAVAILABLE monitoring position %s", position.id)
            continue

        _update_trailing_stop(db, position, price)
        exit_reason = _check_stop_or_target(position, price)  # unconditional -- the strategy's own declared risk boundary

        risk_event = None if exit_reason is not None else _position_risk_decision(
            db, position, limits=limits, system_state=system_state, news_level=news_level
        )

        if exit_reason is None and risk_event is None:
            db.commit()  # persist the trailing stop's ratchet even when nothing closed this cycle
            continue

        asset = db.get(Asset, position.asset_id)
        if asset is None:
            unavailable += 1
            logger.warning("DATA_UNAVAILABLE closing position %s: asset %s not found", position.id, position.asset_id)
            continue

        if risk_event is not None:
            decision, close_reason = risk_event
            if decision.action == "hold":
                db.add(
                    TradingEvent(
                        event_type="portfolio_emergency_action", entity_type="position", entity_id=position.id,
                        payload={"action": "hold", "trigger": decision.trigger, "reason": decision.reason},
                    )
                )
                db.commit()
                continue
            if decision.action == "reduce":
                trade = reduce_position(
                    db, provider, position, asset=asset, fraction=limits.position_risk_policy.reduce_fraction, reason=decision.reason,
                )
                if trade is None:
                    unavailable += 1
                    logger.warning("DATA_UNAVAILABLE reducing position %s (%s)", position.id, decision.trigger)
                else:
                    logger.info(
                        "Reduced position %s (%s) trigger=%s remaining_size=%s", position.id, asset.symbol, decision.trigger, position.size,
                    )
                continue
            exit_reason = close_reason  # action == "close"

        assert exit_reason is not None  # every path that reaches here set it: stop/target hit, or a "close" decision above
        trade = close_position(db, provider, position, asset=asset, exit_reason=exit_reason, expected_price=price)
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
