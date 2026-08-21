"""apps/worker/capital_defense.py -- "PROMPT 12" §107-108: the periodic
AdvancedRiskEngine cadence, its RiskAssessment persistence, SystemState
flag sync, and escalation/de-escalation alerting."""
from __future__ import annotations

from datetime import datetime, timezone

from apps.worker.capital_defense import run_capital_defense_cycle
from packages.portfolio.state import refresh_snapshot
from packages.shared.models import Alert, Order, RiskAssessment, SystemState

_NOW = datetime.now(timezone.utc)


def _healthy_system_state(db_session) -> SystemState:
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.trading_enabled = True
    state.trading_paused = False
    state.safety_belt_level = "normal"
    state.worker_last_heartbeat = _NOW
    db_session.add(state)
    db_session.commit()
    return state


def test_cycle_persists_a_risk_assessment_row(db_session):
    _healthy_system_state(db_session)
    n_before = db_session.query(RiskAssessment).count()

    run_capital_defense_cycle(db_session)

    n_after = db_session.query(RiskAssessment).count()
    assert n_after == n_before + 1
    latest = db_session.query(RiskAssessment).order_by(RiskAssessment.id.desc()).first()
    assert latest.risk_state == "normal"
    assert latest.capital_preservation_mode is False
    assert latest.zero_trade_mode is False


def test_cycle_syncs_system_state_flags(db_session):
    state = _healthy_system_state(db_session)
    assert state.capital_preservation_mode is False
    assert state.zero_trade_mode is False

    refresh_snapshot(db_session, cash=1_000_000.0)
    refresh_snapshot(db_session, cash=15_000.0)  # deep drawdown -> EMERGENCY

    run_capital_defense_cycle(db_session)

    db_session.refresh(state)
    assert state.capital_preservation_mode is True
    assert state.zero_trade_mode is True


def test_cycle_raises_alert_on_fresh_escalation(db_session):
    _healthy_system_state(db_session)
    n_alerts_before = db_session.query(Alert).filter(Alert.category == "risk").count()

    for _ in range(10):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="rejected", is_paper=True))
    db_session.commit()

    run_capital_defense_cycle(db_session)

    alerts = db_session.query(Alert).filter(Alert.category == "risk").order_by(Alert.id.desc()).all()
    assert len(alerts) == n_alerts_before + 1
    assert "escalated" in alerts[0].message


def test_cycle_does_not_re_alert_while_already_elevated(db_session):
    _healthy_system_state(db_session)
    for _ in range(10):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="rejected", is_paper=True))
    db_session.commit()

    run_capital_defense_cycle(db_session)
    n_alerts_after_first = db_session.query(Alert).filter(Alert.category == "risk").count()

    run_capital_defense_cycle(db_session)  # still elevated, same reason
    n_alerts_after_second = db_session.query(Alert).filter(Alert.category == "risk").count()

    assert n_alerts_after_second == n_alerts_after_first


def test_cycle_raises_info_alert_when_returning_to_normal(db_session):
    _healthy_system_state(db_session)
    for _ in range(10):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="rejected", is_paper=True))
    db_session.commit()
    run_capital_defense_cycle(db_session)  # escalates

    # Clear the rejected orders' effect by making the recent-orders window
    # clean again (new, successful orders push the rejected ones out of the
    # execution risk lookback).
    for _ in range(60):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="filled", slippage_bps=1.0, is_paper=True))
    db_session.commit()

    run_capital_defense_cycle(db_session)

    latest_alert = db_session.query(Alert).filter(Alert.category == "risk").order_by(Alert.id.desc()).first()
    assert latest_alert is not None
    assert latest_alert.severity == "info"
    assert "lifted" in latest_alert.message
