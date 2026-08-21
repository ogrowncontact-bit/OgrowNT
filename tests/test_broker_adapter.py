"""packages/execution/broker/paper.py -- "PROMPT 13" §3, §7-8, §23, §40-41,
§79-81: PaperBrokerAdapter's full BrokerAdapter surface, partial fills, and
marketable-limit-order handling."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.execution.adapters.base import OrderRequest
from packages.execution.broker.capabilities import PAPER_CAPABILITIES
from packages.execution.broker.paper import PARTIAL_FILL_VOLUME_THRESHOLD, PaperBrokerAdapter
from packages.shared.models import OHLCV, Asset, Order, Position, StrategyRow, TradingEvent


def _asset_with_price(db_session, symbol: str, price: float, *, volume: float = 1000.0, asset_class: str = "crypto") -> Asset:
    asset = Asset(symbol=symbol, asset_class=asset_class, is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=price, high=price * 1.001, low=price * 0.999, close=price, volume=volume)
    )
    db_session.commit()
    return asset


def test_connect_disconnect_are_harmless_noops(db_session):
    adapter = PaperBrokerAdapter(db_session)
    assert adapter.connect() is None
    assert adapter.disconnect() is None


def test_health_check_reports_ok_with_low_latency(db_session):
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.health_check()
    assert result.ok is True
    assert result.latency_ms >= 0


def test_get_account_reflects_portfolio_state(db_session):
    adapter = PaperBrokerAdapter(db_session)
    account = adapter.get_account()
    assert account.currency == "USD"
    assert account.balance == account.available_balance
    assert account.margin == 0.0


def test_get_positions_returns_open_positions_with_unrealized_pnl(db_session):
    asset = _asset_with_price(db_session, "BROKERPOS", 100.0)
    strategy = StrategyRow(code="broker_pos_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=90.0, current_stop=85.0, size=1.0, status="open"))
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BROKERPOS"
    assert positions[0].unrealized_pnl is not None and positions[0].unrealized_pnl > 0  # price 100 > entry 90


def test_get_open_orders_only_returns_non_terminal_orders(db_session):
    db_session.add_all([
        Order(order_type="market", side="buy", qty=1.0, status="new"),
        Order(order_type="market", side="buy", qty=1.0, status="filled"),
    ])
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    open_orders = adapter.get_open_orders()
    assert len(open_orders) == 1
    assert open_orders[0].status == "new"


def test_get_order_found_and_not_found(db_session):
    order = Order(order_type="market", side="buy", qty=1.0, status="filled", broker_order_id="abc-123")
    db_session.add(order)
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    found = adapter.get_order("abc-123")
    assert found is not None and found.status == "filled"
    assert adapter.get_order("does-not-exist") is None


def test_get_trades_returns_filled_and_partially_filled_only(db_session):
    db_session.add_all([
        Order(order_type="market", side="buy", qty=1.0, status="filled"),
        Order(order_type="market", side="buy", qty=1.0, status="partially_filled"),
        Order(order_type="market", side="buy", qty=1.0, status="rejected"),
    ])
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    trades = adapter.get_trades(limit=50)
    assert len(trades) == 2


def test_get_market_data_found_and_unknown_symbol(db_session):
    _asset_with_price(db_session, "BROKERMD", 50.0)
    adapter = PaperBrokerAdapter(db_session)
    candle = adapter.get_market_data("BROKERMD", "1m")
    assert candle is not None and candle.close == 50.0
    assert adapter.get_market_data("NOSUCHSYMBOL", "1m") is None


def test_submit_order_full_fill_within_volume_threshold(db_session):
    asset = _asset_with_price(db_session, "BROKERFILL", 100.0, volume=1000.0)
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=10.0))
    assert result.status == "filled"
    assert result.detail["filled_qty"] == 10.0


def test_submit_order_partial_fill_above_volume_threshold(db_session):
    asset = _asset_with_price(db_session, "BROKERPARTIAL", 100.0, volume=100.0)
    adapter = PaperBrokerAdapter(db_session)
    requested = 100.0 * PARTIAL_FILL_VOLUME_THRESHOLD * 2  # comfortably above the cap
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=requested))
    assert result.status == "partially_filled"
    assert result.detail["filled_qty"] == 100.0 * PARTIAL_FILL_VOLUME_THRESHOLD
    assert result.detail["filled_qty"] < requested


def test_submit_order_rejects_when_data_unavailable(db_session):
    asset = Asset(symbol="BROKERNODATA", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="market", qty=1.0))
    assert result.status == "rejected"
    assert result.detail["reason"] == "data_unavailable"


def test_submit_order_rejects_unsupported_order_type(db_session):
    asset = _asset_with_price(db_session, "BROKERSTOP", 100.0)
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="stop", qty=1.0))
    assert result.status == "rejected"
    assert result.detail["reason"] == "order_type_not_supported_by_broker"


def test_submit_marketable_buy_limit_fills_no_worse_than_limit(db_session):
    asset = _asset_with_price(db_session, "BROKERLIMITBUY", 100.0)
    adapter = PaperBrokerAdapter(db_session)
    # A buy limit at or above the market price is immediately marketable.
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="limit", qty=1.0, limit_price=105.0))
    assert result.status == "filled"
    assert result.filled_price <= 105.0


def test_submit_marketable_sell_limit_fills_no_worse_than_limit(db_session):
    asset = _asset_with_price(db_session, "BROKERLIMITSELL", 100.0)
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="sell", order_type="limit", qty=1.0, limit_price=95.0))
    assert result.status == "filled"
    assert result.filled_price >= 95.0


def test_submit_non_marketable_limit_is_honestly_rejected_not_queued(db_session):
    asset = _asset_with_price(db_session, "BROKERLIMITQUEUE", 100.0)
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="limit", qty=1.0, limit_price=50.0))
    assert result.status == "rejected"
    assert result.detail["reason"] == "limit_queuing_not_implemented"


def test_submit_limit_order_missing_limit_price_is_rejected(db_session):
    asset = _asset_with_price(db_session, "BROKERLIMITNOPRICE", 100.0)
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="limit", qty=1.0))
    assert result.status == "rejected"
    assert result.detail["reason"] == "limit_order_missing_limit_price"


def test_cancel_order_marks_cancelled_and_records_event(db_session):
    order = Order(order_type="market", side="buy", qty=1.0, status="new", broker_order_id="cancel-me")
    db_session.add(order)
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    adapter.cancel_order("cancel-me")
    db_session.refresh(order)
    assert order.status == "cancelled"
    events = db_session.query(TradingEvent).filter(TradingEvent.event_type == "order_cancelled").all()
    assert len(events) == 1


def test_cancel_order_on_terminal_order_is_a_noop(db_session):
    order = Order(order_type="market", side="buy", qty=1.0, status="filled", broker_order_id="already-filled")
    db_session.add(order)
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    adapter.cancel_order("already-filled")
    db_session.refresh(order)
    assert order.status == "filled"  # untouched


def test_replace_order_is_honestly_unsupported(db_session):
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.replace_order("whatever", qty=2.0)
    assert result.status == "rejected"
    assert result.detail["reason"] == "replace_not_supported_by_broker"


def test_get_fees_uses_provider_specific_rate_for_known_asset_classes(db_session):
    adapter = PaperBrokerAdapter(db_session)
    crypto_fee = adapter.get_fees(asset_class="crypto", notional=10_000.0, liquidity="taker")
    forex_fee = adapter.get_fees(asset_class="forex", notional=10_000.0, liquidity="taker")
    assert crypto_fee != forex_fee
    assert crypto_fee > 0 and forex_fee > 0


def test_get_instrument_returns_precision_fields(db_session):
    asset = _asset_with_price(db_session, "BROKERINSTR", 100.0)
    asset.tick_size, asset.step_size, asset.min_quantity, asset.min_notional = 0.01, 0.001, 0.001, 5.0
    db_session.add(asset)
    db_session.commit()

    adapter = PaperBrokerAdapter(db_session)
    spec = adapter.get_instrument("BROKERINSTR")
    assert spec.tick_size == 0.01 and spec.min_notional == 5.0


def test_get_capabilities_returns_paper_capabilities(db_session):
    adapter = PaperBrokerAdapter(db_session)
    assert adapter.get_capabilities() == PAPER_CAPABILITIES
    assert adapter.kind == "paper"
    assert adapter.is_paper is True
