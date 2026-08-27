"""packages/system/health_score.py -- "PROMPT 14" §116-119."""
from __future__ import annotations

from packages.shared.models import SystemState
from packages.system.health_score import CAUTION, DEGRADED, HALTED, NOT_READY, READY, compute_system_health_score


def test_all_green_components_and_normal_trading_state_scores_ready(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, trading_paused=False, safety_belt_level="normal"))
    db_session.commit()
    result = compute_system_health_score(
        db_session, component_health={"database": "green", "worker": "green", "market_data": "green", "risk_engine": "green", "ai_services": "green"}
    )
    assert result.score == 100.0
    assert result.readiness_state == READY
    assert result.reasons == []


def test_database_red_forces_halted_regardless_of_score(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, trading_paused=False, safety_belt_level="normal"))
    db_session.commit()
    result = compute_system_health_score(db_session, component_health={"database": "red", "worker": "green"})
    assert result.readiness_state == HALTED


def test_kill_switch_triggered_forces_halted(db_session):
    db_session.add(SystemState(id=True, trading_enabled=False, trading_paused=False, safety_belt_level="kill_switch"))
    db_session.commit()
    result = compute_system_health_score(db_session, component_health={"database": "green", "worker": "green"})
    assert result.readiness_state == HALTED
    assert any("kill switch" in r for r in result.reasons)


def test_trading_paused_degrades_score_and_reports_the_reason(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, trading_paused=True, paused_reason="reconciliation mismatch", safety_belt_level="normal"))
    db_session.commit()
    result = compute_system_health_score(db_session, component_health={"database": "green", "worker": "green"})
    assert result.readiness_state in (CAUTION, DEGRADED)
    assert any("reconciliation mismatch" in r for r in result.reasons)


def test_red_component_lowers_score_and_is_reported(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, trading_paused=False, safety_belt_level="normal"))
    db_session.commit()
    result = compute_system_health_score(db_session, component_health={"database": "green", "worker": "red"})
    assert result.score < 100.0
    assert any("worker" in r for r in result.reasons)


def test_no_system_state_row_defaults_to_healthy_trading_state(db_session):
    """A fresh test DB has no SystemState row yet -- the score must never
    crash on a missing row, and must not fabricate a paused/halted claim."""
    result = compute_system_health_score(db_session, component_health={"database": "green", "worker": "green"})
    assert result.readiness_state == READY


def test_score_below_40_is_not_ready(db_session):
    db_session.add(SystemState(id=True, trading_enabled=True, trading_paused=False, safety_belt_level="emergency"))
    db_session.commit()
    result = compute_system_health_score(
        db_session, component_health={"database": "yellow", "worker": "red", "market_data": "red", "risk_engine": "red", "ai_services": "red"}
    )
    assert result.readiness_state in (NOT_READY, DEGRADED, HALTED)
