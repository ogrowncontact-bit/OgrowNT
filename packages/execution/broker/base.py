"""BrokerAdapter — "PROMPT 13" §3's Universal Broker Interface.

A structural (Protocol) superset of the existing packages.execution.
adapters.base.ExecutionProvider: submit_order/cancel_order/get_order/
get_balance keep their exact signatures (order_manager.py, the sole writer
of Position/Trade rows, is untouched — every function that already accepts
an ExecutionProvider keeps working unmodified against anything satisfying
BrokerAdapter too, since Protocol subtyping is structural). What's new is
account/position/order-history introspection, market data pass-through,
fee/instrument lookup, and connection lifecycle — the richer surface a real
broker integration needs that a single synchronous submit_order() call
never did.

Method names are snake_case, not the spec's literal camelCase
(connect/getAccount/createOrder/...) — the same "idiomatic Python over a
literal transliteration" convention this codebase has used since Phase 1
(e.g. evaluate_signal, not evaluateSignal). See
docs/broker-execution-infrastructure.md for the full naming map.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from packages.data.connectors.market.base import Candle
from packages.execution.adapters.base import BalanceSnapshot, OrderRequest, OrderResult

if TYPE_CHECKING:
    from packages.execution.broker.capabilities import BrokerCapabilities
    from packages.execution.instrument import InstrumentSpec


@dataclass(frozen=True)
class AccountInfo:
    """§31 AccountSnapshot's field set, as returned by a live get_account()
    call — packages/execution/broker_reconciliation.py persists a copy of
    this into the account_snapshots table on each reconciliation tick."""

    balance: float
    available_balance: float
    equity: float
    margin: float
    margin_used: float
    margin_available: float
    currency: str
    ts: datetime


@dataclass(frozen=True)
class PositionInfo:
    """§32 PositionSnapshot's field set, as returned by a live
    get_positions() call — the OTHER side of
    packages/execution/broker_reconciliation.py's comparison against this
    system's own `positions` table (never the same object)."""

    symbol: str
    quantity: float
    average_price: float
    mark_price: float | None
    unrealized_pnl: float | None
    realized_pnl: float | None
    side: str
    leverage: float
    margin: float


@dataclass(frozen=True)
class HealthCheckResult:
    ok: bool
    latency_ms: float
    detail: dict = field(default_factory=dict)


@runtime_checkable
class BrokerAdapter(Protocol):
    name: str
    is_paper: bool
    kind: str  # 'paper' | 'sandbox' | 'live'

    # -- connection lifecycle (§3) ---------------------------------------
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health_check(self) -> HealthCheckResult: ...

    # -- account / position / order introspection (§3, §31-32) ----------
    def get_account(self) -> AccountInfo: ...
    def get_balances(self) -> BalanceSnapshot: ...
    def get_positions(self) -> list[PositionInfo]: ...
    def get_open_orders(self) -> list[OrderResult]: ...
    def get_order(self, broker_order_id: str) -> OrderResult | None: ...
    def get_trades(self, *, limit: int = 50) -> list[OrderResult]: ...

    # -- market data pass-through (§57 — a real broker often IS also a
    # market data source; this simply exposes whatever provider the
    # adapter was constructed with, never a second, competing feed) -----
    def get_market_data(self, symbol: str, timeframe: str) -> Candle | None: ...

    # -- order submission (§3, §7-8) -------------------------------------
    def submit_order(self, order: OrderRequest) -> OrderResult: ...
    def cancel_order(self, broker_order_id: str) -> None: ...
    def replace_order(self, broker_order_id: str, *, qty: float | None = None, limit_price: float | None = None) -> OrderResult: ...

    # -- fees / instrument metadata (§60-64) -----------------------------
    def get_fees(self, *, asset_class: str, notional: float, liquidity: str = "taker") -> float: ...
    def get_instrument(self, symbol: str) -> InstrumentSpec: ...

    # -- capability introspection (§20) ----------------------------------
    def get_capabilities(self) -> BrokerCapabilities: ...
