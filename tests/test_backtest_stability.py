from datetime import datetime, timedelta, timezone

from packages.backtest.stability import check_parameter_stability
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
    import pytest
    with pytest.raises(ValueError):
        check_parameter_stability(
            None, strategy_code="not_a_real_strategy", asset_id=1, symbol="X", timeframe=TIMEFRAME,
            start_ts=datetime.now(timezone.utc), end_ts=datetime.now(timezone.utc), initial_capital=10_000.0,
        )


def test_flat_market_yields_no_verdict(db_session):
    asset = _asset(db_session, "STABFLAT")
    start = datetime.now(timezone.utc) - timedelta(minutes=100)
    _insert_candles(db_session, asset, [100.0] * 100, start)

    result = check_parameter_stability(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=100), initial_capital=10_000.0,
    )
    assert result.stable is None
    assert "no trades" in result.reason


def test_uptrend_produces_a_stability_verdict_and_perturbs_every_numeric_param(db_session):
    asset = _asset(db_session, "STABTREND")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    result = check_parameter_stability(
        db_session, strategy_code="trend_following_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    assert result.base.result.num_trades >= 1
    # 3 numeric params (entry_threshold, risk_reward, atr_stop_buffer) x 2 perturbations each
    assert len(result.perturbed) == 6
    assert result.stable is not None
    assert isinstance(result.stable, bool)


def test_integer_param_perturbation_stays_a_valid_integer(db_session):
    asset = _asset(db_session, "STABBREAKOUT")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    # breakout_v1's `lookback` is an int -- perturbing it by +/-20% must not
    # crash the engine's candle slicing (which requires an int index).
    result = check_parameter_stability(
        db_session, strategy_code="breakout_v1", asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    for run in [result.base, *result.perturbed]:
        assert isinstance(run.params["lookback"], int)
