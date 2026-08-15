from datetime import datetime, timedelta, timezone

from packages.quant.learning.strategy_stats import MIN_TRADES_FOR_HEALTH_SCORE, compute_strategy_performance
from packages.shared.models import Asset, MarketRegime, Position, Signal, StrategyRow, Trade


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


def _closed_trade(db_session, *, strategy, asset, pnl: float, r_multiple: float, outcome: str, regime: str | None = None, minutes_ago: int = 0) -> Trade:
    signal = None
    if regime is not None:
        regime_row = MarketRegime(asset_id=asset.id, timeframe="1m", regime=regime, confidence=0.8, features={})
        db_session.add(regime_row)
        db_session.commit()
        signal = Signal(
            strategy_id=strategy.id, asset_id=asset.id, direction="long",
            entry_price=100.0, stop_price=95.0, target_price=110.0,
            regime_id=regime_row.id, status="executed",
        )
        db_session.add(signal)
        db_session.commit()

    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id if signal else None,
        direction="long", entry_price=100.0, current_stop=95.0, size=1.0,
        status="closed", realized_pnl=pnl, exit_price=100.0 + pnl, exit_reason="target_hit",
    )
    db_session.add(position)
    db_session.commit()

    trade = Trade(
        position_id=position.id, pnl=pnl, r_multiple=r_multiple, outcome=outcome,
        closed_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db_session.add(trade)
    db_session.commit()
    return trade


def test_no_trades_yields_empty_performance_row(db_session):
    strategy = _strategy(db_session, "empty_v1")
    perf = compute_strategy_performance(db_session, strategy.id)
    assert perf.total_trades == 0
    assert perf.window_trades == 0
    assert perf.win_rate is None
    assert perf.health_score is None


def test_below_minimum_sample_has_no_health_score(db_session):
    strategy = _strategy(db_session, "thin_v1")
    asset = _asset(db_session, "THINPERF")
    for i in range(MIN_TRADES_FOR_HEALTH_SCORE - 1):
        _closed_trade(db_session, strategy=strategy, asset=asset, pnl=10.0, r_multiple=1.0, outcome="win", minutes_ago=i)

    perf = compute_strategy_performance(db_session, strategy.id)
    assert perf.total_trades == MIN_TRADES_FOR_HEALTH_SCORE - 1
    assert perf.win_rate == 1.0
    assert perf.health_score is None  # sample too thin for a confident score


def test_all_wins_scores_high_and_no_drawdown(db_session):
    strategy = _strategy(db_session, "allwin_v1")
    asset = _asset(db_session, "ALLWINPERF")
    for i in range(MIN_TRADES_FOR_HEALTH_SCORE):
        _closed_trade(db_session, strategy=strategy, asset=asset, pnl=10.0, r_multiple=2.0, outcome="win", minutes_ago=i)

    perf = compute_strategy_performance(db_session, strategy.id)
    assert perf.win_rate == 1.0
    assert perf.profit_factor is None  # no losing trades -> undefined, not fabricated
    assert perf.expectancy == 2.0
    assert perf.max_drawdown == 0.0
    assert perf.health_score is not None and perf.health_score > 80


def test_all_losses_scores_low(db_session):
    strategy = _strategy(db_session, "allloss_v1")
    asset = _asset(db_session, "ALLLOSSPERF")
    for i in range(MIN_TRADES_FOR_HEALTH_SCORE):
        _closed_trade(db_session, strategy=strategy, asset=asset, pnl=-10.0, r_multiple=-1.0, outcome="loss", minutes_ago=i)

    perf = compute_strategy_performance(db_session, strategy.id)
    assert perf.win_rate == 0.0
    assert perf.expectancy == -1.0
    assert perf.max_drawdown == 50.0  # cumulative pnl only ever falls, peak stays at 0
    assert perf.health_score is not None and perf.health_score < 30


def test_mixed_trades_compute_profit_factor_and_avg(db_session):
    strategy = _strategy(db_session, "mixed_v1")
    asset = _asset(db_session, "MIXEDPERF")
    _closed_trade(db_session, strategy=strategy, asset=asset, pnl=20.0, r_multiple=2.0, outcome="win", minutes_ago=4)
    _closed_trade(db_session, strategy=strategy, asset=asset, pnl=20.0, r_multiple=2.0, outcome="win", minutes_ago=3)
    _closed_trade(db_session, strategy=strategy, asset=asset, pnl=-10.0, r_multiple=-1.0, outcome="loss", minutes_ago=2)
    _closed_trade(db_session, strategy=strategy, asset=asset, pnl=-10.0, r_multiple=-1.0, outcome="loss", minutes_ago=1)
    _closed_trade(db_session, strategy=strategy, asset=asset, pnl=15.0, r_multiple=1.5, outcome="win", minutes_ago=0)

    perf = compute_strategy_performance(db_session, strategy.id)
    assert perf.total_trades == 5
    assert perf.win_rate == 0.6
    assert perf.avg_win == round(55.0 / 3, 4)
    assert perf.avg_loss == 10.0
    assert perf.profit_factor == round(55.0 / 20.0, 4)
    assert perf.expectancy == round((2.0 + 2.0 - 1.0 - 1.0 + 1.5) / 5, 4)


def test_best_and_worst_regime_derived_from_signal_r_multiples(db_session):
    strategy = _strategy(db_session, "regime_v1")
    asset = _asset(db_session, "REGIMEPERF")
    for i in range(3):
        _closed_trade(db_session, strategy=strategy, asset=asset, pnl=10.0, r_multiple=2.0, outcome="win", regime="trending_bull", minutes_ago=10 + i)
    for i in range(3):
        _closed_trade(db_session, strategy=strategy, asset=asset, pnl=-10.0, r_multiple=-1.5, outcome="loss", regime="ranging", minutes_ago=i)

    perf = compute_strategy_performance(db_session, strategy.id)
    assert perf.best_regime == "trending_bull"
    assert perf.worst_regime == "ranging"


def test_window_trades_caps_at_configured_limit(db_session, monkeypatch):
    import packages.quant.learning.strategy_stats as stats_module
    monkeypatch.setattr(stats_module, "WINDOW_TRADES", 3)

    strategy = _strategy(db_session, "windowed_v1")
    asset = _asset(db_session, "WINDOWPERF")
    for i in range(6):
        _closed_trade(db_session, strategy=strategy, asset=asset, pnl=10.0, r_multiple=1.0, outcome="win", minutes_ago=i)

    perf = stats_module.compute_strategy_performance(db_session, strategy.id)
    assert perf.total_trades == 6
    assert perf.window_trades == 3
