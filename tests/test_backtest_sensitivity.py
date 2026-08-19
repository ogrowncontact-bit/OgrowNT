from datetime import datetime, timedelta, timezone

from packages.backtest.sensitivity import (
    COST_MULTIPLIERS,
    SLIPPAGE_MULTIPLIERS,
    run_capital_sensitivity,
    run_cost_sensitivity,
    run_slippage_sensitivity,
)
from packages.quant.strategies import TrendFollowingStrategy
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


def test_cost_sensitivity_sweeps_base_25_50_100_percent(db_session):
    asset = _asset(db_session, "SENSCOST")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    report = run_cost_sensitivity(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    assert [p.level for p in report.points] == list(COST_MULTIPLIERS)
    # Net return should never improve as costs rise.
    returns = [p.result.net_return for p in report.points if p.result.net_return is not None]
    assert returns == sorted(returns, reverse=True)


def test_slippage_sensitivity_sweeps_1x_2x_5x_10x(db_session):
    asset = _asset(db_session, "SENSSLIP")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    report = run_slippage_sensitivity(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    assert [p.level for p in report.points] == list(SLIPPAGE_MULTIPLIERS)
    assert report.kind == "slippage"


def test_capital_sensitivity_sweeps_multiple_capital_levels(db_session):
    asset = _asset(db_session, "SENSCAP")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    report = run_capital_sensitivity(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200),
    )
    assert len(report.points) == 5
    assert report.kind == "capital"
    for point in report.points:
        assert point.result.num_trades >= 0


def test_survives_all_levels_is_none_when_nothing_judgeable(db_session):
    asset = _asset(db_session, "SENSFLAT")
    start = datetime.now(timezone.utc) - timedelta(minutes=10)
    for i in range(10):  # fewer than MIN_CANDLES_REQUIRED -- insufficient_history, net_return stays None
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=100.0, high=100.5, low=99.5, close=100.0, volume=500.0, data_quality="high")
        )
    db_session.commit()

    report = run_cost_sensitivity(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=10), initial_capital=10_000.0,
    )
    assert report.survives_all_levels is None
    assert all(p.result.notes.get("reason") == "insufficient_history" for p in report.points)
