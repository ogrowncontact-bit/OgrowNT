"""Trade Monitor — docs/blueprint/04-agents-architecture.md#agent-12.

For every open position: has the stop or target been hit at the latest
known price? If not, does the entry thesis still hold — has the asset's
regime moved into this strategy's declared worst_regimes since entry? If
either is true, the Execution Engine closes the position. The system does
not stay married to "I was right when I entered."
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.execution.adapters.base import ExecutionProvider
from packages.execution.order_manager import close_position
from packages.quant.patterns.performance import record_trade_outcome
from packages.quant.strategies import ALL_STRATEGIES
from packages.shared.market_data import get_latest_close
from packages.shared.models import Asset, MarketRegime, Pattern, Position, Signal, StrategyRow, Trade

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


def run_trade_monitor_cycle(db: Session, provider: ExecutionProvider) -> dict:
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
            logger.info(
                "Closed position %s (%s) reason=%s pnl=%.2f outcome=%s",
                position.id, asset.symbol, exit_reason, trade.pnl, trade.outcome,
            )

    summary = {"checked": checked, "closed": closed, "unavailable": unavailable}
    logger.info("Trade monitor cycle complete: %s", summary)
    return summary
