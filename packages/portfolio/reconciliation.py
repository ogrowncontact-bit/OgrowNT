"""Paper Reconciliation Engine — "PROMPT 8" §69-71.

Periodically re-derives the paper account's cash from first principles
(every position ever opened/closed, every entry fee ever paid, every
realized P&L) and compares it against packages/portfolio/state.py's
incrementally-maintained ledger (packages/execution/order_manager.py
updates it fill by fill, in `packages/portfolio/state.py`'s
`portfolio_snapshots` table). The two should always agree exactly — a
mismatch means a bug somewhere in that incremental math, not something to
paper over: trading is paused (SystemState.trading_paused, deliberately
NOT the Kill Switch — this is an accounting-integrity stop, not a
market-risk one) until an operator investigates and manually resumes.

Also checks the "boring but load-bearing" invariants named in §62 (cash>=0,
position size>=0, fees>=0) that would otherwise only ever surface later as
a downstream symptom (e.g. a negative size silently corrupting P&L math)
rather than a direct, named failure caught at the source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.portfolio.state import get_latest_cash
from packages.shared.models import Alert, Order, Position, SystemState, Trade, TradingEvent
from packages.shared.settings import get_settings

# Float accounting across many fills accumulates rounding error — this is a
# "did something actually break" tolerance, not a policy gap: every
# individual number involved is already rounded to cents in
# packages/execution/order_manager.py before it's stored.
CASH_RECONCILIATION_TOLERANCE = 0.05


@dataclass(frozen=True)
class ReconciliationResult:
    ok: bool
    expected_cash: float
    actual_cash: float
    cash_diff: float
    violations: list[str] = field(default_factory=list)


def _expected_cash(db: Session) -> float:
    """Ledger reconstruction, independent of packages/portfolio/state.py's
    running total: initial capital, minus every entry fee ever paid, minus
    the notional still tied up in currently-open positions, plus every
    trade's realized P&L (which already nets its own exit fee — see
    packages/execution/order_manager.py's close_position). Aggregated in
    SQL, not by loading every row into Python — this can run every cycle
    over a long-lived account (docs/blueprint/00-overview.md's "never heavy
    analysis inline" applies to this scheduled check too).

    After a RESET PAPER ACCOUNT (SystemState.last_reset_at), fees/trades
    from before the reset are excluded — they're sunk into the account's
    prior life, not this one — matching packages/portfolio/state.py's own
    reset-epoch handling so the two never disagree right after a reset.
    """
    initial_capital = get_settings().initial_paper_capital
    state = db.get(SystemState, True)
    epoch = state.last_reset_at if state is not None else None

    fees_query = select(func.coalesce(func.sum(Order.fees), 0.0)).where(Order.signal_id.isnot(None), Order.status == "filled")
    pnl_query = select(func.coalesce(func.sum(Trade.pnl), 0.0))
    if epoch is not None:
        fees_query = fees_query.where(Order.submitted_at >= epoch)
        pnl_query = pnl_query.where(Trade.closed_at >= epoch)

    # func.coalesce(...) guarantees a non-NULL row at the SQL level (there's
    # always exactly one row from an unconditional SUM), but SQLAlchemy's
    # stubs still type scalar_one() as `float | None` here — `or 0.0` keeps
    # mypy honest without lying about what the query can actually return.
    total_entry_fees = db.execute(fees_query).scalar_one() or 0.0

    capital_tied_up = (
        db.execute(
            select(func.coalesce(func.sum(Position.entry_price * Position.size), 0.0)).where(Position.status == "open")
        ).scalar_one()
        or 0.0
    )

    total_realized_pnl = db.execute(pnl_query).scalar_one() or 0.0

    return initial_capital - total_entry_fees - capital_tied_up + total_realized_pnl


def run_reconciliation(db: Session) -> ReconciliationResult:
    """Pure check — never mutates anything. See reconcile_and_enforce() for
    the version that pauses trading on failure."""
    violations: list[str] = []

    actual_cash = get_latest_cash(db)
    expected_cash = _expected_cash(db)
    cash_diff = round(actual_cash - expected_cash, 4)
    if abs(cash_diff) > CASH_RECONCILIATION_TOLERANCE:
        violations.append(f"cash_mismatch: ledger={actual_cash:.2f} expected={expected_cash:.2f} diff={cash_diff:.4f}")
    if actual_cash < 0:
        violations.append(f"negative_cash: {actual_cash:.2f}")

    for position in db.query(Position).filter(Position.status == "open").all():
        if position.size <= 0:
            violations.append(f"non_positive_position_size: position_id={position.id} size={position.size}")

    negative_fee_orders = db.query(Order.id, Order.fees).filter(Order.fees.isnot(None), Order.fees < 0).all()
    for order_id, fees in negative_fee_orders:
        violations.append(f"negative_fees: order_id={order_id} fees={fees}")

    return ReconciliationResult(
        ok=len(violations) == 0,
        expected_cash=round(expected_cash, 4),
        actual_cash=round(actual_cash, 4),
        cash_diff=cash_diff,
        violations=violations,
    )


def reconcile_and_enforce(db: Session) -> ReconciliationResult:
    """Runs run_reconciliation() and, on any violation, pauses trading
    (idempotently — a second consecutive failure doesn't re-pause/re-alert,
    same "page once, not every tick" discipline as
    apps/worker/supervisor.py's CadenceFailureTracker) and records both a
    TradingEvent (machine-readable, for the decision trace / activity feed)
    and a critical Alert (so it actually reaches the operator via
    packages/notifications)."""
    result = run_reconciliation(db)
    if result.ok:
        return result

    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
        db.add(state)

    db.add(
        TradingEvent(
            event_type="reconciliation_mismatch", entity_type="system_state", entity_id=None,
            payload={"violations": result.violations, "expected_cash": result.expected_cash, "actual_cash": result.actual_cash},
        )
    )

    if not state.trading_paused:
        state.trading_paused = True
        state.paused_reason = f"reconciliation_mismatch: {'; '.join(result.violations)}"
        state.paused_at = datetime.now(timezone.utc)
        db.add(state)
        db.add(
            Alert(
                severity="critical", category="system",
                message=f"Paper account reconciliation failed — trading paused: {'; '.join(result.violations)}",
                meta={"violations": result.violations, "expected_cash": result.expected_cash, "actual_cash": result.actual_cash},
            )
        )

    db.commit()
    return result
