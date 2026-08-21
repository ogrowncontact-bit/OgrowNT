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
# "PROMPT 13" §8 widens the order-type vocabulary the schema can express;
# only "market" and an already-marketable "limit" are actually activated by
# PaperBrokerAdapter (packages/execution/broker/paper.py) — the rest are
# capability-gated, not implemented, same as every other honestly-scoped gap
# in this codebase (see docs/broker-execution-infrastructure.md).
OrderType = Literal["market", "limit", "stop", "stop_limit", "take_profit", "take_profit_limit"]
# "PROMPT 13" §10-11 widens the terminal-state vocabulary: 'new' has served
# as CREATED/PENDING since Phase 3 and is kept as-is (every existing caller
# already checks status == 'new'); 'cancel_pending'/'expired'/'failed'/
# 'unknown' are additive states no pre-Prompt-13 code path could ever
# produce, so every existing OrderStatus check keeps working unchanged.
OrderStatus = Literal[
    "new", "submitted", "filled", "partially_filled", "cancelled", "rejected",
    "cancel_pending", "expired", "failed", "unknown",
]


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
