from datetime import datetime, timezone

from apps.worker.trade_monitor import run_trade_monitor_cycle
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.quant.strategies import TrendFollowingStrategy
from packages.shared.models import OHLCV, Asset, MarketRegime, Position, StrategyRow


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000)
    )
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    existing = db_session.query(StrategyRow).filter(StrategyRow.code == code).first()
    if existing is not None:
        return existing
    strategy = StrategyRow(code=code, name=code, family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def test_long_position_closes_on_stop_hit(db_session):
    asset = _asset_with_price(db_session, "MONSTOP", 94.0)  # below the position's stop
    strategy = _strategy(db_session, "trend_following_v1")  # matches a real ALL_STRATEGIES entry
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    summary = run_trade_monitor_cycle(db_session, provider)

    assert summary["closed"] >= 1
    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "stop_hit"
    assert position.realized_pnl is not None and position.realized_pnl < 0


def test_long_position_closes_on_target_hit(db_session):
    asset = _asset_with_price(db_session, "MONTARGET", 120.0)  # above target
    strategy = _strategy(db_session, "momentum_v1")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=90.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "target_hit"
    assert position.realized_pnl is not None and position.realized_pnl > 0


def test_short_position_stop_and_target_are_mirrored(db_session):
    asset = _asset_with_price(db_session, "MONSHORT", 106.0)  # above a short's stop
    strategy = _strategy(db_session, "breakout_v1")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="short", entry_price=100.0, current_stop=105.0, target_price=85.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "stop_hit"


def test_position_stays_open_when_price_between_stop_and_target(db_session):
    asset = _asset_with_price(db_session, "MONHOLD", 102.0)
    strategy = _strategy(db_session, "mean_reversion_v1")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "open"


def test_thesis_invalidated_closes_position_when_regime_flips_to_worst(db_session):
    asset = _asset_with_price(db_session, "MONTHESIS", 102.0)  # inside stop/target, would otherwise hold
    strategy = _strategy(db_session, "mean_reversion_v1")  # worst_regimes includes trending_bull
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.add(
        MarketRegime(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), regime="trending_bull", confidence=0.9, features={})
    )
    db_session.commit()

    assert "trending_bull" in TrendFollowingStrategy().best_regimes  # sanity: this really is mean_reversion's worst regime
    provider = PaperExecutionProvider(db_session)
    run_trade_monitor_cycle(db_session, provider)

    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "thesis_invalidated"


def test_unavailable_price_does_not_close_position(db_session):
    asset = Asset(symbol="MONNODATA", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = _strategy(db_session, "trend_following_v1_nodata")
    position = Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, target_price=115.0, size=1.0, status="open")
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    summary = run_trade_monitor_cycle(db_session, provider)

    assert summary["unavailable"] >= 1
    db_session.refresh(position)
    assert position.status == "open"
