from datetime import datetime, timezone

from packages.execution.adapters.base import OrderRequest
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.execution.order_manager import close_position, open_position
from packages.portfolio.state import get_latest_cash, refresh_snapshot
from packages.shared.models import OHLCV, Asset, Order, Position, Signal, StrategyRow, Trade


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

    trade = close_position(db_session, provider, position, asset=asset, exit_reason="manual")

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
