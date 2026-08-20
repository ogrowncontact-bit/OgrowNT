"""Prompt 4 §37 — full mathematically-validated Risk Engine simulation:
EUR 10,000 -> a losing streak -> risk state escalates (NORMAL -> DEFENSIVE ->
EMERGENCY -> KILL_SWITCH) -> position size decreases as the belt tightens ->
the daily loss limit hard-blocks new trades -> the kill switch blocks
everything regardless of belt. Every number below is hand-derived from
packages/risk/position_sizing.py's formula and config/risk_limits.yaml's
real (not hand-rolled) limits, not just asserted against the engine's own
output, so this genuinely checks the math, not just internal consistency.
"""
from datetime import datetime, timezone

import pytest

from packages.portfolio.state import PortfolioState
from packages.risk.config import load_risk_limits
from packages.risk.engine import SignalForRisk, evaluate_signal
from packages.risk.safety_belt import EMERGENCY, KILL_SWITCH, NORMAL, evaluate_safety_belt, should_trigger_kill_switch
from packages.shared.models import Asset, Signal, StrategyRow, SystemState

STARTING_EQUITY = 10_000.0
LIMITS = load_risk_limits()  # the real config/risk_limits.yaml, not a hand-rolled stand-in


def _now() -> datetime:
    # Computed fresh on every call, never once at module import time -- a
    # module-level constant here would drift stale (relative to
    # config/risk_limits.yaml's max_staleness_seconds=120) on a slow full-
    # suite run, since this test isn't necessarily the first to execute.
    return datetime.now(timezone.utc)


def _state(**overrides) -> PortfolioState:
    base = dict(
        ts=_now(), cash=STARTING_EQUITY, equity=STARTING_EQUITY, exposure_pct=0.0,
        daily_pnl=0.0, daily_loss_pct=0.0, weekly_pnl=0.0, weekly_loss_pct=0.0,
        monthly_pnl=0.0, monthly_loss_pct=0.0, drawdown_pct=0.0, unrealized_pnl=0.0, open_positions=[],
    )
    base.update(overrides)
    return PortfolioState(**base)


def _signal(db_session, asset) -> SignalForRisk:
    strategy = db_session.query(StrategyRow).filter(StrategyRow.code == "simulation_strategy").first()
    if strategy is None:
        strategy = StrategyRow(code="simulation_strategy", name="Simulation", family="trend", version="1.0")
        db_session.add(strategy)
        db_session.commit()
    now = _now()
    signal_row = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=now, direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()
    return SignalForRisk(
        signal_id=signal_row.id, asset_id=asset.id, strategy_id=strategy.id, direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, risk_reward=3.0, confidence=1.0,
        volatility_factor=1.0, data_quality="high", data_ts=now, tier="high_quality", asset_class=asset.asset_class,
    )


def test_full_drawdown_simulation_math(db_session):
    trading_on = SystemState(id=True, trading_enabled=True)

    # --- Step 1: NORMAL belt, clean equity, full-size approval -------------
    # Hand-derived from packages/risk/position_sizing.py's formula with the
    # real config/risk_limits.yaml values (per_trade.max_risk_pct=1.0,
    # portfolio.max_single_asset_pct=15, entry=100, stop=95):
    #   risk_budget          = 10000 * 1.0/100                = 100
    #   stop_distance_pct    = |100-95| / 100                 = 0.05
    #   raw_notional         = 100 / 0.05                     = 2000   (risk_budget cap, post confidence/vol)
    #   single_asset_cap     = 10000 * 15/100                 = 1500   <- binding (smallest cap)
    #   quantity             = 1500 / 100                     = 15.0 units
    asset = Asset(symbol="SIMDRAWDOWN", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    baseline_state = _state()
    assert evaluate_safety_belt(baseline_state, LIMITS) == NORMAL

    baseline = evaluate_signal(db_session, _signal(db_session, asset), baseline_state, trading_on, LIMITS)
    assert baseline.approved
    assert baseline.safety_belt_level == NORMAL
    assert baseline.approved_quantity == pytest.approx(15.0)

    # --- Step 2: a losing streak drags daily_loss_pct into the DEFENSIVE
    # warning zone (>= 0.7 * max_daily_loss_pct = 2.1%, still below the 3%
    # hard block) -- size must shrink by exactly the DEFENSIVE multiplier
    # from config/risk_limits.yaml's safety_belt_multipliers.defensive (0.5),
    # equity held constant so this isolates the multiplier's effect.
    defensive_state = _state(daily_loss_pct=2.5)
    assert evaluate_safety_belt(defensive_state, LIMITS) == "defensive"

    reduced = evaluate_signal(db_session, _signal(db_session, asset), defensive_state, trading_on, LIMITS)
    assert reduced.approved  # DEFENSIVE reduces size, does not block outright
    assert reduced.safety_belt_level == "defensive"
    expected_defensive_multiplier = LIMITS.safety_belt_multipliers.defensive
    assert expected_defensive_multiplier == 0.5
    assert reduced.approved_quantity == pytest.approx(baseline.approved_quantity * expected_defensive_multiplier)
    assert reduced.approved_quantity < baseline.approved_quantity

    # --- Step 3: the loss continues to the hard daily loss limit (>= 3%) --
    # new trades are blocked outright, not just reduced.
    blocked_daily_state = _state(daily_loss_pct=3.5)
    blocked_daily = evaluate_signal(db_session, _signal(db_session, asset), blocked_daily_state, trading_on, LIMITS)
    assert not blocked_daily.approved
    assert blocked_daily.reason == "daily_loss_limit"
    assert blocked_daily.approved_quantity is None

    # --- Step 4: drawdown reaches the EMERGENCY threshold (15%) -- belt
    # escalates further, blocking everything below "exceptional" tier.
    emergency_state = _state(drawdown_pct=LIMITS.loss_limits.max_portfolio_drawdown_pct)
    assert evaluate_safety_belt(emergency_state, LIMITS) == EMERGENCY
    blocked_emergency = evaluate_signal(db_session, _signal(db_session, asset), emergency_state, trading_on, LIMITS)
    assert not blocked_emergency.approved
    assert blocked_emergency.reason == "safety_belt_emergency"

    # --- Step 5: drawdown deteriorates further to 1.5x the EMERGENCY
    # threshold -- the Kill Switch auto-trigger condition (packages/risk/
    # monitor.py calls should_trigger_kill_switch every worker cycle and, if
    # true, sets system_state.trading_enabled=False). Once that happens, the
    # Risk Engine blocks every signal regardless of belt or tier -- the
    # single hard override the whole system defers to.
    kill_switch_state = _state(drawdown_pct=LIMITS.loss_limits.max_portfolio_drawdown_pct * 1.5)
    assert should_trigger_kill_switch(kill_switch_state, LIMITS)

    trading_halted = SystemState(id=True, trading_enabled=False)
    blocked_kill_switch = evaluate_signal(
        db_session, _signal(db_session, asset), kill_switch_state, trading_halted, LIMITS
    )
    assert not blocked_kill_switch.approved
    assert blocked_kill_switch.reason == "kill_switch"

    # --- Loss Recovery Rule: drawdown increasing must never increase risk,
    # only decrease it. Walk the belt's size multiplier across the whole
    # escalation above and confirm it is monotonically non-increasing.
    multipliers_by_drawdown = [
        (0.0, NORMAL, LIMITS.safety_belt_multipliers.normal),
        (LIMITS.loss_limits.max_portfolio_drawdown_pct, EMERGENCY, LIMITS.safety_belt_multipliers.emergency),
        (LIMITS.loss_limits.max_portfolio_drawdown_pct * 1.5, KILL_SWITCH, LIMITS.safety_belt_multipliers.kill_switch),
    ]
    for i in range(1, len(multipliers_by_drawdown)):
        prev_drawdown, _, prev_multiplier = multipliers_by_drawdown[i - 1]
        drawdown, _, multiplier = multipliers_by_drawdown[i]
        assert drawdown > prev_drawdown
        assert multiplier <= prev_multiplier, "drawdown increased but risk multiplier did not decrease"
