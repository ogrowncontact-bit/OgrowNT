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
from packages.quant.strategies import ALL_STRATEGIES
from packages.shared.market_data import get_latest_close
from packages.shared.models import Asset, MarketRegime, Position, StrategyRow

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
            logger.info(
                "Closed position %s (%s) reason=%s pnl=%.2f outcome=%s",
                position.id, asset.symbol, exit_reason, trade.pnl, trade.outcome,
            )

    summary = {"checked": checked, "closed": closed, "unavailable": unavailable}
    logger.info("Trade monitor cycle complete: %s", summary)
    return summary
