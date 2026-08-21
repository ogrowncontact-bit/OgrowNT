"""packages/risk/stress.py -- "PROMPT 12" §77-84: live-portfolio stress
testing (reusing packages/backtest's Monte Carlo/Risk of Ruin) and
historical-simulation VaR/CVaR."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.risk.stress import (
    MIN_RETURNS_FOR_VAR,
    MIN_TRADES_FOR_STRESS_TEST,
    compute_value_at_risk,
    run_live_stress_test,
)
from packages.shared.models import Asset, PortfolioSnapshot, Position, StrategyRow, Trade

_START = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _closed_trade(db_session, asset: Asset, strategy: StrategyRow, pnl: float, closed_at: datetime) -> Trade:
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0,
        size=1.0, status="closed", closed_at=closed_at,
    )
    db_session.add(position)
    db_session.commit()
    outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
    trade = Trade(position_id=position.id, pnl=pnl, outcome=outcome, closed_at=closed_at)
    db_session.add(trade)
    db_session.commit()
    return trade


def test_stress_test_reports_insufficient_history_below_minimum_trades(db_session):
    asset = Asset(symbol="STRESS_FEW", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session, "stress_few_strategy")
    for i in range(MIN_TRADES_FOR_STRESS_TEST - 1):
        _closed_trade(db_session, asset, strategy, 10.0, _START + timedelta(minutes=i))

    result = run_live_stress_test(db_session, initial_capital=10000.0)
    assert result.sufficient_history is False
    assert result.monte_carlo is None
    assert result.risk_of_ruin is None


def test_stress_test_runs_monte_carlo_once_enough_trades_exist(db_session):
    asset = Asset(symbol="STRESS_ENOUGH", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session, "stress_enough_strategy")
    for i in range(MIN_TRADES_FOR_STRESS_TEST + 5):
        pnl = 20.0 if i % 2 == 0 else -10.0
        _closed_trade(db_session, asset, strategy, pnl, _START + timedelta(minutes=i))

    result = run_live_stress_test(
        db_session, initial_capital=10000.0, method="bootstrap", num_simulations=100, random_seed=1,
        drawdown_threshold_pct=5.0,
    )
    assert result.sufficient_history is True
    assert result.trades_used == MIN_TRADES_FOR_STRESS_TEST + 5
    assert result.monte_carlo is not None
    assert result.monte_carlo.num_simulations == 100
    assert result.risk_of_ruin is not None  # drawdown_threshold_pct was given
    assert result.risk_of_ruin.probability_of_ruin is not None


def test_stress_test_deterministic_for_same_seed(db_session):
    asset = Asset(symbol="STRESS_SEED", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session, "stress_seed_strategy")
    for i in range(MIN_TRADES_FOR_STRESS_TEST + 3):
        pnl = 15.0 if i % 3 else -25.0
        _closed_trade(db_session, asset, strategy, pnl, _START + timedelta(minutes=i))

    r1 = run_live_stress_test(db_session, initial_capital=10000.0, num_simulations=200, random_seed=7)
    r2 = run_live_stress_test(db_session, initial_capital=10000.0, num_simulations=200, random_seed=7)
    assert r1.monte_carlo is not None and r2.monte_carlo is not None
    assert r1.monte_carlo.percentiles == r2.monte_carlo.percentiles


def test_value_at_risk_reports_insufficient_history_below_minimum_returns(db_session):
    for i in range(MIN_RETURNS_FOR_VAR):  # produces fewer returns than needed (N snapshots = N-1 returns)
        db_session.add(PortfolioSnapshot(ts=_START + timedelta(hours=i), equity=10000.0 + i, cash=10000.0))
    db_session.commit()

    result = compute_value_at_risk(db_session)
    assert result.var_pct is None
    assert result.cvar_pct is None
    assert "not enough" in result.note


def test_value_at_risk_computed_once_enough_returns_exist(db_session):
    equity = 10000.0
    for i in range(MIN_RETURNS_FOR_VAR + 10):
        # Alternate a modest gain and a larger loss to build a realistic
        # left-skewed return distribution.
        equity += 50.0 if i % 4 else -200.0
        db_session.add(PortfolioSnapshot(ts=_START + timedelta(hours=i), equity=equity, cash=equity))
    db_session.commit()

    result = compute_value_at_risk(db_session, confidence=0.95)
    assert result.var_pct is not None
    assert result.cvar_pct is not None
    assert result.var_pct >= 0
    # Expected shortfall (average of the worst tail) is always at least as
    # severe as the VaR cutoff itself.
    assert result.cvar_pct >= result.var_pct


def test_value_at_risk_respects_reset_epoch(db_session):
    from packages.shared.models import SystemState

    equity = 10000.0
    for i in range(MIN_RETURNS_FOR_VAR + 5):
        equity -= 500.0  # a severe pre-reset drawdown that must not leak into the post-reset VaR
        db_session.add(PortfolioSnapshot(ts=_START + timedelta(hours=i), equity=equity, cash=equity))
    db_session.commit()

    reset_at = _START + timedelta(hours=MIN_RETURNS_FOR_VAR + 5)
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.last_reset_at = reset_at
    db_session.add(state)
    db_session.commit()

    fresh_equity = 20000.0
    for i in range(MIN_RETURNS_FOR_VAR + 5):
        fresh_equity += 10.0  # tiny, calm post-reset returns
        db_session.add(PortfolioSnapshot(ts=reset_at + timedelta(hours=i + 1), equity=fresh_equity, cash=fresh_equity))
    db_session.commit()

    result = compute_value_at_risk(db_session, confidence=0.95)
    assert result.var_pct is not None
    assert result.var_pct < 5.0  # nowhere near the pre-reset 5%-per-period crash
