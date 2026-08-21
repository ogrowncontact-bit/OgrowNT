"""Broker Health cadence — "PROMPT 13" §46-47, §106's BrokerHealthWorker
(+ ClockSyncWorker/RateLimitWorker folded in here, see module docstring
below for why they don't get their own cadences).

Same "current call plus a persisted trend" role
packages/execution/health.py's own docstring describes, just wired into
the worker loop: one BrokerHealthCheck row per registered (non-'live')
broker per tick, with an Alert only on a FRESH transition into
UNAVAILABLE/QUARANTINED (never every tick while already degraded) — the
same was_elevated/is_elevated discipline apps/worker/capital_defense.py
already uses, adapted to "last persisted row" (a per-broker state) instead
of a SystemState column (portfolio-wide) since there is no natural
per-broker slot on that singleton table.

ClockSyncWorker/RateLimitWorker (§106) don't get their own cadences:
packages/execution/clock.py's ClockService and packages/execution/
rate_limit.py's RateLimitManager have no real second broker clock or real
network quota to check against in this deployment (see those modules' own
docstrings) — there is nothing periodic for either to DO yet beyond what a
direct API/test call already exercises.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.execution.broker.registry import BrokerRegistry, get_or_create_broker_row
from packages.execution.broker_events import record_event
from packages.execution.health import QUARANTINED, UNAVAILABLE, BrokerHealthAssessment, assess_broker_health
from packages.shared.models import Alert, BrokerHealthCheck, TradingEvent

logger = logging.getLogger("worker.broker_health")

_ALERT_WORTHY_STATES = {UNAVAILABLE, QUARANTINED}


def run_broker_health_cycle(db: Session, registry: BrokerRegistry) -> list[BrokerHealthAssessment]:
    assessments: list[BrokerHealthAssessment] = []

    for adapter in registry.list():
        if adapter.kind == "live":
            continue  # never registered in practice (packages/execution/broker/registry.py) — defensive skip anyway

        broker_row = get_or_create_broker_row(db, name=adapter.name, kind=adapter.kind)
        db.flush()

        previous = (
            db.query(BrokerHealthCheck)
            .filter(BrokerHealthCheck.broker_id == broker_row.id)
            .order_by(BrokerHealthCheck.ts.desc())
            .first()
        )
        was_elevated = previous is not None and previous.state in _ALERT_WORTHY_STATES

        assessment = assess_broker_health(db, adapter, broker_id=broker_row.id)
        db.add(
            BrokerHealthCheck(
                broker_id=broker_row.id, state=assessment.state, latency_ms=assessment.latency_ms,
                error_count=assessment.recent_error_count, detail={"reasons": assessment.reasons},
            )
        )
        # §102-103's idempotent event log — deliberately keyed on `state`
        # only (not latency_ms, which fluctuates every tick): consecutive
        # ticks reporting the SAME qualitative state are "the same event"
        # and collapse via record_event()'s dedup, exactly matching "the
        # same event received twice is a no-op." A genuine state change
        # always produces a new, distinct row.
        record_event(db, broker_id=broker_row.id, event_type="health_check", payload={"state": assessment.state})

        is_elevated = assessment.state in _ALERT_WORTHY_STATES
        if is_elevated and not was_elevated:
            db.add(
                TradingEvent(
                    event_type="broker_health_degraded", entity_type="broker", entity_id=broker_row.id,
                    payload={"state": assessment.state, "reasons": assessment.reasons},
                )
            )
            db.add(
                Alert(
                    severity="critical" if assessment.state == QUARANTINED else "warning", category="system",
                    message=f"Broker '{adapter.name}' health degraded to {assessment.state}",
                    meta={"broker": adapter.name, "state": assessment.state, "reasons": assessment.reasons},
                )
            )
        elif was_elevated and not is_elevated:
            db.add(
                Alert(
                    severity="info", category="system",
                    message=f"Broker '{adapter.name}' health recovered to {assessment.state}",
                    meta={"broker": adapter.name, "state": assessment.state},
                )
            )

        assessments.append(assessment)
        logger.info("Broker health: broker=%s state=%s latency_ms=%s", adapter.name, assessment.state, assessment.latency_ms)

    db.commit()
    return assessments
