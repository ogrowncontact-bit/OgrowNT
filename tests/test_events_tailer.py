"""packages/events/channels.py + tailer.py -- "PROMPT 14" §59-62, §70-71,
§101, §131.
"""
from __future__ import annotations

from datetime import datetime, timezone

from packages.events.channels import (
    ALERT_CATEGORY_TO_INCIDENT_CATEGORY,
    CHANNELS,
    INCIDENT_WORTHY_EVENT_TYPES,
    channel_for_trading_event,
    severity_for_trading_event,
)
from packages.events.tailer import build_heartbeat_event, detect_incidents, tail_new_events
from packages.shared.models import Alert, Incident, SystemState, TradingEvent

_NOW = datetime.now(timezone.utc)


# -- channels.py --------------------------------------------------------
def test_every_trading_event_check_constraint_value_maps_to_a_real_channel():
    """A future TradingEvent event_type this map hasn't been updated for
    yet must still resolve to a valid channel (the "events" catch-all),
    never raise and never silently vanish."""
    known_event_types = (
        "order_submitted", "order_filled", "order_rejected", "position_opened", "position_closed",
        "risk_blocked", "no_trade", "trading_paused", "trading_resumed", "kill_switch_triggered",
        "kill_switch_released", "reconciliation_mismatch", "portfolio_emergency_action",
        "loss_streak_detected", "worker_restarted", "crash_loop_protection_triggered",
        "order_partially_filled", "order_cancelled", "broker_health_degraded",
    )
    for event_type in known_event_types:
        assert channel_for_trading_event(event_type) in CHANNELS
    assert channel_for_trading_event("some_future_event_type_not_yet_mapped") == "events"


def test_critical_event_types_are_severity_critical_not_info():
    assert severity_for_trading_event("kill_switch_triggered") == "critical"
    assert severity_for_trading_event("crash_loop_protection_triggered") == "critical"
    assert severity_for_trading_event("reconciliation_mismatch") == "critical"


def test_ordinary_event_types_default_to_info():
    assert severity_for_trading_event("position_opened") == "info"


def test_incident_worthy_map_only_covers_genuinely_critical_types():
    assert set(INCIDENT_WORTHY_EVENT_TYPES) == {
        "kill_switch_triggered", "crash_loop_protection_triggered", "reconciliation_mismatch",
    }
    assert INCIDENT_WORTHY_EVENT_TYPES["kill_switch_triggered"] == "system"
    assert INCIDENT_WORTHY_EVENT_TYPES["reconciliation_mismatch"] == "broker"


def test_alert_category_map_covers_every_real_alert_category():
    for category in ("trade", "risk", "loss", "emergency", "learning", "system", "market", "news"):
        assert category in ALERT_CATEGORY_TO_INCIDENT_CATEGORY


# -- tailer.py: tail_new_events ------------------------------------------
def test_tail_new_events_returns_nothing_when_no_rows_exist_yet(db_session):
    result = tail_new_events(db_session, since_trading_event_id=0, since_alert_id=0)
    assert result.events == []
    assert result.last_trading_event_id == 0
    assert result.last_alert_id == 0


def test_tail_new_events_only_returns_rows_newer_than_the_cursor(db_session):
    db_session.add(TradingEvent(event_type="trading_resumed", payload={}))
    db_session.commit()
    first = tail_new_events(db_session, since_trading_event_id=0, since_alert_id=0)
    assert len(first.events) == 1

    # A second tail from the NEW cursor sees nothing new.
    second = tail_new_events(db_session, since_trading_event_id=first.last_trading_event_id, since_alert_id=0)
    assert second.events == []

    db_session.add(TradingEvent(event_type="trading_paused", payload={"reason": "test"}))
    db_session.commit()
    third = tail_new_events(db_session, since_trading_event_id=first.last_trading_event_id, since_alert_id=0)
    assert len(third.events) == 1
    assert third.events[0].event_type == "trading_paused"


def test_tail_new_events_derives_correlation_id_from_entity_type_and_id(db_session):
    db_session.add(TradingEvent(event_type="position_opened", entity_type="position", entity_id=42, payload={}))
    db_session.commit()
    result = tail_new_events(db_session, since_trading_event_id=0, since_alert_id=0)
    assert result.events[0].correlation_id == "position:42"


def test_tail_new_events_alerts_get_alerts_channel_and_own_severity(db_session):
    db_session.add(Alert(severity="critical", category="risk", message="test alert", meta={}))
    db_session.commit()
    result = tail_new_events(db_session, since_trading_event_id=0, since_alert_id=0)
    assert len(result.events) == 1
    assert result.events[0].channel == "alerts"
    assert result.events[0].severity == "critical"
    assert result.events[0].source == "alerts"


def test_tail_new_events_combines_trading_events_and_alerts_in_one_call(db_session):
    db_session.add(TradingEvent(event_type="no_trade", payload={}))
    db_session.add(Alert(severity="info", category="system", message="ok", meta={}))
    db_session.commit()
    result = tail_new_events(db_session, since_trading_event_id=0, since_alert_id=0)
    assert len(result.events) == 2


# -- tailer.py: build_heartbeat_event -------------------------------------
def test_build_heartbeat_event_reflects_current_system_state(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, trading_paused=False, safety_belt_level="normal"))
    db_session.commit()
    event = build_heartbeat_event(db_session)
    assert event.event_type == "heartbeat"
    assert event.channel == "system"
    assert event.payload["trading_enabled"] is True
    assert event.payload["safety_belt_level"] == "normal"


def test_build_heartbeat_event_never_persists_anything(db_session):
    before = db_session.query(TradingEvent).count()
    build_heartbeat_event(db_session)
    after = db_session.query(TradingEvent).count()
    assert before == after


# -- tailer.py: detect_incidents ------------------------------------------
def test_detect_incidents_creates_one_for_a_kill_switch_trading_event(db_session):
    result = tail_new_events(db_session, since_trading_event_id=10**9, since_alert_id=10**9)  # empty on purpose
    from packages.events.bus import Event

    fabricated = [Event(event_type="kill_switch_triggered", source="trading_events", channel="system", severity="critical", payload={})]
    created = detect_incidents(db_session, fabricated)
    assert len(created) == 1
    assert created[0].category == "system"
    assert created[0].status == "detected"
    assert result.events == []  # sanity: the tail itself found nothing real


def test_detect_incidents_creates_one_for_a_critical_alert(db_session):
    from packages.events.bus import Event

    fabricated = [
        Event(
            event_type="alert.risk", source="alerts", channel="alerts", severity="critical",
            payload={"message": "drawdown critical", "category": "risk"},
        )
    ]
    created = detect_incidents(db_session, fabricated)
    assert len(created) == 1
    assert created[0].category == "risk"


def test_detect_incidents_ignores_non_critical_events(db_session):
    from packages.events.bus import Event

    fabricated = [Event(event_type="position_opened", source="trading_events", channel="portfolio", severity="info", payload={})]
    created = detect_incidents(db_session, fabricated)
    assert created == []


def test_detect_incidents_is_idempotent_while_an_incident_is_still_open(db_session):
    """§59-62's "page once, not every tick" -- a second occurrence of the
    SAME source_event_type while one is already open never creates a
    duplicate Incident row."""
    from packages.events.bus import Event

    event = Event(event_type="reconciliation_mismatch", source="trading_events", channel="execution", severity="critical", payload={})
    first = detect_incidents(db_session, [event])
    second = detect_incidents(db_session, [event])
    assert len(first) == 1
    assert second == []
    assert db_session.query(Incident).filter(Incident.source_event_type == "reconciliation_mismatch").count() == 1


def test_detect_incidents_creates_a_new_one_once_the_prior_is_resolved(db_session):
    from packages.events.bus import Event

    event = Event(event_type="crash_loop_protection_triggered", source="trading_events", channel="system", severity="critical", payload={})
    first = detect_incidents(db_session, [event])
    first[0].status = "resolved"
    db_session.commit()

    second = detect_incidents(db_session, [event])
    assert len(second) == 1
    assert second[0].id != first[0].id
