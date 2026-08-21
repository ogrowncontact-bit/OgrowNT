"""Broker-level Reconciliation Engine — "PROMPT 13" §33-38, §78.

Layered ON TOP OF, not a replacement for, the existing cash-only
PaperReconciliationEngine (packages/portfolio/reconciliation.py, "PROMPT 8"
§69-71, completely unchanged): that one reconstructs cash from first
principles every RECONCILIATION_INTERVAL_SECONDS tick and already pauses
trading on a mismatch. This module additionally compares what a
BrokerAdapter REPORTS (get_account/get_positions/get_open_orders) against
this system's own internal ledger — the comparison §33-38 actually asks for.

Honesty note: PaperBrokerAdapter's get_account()/get_positions()/
get_open_orders() are themselves derived from the SAME `positions`/`orders`
tables this module compares them against (packages/execution/broker/
paper.py has no separate ledger) — so in this deployment, this check will
by construction never find a real divergence. That is not a limitation
worth hiding: it's the same honest "architecture-ready, proven via
synthetic injection since only one real implementation exists" situation as
packages/data/connectors/market/failover.py ("PROMPT 12") — tests exercise
the mismatch-detection path with a stub adapter that deliberately reports
different numbers, not by hoping PaperBrokerAdapter someday disagrees with
itself.

On mismatch: reuses SystemState.trading_paused (an accounting-integrity
stop), NEVER the Kill Switch — the exact same, deliberate distinction
packages/portfolio/reconciliation.py already documents for its own cash
check (§35 "BLOCK_NEW_TRADES", not "halt everything").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.execution.broker.base import BrokerAdapter
from packages.portfolio.state import compute_state
from packages.shared.models import (
    AccountSnapshot,
    Alert,
    Asset,
    BrokerPositionSnapshot,
    Order,
    Position,
    ReconciliationRun,
    SystemState,
    TradingEvent,
)

BALANCE_TOLERANCE = 0.05
QUANTITY_TOLERANCE = 1e-6
PRICE_TOLERANCE_PCT = 1.0


@dataclass(frozen=True)
class BrokerReconciliationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    position_mismatches: list[str] = field(default_factory=list)
    order_mismatches: list[str] = field(default_factory=list)
    balance_diff: float | None = None


def run_broker_reconciliation(db: Session, broker: BrokerAdapter) -> BrokerReconciliationResult:
    """Pure check — never mutates anything. See
    run_broker_reconciliation_and_enforce() for the persisting/enforcing
    version."""
    account = broker.get_account()
    internal_state = compute_state(db)
    balance_diff = round(account.equity - internal_state.equity, 4)

    violations: list[str] = []
    if abs(balance_diff) > BALANCE_TOLERANCE:
        violations.append(
            f"balance_mismatch: broker_equity={account.equity:.2f} internal_equity={internal_state.equity:.2f} diff={balance_diff:.4f}"
        )

    broker_positions = {p.symbol: p for p in broker.get_positions()}
    internal_positions = db.query(Position).filter(Position.status == "open").all()
    internal_by_symbol: dict[str, Position] = {}
    for position in internal_positions:
        asset = db.get(Asset, position.asset_id)
        if asset is not None:
            internal_by_symbol[asset.symbol] = position

    position_mismatches: list[str] = []
    for symbol, internal in internal_by_symbol.items():
        broker_position = broker_positions.pop(symbol, None)
        if broker_position is None:
            position_mismatches.append(f"missing_at_broker: {symbol}")
            continue
        if abs(broker_position.quantity - internal.size) > QUANTITY_TOLERANCE:
            position_mismatches.append(f"quantity_mismatch: {symbol} broker={broker_position.quantity} internal={internal.size}")
        if internal.entry_price > 0:
            price_diff_pct = abs(broker_position.average_price - internal.entry_price) / internal.entry_price * 100
            if price_diff_pct > PRICE_TOLERANCE_PCT:
                position_mismatches.append(
                    f"avg_price_mismatch: {symbol} broker={broker_position.average_price} internal={internal.entry_price}"
                )
    for symbol in broker_positions:
        position_mismatches.append(f"unexpected_at_broker: {symbol}")

    broker_open_orders = {o.broker_order_id for o in broker.get_open_orders() if o.broker_order_id}
    internal_open_orders = db.query(Order).filter(Order.status.in_(("new", "submitted", "cancel_pending"))).all()
    internal_broker_ids = {o.broker_order_id for o in internal_open_orders if o.broker_order_id}

    order_mismatches: list[str] = []
    for order in internal_open_orders:
        if order.broker_order_id and order.broker_order_id not in broker_open_orders:
            order_mismatches.append(f"missing_at_broker: order_id={order.id}")
    for broker_order_id in broker_open_orders - internal_broker_ids:
        order_mismatches.append(f"unexpected_at_broker: broker_order_id={broker_order_id}")

    violations.extend(position_mismatches)
    violations.extend(order_mismatches)

    return BrokerReconciliationResult(
        ok=not violations, violations=violations, position_mismatches=position_mismatches,
        order_mismatches=order_mismatches, balance_diff=balance_diff,
    )


def run_broker_reconciliation_and_enforce(db: Session, broker: BrokerAdapter, *, broker_id: int) -> BrokerReconciliationResult:
    """Runs run_broker_reconciliation(), persists a ReconciliationRun row
    (§78's dashboard trend — every tick, not just failures) plus
    AccountSnapshot/BrokerPositionSnapshot rows (§31-32), and on any
    violation pauses trading — idempotently, same "page once, not every
    tick" discipline as packages/portfolio/reconciliation.py's own
    reconcile_and_enforce()."""
    result = run_broker_reconciliation(db, broker)
    now = datetime.now(timezone.utc)

    account = broker.get_account()
    db.add(
        AccountSnapshot(
            broker_id=broker_id, ts=now, balance=account.balance, available_balance=account.available_balance,
            equity=account.equity, margin=account.margin, margin_used=account.margin_used,
            margin_available=account.margin_available, currency=account.currency,
        )
    )
    for position in broker.get_positions():
        db.add(
            BrokerPositionSnapshot(
                broker_id=broker_id, ts=now, symbol=position.symbol, quantity=position.quantity,
                average_price=position.average_price, mark_price=position.mark_price,
                unrealized_pnl=position.unrealized_pnl, realized_pnl=position.realized_pnl,
                side=position.side, leverage=position.leverage, margin=position.margin,
            )
        )
    db.add(
        ReconciliationRun(
            broker_id=broker_id, ts=now, ok=result.ok, violations=result.violations,
            position_mismatches=result.position_mismatches, order_mismatches=result.order_mismatches,
            balance_diff=result.balance_diff,
        )
    )

    if not result.ok:
        state = db.get(SystemState, True)
        if state is None:
            state = SystemState(id=True)
            db.add(state)

        db.add(
            TradingEvent(
                event_type="reconciliation_mismatch", entity_type="broker", entity_id=broker_id,
                payload={"violations": result.violations, "balance_diff": result.balance_diff},
            )
        )
        if not state.trading_paused:
            state.trading_paused = True
            state.paused_reason = f"broker_reconciliation_mismatch: {'; '.join(result.violations)}"
            state.paused_at = now
            db.add(state)
            db.add(
                Alert(
                    severity="critical", category="system",
                    message=f"Broker reconciliation failed — trading paused: {'; '.join(result.violations)}",
                    meta={"violations": result.violations, "balance_diff": result.balance_diff},
                )
            )

    db.commit()
    return result
