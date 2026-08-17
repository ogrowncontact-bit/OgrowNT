from datetime import datetime, timedelta, timezone

import pytest

from packages.backtest.optimize import optimize_parameters
from packages.shared.models import OHLCV, Asset

TIMEFRAME = "1m"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _insert_candles(db_session, asset: Asset, closes: list[float], start: datetime) -> None:
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i),
                open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high",
            )
        )
    db_session.commit()


def test_unknown_strategy_code_raises():
    with pytest.raises(ValueError):
        optimize_parameters(
            None, strategy_code="not_real", asset_id=1, symbol="X", timeframe=TIMEFRAME,
            start_ts=datetime.now(timezone.utc), end_ts=datetime.now(timezone.utc), window_days=1.0, initial_capital=10_000.0,
        )


def test_flat_market_finds_no_consistent_candidate(db_session):
    asset = _asset(db_session, "OPTFLAT")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_candles(db_session, asset, [100.0] * 200, start)

    result = optimize_parameters(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), window_days=100 / (24 * 60), initial_capital=10_000.0,
        multipliers=(0.8, 1.0, 1.2),
    )
    assert result.best is None
    assert "consistency bar" in result.reason
    assert len(result.candidates) == 3**3  # trend_following_v1 has 3 numeric params


def test_grid_size_matches_param_count_and_multipliers(db_session):
    asset = _asset(db_session, "OPTGRID")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    result = optimize_parameters(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), window_days=100 / (24 * 60), initial_capital=10_000.0,
        multipliers=(0.8, 1.0, 1.2),
    )
    assert len(result.candidates) == 3**3
    assert all(len(c.params) == 3 for c in result.candidates)


def test_max_combinations_bounds_grid_size_and_keeps_base_params(db_session):
    asset = _asset(db_session, "OPTBOUND")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    # breakout_v1 has 4 numeric params -> 3^4 = 81 combos, well above a small cap
    result = optimize_parameters(
        db_session, strategy_code="breakout_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), window_days=100 / (24 * 60), initial_capital=10_000.0,
        multipliers=(0.8, 1.0, 1.2), max_combinations=5,
    )
    assert len(result.candidates) == 5

    from packages.quant.strategies import BreakoutStrategy
    default_params = {k: v for k, v in vars(BreakoutStrategy()).items() if isinstance(v, (int, float))}
    assert any(c.params == default_params for c in result.candidates)


def test_integer_params_stay_integers_after_perturbation(db_session):
    asset = _asset(db_session, "OPTINT")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    result = optimize_parameters(
        db_session, strategy_code="breakout_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), window_days=100 / (24 * 60), initial_capital=10_000.0,
        multipliers=(0.8, 1.0, 1.2), max_combinations=6,
    )
    for c in result.candidates:
        assert isinstance(c.params["lookback"], int)


def test_best_candidate_passed_consistency_when_one_exists(db_session):
    asset = _asset(db_session, "OPTBEST")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    result = optimize_parameters(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), window_days=100 / (24 * 60), initial_capital=10_000.0,
        multipliers=(0.8, 1.0, 1.2),
    )
    if result.best is not None:
        assert result.best.walk_forward.consistent is True
        assert "consistent candidates" in result.reason
