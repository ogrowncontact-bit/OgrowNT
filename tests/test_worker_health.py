from datetime import datetime, timedelta, timezone

from packages.shared.models import SystemState
from packages.shared.worker_health import is_heartbeat_stale, record_heartbeat

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
