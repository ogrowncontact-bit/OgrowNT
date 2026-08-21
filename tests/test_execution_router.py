"""packages/execution/router.py -- "PROMPT 13" §67-70."""
from __future__ import annotations

from packages.execution.broker.capabilities import BrokerCapabilities
from packages.execution.broker.registry import BrokerRegistry
from packages.execution.router import ExecutionRouter, OrderTypeSelector

_FULL_CAPS = BrokerCapabilities(
    supports_market_orders=True, supports_limit_orders=True, supports_stop_orders=True, supports_short=True,
    supports_fractional=True, supports_crypto=True, supports_stocks=True, supports_forex=True,
    supports_futures=True, supports_websocket=True,
)
_NO_STOP_CAPS = BrokerCapabilities(
    supports_market_orders=True, supports_limit_orders=True, supports_stop_orders=False, supports_short=True,
    supports_fractional=True, supports_crypto=True, supports_stocks=True, supports_forex=True,
    supports_futures=False, supports_websocket=False,
)


class _HealthResult:
    def __init__(self, ok: bool, latency_ms: float):
        self.ok = ok
        self.latency_ms = latency_ms
        self.detail: dict = {}


class _StubAdapter:
    def __init__(self, name: str, *, kind: str = "paper", fee_rate: float, latency_ms: float, healthy: bool = True, caps: BrokerCapabilities = _FULL_CAPS):
        self.name = name
        self.kind = kind
        self._fee_rate = fee_rate
        self._latency_ms = latency_ms
        self._healthy = healthy
        self._caps = caps

    def health_check(self):
        return _HealthResult(self._healthy, self._latency_ms)

    def get_fees(self, *, asset_class: str, notional: float, liquidity: str = "taker") -> float:
        return notional * self._fee_rate

    def get_capabilities(self) -> BrokerCapabilities:
        return self._caps


def test_selects_the_only_registered_broker():
    registry = BrokerRegistry()
    registry.register(_StubAdapter("solo", fee_rate=0.001, latency_ms=1.0))
    router = ExecutionRouter()
    selected = router.select_broker(registry, asset_class="crypto", order_type="market")
    assert selected is not None and selected.name == "solo"


def test_never_selects_a_live_kind_adapter_even_if_registered():
    registry = BrokerRegistry()
    registry.register(_StubAdapter("live_one", kind="live", fee_rate=0.0, latency_ms=0.0))
    router = ExecutionRouter()
    assert router.select_broker(registry, asset_class="crypto", order_type="market") is None


def test_excludes_unhealthy_brokers():
    registry = BrokerRegistry()
    registry.register(_StubAdapter("sick", fee_rate=0.0001, latency_ms=1.0, healthy=False))
    registry.register(_StubAdapter("healthy_one", fee_rate=0.01, latency_ms=1.0, healthy=True))
    router = ExecutionRouter()
    selected = router.select_broker(registry, asset_class="crypto", order_type="market")
    assert selected is not None and selected.name == "healthy_one"


def test_excludes_brokers_missing_the_requested_order_type_capability():
    registry = BrokerRegistry()
    registry.register(_StubAdapter("no_stop", fee_rate=0.001, latency_ms=1.0, caps=_NO_STOP_CAPS))
    router = ExecutionRouter()
    assert router.select_broker(registry, asset_class="crypto", order_type="stop") is None
    assert router.select_broker(registry, asset_class="crypto", order_type="market") is not None


def test_never_picks_purely_on_lowest_fee_when_a_healthy_competitor_is_much_faster():
    """§69's "não escolher broker simplesmente porque fee = lowest" --
    proven by a case where the cheaper broker also has meaningfully worse
    latency, and the router still picks the more expensive-but-faster one
    because latency is genuinely blended into the score."""
    registry = BrokerRegistry()
    registry.register(_StubAdapter("cheap_and_slow", fee_rate=0.00001, latency_ms=950.0))
    registry.register(_StubAdapter("pricier_but_fast", fee_rate=0.0005, latency_ms=1.0))
    router = ExecutionRouter()
    scored = router.score_brokers(registry, asset_class="crypto", order_type="market")
    assert scored[0].broker_name == "pricier_but_fast"


def test_order_type_selector_honors_a_supported_preference():
    selected = OrderTypeSelector().select(requested_order_type="limit", capabilities=_FULL_CAPS)
    assert selected == "limit"


def test_order_type_selector_falls_back_to_market_when_unsupported():
    selected = OrderTypeSelector().select(requested_order_type="stop", capabilities=_NO_STOP_CAPS)
    assert selected == "market"
