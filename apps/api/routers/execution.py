"""Account/order-detail/execution/reconciliation/instrument/execution-health
endpoints — "PROMPT 13" §105.

Read-only (get_current_admin). Grouped under one router file since each is
a small, focused read over data another module already computes/persists —
same "don't split a handful of thin GETs across many files" convention as
apps/api/routers/portfolio.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    AccountOut,
    ExecutionHealthOut,
    ExecutionOut,
    InstrumentOut,
    OrderDetailOut,
    ReconciliationOut,
)
from packages.execution.broker.paper import PaperBrokerAdapter
from packages.execution.instrument import get_instrument
from packages.execution.quality import assess_execution_quality
from packages.shared.models import AdminUser, Asset, Broker, Order, ReconciliationRun
from packages.shared.models import Execution as ExecutionRow

router = APIRouter(prefix="/api", tags=["execution"])


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[AccountOut]:
    adapter = PaperBrokerAdapter(db)
    account = adapter.get_account()
    return [
        AccountOut(
            broker_name=adapter.name, balance=account.balance, available_balance=account.available_balance,
            equity=account.equity, margin=account.margin, margin_used=account.margin_used,
            margin_available=account.margin_available, currency=account.currency, ts=account.ts,
        )
    ]


def _execution_out(row: ExecutionRow) -> ExecutionOut:
    return ExecutionOut(
        id=row.id, order_id=row.order_id, broker_order_id=row.broker_order_id, symbol=row.symbol, side=row.side,
        quantity=row.quantity, price=row.price, fee=row.fee, fee_currency=row.fee_currency,
        slippage_bps=row.slippage_bps, ts=row.ts, liquidity=row.liquidity, execution_mode=row.execution_mode,
    )


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def get_order_detail(order_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> OrderDetailOut:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    broker_name = None
    if order.broker_id is not None:
        broker_row = db.get(Broker, order.broker_id)
        broker_name = broker_row.name if broker_row is not None else None

    fills = db.query(ExecutionRow).filter(ExecutionRow.order_id == order.id).order_by(ExecutionRow.ts).all()
    return OrderDetailOut(
        id=order.id, position_id=order.position_id, signal_id=order.signal_id, broker_order_id=order.broker_order_id,
        broker_name=broker_name, order_type=order.order_type, side=order.side, qty=order.qty,
        limit_price=order.limit_price, stop_price=order.stop_price, take_profit_price=order.take_profit_price,
        time_in_force=order.time_in_force, status=order.status, execution_mode=order.execution_mode,
        submitted_at=order.submitted_at, filled_at=order.filled_at, filled_price=order.filled_price,
        expected_price=order.expected_price, fees=order.fees, slippage_bps=order.slippage_bps,
        latency_ms=order.latency_ms, idempotency_key=order.idempotency_key, decision_id=order.decision_id,
        risk_decision_id=order.risk_decision_id, fills=[_execution_out(f) for f in fills],
    )


@router.get("/executions", response_model=list[ExecutionOut])
def list_executions(limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[ExecutionOut]:
    rows = db.query(ExecutionRow).order_by(ExecutionRow.id.desc()).limit(limit).all()
    return [_execution_out(row) for row in rows]


@router.get("/reconciliation", response_model=list[ReconciliationOut])
def list_reconciliation_runs(limit: int = 20, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[ReconciliationOut]:
    rows = db.query(ReconciliationRun).order_by(ReconciliationRun.ts.desc()).limit(limit).all()
    out: list[ReconciliationOut] = []
    for row in rows:
        broker_row = db.get(Broker, row.broker_id)
        out.append(
            ReconciliationOut(
                id=row.id, broker_name=broker_row.name if broker_row is not None else "unknown", ts=row.ts,
                ok=row.ok, violations=row.violations, position_mismatches=row.position_mismatches,
                order_mismatches=row.order_mismatches, balance_diff=row.balance_diff,
            )
        )
    return out


def _instrument_out(asset: Asset) -> InstrumentOut:
    spec = get_instrument(asset)
    return InstrumentOut(
        symbol=spec.symbol, asset_class=spec.asset_class, tick_size=spec.tick_size, step_size=spec.step_size,
        min_quantity=spec.min_quantity, min_notional=spec.min_notional,
    )


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[InstrumentOut]:
    return [_instrument_out(asset) for asset in db.query(Asset).all()]


@router.get("/instruments/{symbol}", response_model=InstrumentOut)
def get_instrument_detail(symbol: str, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> InstrumentOut:
    asset = db.query(Asset).filter(Asset.symbol == symbol).one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")
    return _instrument_out(asset)


@router.get("/execution/health", response_model=ExecutionHealthOut)
def get_execution_health(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> ExecutionHealthOut:
    assessment = assess_execution_quality(db)
    return ExecutionHealthOut(
        evaluated=assessment.evaluated, orders_evaluated=assessment.orders_evaluated,
        filled_orders=assessment.filled_orders, rejected_orders=assessment.rejected_orders,
        fill_ratio=assessment.fill_ratio, avg_latency_ms=assessment.avg_latency_ms,
        avg_slippage_bps=assessment.avg_slippage_bps, avg_price_deviation_pct=assessment.avg_price_deviation_pct,
        market_impact_estimate_bps=assessment.market_impact_estimate_bps,
    )
