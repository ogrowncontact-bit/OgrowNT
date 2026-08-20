from datetime import datetime, timedelta, timezone

from packages.shared.models import SystemHealth, SystemState, TradingEvent
from packages.shared.worker_health import (
    compute_autonomous_status,
    is_heartbeat_stale,
    record_heartbeat,
    record_system_health_snapshot,
    record_worker_restart,
)

NOW = datetime.now(timezone.utc)


def test_record_heartbeat_creates_system_state_if_missing(db_session):
    assert db_session.get(SystemState, True) is None
    record_heartbeat(db_session)

    state = db_session.get(SystemState, True)
    assert state is not None
    assert state.worker_last_heartbeat is not None
    assert (datetime.now(timezone.utc) - state.worker_last_heartbeat).total_seconds() < 5


def test_record_heartbeat_updates_existing_system_state(db_session):
    db_session.add(SystemState(id=True, worker_last_heartbeat=NOW - timedelta(days=1)))
    db_session.commit()

    record_heartbeat(db_session)

    state = db_session.get(SystemState, True)
    assert state.worker_last_heartbeat > NOW - timedelta(minutes=1)


def test_is_heartbeat_stale_none_is_always_stale():
    assert is_heartbeat_stale(None, scan_interval_seconds=60) is True


def test_is_heartbeat_stale_recent_is_not_stale():
    recent = NOW - timedelta(seconds=10)
    assert is_heartbeat_stale(recent, scan_interval_seconds=60, now=NOW) is False


def test_is_heartbeat_stale_old_is_stale():
    old = NOW - timedelta(minutes=10)
    assert is_heartbeat_stale(old, scan_interval_seconds=60, now=NOW) is True


def test_is_heartbeat_stale_respects_floor_for_short_scan_intervals():
    # scan_interval_seconds=1 -> 3x multiplier is only 3s, but the 180s
    # floor should still apply, so a heartbeat 10s old must not be stale.
    ten_seconds_old = NOW - timedelta(seconds=10)
    assert is_heartbeat_stale(ten_seconds_old, scan_interval_seconds=1, now=NOW) is False


def test_is_heartbeat_stale_scales_with_scan_interval():
    # scan_interval_seconds=120 -> 3x multiplier is 360s, above the floor.
    five_minutes_old = NOW - timedelta(minutes=5)
    assert is_heartbeat_stale(five_minutes_old, scan_interval_seconds=120, now=NOW) is False
    seven_minutes_old = NOW - timedelta(minutes=7)
    assert is_heartbeat_stale(seven_minutes_old, scan_interval_seconds=120, now=NOW) is True


def test_compute_autonomous_status_priority_order():
    alive = SystemState(id=True, worker_last_heartbeat=NOW, trading_enabled=True, trading_paused=False)
    assert compute_autonomous_status(alive, safety_belt_level="normal", worker_alive=True) == "running"

    never_started = SystemState(id=True, worker_last_heartbeat=None)
    assert compute_autonomous_status(never_started, safety_belt_level="normal", worker_alive=False) == "starting"

    died = SystemState(id=True, worker_last_heartbeat=NOW, trading_enabled=True)
    assert compute_autonomous_status(died, safety_belt_level="normal", worker_alive=False) == "error"

    killed = SystemState(id=True, worker_last_heartbeat=NOW, trading_enabled=False)
    assert compute_autonomous_status(killed, safety_belt_level="normal", worker_alive=True) == "kill_switch"

    for belt in ("emergency", "defensive", "caution"):
        state = SystemState(id=True, worker_last_heartbeat=NOW, trading_enabled=True)
        assert compute_autonomous_status(state, safety_belt_level=belt, worker_alive=True) == belt

    paused = SystemState(id=True, worker_last_heartbeat=NOW, trading_enabled=True, trading_paused=True)
    assert compute_autonomous_status(paused, safety_belt_level="normal", worker_alive=True) == "paused"


def test_record_system_health_snapshot_persists_a_row(db_session):
    record_heartbeat(db_session)
    snapshot = record_system_health_snapshot(db_session, cadence_failures={"news": 1})

    assert snapshot.autonomous_status == "running"
    assert snapshot.trading_mode == "paper"
    assert snapshot.cadence_failures == {"news": 1}
    assert db_session.query(SystemHealth).count() == 1


def test_record_worker_restart_does_not_trigger_below_the_limit(db_session):
    for _ in range(3):
        triggered = record_worker_restart(db_session, max_restarts=5, window_seconds=3600)
        assert not triggered
    state = db_session.get(SystemState, True)
    assert state.worker_restart_count == 3
    assert not state.trading_paused


def test_record_worker_restart_triggers_crash_loop_protection_over_the_limit(db_session):
    for _ in range(6):
        triggered = record_worker_restart(db_session, max_restarts=5, window_seconds=3600)
    assert triggered  # the 6th call crosses max_restarts=5
    state = db_session.get(SystemState, True)
    assert state.trading_paused
    assert "crash_loop_protection" in state.paused_reason
    assert db_session.query(TradingEvent).filter(TradingEvent.event_type == "crash_loop_protection_triggered").count() == 1


def test_record_worker_restart_resets_the_window_after_it_expires(db_session):
    db_session.add(SystemState(id=True, restart_window_started_at=NOW - timedelta(hours=2), worker_restart_count=10))
    db_session.commit()

    record_worker_restart(db_session, max_restarts=5, window_seconds=3600)  # window (1h) has long expired

    state = db_session.get(SystemState, True)
    assert state.worker_restart_count == 1  # window reset, not 11
    assert not state.trading_paused
