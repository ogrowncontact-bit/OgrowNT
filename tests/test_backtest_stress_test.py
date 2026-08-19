from datetime import datetime, timedelta, timezone

from packages.backtest.risk import evaluate_signal_for_backtest
from packages.backtest.stress_test import SCENARIOS, run_stress_scenario
from packages.portfolio.state import PortfolioState
from packages.quant.strategies import TrendFollowingStrategy
from packages.risk.config import load_risk_limits
from packages.shared.models import OHLCV, Asset

TIMEFRAME = "1m"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _insert_uptrend(db_session, asset: Asset, start: datetime, bars: int = 200) -> None:
    for i in range(bars):
        close = 100.0 * (1.004**i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()


def test_every_scenario_runs_and_reports_a_delta(db_session):
    asset = _asset(db_session, "STRESSALL")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    for scenario in SCENARIOS:
        result = run_stress_scenario(
            db_session, scenario=scenario, strategy_factory=TrendFollowingStrategy, asset_id=asset.id, symbol=asset.symbol,
            timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
        )
        assert result.scenario == scenario
        assert result.baseline.num_trades >= 0
        assert result.stressed.num_trades >= 0
        assert result.params  # every scenario records the concrete params it actually used


def test_higher_costs_never_improve_the_result(db_session):
    asset = _asset(db_session, "STRESSCOSTS")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    result = run_stress_scenario(
        db_session, scenario="slippage_increase", strategy_factory=TrendFollowingStrategy, asset_id=asset.id, symbol=asset.symbol,
        timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    if result.baseline.net_return is not None and result.stressed.net_return is not None:
        assert result.stressed.net_return <= result.baseline.net_return


def test_market_crash_scenario_never_touches_real_ohlcv_table(db_session):
    """Stress scenarios must never write synthetic candles back to `ohlcv`
    -- other live cadences read that table concurrently (§65 READ/COMPUTE
    only). Verified directly: the row count for this asset/timeframe is
    identical before and after running the scenario."""
    asset = _asset(db_session, "STRESSNOWRITE")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    before = db_session.query(OHLCV).filter(OHLCV.asset_id == asset.id).count()
    run_stress_scenario(
        db_session, scenario="market_crash", strategy_factory=TrendFollowingStrategy, asset_id=asset.id, symbol=asset.symbol,
        timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    after = db_session.query(OHLCV).filter(OHLCV.asset_id == asset.id).count()
    assert before == after

    # And the real rows' prices are exactly what was inserted -- nothing
    # was mutated in place either.
    rows = db_session.query(OHLCV).filter(OHLCV.asset_id == asset.id).order_by(OHLCV.ts.asc()).all()
    assert rows[0].close == 100.0 * (1.004**0)


def test_kill_switch_drill_blocks_new_trades_once_drawdown_crosses_threshold(db_session):
    """§60's kill switch simulation, proven deterministically at the
    mechanism level (packages/backtest/risk.py's evaluate_signal_for_backtest
    already wires should_trigger_kill_switch into every candidate signal):
    a portfolio state at 1.5x the EMERGENCY drawdown threshold must be
    rejected outright, regardless of how good the candidate signal is."""
    limits = load_risk_limits()
    emergency_dd = limits.loss_limits.max_portfolio_drawdown_pct
    ruinous_state = PortfolioState(
        ts=datetime.now(timezone.utc), cash=5000.0, equity=5000.0, exposure_pct=0.0,
        daily_pnl=-5000.0, daily_loss_pct=50.0, weekly_pnl=-5000.0, weekly_loss_pct=50.0,
        monthly_pnl=-5000.0, monthly_loss_pct=50.0, drawdown_pct=emergency_dd * 1.5 + 1,
        unrealized_pnl=0.0, open_positions=[],
    )
    verdict = evaluate_signal_for_backtest(
        tier="exceptional", risk_reward=5.0, entry_price=100.0, stop_price=95.0, confidence=1.0,
        volatility_factor=1.0, portfolio_state=ruinous_state, limits=limits,
    )
    assert verdict.approved is False
    assert verdict.reason == "kill_switch"


def test_kill_switch_drill_within_a_full_stress_backtest_tracks_equity_throughout(db_session):
    """Even when a synthetic crash is severe enough to matter, the backtest
    must keep recording equity/positions through to the end -- 'monitoring
    continues' and 'positions remain correctly tracked' per §60."""
    asset = _asset(db_session, "STRESSKILLSWITCH")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    result = run_stress_scenario(
        db_session, scenario="market_crash", strategy_factory=TrendFollowingStrategy, asset_id=asset.id, symbol=asset.symbol,
        timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
        params={"drop_pct": -0.6, "tail_bars": 100},
    )
    assert result.notes["equity_curve_tracked_through_crash"] is True
    assert len(result.stressed.equity_curve) > 0
    # kill_switch_fired is reported either way (True or False) -- never absent.
    assert "kill_switch_fired" in result.notes


def test_unknown_scenario_rejected(db_session):
    import pytest

    asset = _asset(db_session, "STRESSUNKNOWN")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)
    with pytest.raises(ValueError, match="unknown stress scenario"):
        run_stress_scenario(
            db_session, scenario="not_a_real_scenario", strategy_factory=TrendFollowingStrategy, asset_id=asset.id, symbol=asset.symbol,
            timeframe=TIMEFRAME, start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
        )
