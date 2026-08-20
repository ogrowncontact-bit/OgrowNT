"""Historical Analog Engine -- "PROMPT 11" §62-63."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.historical_analog import (
    MIN_ADEQUATE_SAMPLE,
    QUALITY_ADEQUATE,
    QUALITY_LOW_SAMPLE,
    HistoricalAnalogEngine,
)
from packages.shared.models import Asset, MarketMemory, Position, Signal, StrategyRow

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _signal_with_position(db_session, asset: Asset, strategy: StrategyRow, *, realized_pnl: float | None) -> Signal:
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0)
    db_session.add(signal)
    db_session.commit()
    db_session.add(
        Position(
            asset_id=asset.id, strategy_id=strategy.id, signal_id=signal.id, direction="long", entry_price=100.0,
            current_stop=95.0, size=1.0, status="closed", realized_pnl=realized_pnl,
        )
    )
    db_session.commit()
    return signal


def _memory(db_session, *, regime: str, pattern_type: str, direction: str, outcome: str, signal_id: int | None, ts) -> None:
    db_session.add(
        MarketMemory(
            ts=ts, context={"regime": regime, "pattern_type": pattern_type, "direction": direction}, outcome=outcome,
            signal_id=signal_id,
        )
    )
    db_session.commit()


def test_find_analogs_with_no_history_is_honestly_low_sample(db_session):
    result = HistoricalAnalogEngine().find_analogs(db_session, regime="trending_bull", pattern_type="breakout", direction="long")
    assert result.sample_size == 0
    assert result.win_rate is None
    assert result.quality == QUALITY_LOW_SAMPLE
    assert result.outcome_counts == {"win": 0, "loss": 0, "breakeven": 0}
    assert result.realized_pnl_samples == []
    assert result.worst_pnl is None


def test_find_analogs_reaches_adequate_quality_with_enough_matches(db_session):
    for i in range(MIN_ADEQUATE_SAMPLE):
        _memory(
            db_session, regime="trending_bull", pattern_type="breakout", direction="long", outcome="win",
            signal_id=None, ts=_START + timedelta(hours=i),
        )
    result = HistoricalAnalogEngine().find_analogs(db_session, regime="trending_bull", pattern_type="breakout", direction="long", k=MIN_ADEQUATE_SAMPLE)
    assert result.sample_size == MIN_ADEQUATE_SAMPLE
    assert result.win_rate == 1.0
    assert result.quality == QUALITY_ADEQUATE
    assert result.outcome_counts["win"] == MIN_ADEQUATE_SAMPLE


def test_find_analogs_below_min_sample_is_low_quality(db_session):
    for i in range(MIN_ADEQUATE_SAMPLE - 1):
        _memory(
            db_session, regime="ranging", pattern_type="mean_reversion", direction="short", outcome="loss",
            signal_id=None, ts=_START + timedelta(hours=i),
        )
    result = HistoricalAnalogEngine().find_analogs(db_session, regime="ranging", pattern_type="mean_reversion", direction="short", k=10)
    assert result.sample_size == MIN_ADEQUATE_SAMPLE - 1
    assert result.quality == QUALITY_LOW_SAMPLE


def test_find_analogs_pulls_real_realized_pnl_via_signal_position_link(db_session):
    asset = _asset(db_session, "ANALOG_ASSET")
    strategy = _strategy(db_session, "analog_test_strategy")
    winner = _signal_with_position(db_session, asset, strategy, realized_pnl=250.0)
    loser = _signal_with_position(db_session, asset, strategy, realized_pnl=-80.0)

    _memory(db_session, regime="trending_bull", pattern_type="breakout", direction="long", outcome="win", signal_id=winner.id, ts=_START)
    _memory(db_session, regime="trending_bull", pattern_type="breakout", direction="long", outcome="loss", signal_id=loser.id, ts=_START + timedelta(hours=1))

    result = HistoricalAnalogEngine().find_analogs(db_session, regime="trending_bull", pattern_type="breakout", direction="long", k=10)
    assert result.sample_size == 2
    assert sorted(result.realized_pnl_samples) == [-80.0, 250.0]
    assert result.worst_pnl == -80.0


def test_find_analogs_only_counts_rows_matching_the_query_context(db_session):
    _memory(db_session, regime="trending_bull", pattern_type="breakout", direction="long", outcome="win", signal_id=None, ts=_START)
    _memory(db_session, regime="panic", pattern_type="reversal", direction="short", outcome="loss", signal_id=None, ts=_START + timedelta(hours=1))

    result = HistoricalAnalogEngine().find_analogs(db_session, regime="trending_bull", pattern_type="breakout", direction="long", k=10)
    assert result.sample_size == 1
    assert result.outcome_counts["win"] == 1
    assert result.outcome_counts["loss"] == 0
