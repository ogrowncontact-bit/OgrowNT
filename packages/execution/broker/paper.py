"""PaperBrokerAdapter — "PROMPT 13" §23.

Extends PaperExecutionProvider (packages/execution/adapters/paper.py,
unchanged) with the richer BrokerAdapter surface: connection lifecycle,
account/position/order introspection, fee/instrument lookup, and two
genuinely new fill behaviors submit_order() didn't have before —

  - a volume-capped PARTIAL FILL (§40-41, §79-81) when the requested
    quantity would exceed what PARTIAL_FILL_VOLUME_THRESHOLD times the
    bar's own volume can reasonably absorb, reusing the exact same
    volume_ratio math packages/execution/fills.py's slippage calculation
    already does — a large order fills the portion the market could
    plausibly absorb and the remainder is simply not filled (no fabricated
    resting order), same "market IOC" behavior a thin real venue would show
    without a full order book.
  - an already-MARKETABLE limit order (§8): a limit price that already
    crosses the current market price fills immediately, capped so it never
    fills worse than the limit — exactly what a real limit order guarantees.
    A NON-marketable limit order (one that would need to rest and wait) is
    honestly REJECTED with reason="limit_queuing_not_implemented" rather
    than fabricating a resting-order state nothing in this codebase would
    ever come back to resolve — this synchronous, single-tick paper broker
    has no order book / matching engine. See
    docs/broker-execution-infrastructure.md for the full divergence.

This is the ONLY adapter this codebase's own apps/worker/apps/api
processes ever construct — see packages/execution/broker/live.py and
packages/execution/firewall.py for why "live" stays structurally
unreachable regardless.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from packages.data.connectors.market.base import Candle
from packages.execution.adapters.base import BalanceSnapshot, OrderRequest, OrderResult, OrderStatus
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.execution.broker.base import AccountInfo, HealthCheckResult, PositionInfo
from packages.execution.broker.capabilities import PAPER_CAPABILITIES, BrokerCapabilities
from packages.execution.fees import FeeEngine
from packages.execution.fills import SPREAD_BPS, simulate_fill
from packages.execution.instrument import InstrumentSpec, get_instrument
from packages.shared.market_data import get_latest_candle_row
from packages.shared.models import Asset, Order, Position, TradingEvent

# A requested quantity more than this many multiples of the bar's own
# volume can't plausibly fill in full on a single tick — the fillable
# portion is capped here rather than at fills.py's slippage-cap
# (MAX_VOLUME_RATIO_FOR_SLIPPAGE=5.0), so a genuinely oversized order
# partially fills (§40-41) before slippage would even reach its own cap.
PARTIAL_FILL_VOLUME_THRESHOLD = 3.0


def _to_order_result(order: Order) -> OrderResult:
    return OrderResult(
        broker_order_id=order.broker_order_id or "",
        status=order.status,  # type: ignore[arg-type]  # DB CHECK constraint guarantees a valid OrderStatus
        filled_price=order.filled_price,
        filled_at=order.filled_at,
        fees=order.fees,
        slippage_bps=order.slippage_bps,
        detail={"order_id": order.id},
    )


class PaperBrokerAdapter(PaperExecutionProvider):
    kind = "paper"

    def __init__(self, db):  # noqa: ANN001 - Session, matches PaperExecutionProvider's own untyped __init__
        super().__init__(db)
        self._fee_engine = FeeEngine()

    # -- connection lifecycle ------------------------------------------
    def connect(self) -> None:
        return None  # no real network connection exists for paper trading

    def disconnect(self) -> None:
        return None

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            self.db.execute(select(1))
            ok, detail = True, {}
        except Exception as exc:  # noqa: BLE001 - report, never crash the caller
            ok, detail = False, {"error": str(exc)}
        return HealthCheckResult(ok=ok, latency_ms=round((time.monotonic() - start) * 1000, 3), detail=detail)

    # -- account / position / order introspection -----------------------
    def get_account(self) -> AccountInfo:
        from packages.portfolio.state import compute_state

        state = compute_state(self.db)
        return AccountInfo(
            balance=state.cash, available_balance=state.cash, equity=state.equity,
            margin=0.0, margin_used=0.0, margin_available=state.cash,
            currency="USD", ts=datetime.now(timezone.utc),
        )

    def get_balances(self) -> BalanceSnapshot:
        return self.get_balance()

    def get_positions(self) -> list[PositionInfo]:
        positions = self.db.query(Position).filter(Position.status == "open").all()
        infos: list[PositionInfo] = []
        for position in positions:
            asset = self.db.get(Asset, position.asset_id)
            candle = get_latest_candle_row(self.db, position.asset_id)
            mark = candle.close if candle is not None else None
            unrealized = None
            if mark is not None:
                unrealized = (mark - position.entry_price) * position.size
                if position.direction == "short":
                    unrealized = -unrealized
            infos.append(
                PositionInfo(
                    symbol=asset.symbol if asset is not None else str(position.asset_id),
                    quantity=position.size, average_price=position.entry_price, mark_price=mark,
                    unrealized_pnl=unrealized, realized_pnl=None, side=position.direction,
                    leverage=1.0, margin=0.0,
                )
            )
        return infos

    def get_open_orders(self) -> list[OrderResult]:
        orders = self.db.query(Order).filter(Order.status.in_(("new", "submitted", "cancel_pending"))).all()
        return [_to_order_result(o) for o in orders]

    def get_order(self, broker_order_id: str) -> OrderResult | None:
        # Unlike PaperExecutionProvider.get_order() (always None, "stateless
        # between calls") — this adapter IS Session-bound, so it can honestly
        # answer from the orders table instead. Still None (not a fabricated
        # guess) when the id genuinely isn't found.
        order = self.db.query(Order).filter(Order.broker_order_id == broker_order_id).one_or_none()
        return _to_order_result(order) if order is not None else None

    def get_trades(self, *, limit: int = 50) -> list[OrderResult]:
        orders = (
            self.db.query(Order)
            .filter(Order.status.in_(("filled", "partially_filled")))
            .order_by(Order.id.desc())
            .limit(limit)
            .all()
        )
        return [_to_order_result(o) for o in orders]

    def get_market_data(self, symbol: str, timeframe: str) -> Candle | None:
        asset = self.db.query(Asset).filter(Asset.symbol == symbol).one_or_none()
        if asset is None:
            return None
        row = get_latest_candle_row(self.db, asset.id, timeframe)
        if row is None:
            return None
        return Candle(ts=row.ts, open=row.open, high=row.high, low=row.low, close=row.close, volume=row.volume, data_quality=row.data_quality)  # type: ignore[arg-type]

    # -- order submission -------------------------------------------------
    def submit_order(self, order: OrderRequest) -> OrderResult:
        if order.order_type not in ("market", "limit"):
            return OrderResult(
                broker_order_id=str(uuid4()), status="rejected",
                detail={"reason": "order_type_not_supported_by_broker", "order_type": order.order_type},
            )

        candle = get_latest_candle_row(self.db, order.asset_id)
        if candle is None or candle.data_quality != "high":
            return OrderResult(broker_order_id=str(uuid4()), status="rejected", detail={"reason": "data_unavailable"})

        if order.order_type == "limit":
            if order.limit_price is None:
                return OrderResult(broker_order_id=str(uuid4()), status="rejected", detail={"reason": "limit_order_missing_limit_price"})
            marketable = (order.limit_price >= candle.close) if order.side == "buy" else (order.limit_price <= candle.close)
            if not marketable:
                return OrderResult(
                    broker_order_id=str(uuid4()), status="rejected",
                    detail={"reason": "limit_queuing_not_implemented", "limit_price": order.limit_price, "market_price": candle.close},
                )

        asset = self.db.get(Asset, order.asset_id)
        asset_class = asset.asset_class if asset is not None else "crypto"

        volume_ratio = (order.qty / candle.volume) if candle.volume else 1.0
        filled_qty = order.qty
        status: OrderStatus = "filled"
        if candle.volume and volume_ratio > PARTIAL_FILL_VOLUME_THRESHOLD:
            filled_qty = round(candle.volume * PARTIAL_FILL_VOLUME_THRESHOLD, 8)
            status = "partially_filled"

        fill = simulate_fill(mid_price=candle.close, volume=candle.volume, qty=filled_qty, side=order.side)
        fee = self._fee_engine.compute_fee(asset_class=asset_class, price=fill.price, qty=filled_qty, liquidity="taker")

        fill_price = fill.price
        if order.order_type == "limit" and order.limit_price is not None:
            # A limit order never fills worse than its own limit price.
            fill_price = min(fill_price, order.limit_price) if order.side == "buy" else max(fill_price, order.limit_price)

        return OrderResult(
            broker_order_id=str(uuid4()), status=status, filled_price=round(fill_price, 8),
            filled_at=datetime.now(timezone.utc), fees=fee, slippage_bps=fill.slippage_bps,
            detail={
                "mid_price": candle.close, "spread_bps": SPREAD_BPS,
                "requested_qty": order.qty, "filled_qty": filled_qty,
            },
        )

    def cancel_order(self, broker_order_id: str) -> None:
        order = self.db.query(Order).filter(Order.broker_order_id == broker_order_id).one_or_none()
        if order is not None and order.status in ("new", "submitted", "cancel_pending"):
            order.status = "cancelled"
            self.db.add(order)
            self.db.add(TradingEvent(event_type="order_cancelled", entity_type="order", entity_id=order.id, payload={"broker_order_id": broker_order_id}))
            self.db.commit()

    def replace_order(self, broker_order_id: str, *, qty: float | None = None, limit_price: float | None = None) -> OrderResult:
        # A paper order fills synchronously (or is rejected) the instant
        # it's submitted — there is never a resting order left to modify.
        # Honestly rejected, never a fabricated success.
        return OrderResult(broker_order_id=broker_order_id, status="rejected", detail={"reason": "replace_not_supported_by_broker"})

    # -- fees / instrument / capabilities ---------------------------------
    def get_fees(self, *, asset_class: str, notional: float, liquidity: str = "taker") -> float:
        return self._fee_engine.compute_fee(asset_class=asset_class, price=notional, qty=1.0, liquidity=liquidity)

    def get_instrument(self, symbol: str) -> InstrumentSpec:
        asset = self.db.query(Asset).filter(Asset.symbol == symbol).one_or_none()
        if asset is None:
            raise ValueError(f"unknown symbol: {symbol}")
        return get_instrument(asset)

    def get_capabilities(self) -> BrokerCapabilities:
        return PAPER_CAPABILITIES
