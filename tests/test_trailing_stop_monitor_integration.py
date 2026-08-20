"""apps/worker/trade_monitor.py's trailing-stop wiring — "PROMPT 8" §27-29,
end to end through run_trade_monitor_cycle (not just the pure math in
tests/test_trailing_stop.py)."""
from datetime import datetime, timedelta, timezone

from apps.worker.trade_monitor import run_trade_monitor_cycle
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.shared.models import OHLCV, Asset, Position, StrategyRow

_BASE_TS = datetime.now(timezone.utc) - timedelta(hours=1)


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def _push_price(db_session, asset: Asset, price: float, minute: int) -> None:
    db_session.add(
        OHLCV(
            asset_id=asset.id, timeframe="1m", ts=_BASE_TS + timedelta(minutes=minute),
            open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000,
        )
    )
    db_session.commit()


def test_trailing_stop_ratchets_up_then_closes_on_reversal(db_session):
    asset = _asset(db_session, "TRAILMONITOR")
    strategy = StrategyRow(code="trail_monitor_strategy", name="Trail Monitor", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()

    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=95.0, target_price=1000.0, size=1.0, status="open",
        trailing_stop_config={"type": "fixed_distance", "value": 5.0},
    )
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)

    # Price rallies to 110 -> stop should ratchet from 95 up to 105.
    _push_price(db_session, asset, 110.0, minute=1)
    run_trade_monitor_cycle(db_session, provider)
    db_session.refresh(position)
    assert position.status == "open"
    assert position.current_stop == 105.0
    assert position.favorable_extreme_price == 110.0

    # A pullback to 106 (still above the new stop) must NOT loosen the stop.
    _push_price(db_session, asset, 106.0, minute=2)
    run_trade_monitor_cycle(db_session, provider)
    db_session.refresh(position)
    assert position.status == "open"
    assert position.current_stop == 105.0
    assert position.favorable_extreme_price == 110.0

    # A drop through the trailing stop closes the position with the
    # distinct 'trailing_stop_hit' reason, not the static 'stop_hit'.
    _push_price(db_session, asset, 104.0, minute=3)
    run_trade_monitor_cycle(db_session, provider)
    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "trailing_stop_hit"
    assert position.realized_pnl > 0  # closed above the original 100 entry, despite the pullback


def test_position_without_trailing_stop_config_still_uses_static_stop_hit(db_session):
    asset = _asset(db_session, "TRAILMONITORSTATIC")
    strategy = StrategyRow(code="trail_monitor_static_strategy", name="Static", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()

    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0,
        current_stop=95.0, target_price=115.0, size=1.0, status="open",
    )
    db_session.add(position)
    db_session.commit()

    provider = PaperExecutionProvider(db_session)
    _push_price(db_session, asset, 94.0, minute=1)
    run_trade_monitor_cycle(db_session, provider)
    db_session.refresh(position)
    assert position.status == "closed"
    assert position.exit_reason == "stop_hit"
    assert position.favorable_extreme_price is None  # never touched -- no trailing_stop_config
