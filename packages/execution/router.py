"""ExecutionRouter — "PROMPT 13" §67-70.

select_broker() picks among BrokerRegistry's registered adapters. In this
codebase's own deployment there is exactly one non-'live' adapter ever
registered (PaperBrokerAdapter), so routing always resolves to it — but the
selection logic is real, not a single-adapter special case: it is tested
with additional stub adapters (same "architecture-ready, tested via stubs
since only one real implementation exists" precedent as
packages/data/connectors/market/failover.py, "PROMPT 12").

§69 "não escolher broker simplesmente porque fee = lowest" is enforced
structurally, not just by intent: capability match, asset-class support,
and a live health check are hard PRE-FILTERS (a degraded/incapable/live-kind
adapter is never even scored), and the composite score among survivors
blends fee AND latency — a broker can never win purely on the cheapest fee
alone if a healthy competitor is meaningfully faster.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.execution.broker.base import BrokerAdapter
from packages.execution.broker.capabilities import BrokerCapabilities
from packages.execution.broker.registry import BrokerRegistry

_FEE_WEIGHT = 0.6
_LATENCY_WEIGHT = 0.4
# A health-check latency at/above this scores 0 on the latency axis — a
# synchronous in-process paper adapter should never approach it; it exists
# so the scoring genuinely discriminates in tests using a deliberately slow
# stub adapter.
_LATENCY_NORMALIZATION_MS = 1000.0

_STOP_FAMILY_ORDER_TYPES = {"stop", "stop_limit", "take_profit", "take_profit_limit"}
_ASSET_CLASS_CAPABILITY = {
    "crypto": "supports_crypto",
    "forex": "supports_forex",
    "equity": "supports_stocks",
}


@dataclass(frozen=True)
class BrokerScore:
    adapter: BrokerAdapter
    broker_name: str
    score: float
    fee_rate: float
    latency_ms: float
    reasons: list[str] = field(default_factory=list)


def _supports_order_type(caps: BrokerCapabilities, order_type: str) -> bool:
    if order_type == "market":
        return caps.supports_market_orders
    if order_type == "limit":
        return caps.supports_limit_orders
    if order_type in _STOP_FAMILY_ORDER_TYPES:
        return caps.supports_stop_orders
    return False


def _supports_asset_class(caps: BrokerCapabilities, asset_class: str) -> bool:
    attr = _ASSET_CLASS_CAPABILITY.get(asset_class)
    if attr is None:
        return True  # an asset class this router has no explicit capability flag for is not pre-filtered out
    return bool(getattr(caps, attr))


class ExecutionRouter:
    def score_brokers(
        self, registry: BrokerRegistry, *, asset_class: str, order_type: str, representative_notional: float = 10_000.0,
    ) -> list[BrokerScore]:
        scored: list[BrokerScore] = []
        for adapter in registry.list():
            # §97 — never selected regardless of score, even if somehow registered.
            if adapter.kind == "live":
                continue
            caps = adapter.get_capabilities()
            if not _supports_order_type(caps, order_type) or not _supports_asset_class(caps, asset_class):
                continue
            health = adapter.health_check()
            if not health.ok:
                continue

            fee = adapter.get_fees(asset_class=asset_class, notional=representative_notional)
            fee_rate = (fee / representative_notional) if representative_notional else 0.0
            fee_score = max(0.0, 1.0 - fee_rate * 100)  # a 1% fee rate already scores 0 on this axis
            latency_score = max(0.0, 1.0 - (health.latency_ms / _LATENCY_NORMALIZATION_MS))
            composite = _FEE_WEIGHT * fee_score + _LATENCY_WEIGHT * latency_score

            scored.append(
                BrokerScore(
                    adapter=adapter, broker_name=adapter.name, score=round(composite, 4),
                    fee_rate=round(fee_rate, 6), latency_ms=health.latency_ms,
                    reasons=[f"fee_rate={fee_rate:.6f}", f"latency_ms={health.latency_ms}"],
                )
            )
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    def select_broker(
        self, registry: BrokerRegistry, *, asset_class: str, order_type: str, representative_notional: float = 10_000.0,
    ) -> BrokerAdapter | None:
        scored = self.score_brokers(registry, asset_class=asset_class, order_type=order_type, representative_notional=representative_notional)
        return scored[0].adapter if scored else None


class OrderTypeSelector:
    """§70 — validates/normalizes a strategy's requested order type against
    what the selected broker actually supports; it never overrides an
    already-supported preference with a "smarter" choice of its own (this
    codebase's "no implicit behavior" discipline, same precedent as
    packages/risk/position_policy.py's own §30 note)."""

    def select(self, *, requested_order_type: str, capabilities: BrokerCapabilities) -> str:
        if _supports_order_type(capabilities, requested_order_type):
            return requested_order_type
        return "market"  # the one type every registered adapter is required to support
