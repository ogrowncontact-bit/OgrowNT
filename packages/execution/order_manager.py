"""Order Manager — translates a risk-approved signal / an open position's
exit into ExecutionProvider calls, and persists the result (orders,
positions, trades) plus the resulting cash/equity change via the Portfolio
Engine. This is the only code that creates Position/Trade rows — the
Execution Engine agent (docs/blueprint/04-agents-architecture.md#agent-11).

"PROMPT 13" §40-41: open_position() now honestly handles a
'partially_filled' OrderResult (PaperBrokerAdapter, packages/execution/
broker/paper.py — the original PaperExecutionProvider never returns this
status, so every pre-existing caller/test is unaffected) by opening the
Position at the quantity that ACTUALLY filled (result.detail["filled_qty"],
falling back to the originally requested quantity when a provider doesn't
supply it) rather than either rejecting the whole order or silently
pretending the full size filled. close_position()/reduce_position()
deliberately do NOT get the same treatment — a closing/reducing order is
essentially always much smaller than the position's own original opening
order, so it practically never trips PaperBrokerAdapter's volume-based
partial-fill threshold, and building full partial-close semantics (a
position simultaneously mid-close and still partially open) is a
meaningfully bigger change than this phase's scope calls for; a partial
fill on close/reduce is treated the same conservative way a full rejection
already was (nothing changes, Trade Monitor retries next cycle). See
docs/broker-execution-infrastructure.md.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.execution.adapters.base import ExecutionProvider, OrderRequest, Side
from packages.portfolio.state import get_latest_cash, refresh_snapshot
from packages.shared.models import Asset, Execution, Order, Position, Signal, SystemState, Trade, TradingEvent


def _current_belt_level(db: Session) -> str:
    """The scan_monitor cadence (apps/worker/main.py) updates system_state
    every cycle before the strategy cadence that can lead to a fill, so this
    is always the real current level — never the refresh_snapshot() default."""
    state = db.get(SystemState, True)
    return state.safety_belt_level if state is not None else "normal"


def _idempotency_key(db: Session, *, purpose: str, position_id: int | None, signal_id: int | None) -> str:
    """"PROMPT 8" §67-68 duplicate-order protection. Keyed by how many
    Order rows already exist for this position (open + every prior close
    attempt share `position_id` — order.position_id is set on the opening
    order too, right after the Position is created below) so a genuine
    next-cycle retry after a DATA_UNAVAILABLE rejection gets a fresh key
    (the failed attempt's Order row already counts), while two callers
    racing on the SAME attempt compute the SAME key and the second INSERT
    hits the unique constraint instead of placing a second real order.
    Opening has no prior attempts to count — a signal is used at most once
    (apps/worker/strategy_runner.py mints a brand new Signal every cycle,
    never re-submits an old one), so attempt 0 is always correct there.
    """
    if position_id is not None:
        attempt = db.query(Order).filter(Order.position_id == position_id).count()
        return f"{purpose}:{position_id}:{attempt}"
    return f"{purpose}:{signal_id}:0"


def open_position(db: Session, provider: ExecutionProvider, *, signal: Signal, asset: Asset, quantity: float) -> Position | None:
    idempotency_key = _idempotency_key(db, purpose="open", position_id=None, signal_id=signal.id)
    decision_time = time.monotonic()
    side: Side = "buy" if signal.direction == "long" else "sell"
    result = provider.submit_order(
        OrderRequest(asset_id=asset.id, symbol=asset.symbol, side=side, order_type="market", qty=quantity)
    )
    latency_ms = (time.monotonic() - decision_time) * 1000

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
        idempotency_key=idempotency_key,
        expected_price=signal.entry_price,
        latency_ms=round(latency_ms, 3),
    )
    db.add(order)
    db.flush()
    db.add(TradingEvent(event_type="order_submitted", entity_type="order", entity_id=order.id, payload={"side": side, "qty": quantity, "purpose": "open"}))

    if result.status not in ("filled", "partially_filled") or result.filled_price is None:
        db.add(
            TradingEvent(
                event_type="order_rejected", entity_type="order", entity_id=order.id,
                payload={"status": result.status, "detail": result.detail},
            )
        )
        db.commit()
        return None

    # "PROMPT 13" §40-41 — never assume the requested quantity is what
    # actually filled. min()-clamped defensively: a provider's own
    # filled_qty can never legitimately exceed what was requested.
    filled_qty = min(result.detail.get("filled_qty", quantity), quantity)

    position = Position(
        asset_id=asset.id,
        strategy_id=signal.strategy_id,
        signal_id=signal.id,
        direction=signal.direction,
        entry_price=result.filled_price,
        current_stop=signal.stop_price,
        target_price=signal.target_price,
        size=filled_qty,
        opened_at=result.filled_at,
        status="open",
    )
    db.add(position)
    db.flush()
    order.position_id = position.id
    signal.status = "executed"
    db.add(
        Execution(
            order_id=order.id, broker_order_id=order.broker_order_id, symbol=asset.symbol, side=side,
            quantity=filled_qty, price=result.filled_price, fee=result.fees or 0.0, fee_currency="USD",
            slippage_bps=result.slippage_bps, ts=result.filled_at or datetime.now(timezone.utc),
            liquidity="taker", execution_mode=getattr(provider, "kind", "paper"),
        )
    )
    fill_event_type = "order_filled" if result.status == "filled" else "order_partially_filled"
    db.add(
        TradingEvent(
            event_type=fill_event_type, entity_type="order", entity_id=order.id,
            payload={"filled_price": result.filled_price, "filled_qty": filled_qty, "requested_qty": quantity},
        )
    )
    db.add(
        TradingEvent(
            event_type="position_opened", entity_type="position", entity_id=position.id,
            payload={"asset": asset.symbol, "direction": position.direction, "entry_price": position.entry_price, "size": filled_qty},
        )
    )
    db.commit()

    notional = result.filled_price * filled_qty
    new_cash = get_latest_cash(db) - notional - (result.fees or 0.0)
    refresh_snapshot(db, cash=new_cash, safety_belt_level=_current_belt_level(db))

    return position


def close_position(
    db: Session, provider: ExecutionProvider, position: Position, *, asset: Asset, exit_reason: str, expected_price: float | None = None,
) -> Trade | None:
    idempotency_key = _idempotency_key(db, purpose="close", position_id=position.id, signal_id=None)
    decision_time = time.monotonic()
    side: Side = "sell" if position.direction == "long" else "buy"
    result = provider.submit_order(
        OrderRequest(asset_id=asset.id, symbol=asset.symbol, side=side, order_type="market", qty=position.size)
    )
    latency_ms = (time.monotonic() - decision_time) * 1000

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
        idempotency_key=idempotency_key,
        expected_price=expected_price if expected_price is not None else position.current_stop,
        latency_ms=round(latency_ms, 3),
    )
    db.add(order)
    db.flush()
    db.add(TradingEvent(event_type="order_submitted", entity_type="order", entity_id=order.id, payload={"side": side, "qty": position.size, "purpose": "close", "exit_reason": exit_reason}))

    if result.status != "filled" or result.filled_price is None:
        db.add(
            TradingEvent(
                event_type="order_rejected", entity_type="order", entity_id=order.id,
                payload={"status": result.status, "detail": result.detail},
            )
        )
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
    db.add(
        Execution(
            order_id=order.id, broker_order_id=order.broker_order_id, symbol=asset.symbol, side=side,
            quantity=order.qty, price=result.filled_price, fee=result.fees or 0.0, fee_currency="USD",
            slippage_bps=result.slippage_bps, ts=result.filled_at or datetime.now(timezone.utc),
            liquidity="taker", execution_mode=getattr(provider, "kind", "paper"),
        )
    )
    db.add(TradingEvent(event_type="order_filled", entity_type="order", entity_id=order.id, payload={"filled_price": result.filled_price}))
    db.add(
        TradingEvent(
            event_type="position_closed", entity_type="position", entity_id=position.id,
            payload={"asset": asset.symbol, "exit_reason": exit_reason, "pnl": trade.pnl, "outcome": outcome},
        )
    )
    db.commit()

    notional_returned = position.entry_price * position.size
    new_cash = get_latest_cash(db) + notional_returned + pnl
    refresh_snapshot(db, cash=new_cash, safety_belt_level=_current_belt_level(db))

    return trade


def reduce_position(
    db: Session, provider: ExecutionProvider, position: Position, *, asset: Asset, fraction: float, reason: str,
) -> Trade | None:
    """"PROMPT 8" §28-30's REDUCE action — partially closes `fraction` of
    the position, realizing P&L on that slice while the remainder stays
    open at its existing stop/target, completely untouched. Distinct from
    close_position(): the Position row's status stays 'open' and its size
    shrinks rather than zeroing out. A fraction that would leave nothing
    open (>=1.0) or nothing to reduce (<=0) falls back to a full close —
    "reduce everything" and "reduce nothing" both mean something else.
    """
    if fraction <= 0:
        return None
    if fraction >= 1.0:
        return close_position(db, provider, position, asset=asset, exit_reason=reason)

    reduce_qty = round(position.size * fraction, 8)
    if reduce_qty <= 0:
        return None

    idempotency_key = _idempotency_key(db, purpose="reduce", position_id=position.id, signal_id=None)
    decision_time = time.monotonic()
    side: Side = "sell" if position.direction == "long" else "buy"
    result = provider.submit_order(
        OrderRequest(asset_id=asset.id, symbol=asset.symbol, side=side, order_type="market", qty=reduce_qty)
    )
    latency_ms = (time.monotonic() - decision_time) * 1000

    order = Order(
        position_id=position.id,
        broker_order_id=result.broker_order_id,
        order_type="market",
        side=side,
        qty=reduce_qty,
        status=result.status,
        submitted_at=datetime.now(timezone.utc),
        filled_at=result.filled_at,
        filled_price=result.filled_price,
        fees=result.fees,
        slippage_bps=result.slippage_bps,
        is_paper=provider.is_paper,
        idempotency_key=idempotency_key,
        expected_price=position.current_stop,
        latency_ms=round(latency_ms, 3),
    )
    db.add(order)
    db.flush()
    db.add(TradingEvent(event_type="order_submitted", entity_type="order", entity_id=order.id, payload={"side": side, "qty": reduce_qty, "purpose": "reduce", "reason": reason}))

    if result.status != "filled" or result.filled_price is None:
        db.add(
            TradingEvent(
                event_type="order_rejected", entity_type="order", entity_id=order.id,
                payload={"status": result.status, "detail": result.detail},
            )
        )
        db.commit()
        return None  # DATA_UNAVAILABLE — position stays fully open, retried next cycle

    direction_mult = 1 if position.direction == "long" else -1
    pnl = (result.filled_price - position.entry_price) * reduce_qty * direction_mult - (result.fees or 0.0)

    position.size = round(position.size - reduce_qty, 8)
    db.flush()

    outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
    trade = Trade(
        position_id=position.id,
        opened_order_id=None,
        closed_order_id=order.id,
        pnl=round(pnl, 2),
        r_multiple=None,  # a partial slice's R-multiple isn't the position's own — leave it honestly unset
        outcome=outcome,
        is_paper=provider.is_paper,
        closed_at=result.filled_at,
    )
    db.add(trade)
    db.add(
        Execution(
            order_id=order.id, broker_order_id=order.broker_order_id, symbol=asset.symbol, side=side,
            quantity=reduce_qty, price=result.filled_price, fee=result.fees or 0.0, fee_currency="USD",
            slippage_bps=result.slippage_bps, ts=result.filled_at or datetime.now(timezone.utc),
            liquidity="taker", execution_mode=getattr(provider, "kind", "paper"),
        )
    )
    db.add(TradingEvent(event_type="order_filled", entity_type="order", entity_id=order.id, payload={"filled_price": result.filled_price}))
    db.add(
        TradingEvent(
            event_type="portfolio_emergency_action", entity_type="position", entity_id=position.id,
            payload={"action": "reduce", "asset": asset.symbol, "reason": reason, "reduced_qty": reduce_qty, "remaining_size": position.size, "pnl": trade.pnl},
        )
    )
    db.commit()

    notional_returned = position.entry_price * reduce_qty
    new_cash = get_latest_cash(db) + notional_returned + pnl
    refresh_snapshot(db, cash=new_cash, safety_belt_level=_current_belt_level(db))

    return trade
