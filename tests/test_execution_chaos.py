"""Chaos testing -- "PROMPT 13" §100-101: broker timeout, network failure,
clock drift, duplicate/out-of-order events, and unknown order state. Same
"simulate the failure mode directly, confirm the system degrades safely
rather than corrupting state" discipline as
tests/test_crash_recovery_and_continuous_simulation.py ("PROMPT 8")."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.broker.registry import get_or_create_broker_row
from packages.execution.broker_events import record_event
from packages.execution.broker_reconciliation import run_broker_reconciliation
from packages.execution.clock import ClockService
from packages.execution.health import UNAVAILABLE, assess_broker_health
from packages.shared.models import BrokerEvent, Order, ReconciliationRun

_NOW = datetime.now(timezone.utc)


class _HealthResult:
    def __init__(self, ok: bool, latency_ms: float = 1.0):
        self.ok = ok
        self.latency_ms = latency_ms
        self.detail: dict = {}


class _TimeoutAdapter:
    """§100 broker timeout -- health_check reports failure, same shape a
    real network timeout would produce (no exception, an honest ok=False)."""

    def health_check(self):
        return _HealthResult(False)


class _OutageAdapter:
    """§100 API outage -- every call raises, simulating a broker whose
    connection dropped entirely mid-call rather than returning any answer."""

    name = "outage_stub"

    def get_account(self):
        raise ConnectionError("simulated broker outage")

    def get_positions(self):
        raise ConnectionError("simulated broker outage")

    def get_open_orders(self):
        raise ConnectionError("simulated broker outage")


def test_broker_timeout_degrades_to_unavailable_not_a_crash(db_session):
    broker = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()
    result = assess_broker_health(db_session, _TimeoutAdapter(), broker_id=broker.id)
    assert result.state == UNAVAILABLE


def test_broker_outage_during_reconciliation_propagates_without_a_partial_commit(db_session):
    """§100 -- a mid-call outage must not leave a half-written
    ReconciliationRun row behind; the exception propagates cleanly to the
    worker loop's own per-cadence try/except (apps/worker/main.py), which
    is what actually isolates this from the rest of the cycle."""
    with pytest.raises(ConnectionError):
        run_broker_reconciliation(db_session, _OutageAdapter())
    assert db_session.query(ReconciliationRun).count() == 0


def test_clock_drift_against_a_broker_reported_timestamp_is_detected():
    """§55-56 -- a broker reporting a timestamp far from this process's own
    clock (e.g. after a long GC pause, a suspended VM, or genuine clock
    skew) must be flagged, not silently trusted."""
    broker_reported_ts = _NOW - timedelta(minutes=10)
    result = ClockService().check_drift(broker_reported_ts, now=_NOW, max_drift_seconds=30.0)
    assert result.within_tolerance is False


def test_duplicate_event_during_a_simulated_reconnect_is_not_double_processed(db_session):
    """§101 -- a broker reconnect can redeliver the same event; processing
    it twice must be a no-op."""
    broker = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()

    _, first_created = record_event(db_session, broker_id=broker.id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()
    # Simulate a reconnect redelivering the exact same event.
    _, redelivered_created = record_event(db_session, broker_id=broker.id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()

    assert first_created is True
    assert redelivered_created is False
    assert db_session.query(BrokerEvent).filter(BrokerEvent.broker_id == broker.id).count() == 1


def test_out_of_order_sequence_numbers_do_not_break_dedup(db_session):
    """§101 -- events may arrive out of order; dedup is keyed on payload
    content, not arrival order, so a late-arriving lower sequence number
    still dedupes correctly against an already-recorded event."""
    broker = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()

    record_event(db_session, broker_id=broker.id, event_type="health_check", payload={"state": "healthy"}, sequence=5)
    db_session.commit()
    _, created = record_event(db_session, broker_id=broker.id, event_type="health_check", payload={"state": "healthy"}, sequence=2)
    assert created is False  # arrived "late" (lower sequence) but is still the same event


def test_unknown_order_status_is_never_silently_treated_as_filled(db_session):
    """§11 -- "se broker retornar estado desconhecido: UNKNOWN. Nunca
    assumir FILLED." An order genuinely persisted with status='unknown'
    must round-trip as exactly that, never coerced into a false positive."""
    order = Order(order_type="market", side="buy", qty=1.0, status="unknown", broker_order_id="mystery-order")
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    assert order.status == "unknown"
    assert order.status != "filled"


def test_websocket_streaming_is_honestly_unsupported_not_silently_stubbed():
    """§100's 'websocket disconnect' scenario doesn't apply here: this
    codebase never claims websocket support in the first place
    (PaperBrokerAdapter's own capabilities honestly report it as
    unsupported), so there is no stream to disconnect."""
    from packages.execution.broker.capabilities import PAPER_CAPABILITIES

    assert PAPER_CAPABILITIES.supports_websocket is False
