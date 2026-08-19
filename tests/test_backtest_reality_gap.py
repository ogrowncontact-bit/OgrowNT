from datetime import datetime, timedelta, timezone

from packages.backtest.engine import run_backtest
from packages.backtest.persistence import persist_backtest_run
from packages.backtest.reality_gap import analyze_reality_gap
from packages.quant.strategies import TrendFollowingStrategy
from packages.shared.models import OHLCV, Asset, StrategyPerformance, StrategyRow

TIMEFRAME = "1m"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _run_and_persist(db_session, strategy_row: StrategyRow, asset: Asset, start: datetime, end: datetime):
    result = run_backtest(
        db_session, strategy=TrendFollowingStrategy(), asset_id=asset.id, symbol=asset.symbol, timeframe=TIMEFRAME,
        start_ts=start, end_ts=end, initial_capital=10_000.0,
    )
    return persist_backtest_run(
        db_session, strategy_row=strategy_row, asset=asset, timeframe=TIMEFRAME, kind="backtest",
        group_label=None, window_index=None, total_windows=None, params={},
        start_ts=start, end_ts=end, initial_capital=10_000.0, result=result,
    )


def _insert_uptrend(db_session, asset: Asset, start: datetime, bars: int = 200) -> None:
    for i in range(bars):
        close = 100.0 * (1.004**i)
        db_session.add(
            OHLCV(asset_id=asset.id, timeframe=TIMEFRAME, ts=start + timedelta(minutes=i), open=close * 0.999, high=close * 1.002, low=close * 0.998, close=close, volume=500.0, data_quality="high")
        )
    db_session.commit()


def test_unknown_strategy_reports_not_found(db_session):
    gap = analyze_reality_gap(db_session, 999_999)
    assert gap.notes == ["strategy not found"]


def test_no_reference_backtest_reports_honestly(db_session):
    strategy = _strategy(db_session, "REALITYGAPNOREF")
    gap = analyze_reality_gap(db_session, strategy.id)
    assert gap.reference_backtest_id is None
    assert "no reference backtest" in gap.notes[0]


def test_no_live_performance_reports_honestly(db_session):
    strategy = _strategy(db_session, "REALITYGAPNOLIVE")
    asset = _asset(db_session, "RGNOLIVE")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    _run_and_persist(db_session, strategy, asset, start, start + timedelta(minutes=200))

    gap = analyze_reality_gap(db_session, strategy.id)
    assert gap.reference_backtest_id is not None
    assert "no live paper-trading performance" in gap.notes[0]


def test_full_comparison_computes_differences(db_session):
    strategy = _strategy(db_session, "REALITYGAPFULL")
    asset = _asset(db_session, "RGFULL")
    start = datetime.now(timezone.utc) - timedelta(minutes=200)
    _insert_uptrend(db_session, asset, start)

    ref = _run_and_persist(db_session, strategy, asset, start, start + timedelta(minutes=200))

    db_session.add(
        StrategyPerformance(
            strategy_id=strategy.id, window_trades=20, total_trades=20, win_rate=(ref.win_rate or 0.5) - 0.1,
            profit_factor=1.5, avg_win=100.0, avg_loss=-50.0, sharpe=1.0, max_drawdown=(ref.max_drawdown or 1.0) + 2.0,
            expectancy=(ref.expectancy or 0.5) - 0.2,
        )
    )
    db_session.commit()

    gap = analyze_reality_gap(db_session, strategy.id)
    assert gap.reference_backtest_id == ref.id
    assert gap.return_difference is None  # units genuinely don't line up -- see module docstring
    assert any("NOT AVAILABLE" in n for n in gap.notes)
    assert gap.win_rate_difference is not None and abs(gap.win_rate_difference - (-0.1)) < 1e-6
    assert gap.expectancy_difference is not None and abs(gap.expectancy_difference - (-0.2)) < 1e-6
    assert gap.drawdown_difference is not None and abs(gap.drawdown_difference - 2.0) < 1e-6
