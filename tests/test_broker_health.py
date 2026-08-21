"""packages/execution/health.py -- "PROMPT 13" §46-47."""
from __future__ import annotations

from packages.execution.broker.registry import get_or_create_broker_row
from packages.execution.health import (
    _LATENCY_DEGRADED_MS,
    _LATENCY_UNAVAILABLE_MS,
    DEGRADED,
    HEALTHY,
    QUARANTINED,
    UNAVAILABLE,
    assess_broker_health,
)
from packages.shared.models import BrokerHealthCheck


class _HealthResult:
    def __init__(self, ok: bool, latency_ms: float = 1.0):
        self.ok = ok
        self.latency_ms = latency_ms
        self.detail: dict = {}


class _StubAdapter:
    def __init__(self, results):
        self._results = list(results)

    def health_check(self):
        return self._results.pop(0)


def _broker_id(db_session) -> int:
    broker = get_or_create_broker_row(db_session, name="stub", kind="paper")
    db_session.commit()
    return broker.id


def test_fast_ok_check_is_healthy(db_session):
    broker_id = _broker_id(db_session)
    adapter = _StubAdapter([_HealthResult(True, latency_ms=1.0)])
    result = assess_broker_health(db_session, adapter, broker_id=broker_id)
    assert result.state == HEALTHY


def test_elevated_latency_is_degraded(db_session):
    broker_id = _broker_id(db_session)
    adapter = _StubAdapter([_HealthResult(True, latency_ms=_LATENCY_DEGRADED_MS + 1)])
    result = assess_broker_health(db_session, adapter, broker_id=broker_id)
    assert result.state == DEGRADED


def test_very_high_latency_is_unavailable(db_session):
    broker_id = _broker_id(db_session)
    adapter = _StubAdapter([_HealthResult(True, latency_ms=_LATENCY_UNAVAILABLE_MS + 1)])
    result = assess_broker_health(db_session, adapter, broker_id=broker_id)
    assert result.state == UNAVAILABLE


def test_single_failed_check_is_unavailable_not_quarantined(db_session):
    broker_id = _broker_id(db_session)
    adapter = _StubAdapter([_HealthResult(False)])
    result = assess_broker_health(db_session, adapter, broker_id=broker_id)
    assert result.state == UNAVAILABLE


def test_a_streak_of_failures_escalates_to_quarantined(db_session):
    """A single bad tick is noise; a persisted STREAK of failures (read back
    from broker_health_checks) is a signal — same discipline as the worker's
    own CadenceFailureTracker."""
    broker_id = _broker_id(db_session)
    db_session.add_all([
        BrokerHealthCheck(broker_id=broker_id, state=UNAVAILABLE, latency_ms=None, error_count=1, detail={}),
        BrokerHealthCheck(broker_id=broker_id, state=UNAVAILABLE, latency_ms=None, error_count=1, detail={}),
    ])
    db_session.commit()

    adapter = _StubAdapter([_HealthResult(False)])
    result = assess_broker_health(db_session, adapter, broker_id=broker_id, quarantine_failure_streak=3)
    assert result.state == QUARANTINED
    assert result.recent_error_count == 3
