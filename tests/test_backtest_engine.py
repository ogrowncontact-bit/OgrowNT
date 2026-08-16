from datetime import datetime, timedelta, timezone

from packages.backtest.engine import run_backtest
from packages.quant.strategies import BreakoutStrategy, TrendFollowingStrategy
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


def test_insufficient_history_returns_honest_empty_result(db_session):
    asset = _asset(db_session, "BTINSUF")
    start = datetime.now(timezone.utc) - timedelta(minutes=10)
    _insert_candles(db_session, asset, [100.0 + i * 0.1 for i in range(10)], start)

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=10), initial_capital=10_000.0,
    )
    assert result.num_trades == 0
    assert result.net_return is None
    assert result.notes["reason"] == "insufficient_history"


def test_strong_uptrend_generates_at_least_one_long_trade(db_session):
    asset = _asset(db_session, "BTUPTREND")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    # A clean, strong monotonic uptrend -- should reliably trigger TrendFollowing's long entry.
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    assert result.num_trades >= 1
    assert all(t["direction"] == "long" for t in result.trades)
    assert result.net_return is not None
    assert len(result.equity_curve) > 0


def test_flat_market_generates_no_signals_for_trend_following(db_session):
    asset = _asset(db_session, "BTFLAT")
    start = datetime.now(timezone.utc) - timedelta(minutes=100)
    _insert_candles(db_session, asset, [100.0] * 100, start)

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=100), initial_capital=10_000.0,
    )
    assert result.num_trades == 0
    assert result.notes["reason"] == "no_trades_generated"


def test_equity_curve_starts_near_initial_capital(db_session):
    asset = _asset(db_session, "BTEQUITY")
    start = datetime.now(timezone.utc) - timedelta(minutes=100)
    _insert_candles(db_session, asset, [100.0] * 100, start)

    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=100), initial_capital=10_000.0,
    )
    assert result.equity_curve[0]["equity"] == 10_000.0


def test_date_range_is_respected_no_bars_outside_window(db_session):
    asset = _asset(db_session, "BTRANGE")
    start = datetime.now(timezone.utc) - timedelta(minutes=300)
    _insert_candles(db_session, asset, [100.0 + i * 0.05 for i in range(300)], start)

    narrow_start = start + timedelta(minutes=280)  # only 20 bars in range -- below MIN_CANDLES_REQUIRED (30)
    result = run_backtest(
        db_session, strategy=BreakoutStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=narrow_start, end_ts=start + timedelta(minutes=300), initial_capital=10_000.0,
    )
    assert result.notes.get("reason") == "insufficient_history"
    assert result.notes["bars_available"] == 20


def test_different_strategies_can_produce_different_trade_counts(db_session):
    asset = _asset(db_session, "BTCOMPARE")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    closes = [100.0 * (1.004 ** i) for i in range(200)]
    _insert_candles(db_session, asset, closes, start)

    trend_result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    from packages.quant.strategies import MeanReversionStrategy
    mean_reversion_result = run_backtest(
        db_session, strategy=MeanReversionStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=start + timedelta(minutes=200), initial_capital=10_000.0,
    )
    # A pure uptrend is TrendFollowing's best regime and MeanReversion's worst --
    # they should not behave identically.
    assert trend_result.num_trades != mean_reversion_result.num_trades or trend_result.net_return != mean_reversion_result.net_return
