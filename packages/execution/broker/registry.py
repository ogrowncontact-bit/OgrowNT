"""BrokerRegistry — "PROMPT 13" §21.

Permits multiple registered BrokerAdapters without any caller hardcoding a
specific one — packages/execution/router.py::ExecutionRouter is the only
thing that ever picks among them. Exactly one adapter (PaperBrokerAdapter)
is ever actually constructed by build_default_registry() below; tests
exercise real selection/routing/failover behavior with additional stub
adapters (same "architecture-ready, tested via stubs since only one real
implementation exists" precedent as packages/data/connectors/market/
failover.py, "PROMPT 12").
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.execution.broker.base import BrokerAdapter
from packages.shared.models import Broker


class BrokerRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapter] = {}
        self._default_name: str | None = None

    def register(self, adapter: BrokerAdapter, *, is_default: bool = False) -> None:
        self._adapters[adapter.name] = adapter
        if is_default or self._default_name is None:
            self._default_name = adapter.name

    def get(self, name: str) -> BrokerAdapter | None:
        return self._adapters.get(name)

    def get_default(self) -> BrokerAdapter | None:
        if self._default_name is None:
            return None
        return self._adapters.get(self._default_name)

    def list(self) -> list[BrokerAdapter]:
        return list(self._adapters.values())

    def __len__(self) -> int:
        return len(self._adapters)


def build_default_registry(db: Session) -> BrokerRegistry:
    """The only registry this codebase's own worker/API processes build —
    a single PaperBrokerAdapter, matching the single 'paper' Broker row
    scripts/seed.py creates. Live trading stays unreachable regardless of
    what a caller registers here (packages/execution/firewall.py), so this
    function deliberately never registers a LiveBrokerAdapter."""
    from packages.execution.broker.paper import PaperBrokerAdapter

    registry = BrokerRegistry()
    registry.register(PaperBrokerAdapter(db), is_default=True)
    return registry


def get_or_create_broker_row(db: Session, *, name: str, kind: str) -> Broker:
    """The Broker table row backing a registered adapter — used wherever a
    persisted broker_id FK is needed (Order.broker_id,
    BrokerHealthCheck.broker_id, ...). Idempotent: scripts/seed.py already
    creates the 'paper' row on a fresh deployment; this is a fallback for
    an adapter registered without a matching seed (e.g. in a test)."""
    existing = db.query(Broker).filter(Broker.name == name).one_or_none()
    if existing is not None:
        return existing
    broker = Broker(name=name, kind=kind, status="active", is_default=(name == "paper"))
    db.add(broker)
    db.flush()
    return broker
