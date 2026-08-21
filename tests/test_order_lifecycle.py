"""packages/execution/order_manager.py -- "PROMPT 13" §40-41: partial-fill
handling and Execution-row creation, layered onto the existing (unchanged)
open_position/close_position/reduce_position tested in test_execution.py."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.execution.broker.paper import PARTIAL_FILL_VOLUME_THRESHOLD, PaperBrokerAdapter
from packages.execution.order_manager import close_position, open_position, reduce_position
from packages.shared.models import OHLCV, Asset, Execution, Signal, StrategyRow


def _asset_with_price(db_session, symbol: str, price: float, *, volume: float = 100.0) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=volume))
    db_session.commit()
    return asset


def _open_signal(db_session, asset, strategy, *, entry_price: float = 100.0) -> Signal:
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long", entry_price=entry_price, stop_price=entry_price * 0.95, status="approved")
    db_session.add(signal)
    db_session.commit()
    return signal


def test_open_position_sizes_at_the_actually_filled_quantity_on_partial_fill(db_session):
    asset = _asset_with_price(db_session, "LIFECYCLEPARTIAL", 100.0, volume=100.0)
    strategy = StrategyRow(code="lifecycle_partial_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    requested = 100.0 * PARTIAL_FILL_VOLUME_THRESHOLD * 3  # comfortably above the broker's own cap
    adapter = PaperBrokerAdapter(db_session)
    position = open_position(db_session, adapter, signal=signal, asset=asset, quantity=requested)

    assert position is not None
    assert position.size == 100.0 * PARTIAL_FILL_VOLUME_THRESHOLD
    assert position.size < requested


def test_open_position_creates_an_execution_row_matching_the_fill(db_session):
    asset = _asset_with_price(db_session, "LIFECYCLEEXEC", 100.0)
    strategy = StrategyRow(code="lifecycle_exec_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    adapter = PaperBrokerAdapter(db_session)
    position = open_position(db_session, adapter, signal=signal, asset=asset, quantity=1.0)
    assert position is not None

    executions = db_session.query(Execution).filter(Execution.symbol == "LIFECYCLEEXEC").all()
    assert len(executions) == 1
    assert executions[0].quantity == 1.0
    assert executions[0].side == "buy"
    assert executions[0].execution_mode == "paper"


def test_rejected_order_produces_zero_execution_rows(db_session):
    asset = Asset(symbol="LIFECYCLEREJECT", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    strategy = StrategyRow(code="lifecycle_reject_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    adapter = PaperBrokerAdapter(db_session)
    position = open_position(db_session, adapter, signal=signal, asset=asset, quantity=1.0)
    assert position is None
    assert db_session.query(Execution).filter(Execution.symbol == "LIFECYCLEREJECT").count() == 0


def test_close_position_creates_an_execution_row(db_session):
    asset = _asset_with_price(db_session, "LIFECYCLECLOSE", 100.0)
    strategy = StrategyRow(code="lifecycle_close_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    adapter = PaperBrokerAdapter(db_session)
    position = open_position(db_session, adapter, signal=signal, asset=asset, quantity=1.0)
    assert position is not None
    trade = close_position(db_session, adapter, position, asset=asset, exit_reason="manual_close")
    assert trade is not None

    executions = db_session.query(Execution).filter(Execution.symbol == "LIFECYCLECLOSE").order_by(Execution.id).all()
    assert len(executions) == 2  # one for the open, one for the close
    assert executions[1].side == "sell"


def test_reduce_position_creates_an_execution_row_sized_to_the_reduced_slice(db_session):
    asset = _asset_with_price(db_session, "LIFECYCLEREDUCE", 100.0)
    strategy = StrategyRow(code="lifecycle_reduce_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    adapter = PaperBrokerAdapter(db_session)
    position = open_position(db_session, adapter, signal=signal, asset=asset, quantity=2.0)
    assert position is not None
    trade = reduce_position(db_session, adapter, position, asset=asset, fraction=0.5, reason="test_reduce")
    assert trade is not None

    executions = db_session.query(Execution).filter(Execution.symbol == "LIFECYCLEREDUCE").order_by(Execution.id).all()
    assert len(executions) == 2
    assert executions[1].quantity == 1.0
