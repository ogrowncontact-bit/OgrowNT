"""packages/execution/broker_events.py -- "PROMPT 13" §102-103."""
from __future__ import annotations

from packages.execution.broker.registry import get_or_create_broker_row
from packages.execution.broker_events import record_event
from packages.shared.models import BrokerEvent


def _broker_id(db_session) -> int:
    broker = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()
    return broker.id


def test_recording_a_new_event_creates_a_row(db_session):
    broker_id = _broker_id(db_session)
    event, created = record_event(db_session, broker_id=broker_id, event_type="health_check", payload={"state": "healthy"})
    assert created is True
    assert event.id is not None


def test_recording_the_identical_event_twice_is_a_noop(db_session):
    """§103: the same event received twice must never be processed twice."""
    broker_id = _broker_id(db_session)
    first, first_created = record_event(db_session, broker_id=broker_id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()
    second, second_created = record_event(db_session, broker_id=broker_id, event_type="health_check", payload={"state": "healthy"})

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert db_session.query(BrokerEvent).filter(BrokerEvent.broker_id == broker_id).count() == 1


def test_a_genuinely_different_payload_creates_a_new_row(db_session):
    broker_id = _broker_id(db_session)
    record_event(db_session, broker_id=broker_id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()
    _, created = record_event(db_session, broker_id=broker_id, event_type="health_check", payload={"state": "degraded"})
    assert created is True
    assert db_session.query(BrokerEvent).filter(BrokerEvent.broker_id == broker_id).count() == 2


def test_same_payload_different_event_type_does_not_dedupe(db_session):
    broker_id = _broker_id(db_session)
    record_event(db_session, broker_id=broker_id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()
    _, created = record_event(db_session, broker_id=broker_id, event_type="order_cancelled", payload={"state": "healthy"})
    assert created is True
