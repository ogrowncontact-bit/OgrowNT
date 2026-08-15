"""ExecutionProvider interface — docs/blueprint/03-api-spec.md#execution-adapter.

Both paper and (later) live adapters implement this. The rest of the system
(worker, API) only ever depends on this interface, never on a concrete
provider — going live for a given asset class is a config change, not a
rewrite. Real adapters (Alpaca/Binance/IBKR) stay unregistered/disabled by
default (docs/blueprint/04-agents-architecture.md#agent-11) until someone
explicitly enables them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop"]
OrderStatus = Literal["new", "submitted", "filled", "partially_filled", "cancelled", "rejected"]


@dataclass(frozen=True)
class OrderRequest:
    asset_id: int
    symbol: str
    side: Side
    order_type: OrderType
    qty: float
    limit_price: float | None = None


@dataclass(frozen=True)
class OrderResult:
    broker_order_id: str
    status: OrderStatus
    filled_price: float | None = None
    filled_at: datetime | None = None
    fees: float | None = None
    slippage_bps: float | None = None
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BalanceSnapshot:
    cash: float
    equity: float


class ExecutionProvider(Protocol):
    name: str
    is_paper: bool

    def submit_order(self, order: OrderRequest) -> OrderResult: ...
    def cancel_order(self, broker_order_id: str) -> None: ...
    def get_order(self, broker_order_id: str) -> OrderResult | None: ...
    def get_balance(self) -> BalanceSnapshot: ...
