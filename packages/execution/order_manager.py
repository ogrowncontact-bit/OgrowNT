"""Order Manager — translates a risk-approved signal / an open position's
exit into ExecutionProvider calls, and persists the result (orders,
positions, trades) plus the resulting cash/equity change via the Portfolio
Engine. This is the only code that creates Position/Trade rows — the
Execution Engine agent (docs/blueprint/04-agents-architecture.md#agent-11).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.execution.adapters.base import ExecutionProvider, OrderRequest, Side
from packages.portfolio.state import get_latest_cash, refresh_snapshot
from packages.shared.models import Asset, Order, Position, Signal, SystemState, Trade


def _current_belt_level(db: Session) -> str:
    """The scan_monitor cadence (apps/worker/main.py) updates system_state
    every cycle before the strategy cadence that can lead to a fill, so this
    is always the real current level — never the refresh_snapshot() default."""
    state = db.get(SystemState, True)
    return state.safety_belt_level if state is not None else "normal"


def open_position(db: Session, provider: ExecutionProvider, *, signal: Signal, asset: Asset, quantity: float) -> Position | None:
    side: Side = "buy" if signal.direction == "long" else "sell"
    result = provider.submit_order(
        OrderRequest(asset_id=asset.id, symbol=asset.symbol, side=side, order_type="market", qty=quantity)
    )

    order = Order(
        signal_id=signal.id,
        broker_order_id=result.broker_order_id,
        order_type="market",
        side=side,
        qty=quantity,
        status=result.status,
        submitted_at=datetime.now(timezone.utc),
        filled_at=result.filled_at,
        filled_price=result.filled_price,
        fees=result.fees,
        slippage_bps=result.slippage_bps,
        is_paper=provider.is_paper,
    )
    db.add(order)
    db.flush()

    if result.status != "filled" or result.filled_price is None:
        db.commit()
        return None

    position = Position(
        asset_id=asset.id,
        strategy_id=signal.strategy_id,
        signal_id=signal.id,
        direction=signal.direction,
        entry_price=result.filled_price,
        current_stop=signal.stop_price,
        target_price=signal.target_price,
        size=quantity,
        opened_at=result.filled_at,
        status="open",
    )
    db.add(position)
    db.flush()
    order.position_id = position.id
    signal.status = "executed"
    db.commit()

    notional = result.filled_price * quantity
    new_cash = get_latest_cash(db) - notional - (result.fees or 0.0)
    refresh_snapshot(db, cash=new_cash, safety_belt_level=_current_belt_level(db))

    return position


def close_position(db: Session, provider: ExecutionProvider, position: Position, *, asset: Asset, exit_reason: str) -> Trade | None:
    side: Side = "sell" if position.direction == "long" else "buy"
    result = provider.submit_order(
        OrderRequest(asset_id=asset.id, symbol=asset.symbol, side=side, order_type="market", qty=position.size)
    )

    order = Order(
        position_id=position.id,
        broker_order_id=result.broker_order_id,
        order_type="market",
        side=side,
        qty=position.size,
        status=result.status,
        submitted_at=datetime.now(timezone.utc),
        filled_at=result.filled_at,
        filled_price=result.filled_price,
        fees=result.fees,
        slippage_bps=result.slippage_bps,
        is_paper=provider.is_paper,
    )
    db.add(order)
    db.flush()

    if result.status != "filled" or result.filled_price is None:
        db.commit()
        return None  # DATA_UNAVAILABLE — position stays open, retried next cycle by Trade Monitor

    direction_mult = 1 if position.direction == "long" else -1
    pnl = (result.filled_price - position.entry_price) * position.size * direction_mult - (result.fees or 0.0)
    stop_distance = abs(position.entry_price - position.current_stop)
    r_multiple = (pnl / (stop_distance * position.size)) if stop_distance > 0 else None

    position.status = "closed"
    position.closed_at = result.filled_at
    position.exit_price = result.filled_price
    position.realized_pnl = round(pnl, 2)
    position.exit_reason = exit_reason
    db.flush()

    outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
    trade = Trade(
        position_id=position.id,
        opened_order_id=None,
        closed_order_id=order.id,
        pnl=round(pnl, 2),
        r_multiple=round(r_multiple, 4) if r_multiple is not None else None,
        outcome=outcome,
        is_paper=provider.is_paper,
        closed_at=result.filled_at,
    )
    db.add(trade)
    db.commit()

    notional_returned = position.entry_price * position.size
    new_cash = get_latest_cash(db) + notional_returned + pnl
    refresh_snapshot(db, cash=new_cash, safety_belt_level=_current_belt_level(db))

    return trade
