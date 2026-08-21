"""packages/risk/advanced_engine.py -- "PROMPT 12" §1-15: the
AdvancedRiskEngine's RiskScore/RiskState aggregation, priority hierarchy,
and fail-closed behavior."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from packages.portfolio.state import refresh_snapshot
from packages.risk import advanced_engine
from packages.risk.advanced_engine import _WEIGHTS, assess_portfolio_risk
from packages.risk.capital_state import CRITICAL, EMERGENCY, HALTED, HIGH_RISK, NORMAL, RISK_STATES
from packages.risk.config import load_risk_limits
from packages.shared.models import Order, SystemState

LIMITS = load_risk_limits()
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


def test_weights_sum_to_one():
    assert round(sum(_WEIGHTS.values()), 6) == 1.0


def test_all_clear_portfolio_is_normal_risk_state(db_session):
    _healthy_system_state(db_session)
    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)

    assert assessment.risk_state == NORMAL
    assert assessment.degraded is False
    assert assessment.capital_preservation_mode is False
    assert assessment.zero_trade_mode is False
    assert assessment.risk_score < 20.0


def test_risk_score_is_zero_when_every_dimension_is_normal(db_session):
    _healthy_system_state(db_session)
    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state == NORMAL
    assert assessment.risk_score == 0.0


def test_risk_score_is_a_genuine_weighted_blend_not_a_mirror_of_risk_state(db_session):
    """risk_score must NOT be floored at severity(risk_state) for the
    ordinary (non-breaker) escalation path -- weights sum to 1.0 and no
    dimension's severity can exceed the max dimension's own severity, so a
    floor there would make the weighted blend mathematically unreachable,
    silently turning the "composite indicator of risk conditions" (see
    module docstring, §9) into nothing more than a copy of risk_state.
    A single CAUTION-only dimension (loss streak, weight 0.10) must score
    well below severity("caution") -- proving the blend, not a floor, is
    what's actually reported."""
    from packages.shared.models import Asset, Position, StrategyRow, Trade

    _healthy_system_state(db_session)
    asset = Asset(symbol="ADVRISK_BLEND", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="advrisk_blend_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    for i in range(5):
        position = Position(
            asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
            size=1.0, status="closed", closed_at=_NOW - timedelta(minutes=5 - i),
        )
        db_session.add(position)
        db_session.commit()
        db_session.add(Trade(position_id=position.id, pnl=-10.0, outcome="loss", closed_at=_NOW - timedelta(minutes=5 - i)))
        db_session.commit()

    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state == "caution"
    severity_of_caution = RISK_STATES.index("caution") / (len(RISK_STATES) - 1) * 100
    assert assessment.risk_score < severity_of_caution


def test_risk_score_is_floored_at_the_breakers_own_severity_when_one_trips(db_session):
    """Unlike the smooth dimension blend above, a TRIPPED circuit breaker
    is a discrete, structural severity that the weighted blend could
    otherwise understate (e.g. a kill switch tripped for a reason none of
    the 7 named dimensions individually reflect) -- so this path DOES
    floor at the breaker's own severity."""
    state = _healthy_system_state(db_session)
    state.trading_enabled = False
    db_session.add(state)
    db_session.commit()

    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state == HALTED
    assert assessment.risk_score == 100.0  # severity(HALTED) == 100, the top of the scale


def test_deep_drawdown_escalates_to_emergency_and_capital_preservation(db_session):
    _healthy_system_state(db_session)
    # A severe peak-to-current equity collapse -- well past DD_LEVEL_5's 15%
    # threshold (config/risk_limits.yaml).
    refresh_snapshot(db_session, cash=1_000_000.0)
    refresh_snapshot(db_session, cash=15_000.0)

    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state == EMERGENCY
    assert assessment.drawdown is not None and assessment.drawdown.level == 5
    assert assessment.capital_preservation_mode is True
    assert assessment.zero_trade_mode is True


def test_kill_switch_tripped_forces_halted_regardless_of_drawdown(db_session):
    state = _healthy_system_state(db_session)
    state.trading_enabled = False
    db_session.add(state)
    db_session.commit()

    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state == HALTED
    assert any("circuit breaker" in r for r in assessment.reasons)


def test_execution_breaker_alone_forces_emergency_not_halted(db_session):
    """"PROMPT 12": only the system/portfolio breakers can reach HALTED --
    an execution-only problem is maximally severe (EMERGENCY) but doesn't
    imply the whole system must stop (positions may still need managing)."""
    _healthy_system_state(db_session)
    for _ in range(10):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="rejected", is_paper=True))
    db_session.commit()

    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state == EMERGENCY
    assert assessment.risk_state != HALTED


def test_fail_closed_when_a_dimension_computation_raises(db_session):
    _healthy_system_state(db_session)
    with patch.object(advanced_engine, "compute_capital_state", side_effect=RuntimeError("simulated DB failure")):
        assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)

    assert assessment.degraded is True
    assert assessment.risk_state == HALTED  # a failed dimension fails closed, never silently "safe"
    assert any("capital/drawdown assessment failed" in r for r in assessment.reasons)


def test_capital_preservation_mode_threshold_matches_high_risk_state(db_session):
    """capital_preservation_mode/zero_trade_mode are pure functions of the
    final risk_state, not a separately-drifting computation -- this asserts
    the documented threshold (HIGH_RISK+ => capital preservation,
    CRITICAL+ => zero trade) directly against the RISK_STATES ordering."""
    assert RISK_STATES.index(HIGH_RISK) < RISK_STATES.index(CRITICAL)
    _healthy_system_state(db_session)
    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    expected_preservation = RISK_STATES.index(assessment.risk_state) >= RISK_STATES.index(HIGH_RISK)
    expected_zero_trade = RISK_STATES.index(assessment.risk_state) >= RISK_STATES.index(CRITICAL)
    assert assessment.capital_preservation_mode == expected_preservation
    assert assessment.zero_trade_mode == expected_zero_trade


@pytest.mark.parametrize("missing_state", [True, False])
def test_missing_system_state_row_does_not_crash(db_session, missing_state):
    # No _healthy_system_state() call -- exercises the "no system_state row
    # yet" honest-degradation path some sub-assessments handle explicitly.
    if not missing_state:
        _healthy_system_state(db_session)
    assessment = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert assessment.risk_state in RISK_STATES
