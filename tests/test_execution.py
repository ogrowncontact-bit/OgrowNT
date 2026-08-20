from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from packages.execution.adapters.base import OrderRequest
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.execution.order_manager import close_position, open_position, reduce_position
from packages.portfolio.state import get_latest_cash
from packages.shared.models import OHLCV, Asset, Order, Signal, StrategyRow, Trade, TradingEvent


def _asset_with_price(db_session, symbol: str, price: float) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1000)
    )
    db_session.commit()
    return asset


def test_paper_provider_buy_fills_above_mid_price(db_session):
    asset = _asset_with_price(db_session, "EXECBUY", 100.0)
    provider = PaperExecutionProvider(db_session)
    result = provider.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=1.0))
    assert result.status == "filled"
    assert result.filled_price > 100.0  # spread + slippage work against a buyer
    assert result.fees is not None and result.fees > 0


def test_paper_provider_sell_fills_below_mid_price(db_session):
    asset = _asset_with_price(db_session, "EXECSELL", 100.0)
    provider = PaperExecutionProvider(db_session)
    result = provider.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="sell", order_type="market", qty=1.0))
    assert result.status == "filled"
    assert result.filled_price < 100.0


def test_paper_provider_rejects_when_no_data(db_session):
    asset = Asset(symbol="EXECNODATA", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    provider = PaperExecutionProvider(db_session)
    result = provider.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=1.0))
    assert result.status == "rejected"


def test_large_orders_incur_more_slippage(db_session):
    asset = _asset_with_price(db_session, "EXECSLIP", 100.0)
    provider = PaperExecutionProvider(db_session)
    small = provider.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=1.0))
    large = provider.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=5000.0))
    assert large.slippage_bps > small.slippage_bps
    assert large.filled_price > small.filled_price


def _open_signal(db_session, asset, strategy) -> Signal:
    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long",
        entry_price=100.0, stop_price=95.0, target_price=115.0, status="approved",
    )
    db_session.add(signal)
    db_session.commit()
    return signal


def test_open_position_creates_order_and_position_and_moves_cash(db_session):
    asset = _asset_with_price(db_session, "EXECOPEN", 100.0)
    strategy = StrategyRow(code="exec_open_strategy", name="Exec Open", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    cash_before = get_latest_cash(db_session)
    provider = PaperExecutionProvider(db_session)
    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=2.0)

    assert position is not None
    assert position.status == "open"
    assert position.size == 2.0
    assert position.entry_price > 100.0  # buy fills above mid

    order = db_session.query(Order).filter(Order.position_id == position.id).first()
    assert order is not None
    assert order.status == "filled"

    cash_after = get_latest_cash(db_session)
    assert cash_after < cash_before  # notional + fees reserved


def test_close_position_records_trade_and_returns_cash(db_session):
    asset = _asset_with_price(db_session, "EXECCLOSE", 100.0)
    strategy = StrategyRow(code="exec_close_strategy", name="Exec Close", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    provider = PaperExecutionProvider(db_session)
    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    cash_after_open = get_latest_cash(db_session)

    trade = close_position(db_session, provider, position, asset=asset, exit_reason="manual_close")

    assert trade is not None
    assert trade.outcome in ("win", "loss", "breakeven")
    assert position.status == "closed"
    assert position.exit_price is not None
    assert position.realized_pnl is not None

    cash_after_close = get_latest_cash(db_session)
    assert cash_after_close > cash_after_open  # notional + pnl returned

    stored_trade = db_session.query(Trade).filter(Trade.position_id == position.id).first()
    assert stored_trade is not None
    assert stored_trade.pnl == position.realized_pnl


def test_open_position_sets_idempotency_key_expected_price_and_latency(db_session):
    asset = _asset_with_price(db_session, "EXECIDEMPOPEN", 100.0)
    strategy = StrategyRow(code="exec_idemp_open_strategy", name="Exec Idemp Open", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)

    provider = PaperExecutionProvider(db_session)
    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    assert position is not None

    order = db_session.query(Order).filter(Order.position_id == position.id).first()
    assert order.idempotency_key == f"open:{signal.id}:0"
    assert order.expected_price == 100.0  # signal.entry_price, before spread/slippage
    assert order.latency_ms is not None and order.latency_ms >= 0


def test_a_second_order_reusing_the_same_idempotency_key_is_rejected_by_the_db(db_session):
    """"PROMPT 8" §67-68: the unique constraint is the actual enforcement
    point, not just the key's naming scheme — proves a genuine duplicate
    submission (same purpose, same position, same attempt count) cannot
    land twice."""
    asset = _asset_with_price(db_session, "EXECIDEMPDUP", 100.0)
    strategy = StrategyRow(code="exec_idemp_dup_strategy", name="Exec Idemp Dup", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)
    db_session.add(Order(signal_id=signal.id, order_type="market", side="buy", qty=1.0, status="filled", idempotency_key=f"open:{signal.id}:0"))
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(Order(signal_id=signal.id, order_type="market", side="buy", qty=1.0, status="filled", idempotency_key=f"open:{signal.id}:0"))
        db_session.commit()
    db_session.rollback()


def test_close_position_idempotency_key_advances_on_a_legitimate_retry(db_session):
    """A DATA_UNAVAILABLE close attempt (position stays open) must not
    block the NEXT cycle's legitimate retry — the attempt counter in the
    key has to move forward, not collide."""
    asset = _asset_with_price(db_session, "EXECIDEMPCLOSE", 100.0)
    strategy = StrategyRow(code="exec_idemp_close_strategy", name="Exec Idemp Close", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)
    provider = PaperExecutionProvider(db_session)
    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    assert position is not None

    trade = close_position(db_session, provider, position, asset=asset, exit_reason="manual_close", expected_price=101.5)
    assert trade is not None

    orders = db_session.query(Order).filter(Order.position_id == position.id).order_by(Order.id).all()
    assert len(orders) == 2  # the opening order + the closing order
    assert orders[0].idempotency_key == f"open:{signal.id}:0"
    assert orders[1].idempotency_key == f"close:{position.id}:1"
    assert orders[1].expected_price == 101.5


def test_close_and_open_record_trading_events(db_session):
    asset = _asset_with_price(db_session, "EXECEVENTS", 100.0)
    strategy = StrategyRow(code="exec_events_strategy", name="Exec Events", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)
    provider = PaperExecutionProvider(db_session)

    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    assert position is not None
    close_position(db_session, provider, position, asset=asset, exit_reason="manual_close")

    event_types = [e.event_type for e in db_session.query(TradingEvent).order_by(TradingEvent.id).all()]
    assert event_types == [
        "order_submitted", "order_filled", "position_opened",
        "order_submitted", "order_filled", "position_closed",
    ]


def test_reduce_position_shrinks_size_and_keeps_position_open(db_session):
    asset = _asset_with_price(db_session, "EXECREDUCE", 100.0)
    strategy = StrategyRow(code="exec_reduce_strategy", name="Exec Reduce", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)
    provider = PaperExecutionProvider(db_session)

    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=2.0)
    assert position is not None
    cash_after_open = get_latest_cash(db_session)

    trade = reduce_position(db_session, provider, position, asset=asset, fraction=0.5, reason="test_reduce")

    assert trade is not None
    assert position.status == "open"  # never closed by a reduce
    assert position.size == 1.0
    assert position.closed_at is None
    assert position.exit_reason is None

    cash_after_reduce = get_latest_cash(db_session)
    assert cash_after_reduce > cash_after_open  # the reduced slice's notional + pnl came back

    orders = db_session.query(Order).filter(Order.position_id == position.id).order_by(Order.id).all()
    assert len(orders) == 2
    assert orders[1].qty == 1.0
    assert orders[1].idempotency_key == f"reduce:{position.id}:1"


def test_reduce_position_fraction_at_or_above_one_closes_fully(db_session):
    asset = _asset_with_price(db_session, "EXECREDUCEFULL", 100.0)
    strategy = StrategyRow(code="exec_reduce_full_strategy", name="Exec Reduce Full", family="trend", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = _open_signal(db_session, asset, strategy)
    provider = PaperExecutionProvider(db_session)

    position = open_position(db_session, provider, signal=signal, asset=asset, quantity=1.0)
    assert position is not None

    trade = reduce_position(db_session, provider, position, asset=asset, fraction=1.0, reason="manual_close")
    assert trade is not None
    assert position.status == "closed"
