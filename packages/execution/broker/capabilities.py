"""BrokerCapabilities — "PROMPT 13" §20.

A plain, computed-not-persisted dataclass (see packages/shared/models.py's
"PROMPT 13" section comment for why there is no BrokerCapability table):
what a given adapter reports here is authoritative for THIS process's
lifetime, and a stale DB row would only ever risk drifting from it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerCapabilities:
    supports_market_orders: bool
    supports_limit_orders: bool
    supports_stop_orders: bool
    supports_short: bool
    supports_fractional: bool
    supports_crypto: bool
    supports_stocks: bool
    supports_forex: bool
    supports_futures: bool
    supports_websocket: bool


# PaperBrokerAdapter's real, honestly-reported capabilities (packages/
# execution/broker/paper.py). Limit orders are supported only for the
# already-marketable case (packages/execution/broker/paper.py's own
# docstring/docs/broker-execution-infrastructure.md); stop-family order
# types are schema-ready (Order.order_type's CHECK constraint accepts them)
# but not activated — createOrder() rejects them with a clear reason rather
# than silently no-op'ing. No live crypto/stock/forex exchange connectivity
# exists in this repository (see packages/execution/broker/live.py) so
# supports_crypto/stocks/forex describe what the mock market data behind
# the paper fill simulation can price, not real venue access.
PAPER_CAPABILITIES = BrokerCapabilities(
    supports_market_orders=True,
    supports_limit_orders=True,
    supports_stop_orders=False,
    supports_short=True,
    supports_fractional=True,
    supports_crypto=True,
    supports_stocks=True,
    supports_forex=True,
    supports_futures=False,
    supports_websocket=False,
)
