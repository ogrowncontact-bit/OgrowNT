"""Order Monitor cadence — "PROMPT 13" §106's OrderMonitorWorker.

A hygiene sweep, not a matching engine: PaperBrokerAdapter's submit_order()
is fully synchronous (packages/execution/broker/paper.py) — under normal
operation, an Order row never actually sits in a non-terminal status
('new'/'submitted'/'cancel_pending') for more than the instant between its
INSERT and the very next line committing its real terminal status. This
cadence exists for the abnormal case: a crash, an exception, or a future
change leaving a row stuck — sweeping anything non-terminal past
`stale_after_seconds` to EXPIRED (§10's terminal-state vocabulary) rather
than letting it sit forever as neither a real order nor an honestly closed
one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.shared.models import Order, TradingEvent

logger = logging.getLogger("worker.order_monitor")

DEFAULT_STALE_AFTER_SECONDS = 300


def run_order_monitor_cycle(db: Session, *, stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=stale_after_seconds)

    stale_orders = (
        db.query(Order)
        .filter(Order.status.in_(("new", "submitted", "cancel_pending")), Order.submitted_at.isnot(None), Order.submitted_at < cutoff)
        .all()
    )
    for order in stale_orders:
        previous_status = order.status
        order.status = "expired"
        db.add(order)
        db.add(
            TradingEvent(
                event_type="order_rejected", entity_type="order", entity_id=order.id,
                payload={"reason": "stale_order_swept_to_expired", "previous_status": previous_status},
            )
        )

    if stale_orders:
        db.commit()
        logger.warning("Order monitor swept %d stale order(s) to EXPIRED", len(stale_orders))
    return len(stale_orders)
