"""Broker Reconciliation cadence — "PROMPT 13" §33-38, §87, §106's
ReconciliationWorker.

Runs packages/execution/broker_reconciliation.py's broker-level check
(positions/orders/balances vs. what a BrokerAdapter reports) on its own
cadence, independent of — and layered on top of — the existing cash-only
PaperReconciliationEngine cadence (packages/portfolio/reconciliation.py,
already wired into apps/worker/main.py since "PROMPT 8").
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.execution.broker.registry import BrokerRegistry, get_or_create_broker_row
from packages.execution.broker_reconciliation import BrokerReconciliationResult, run_broker_reconciliation_and_enforce

logger = logging.getLogger("worker.broker_reconciliation")


def run_broker_reconciliation_cycle(db: Session, registry: BrokerRegistry) -> list[BrokerReconciliationResult]:
    results: list[BrokerReconciliationResult] = []
    for adapter in registry.list():
        if adapter.kind == "live":
            continue
        broker_row = get_or_create_broker_row(db, name=adapter.name, kind=adapter.kind)
        db.flush()
        result = run_broker_reconciliation_and_enforce(db, adapter, broker_id=broker_row.id)
        results.append(result)
        if not result.ok:
            logger.critical("Broker reconciliation mismatch for '%s': %s", adapter.name, result.violations)
        else:
            logger.info("Broker reconciliation OK for '%s' (balance_diff=%s)", adapter.name, result.balance_diff)
    return results
