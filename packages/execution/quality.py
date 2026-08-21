"""ExecutionQualityEngine — "PROMPT 13" §43-45.

Read-side aggregation over fields packages/execution/order_manager.py
already captures on every Order row (expected_price/filled_price/
latency_ms/slippage_bps — all "PROMPT 8") plus, when present, this phase's
new Execution rows (one per fill event — see packages/shared/models.py) for
a genuine fill_ratio. No new computation cadence: this is the same
"pure read-side aggregation over data another module already writes" role
packages/analytics/overview.py plays for the dashboard's Advanced Analytics
panel (Phase 7) — called on demand from the API, never from a worker
cadence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.shared.models import Execution, Order

DEFAULT_LOOKBACK = 100


@dataclass(frozen=True)
class ExecutionQualityAssessment:
    evaluated: bool
    orders_evaluated: int
    filled_orders: int
    rejected_orders: int
    fill_ratio: float | None  # mean(filled_qty / requested_qty) across evaluated orders, 0-1
    avg_latency_ms: float | None
    avg_slippage_bps: float | None
    avg_price_deviation_pct: float | None  # mean |filled_price - expected_price| / expected_price, %
    market_impact_estimate_bps: float | None  # same signal as avg_slippage_bps — see module docstring
    reasons: list[str] = field(default_factory=list)


def _order_fill_ratio(db: Session, order: Order) -> float | None:
    if order.status == "rejected":
        return 0.0
    if order.status == "filled":
        return 1.0
    if order.status == "partially_filled":
        execution = db.query(Execution).filter(Execution.order_id == order.id).order_by(Execution.id.desc()).first()
        if execution is not None and order.qty > 0:
            return round(execution.quantity / order.qty, 4)
        return None  # no Execution row recorded yet (a pre-"PROMPT 13" partial fill) — honestly skip, not fabricate
    return None


def assess_execution_quality(db: Session, *, lookback: int = DEFAULT_LOOKBACK) -> ExecutionQualityAssessment:
    orders = (
        db.query(Order)
        .filter(Order.status.in_(("filled", "partially_filled", "rejected")))
        .order_by(Order.id.desc())
        .limit(lookback)
        .all()
    )
    if not orders:
        return ExecutionQualityAssessment(
            evaluated=False, orders_evaluated=0, filled_orders=0, rejected_orders=0, fill_ratio=None,
            avg_latency_ms=None, avg_slippage_bps=None, avg_price_deviation_pct=None,
            market_impact_estimate_bps=None, reasons=["no recent orders to evaluate"],
        )

    fill_ratios = [r for r in (_order_fill_ratio(db, o) for o in orders) if r is not None]
    latencies = [o.latency_ms for o in orders if o.latency_ms is not None]
    slippages = [o.slippage_bps for o in orders if o.slippage_bps is not None]
    deviations = [
        abs(o.filled_price - o.expected_price) / o.expected_price * 100
        for o in orders
        if o.filled_price is not None and o.expected_price is not None and o.expected_price > 0
    ]

    avg_slippage = round(sum(slippages) / len(slippages), 4) if slippages else None
    return ExecutionQualityAssessment(
        evaluated=True,
        orders_evaluated=len(orders),
        filled_orders=sum(1 for o in orders if o.status in ("filled", "partially_filled")),
        rejected_orders=sum(1 for o in orders if o.status == "rejected"),
        fill_ratio=round(sum(fill_ratios) / len(fill_ratios), 4) if fill_ratios else None,
        avg_latency_ms=round(sum(latencies) / len(latencies), 3) if latencies else None,
        avg_slippage_bps=avg_slippage,
        avg_price_deviation_pct=round(sum(deviations) / len(deviations), 4) if deviations else None,
        # Market impact IS what excess slippage measures in this codebase —
        # there is no separate order-book-depth signal to derive a distinct
        # number from (packages/market/liquidity.py's own OrderBookSnapshot
        # is optional/unpopulated, same honest gap noted there).
        market_impact_estimate_bps=avg_slippage,
        reasons=[],
    )
