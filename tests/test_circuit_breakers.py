"""packages/risk/circuit_breakers.py -- "PROMPT 12" §61-69: the 6 named
circuit breakers and the Emergency Kill Switch state machine."""
from __future__ import annotations

import pytest

from packages.risk.circuit_breakers import (
    ARMED,
    LOCKED,
    RECOVERY,
    asset_breaker_status,
    check_recovery_readiness,
    confirm_recovery,
    portfolio_breaker_status,
    portfolio_wide_breaker_statuses,
    start_recovery,
    strategy_breaker_status,
    system_breaker_status,
    trigger_kill_switch,
)
from packages.shared.models import Asset, StrategyRow, SystemState


def _state(db_session) -> SystemState:
    state = db_session.get(SystemState, True) or SystemState(id=True)
    db_session.add(state)
    db_session.commit()
    return state


# -- Individual breakers --------------------------------------------------


def test_system_breaker_not_tripped_when_trading_enabled(db_session):
    state = _state(db_session)
    state.trading_enabled = True
    db_session.add(state)
    db_session.commit()
    assert system_breaker_status(db_session).tripped is False


def test_system_breaker_tripped_when_kill_switch_off(db_session):
    state = _state(db_session)
    state.trading_enabled = False
    db_session.add(state)
    db_session.commit()
    status = system_breaker_status(db_session)
    assert status.tripped is True
    assert "kill switch" in status.reason


def test_portfolio_breaker_tripped_at_emergency_safety_belt(db_session):
    state = _state(db_session)
    state.safety_belt_level = "emergency"
    db_session.add(state)
    db_session.commit()
    status = portfolio_breaker_status(db_session)
    assert status.tripped is True


def test_portfolio_breaker_not_tripped_at_normal_safety_belt(db_session):
    state = _state(db_session)
    state.safety_belt_level = "normal"
    db_session.add(state)
    db_session.commit()
    assert portfolio_breaker_status(db_session).tripped is False


def test_strategy_breaker_tripped_when_quarantined(db_session):
    strategy = StrategyRow(code="breaker_quarantined", name="x", family="test", version="1.0", lifecycle_stage="quarantine")
    db_session.add(strategy)
    db_session.commit()
    status = strategy_breaker_status(db_session, strategy.id)
    assert status.tripped is True
    assert status.scope_id == strategy.id


def test_strategy_breaker_not_tripped_when_active(db_session):
    strategy = StrategyRow(code="breaker_active", name="x", family="test", version="1.0", lifecycle_stage="paper")
    db_session.add(strategy)
    db_session.commit()
    assert strategy_breaker_status(db_session, strategy.id).tripped is False


def test_asset_breaker_tripped_when_quarantined(db_session):
    asset = Asset(symbol="BREAKER_QUARANTINED", asset_class="crypto", status="quarantined")
    db_session.add(asset)
    db_session.commit()
    status = asset_breaker_status(db_session, asset.id)
    assert status.tripped is True
    assert status.scope_id == asset.id


def test_asset_breaker_not_tripped_when_active(db_session):
    asset = Asset(symbol="BREAKER_ACTIVE", asset_class="crypto", status="active")
    db_session.add(asset)
    db_session.commit()
    assert asset_breaker_status(db_session, asset.id).tripped is False


def test_portfolio_wide_breaker_statuses_returns_four_breakers(db_session):
    _state(db_session)
    statuses = portfolio_wide_breaker_statuses(db_session)
    assert {s.name for s in statuses} == {"system", "portfolio", "execution", "data"}


# -- Emergency Kill Switch state machine -----------------------------------


def test_new_system_state_starts_armed(db_session):
    state = _state(db_session)
    assert state.kill_switch_state == ARMED


def test_trigger_kill_switch_locks_and_disables_trading(db_session):
    _state(db_session)
    state = trigger_kill_switch(db_session, reason="test trip", actor="system")
    assert state.kill_switch_state == LOCKED
    assert state.trading_enabled is False
    assert state.recovery_mode is False


def test_start_recovery_requires_locked_state(db_session):
    _state(db_session)  # still ARMED, never triggered
    with pytest.raises(ValueError, match="LOCKED"):
        start_recovery(db_session, actor="admin@example.com")


def test_start_recovery_transitions_to_recovery_mode(db_session):
    _state(db_session)
    trigger_kill_switch(db_session, reason="test trip", actor="system")
    state = start_recovery(db_session, actor="admin@example.com")
    assert state.kill_switch_state == RECOVERY
    assert state.recovery_mode is True
    assert state.trading_enabled is False  # still disabled -- recovery isn't confirmed yet


def test_confirm_recovery_requires_recovery_state(db_session):
    _state(db_session)  # ARMED, never triggered
    with pytest.raises(ValueError, match="RECOVERY"):
        confirm_recovery(db_session, actor="admin@example.com")


def test_confirm_recovery_re_enables_trading_when_healthy(db_session):
    state = _state(db_session)
    state.worker_last_heartbeat = None  # avoid staleness math needing a real clock in this unit test
    db_session.add(state)
    db_session.commit()
    trigger_kill_switch(db_session, reason="test trip", actor="system")
    start_recovery(db_session, actor="admin@example.com")

    readiness = check_recovery_readiness(db_session)
    assert readiness.ready is False  # worker heartbeat missing -- honestly not ready
    with pytest.raises(ValueError, match="readiness check failed"):
        confirm_recovery(db_session, actor="admin@example.com")

    final = confirm_recovery(db_session, actor="admin@example.com", force=True)
    assert final.kill_switch_state == ARMED
    assert final.trading_enabled is True
    assert final.recovery_mode is False


def test_full_trigger_recovery_confirm_cycle_with_healthy_worker(db_session):
    import datetime as dt

    state = _state(db_session)
    state.worker_last_heartbeat = dt.datetime.now(dt.timezone.utc)
    db_session.add(state)
    db_session.commit()

    trigger_kill_switch(db_session, reason="test trip", actor="system")
    start_recovery(db_session, actor="admin@example.com")
    readiness = check_recovery_readiness(db_session)
    assert readiness.ready is True

    final = confirm_recovery(db_session, actor="admin@example.com")
    assert final.kill_switch_state == ARMED
    assert final.trading_enabled is True
