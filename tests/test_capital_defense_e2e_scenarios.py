"""Advanced Risk & Capital Defense Engine end-to-end scenarios -- "PROMPT
12" §133-136. Four realistic, multi-step simulations exercising the full
pipeline (AdvancedRiskEngine -> evaluate_signal / circuit breakers /
kill-switch recovery) the way apps/worker actually wires it, not just the
individual unit-level behavior each module's own test file already covers.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.portfolio.state import PortfolioState, refresh_snapshot
from packages.risk import circuit_breakers as cb
from packages.risk.advanced_engine import assess_portfolio_risk
from packages.risk.capital_state import EMERGENCY, HALTED, NORMAL
from packages.risk.config import load_risk_limits
from packages.risk.engine import SignalForRisk, evaluate_signal
from packages.shared.models import Asset, CorrelationMatrixEntry, Order, Position, Signal, StrategyRow, SystemState

LIMITS = load_risk_limits()
_NOW = datetime.now(timezone.utc)


def _healthy_system_state(db_session, *, now: datetime | None = None) -> SystemState:
    now = now or _NOW
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.trading_enabled = True
    state.trading_paused = False
    state.safety_belt_level = "normal"
    state.worker_last_heartbeat = now
    db_session.add(state)
    db_session.commit()
    return state


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _signal_for_risk(db_session, asset: Asset, strategy: StrategyRow, **overrides) -> SignalForRisk:
    now = _NOW
    signal_row = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=now, direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="scored",
    )
    db_session.add(signal_row)
    db_session.commit()
    base = dict(
        signal_id=signal_row.id, asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        stop_price=95.0, target_price=115.0, risk_reward=3.0, confidence=0.9, volatility_factor=1.0,
        data_quality="high", data_ts=now, tier="high_quality", asset_class=asset.asset_class,
    )
    base.update(overrides)
    return SignalForRisk(**base)


def _portfolio_state(**overrides) -> PortfolioState:
    base = dict(
        ts=_NOW, cash=10000, equity=10000, exposure_pct=0.0, daily_pnl=0.0, daily_loss_pct=0.0, weekly_pnl=0.0,
        weekly_loss_pct=0.0, monthly_pnl=0.0, monthly_loss_pct=0.0, drawdown_pct=0.0, unrealized_pnl=0.0,
        open_positions=[],
    )
    base.update(overrides)
    return PortfolioState(**base)


# -- Scenario A: deep drawdown -> capital preservation -> zero-trade -> recovers via cooldown hysteresis


def test_scenario_a_deep_drawdown_blocks_new_trades_then_recovers(db_session):
    _healthy_system_state(db_session)
    asset = Asset(symbol="E2EA_ASSET", asset_class="crypto", is_active=True)
    strategy = _strategy(db_session, "e2ea_strategy")
    db_session.add(asset)
    db_session.commit()

    # 1. A severe peak-to-current equity collapse -- past DD_LEVEL_5 (15%).
    refresh_snapshot(db_session, cash=1_000_000.0)
    refresh_snapshot(db_session, cash=800_000.0)

    advanced_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert advanced_risk.risk_state == EMERGENCY
    assert advanced_risk.zero_trade_mode is True

    # 2. A brand-new, otherwise-clean signal is still blocked -- capital
    # preservation doesn't care how good this particular opportunity looks.
    sfr = _signal_for_risk(db_session, asset, strategy)
    verdict = evaluate_signal(
        db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True), advanced_risk=advanced_risk,
    )
    assert not verdict.approved
    assert verdict.reason == "advanced_risk_zero_trade_mode"

    # 3. Recovery: equity genuinely comes back AND enough time passes (a
    # `now` beyond the recovery.cooldown_minutes window) that the old
    # severe-drawdown snapshots no longer count toward the effective,
    # cooldown-adjusted drawdown -- the SAME hysteresis every DrawdownEngine
    # unit test exercises (test_capital_state.py), now proven end-to-end
    # through the full assessment + evaluate_signal pipeline.
    later = _NOW + timedelta(minutes=LIMITS.recovery.cooldown_minutes + 5)
    refresh_snapshot(db_session, cash=1_050_000.0)  # equity genuinely recovers
    _healthy_system_state(db_session, now=later)  # the worker kept heartbeating throughout

    recovered_risk = assess_portfolio_risk(db_session, LIMITS, now=later)
    assert recovered_risk.risk_state == NORMAL
    assert recovered_risk.zero_trade_mode is False

    sfr2 = _signal_for_risk(db_session, asset, strategy)
    verdict2 = evaluate_signal(
        db_session, sfr2, _portfolio_state(), SystemState(id=True, trading_enabled=True), advanced_risk=recovered_risk,
    )
    assert verdict2.approved


# -- Scenario B: kill switch trips -> HALTED -> admin-only recovery flow -> back to NORMAL


def test_scenario_b_kill_switch_trip_and_admin_recovery_flow(db_session):
    _healthy_system_state(db_session)
    asset = Asset(symbol="E2EB_ASSET", asset_class="crypto", is_active=True)
    strategy = _strategy(db_session, "e2eb_strategy")
    db_session.add(asset)
    db_session.commit()

    # 1. The kill switch trips (e.g. an automatic safety-belt-driven trigger).
    cb.trigger_kill_switch(db_session, reason="scenario B: severe loss event", actor="system")
    tripped_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert tripped_risk.risk_state == HALTED

    # 2. Even a perfectly clean signal is blocked -- by the pre-existing
    # step-1 kill-switch gate, before advanced_risk is even consulted
    # (defense in depth: multiple independent layers agree).
    sfr = _signal_for_risk(db_session, asset, strategy)
    state = db_session.get(SystemState, True)
    verdict = evaluate_signal(db_session, sfr, _portfolio_state(), state, advanced_risk=tripped_risk)
    assert not verdict.approved
    assert verdict.reason == "kill_switch"

    # 3. Only an admin can begin recovery, and trading stays disabled
    # through the review step.
    recovering_state = cb.start_recovery(db_session, actor="admin@example.com")
    assert recovering_state.trading_enabled is False
    readiness = cb.check_recovery_readiness(db_session)
    assert readiness.ready is True  # worker heartbeat is healthy in this scenario

    # 4. Confirming recovery re-enables trading.
    confirmed_state = cb.confirm_recovery(db_session, actor="admin@example.com")
    assert confirmed_state.trading_enabled is True
    assert confirmed_state.kill_switch_state == cb.ARMED

    recovered_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert recovered_risk.risk_state == NORMAL

    sfr2 = _signal_for_risk(db_session, asset, strategy)
    verdict2 = evaluate_signal(
        db_session, sfr2, _portfolio_state(), db_session.get(SystemState, True), advanced_risk=recovered_risk,
    )
    assert verdict2.approved


# -- Scenario C: execution-quality collapse -> EMERGENCY (not HALTED) -> open positions untouched -> recovers


def test_scenario_c_execution_degradation_blocks_new_trades_without_forcing_position_closure(db_session):
    _healthy_system_state(db_session)
    asset = Asset(symbol="E2EC_ASSET", asset_class="crypto", is_active=True)
    strategy = _strategy(db_session, "e2ec_strategy")
    db_session.add(asset)
    db_session.commit()

    open_position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
        size=1.0, status="open",
    )
    db_session.add(open_position)
    db_session.commit()
    position_id = open_position.id

    # 1. A run of order rejections trips the execution circuit breaker.
    for _ in range(20):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="rejected", is_paper=True))
    db_session.commit()

    degraded_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert degraded_risk.risk_state == EMERGENCY
    assert degraded_risk.risk_state != HALTED  # execution alone never halts the whole system
    assert degraded_risk.zero_trade_mode is True

    # 2. A new signal is blocked...
    sfr = _signal_for_risk(db_session, asset, strategy)
    verdict = evaluate_signal(
        db_session, sfr, _portfolio_state(), SystemState(id=True, trading_enabled=True), advanced_risk=degraded_risk,
    )
    assert not verdict.approved

    # ...but the ALREADY-OPEN position is never force-closed or modified by
    # any of this -- capital preservation blocks NEW risk, it doesn't
    # reach into existing positions (that's PositionRiskPolicy's job, on a
    # different trigger).
    db_session.refresh(open_position)
    assert open_position.status == "open"
    assert open_position.current_stop == 95.0

    # 3. Recovery: a burst of clean fills pushes the rejected orders out of
    # the execution risk lookback window.
    for _ in range(60):
        db_session.add(Order(order_type="market", side="buy", qty=1.0, status="filled", slippage_bps=1.0, is_paper=True))
    db_session.commit()

    recovered_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert recovered_risk.risk_state == NORMAL

    sfr2 = _signal_for_risk(db_session, asset, strategy)
    verdict2 = evaluate_signal(
        db_session, sfr2, _portfolio_state(), SystemState(id=True, trading_enabled=True), advanced_risk=recovered_risk,
    )
    assert verdict2.approved
    assert db_session.get(Position, position_id).status == "open"  # still untouched


# -- Scenario D: several moderately-elevated dimensions stack into a higher RiskScore without exceeding
#    any single dimension's own severity cap on RiskState


def _closed_loss_trade(db_session, asset: Asset, strategy: StrategyRow, closed_at: datetime) -> None:
    from packages.shared.models import Trade

    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
        size=1.0, status="closed", closed_at=closed_at,
    )
    db_session.add(position)
    db_session.commit()
    db_session.add(Trade(position_id=position.id, pnl=-10.0, outcome="loss", closed_at=closed_at))
    db_session.commit()


def test_scenario_d_multiple_moderate_dimensions_stack_the_score_without_exceeding_the_state_cap(db_session):
    _healthy_system_state(db_session)
    strategy = _strategy(db_session, "e2ed_strategy")

    # Baseline: ONLY a portfolio-wide loss streak is elevated (5 consecutive
    # losses, config/risk_limits.yaml's default threshold).
    loss_asset = Asset(symbol="E2ED_LOSS", asset_class="crypto", is_active=True)
    db_session.add(loss_asset)
    db_session.commit()
    for i in range(5):
        _closed_loss_trade(db_session, loss_asset, strategy, _NOW - timedelta(minutes=5 - i))

    baseline_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)
    assert baseline_risk.risk_state == "caution"  # only loss_streak is elevated

    # Stack two MORE moderately-elevated dimensions on top, each individually
    # only reaching "caution" on its own severity scale: a DD_LEVEL_1
    # drawdown, and a moderate correlated-cluster concentration.
    refresh_snapshot(db_session, cash=1_000_000.0)
    refresh_snapshot(db_session, cash=960_000.0)  # 4% drawdown -> DD_LEVEL_1 ("caution")

    btc = Asset(symbol="E2ED_BTC", asset_class="crypto", is_active=True)
    eth = Asset(symbol="E2ED_ETH", asset_class="crypto", is_active=True)
    db_session.add_all([btc, eth])
    db_session.commit()
    db_session.add(CorrelationMatrixEntry(ts=_NOW, asset_id_a=btc.id, asset_id_b=eth.id, window_days=30, correlation=0.9))
    db_session.add(Position(asset_id=btc.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=6.0, status="open"))
    db_session.add(Position(asset_id=eth.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=6.0, status="open"))
    db_session.commit()

    stacked_risk = assess_portfolio_risk(db_session, LIMITS, now=_NOW)

    # The overall RiskState is still exactly "caution" -- no single new
    # dimension pushed past what the worst individual one already reached,
    # so the max-based aggregation correctly does NOT invent a more severe
    # state out of several moderate ones.
    assert stacked_risk.risk_state == "caution"
    # But the weighted RiskScore DOES reflect that three dimensions are
    # simultaneously elevated now instead of one -- proving the composite
    # score is a genuine aggregate, not just a mirror of the max state.
    assert stacked_risk.risk_score > baseline_risk.risk_score
