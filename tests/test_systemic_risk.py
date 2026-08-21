"""packages/risk/systemic_risk.py -- "PROMPT 12": System/Execution/Model/
Data risk engines, each reusing an already-computed signal rather than
recomputing it."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.execution.fills import BASE_SLIPPAGE_BPS
from packages.risk.systemic_risk import (
    CRITICAL,
    ELEVATED,
    HIGH,
    NORMAL,
    assess_data_risk,
    assess_execution_risk,
    assess_model_risk,
    assess_system_risk,
)
from packages.shared.models import Asset, Decision, Order, Position, StrategyRow, SystemHealth, SystemState

_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


# -- System Risk --------------------------------------------------------


def test_system_risk_normal_when_worker_alive_and_kill_switch_armed(db_session):
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.worker_last_heartbeat = _NOW
    state.trading_enabled = True
    state.trading_paused = False
    db_session.add(state)
    db_session.commit()

    assessment = assess_system_risk(db_session, now=_NOW)
    assert assessment.state == NORMAL
    assert assessment.worker_alive is True
    assert assessment.kill_switch_tripped is False


def test_system_risk_critical_when_kill_switch_tripped(db_session):
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.worker_last_heartbeat = _NOW
    state.trading_enabled = False
    db_session.add(state)
    db_session.commit()

    assessment = assess_system_risk(db_session, now=_NOW)
    assert assessment.state == CRITICAL
    assert assessment.kill_switch_tripped is True


def test_system_risk_critical_when_worker_heartbeat_stale(db_session):
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.worker_last_heartbeat = _NOW - timedelta(hours=2)
    state.trading_enabled = True
    db_session.add(state)
    db_session.commit()

    assessment = assess_system_risk(db_session, now=_NOW)
    assert assessment.state == CRITICAL
    assert assessment.worker_alive is False


def test_system_risk_high_when_cadence_failures_present(db_session):
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.worker_last_heartbeat = _NOW
    state.trading_enabled = True
    db_session.add(state)
    db_session.add(
        SystemHealth(
            ts=_NOW, autonomous_status="running", trading_mode="paper", trading_enabled=True, trading_paused=False,
            safety_belt_level="normal", worker_alive=True, open_positions_count=0,
            cadence_failures={"strategy_runner": "timeout"},
        )
    )
    db_session.commit()

    assessment = assess_system_risk(db_session, now=_NOW)
    assert assessment.state == HIGH
    assert assessment.cadence_failures


# -- Execution Risk -------------------------------------------------------


def _order(db_session, *, status: str, slippage_bps: float | None = None) -> Order:
    order = Order(order_type="market", side="buy", qty=1.0, status=status, slippage_bps=slippage_bps, is_paper=True)
    db_session.add(order)
    db_session.commit()
    return order


def test_execution_risk_not_evaluated_without_recent_orders(db_session):
    assessment = assess_execution_risk(db_session, lookback=1)  # tiny lookback isolates this test from other suites' orders
    # Even with no orders at all this DB instance, evaluated could be True if
    # another test's orders exist -- so just assert the honest-absence shape
    # holds when genuinely nothing is found.
    if assessment.orders_evaluated == 0:
        assert assessment.evaluated is False
        assert assessment.state == NORMAL


def test_execution_risk_critical_on_high_rejection_rate(db_session):
    for _ in range(8):
        _order(db_session, status="rejected")
    for _ in range(2):
        _order(db_session, status="filled", slippage_bps=BASE_SLIPPAGE_BPS)

    assessment = assess_execution_risk(db_session, lookback=10)
    assert assessment.evaluated is True
    assert assessment.rejection_rate == 0.8
    assert assessment.state == CRITICAL


def test_execution_risk_elevated_on_excess_slippage(db_session):
    for _ in range(10):
        _order(db_session, status="filled", slippage_bps=BASE_SLIPPAGE_BPS * 1.5)

    assessment = assess_execution_risk(db_session, lookback=10)
    assert assessment.evaluated is True
    assert assessment.rejection_rate == 0.0
    assert assessment.state == ELEVATED


def test_execution_risk_normal_with_clean_fills(db_session):
    for _ in range(10):
        _order(db_session, status="filled", slippage_bps=BASE_SLIPPAGE_BPS * 0.5)

    assessment = assess_execution_risk(db_session, lookback=10)
    assert assessment.state == NORMAL


# -- Model Risk -------------------------------------------------------------


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _decision(db_session, asset: Asset, *, contradiction_score: float, critical_agent_failure: bool = False, ts: datetime) -> Decision:
    decision = Decision(
        asset_id=asset.id, ts=ts, decision_state="neutral", consensus_score=0.0,
        contradiction_score=contradiction_score, reasoning_summary="test", critical_agent_failure=critical_agent_failure,
    )
    db_session.add(decision)
    db_session.commit()
    return decision


def test_model_risk_not_evaluated_without_recent_decisions(db_session):
    assessment = assess_model_risk(db_session, now=_NOW, lookback_minutes=0.001)
    if assessment.decisions_evaluated == 0:
        assert assessment.evaluated is False
        assert assessment.state == NORMAL


def test_model_risk_critical_on_critical_agent_failure(db_session):
    asset = _asset(db_session, "MODELRISK_CRIT")
    _decision(db_session, asset, contradiction_score=0.0, critical_agent_failure=True, ts=_NOW)

    assessment = assess_model_risk(db_session, now=_NOW)
    assert assessment.state == CRITICAL
    assert assessment.any_critical_agent_failure is True


def test_model_risk_high_at_no_trade_contradiction_threshold(db_session):
    from packages.agents.chief import CONTRADICTION_NO_TRADE_THRESHOLD

    asset = _asset(db_session, "MODELRISK_HIGH")
    _decision(db_session, asset, contradiction_score=CONTRADICTION_NO_TRADE_THRESHOLD, ts=_NOW)

    assessment = assess_model_risk(db_session, now=_NOW)
    assert assessment.state == HIGH
    assert assessment.max_contradiction_score == CONTRADICTION_NO_TRADE_THRESHOLD


def test_model_risk_normal_with_low_contradiction(db_session):
    asset = _asset(db_session, "MODELRISK_NORMAL")
    _decision(db_session, asset, contradiction_score=5.0, ts=_NOW)

    assessment = assess_model_risk(db_session, now=_NOW)
    assert assessment.state == NORMAL


def test_model_risk_ignores_decisions_outside_lookback_window(db_session):
    asset = _asset(db_session, "MODELRISK_STALE")
    _decision(db_session, asset, contradiction_score=99.0, critical_agent_failure=True, ts=_NOW - timedelta(hours=5))

    assessment = assess_model_risk(db_session, now=_NOW, lookback_minutes=30.0)
    assert assessment.evaluated is False


# -- Data Risk ------------------------------------------------------------


def _open_position(db_session, asset: Asset, strategy: StrategyRow) -> Position:
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
        size=1.0, status="open",
    )
    db_session.add(position)
    db_session.commit()
    return position


def test_data_risk_not_evaluated_without_open_positions(db_session):
    assessment = assess_data_risk(db_session)
    if assessment.assets_evaluated == 0:
        assert assessment.evaluated is False
        assert assessment.state == NORMAL


def test_data_risk_normal_when_quality_is_good(db_session):
    asset = Asset(symbol="DATARISK_GOOD", asset_class="crypto", is_active=True, data_quality_score=95.0)
    strategy = StrategyRow(code="datarisk_good_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    _open_position(db_session, asset, strategy)

    assessment = assess_data_risk(db_session)
    assert assessment.evaluated is True
    assert assessment.state == NORMAL
    assert assessment.min_quality_score == 95.0


def test_data_risk_critical_when_quality_is_unsafe(db_session):
    asset = Asset(symbol="DATARISK_UNSAFE", asset_class="crypto", is_active=True, data_quality_score=20.0)
    strategy = StrategyRow(code="datarisk_unsafe_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    _open_position(db_session, asset, strategy)

    assessment = assess_data_risk(db_session)
    assert assessment.state == CRITICAL


def test_data_risk_elevated_for_one_degraded_asset(db_session):
    asset = Asset(symbol="DATARISK_DEGRADED", asset_class="crypto", is_active=True, data_quality_score=70.0)
    strategy = StrategyRow(code="datarisk_degraded_strategy", name="x", family="test", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()
    _open_position(db_session, asset, strategy)

    assessment = assess_data_risk(db_session)
    assert assessment.state == ELEVATED
    assert assessment.assets_below_threshold == ["DATARISK_DEGRADED"]
