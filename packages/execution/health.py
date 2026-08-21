"""BrokerHealthMonitor — "PROMPT 13" §46-47.

Same "current call plus persisted trend" pattern as
packages/shared/worker_health.py: a single health_check() call decides
HEALTHY/DEGRADED by latency, and a run of consecutive failed checks (read
back from broker_health_checks, this phase's new append-only table) is what
promotes UNAVAILABLE to QUARANTINED rather than one bad tick alone —
matching the same "one failure is noise, a streak is a signal" discipline
"PROMPT 8"'s CadenceFailureTracker already uses for worker cadences.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.execution.broker.base import BrokerAdapter
from packages.shared.models import BrokerHealthCheck

HEALTHY = "healthy"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
QUARANTINED = "quarantined"

BROKER_HEALTH_STATES = (HEALTHY, DEGRADED, UNAVAILABLE, QUARANTINED)

# A synchronous in-process paper adapter should answer in low
# single-digit milliseconds; these thresholds exist so the monitor is
# genuinely exercised by a slow/failing stub in tests, not because a real
# paper health_check() is ever expected to approach them.
_LATENCY_DEGRADED_MS = 500.0
_LATENCY_UNAVAILABLE_MS = 2000.0
_QUARANTINE_FAILURE_STREAK = 3


@dataclass(frozen=True)
class BrokerHealthAssessment:
    state: str
    latency_ms: float | None
    recent_error_count: int
    reasons: list[str] = field(default_factory=list)


def assess_broker_health(
    db: Session, broker: BrokerAdapter, *, broker_id: int, quarantine_failure_streak: int = _QUARANTINE_FAILURE_STREAK,
) -> BrokerHealthAssessment:
    result = broker.health_check()

    if not result.ok:
        recent = (
            db.query(BrokerHealthCheck)
            .filter(BrokerHealthCheck.broker_id == broker_id)
            .order_by(BrokerHealthCheck.ts.desc())
            .limit(quarantine_failure_streak - 1)
            .all()
        )
        consecutive_failures = 1 + sum(1 for row in recent if row.state in (UNAVAILABLE, QUARANTINED))
        if consecutive_failures >= quarantine_failure_streak:
            return BrokerHealthAssessment(
                state=QUARANTINED, latency_ms=result.latency_ms, recent_error_count=consecutive_failures,
                reasons=[f"{consecutive_failures} consecutive failed health checks"],
            )
        return BrokerHealthAssessment(
            state=UNAVAILABLE, latency_ms=result.latency_ms, recent_error_count=consecutive_failures,
            reasons=["most recent health check failed", str(result.detail)],
        )

    if result.latency_ms >= _LATENCY_UNAVAILABLE_MS:
        return BrokerHealthAssessment(
            state=UNAVAILABLE, latency_ms=result.latency_ms, recent_error_count=0,
            reasons=[f"health check latency {result.latency_ms}ms exceeds the {_LATENCY_UNAVAILABLE_MS}ms unavailable threshold"],
        )
    if result.latency_ms >= _LATENCY_DEGRADED_MS:
        return BrokerHealthAssessment(
            state=DEGRADED, latency_ms=result.latency_ms, recent_error_count=0,
            reasons=[f"health check latency {result.latency_ms}ms exceeds the {_LATENCY_DEGRADED_MS}ms degraded threshold"],
        )

    return BrokerHealthAssessment(state=HEALTHY, latency_ms=result.latency_ms, recent_error_count=0, reasons=[])
