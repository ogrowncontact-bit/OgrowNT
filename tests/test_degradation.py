from datetime import datetime, timedelta, timezone

from packages.quant.learning.degradation import check_degradation
from packages.shared.models import Alert, Asset, BacktestRun, StrategyPerformance, StrategyRow


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _reference_backtest(db_session, strategy: StrategyRow, asset: Asset, expectancy: float) -> BacktestRun:
    run = BacktestRun(
        strategy_id=strategy.id, asset_id=asset.id, timeframe="1m", kind="backtest",
        start_ts=datetime.now(timezone.utc) - timedelta(days=10), end_ts=datetime.now(timezone.utc) - timedelta(days=5),
        initial_capital=10_000.0, expectancy=expectancy, num_trades=20,
    )
    db_session.add(run)
    db_session.commit()
    return run


def _perf(strategy: StrategyRow, expectancy: float) -> StrategyPerformance:
    return StrategyPerformance(strategy_id=strategy.id, window_trades=30, total_trades=30, expectancy=expectancy)


def test_no_reference_backtest_never_flags(db_session):
    strategy = _strategy(db_session, "degrade_noref_v1")
    db_session.add(_perf(strategy, expectancy=-1.0))
    db_session.commit()

    assert check_degradation(db_session, strategy.id) is False


def test_within_tolerance_does_not_flag(db_session):
    strategy = _strategy(db_session, "degrade_ok_v1")
    asset = _asset(db_session, "DEGRADEOK")
    _reference_backtest(db_session, strategy, asset, expectancy=1.0)
    db_session.add(_perf(strategy, expectancy=0.9))  # only 10% worse, tolerance is 20%
    db_session.commit()

    assert check_degradation(db_session, strategy.id, tolerance_pct=20.0) is False


def test_sustained_degradation_raises_alert(db_session):
    strategy = _strategy(db_session, "degrade_bad_v1")
    asset = _asset(db_session, "DEGRADEBAD")
    _reference_backtest(db_session, strategy, asset, expectancy=1.0)
    db_session.add(_perf(strategy, expectancy=0.5))  # 50% worse, tolerance is 20%
    db_session.commit()

    flagged = check_degradation(db_session, strategy.id, tolerance_pct=20.0)
    assert flagged is True

    alert = db_session.query(Alert).filter(Alert.category == "learning").order_by(Alert.id.desc()).first()
    assert alert is not None and "degraded" in alert.message
    assert alert.meta["degradation_pct"] == 50.0


def test_does_not_double_alert_within_cooldown(db_session):
    strategy = _strategy(db_session, "degrade_cooldown_v1")
    asset = _asset(db_session, "DEGRADECOOLDOWN")
    _reference_backtest(db_session, strategy, asset, expectancy=1.0)
    db_session.add(_perf(strategy, expectancy=0.3))
    db_session.commit()

    first = check_degradation(db_session, strategy.id, tolerance_pct=20.0)
    second = check_degradation(db_session, strategy.id, tolerance_pct=20.0)
    assert first is True
    assert second is False


def test_non_positive_reference_expectancy_never_flags(db_session):
    strategy = _strategy(db_session, "degrade_negref_v1")
    asset = _asset(db_session, "DEGRADENEGREF")
    _reference_backtest(db_session, strategy, asset, expectancy=-0.5)
    db_session.add(_perf(strategy, expectancy=-2.0))
    db_session.commit()

    assert check_degradation(db_session, strategy.id) is False
