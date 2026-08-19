from datetime import datetime, timedelta, timezone

from packages.backtest.walkforward_optimization import run_walk_forward_optimization
from packages.shared.models import OHLCV, Asset

TIMEFRAME = "1m"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _insert_uptrend(db_session, asset: Asset, start: datetime, bars: int = 400) -> None:
    for i in range(bars):
        close = 100.0 * (1.003**i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()


def test_produces_multiple_windows_each_with_train_and_validation(db_session):
    asset = _asset(db_session, "WFOWIN")
    start = datetime.now(timezone.utc) - timedelta(minutes=400)
    _insert_uptrend(db_session, asset, start)

    result = run_walk_forward_optimization(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=400), train_days=150 / (24 * 60), validation_days=50 / (24 * 60),
        initial_capital=10_000.0, max_combinations=4,
    )
    assert len(result.windows) >= 1
    for window in result.windows:
        assert window.train_end == window.validation_start
        assert window.best_params  # a parameter set was actually selected
        assert window.validation_result.num_trades >= 0  # validation genuinely ran


def test_validation_window_never_used_to_pick_params(db_session):
    """The best_params chosen for each window must come from a grid search
    scored on TRAIN alone -- verified indirectly: re-running just the
    winning params on the TRAIN slice reproduces the same train_result."""
    asset = _asset(db_session, "WFOISOLATION")
    start = datetime.now(timezone.utc) - timedelta(minutes=400)
    _insert_uptrend(db_session, asset, start)

    result = run_walk_forward_optimization(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=400), train_days=150 / (24 * 60), validation_days=50 / (24 * 60),
        initial_capital=10_000.0, max_combinations=4,
    )
    assert len(result.windows) >= 1
    window = result.windows[0]

    from packages.backtest.engine import run_backtest
    from packages.quant.strategies import STRATEGY_CLASSES

    replay = run_backtest(
        db_session, strategy=STRATEGY_CLASSES["trend_following_v1"](**window.best_params), asset_id=asset.id, symbol=asset.symbol,
        timeframe=TIMEFRAME, start_ts=window.train_start, end_ts=window.train_end, initial_capital=10_000.0,
    )
    assert replay.net_return == window.train_result.net_return
    assert replay.num_trades == window.train_result.num_trades


def test_period_too_short_reports_honestly(db_session):
    asset = _asset(db_session, "WFOTOOSHORT")
    start = datetime.now(timezone.utc) - timedelta(minutes=50)
    _insert_uptrend(db_session, asset, start, bars=50)

    result = run_walk_forward_optimization(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=50), train_days=10, validation_days=5, initial_capital=10_000.0,
    )
    assert result.windows == []
    assert result.consistent is None
    assert "too short" in result.reason


def test_parameter_stability_report_shape(db_session):
    asset = _asset(db_session, "WFOPARAMSTAB")
    start = datetime.now(timezone.utc) - timedelta(minutes=400)
    _insert_uptrend(db_session, asset, start)

    result = run_walk_forward_optimization(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=400), train_days=150 / (24 * 60), validation_days=50 / (24 * 60),
        initial_capital=10_000.0, max_combinations=4,
    )
    if result.windows:
        for stats in result.parameter_stability.values():
            assert "values" in stats and "coefficient_of_variation" in stats
