from datetime import datetime, timedelta, timezone

from packages.analytics.overview import build_analytics_overview
from packages.shared.models import (
    Asset,
    MarketRegime,
    OpportunityScore,
    Order,
    PatternPerformance,
    Position,
    PortfolioSnapshot,
    Signal,
    StrategyRow,
    Trade,
)

NOW = datetime.now(timezone.utc)


def _asset(db_session, symbol: str = "ANLX") -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy(db_session, code: str = "trend_following_v1") -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def test_empty_database_reports_honest_empty_state(db_session):
    overview = build_analytics_overview(db_session)
    assert overview.equity_curve == []
    assert overview.trade_stats.total_trades == 0
    assert overview.trade_stats.win_rate is None
    assert overview.drawdown.current_drawdown_pct is None
    assert overview.tier_distribution == {}
    assert overview.pattern_leaderboard == []
    assert overview.regime_distribution == {}


def test_equity_curve_is_chronological_and_bounded(db_session):
    for i in range(5):
        db_session.add(
            PortfolioSnapshot(
                ts=NOW - timedelta(hours=5 - i), equity=10_000.0 + i * 100, cash=5_000.0,
                exposure_pct=0.1, daily_pnl=10.0, drawdown_pct=1.0, safety_belt_level="normal",
            )
        )
    db_session.commit()

    overview = build_analytics_overview(db_session, equity_curve_limit=3)
    assert len(overview.equity_curve) == 3
    # oldest-first ordering, and it's the 3 most recent snapshots kept
    tses = [p.ts for p in overview.equity_curve]
    assert tses == sorted(tses)
    assert overview.equity_curve[-1].equity == 10_000.0 + 4 * 100


def test_drawdown_stats_use_latest_snapshot_and_running_peak(db_session):
    db_session.add(PortfolioSnapshot(ts=NOW - timedelta(hours=2), equity=10_000.0, cash=10_000.0, exposure_pct=0.0, daily_pnl=0.0, drawdown_pct=0.0, safety_belt_level="normal"))
    db_session.add(PortfolioSnapshot(ts=NOW - timedelta(hours=1), equity=9_000.0, cash=9_000.0, exposure_pct=0.0, daily_pnl=-1000.0, drawdown_pct=10.0, safety_belt_level="caution"))
    db_session.commit()

    overview = build_analytics_overview(db_session)
    assert overview.drawdown.current_drawdown_pct == 10.0
    assert overview.drawdown.max_drawdown_pct == 10.0
    assert overview.drawdown.peak_equity == 10_000.0


def _trade(db_session, asset: Asset, strategy: StrategyRow, *, pnl: float, r_multiple: float | None, outcome: str) -> Trade:
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=95.0, size=1.0, status="closed", closed_at=NOW,
    )
    db_session.add(position)
    db_session.commit()
    order = Order(position_id=position.id, side="buy", order_type="market", qty=1.0, status="filled")
    db_session.add(order)
    db_session.commit()
    trade = Trade(position_id=position.id, opened_order_id=order.id, closed_order_id=order.id, pnl=pnl, r_multiple=r_multiple, outcome=outcome, is_paper=True, closed_at=NOW)
    db_session.add(trade)
    db_session.commit()
    return trade


def test_trade_stats_match_manual_computation(db_session):
    asset = _asset(db_session)
    strategy = _strategy(db_session)
    _trade(db_session, asset, strategy, pnl=100.0, r_multiple=2.0, outcome="win")
    _trade(db_session, asset, strategy, pnl=100.0, r_multiple=2.0, outcome="win")
    _trade(db_session, asset, strategy, pnl=-50.0, r_multiple=-1.0, outcome="loss")

    overview = build_analytics_overview(db_session)
    stats = overview.trade_stats
    assert stats.total_trades == 3
    assert stats.win_rate == round(2 / 3, 4)
    assert stats.profit_factor == round(200.0 / 50.0, 4)
    assert stats.expectancy == round((2.0 + 2.0 - 1.0) / 3, 4)
    assert stats.avg_pnl == round((100.0 + 100.0 - 50.0) / 3, 4)


def test_tier_distribution_respects_window(db_session):
    asset = _asset(db_session)
    strategy = _strategy(db_session)
    signal_a = Signal(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, stop_price=95.0, ts=NOW)
    signal_b = Signal(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, stop_price=95.0, ts=NOW - timedelta(days=60))
    db_session.add_all([signal_a, signal_b])
    db_session.commit()

    recent = OpportunityScore(
        signal_id=signal_a.id, technical=1, pattern=1, regime_fit=1, historical_edge=1, liquidity=1, news=1,
        risk_reward=1, strategy_performance=1, final_score=80.0, tier="high_quality", created_at=NOW,
    )
    old = OpportunityScore(
        signal_id=signal_b.id, technical=1, pattern=1, regime_fit=1, historical_edge=1, liquidity=1, news=1,
        risk_reward=1, strategy_performance=1, final_score=10.0, tier="ignore", created_at=NOW - timedelta(days=60),
    )
    db_session.add_all([recent, old])
    db_session.commit()

    overview = build_analytics_overview(db_session, tier_window_days=30)
    assert overview.tier_distribution == {"high_quality": 1}


def test_pattern_leaderboard_orders_by_expectancy_desc(db_session):
    db_session.add(PatternPerformance(pattern_type="double_top", regime="ranging", sample_size=10, win_rate=0.4, avg_r_multiple=-0.2, expectancy=-0.2))
    db_session.add(PatternPerformance(pattern_type="breakout_flag", regime="trending_bull", sample_size=15, win_rate=0.65, avg_r_multiple=1.1, expectancy=1.1))
    db_session.add(PatternPerformance(pattern_type="untested", regime="ranging", sample_size=0, win_rate=None, avg_r_multiple=None, expectancy=None))
    db_session.commit()

    overview = build_analytics_overview(db_session)
    assert [e.pattern_type for e in overview.pattern_leaderboard] == ["breakout_flag", "double_top"]


def test_regime_distribution_respects_window(db_session):
    asset = _asset(db_session)
    db_session.add(MarketRegime(asset_id=asset.id, timeframe="1h", ts=NOW, regime="trending_bull", confidence=0.8))
    db_session.add(MarketRegime(asset_id=asset.id, timeframe="1h", ts=NOW - timedelta(days=30), regime="ranging", confidence=0.5))
    db_session.commit()

    overview = build_analytics_overview(db_session, regime_window_days=7)
    assert overview.regime_distribution == {"trending_bull": 1}
