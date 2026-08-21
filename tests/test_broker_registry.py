"""packages/execution/broker/registry.py -- "PROMPT 13" §21."""
from __future__ import annotations

from packages.execution.broker.paper import PaperBrokerAdapter
from packages.execution.broker.registry import BrokerRegistry, build_default_registry, get_or_create_broker_row
from packages.shared.models import Broker


class _StubAdapter:
    def __init__(self, name: str, kind: str = "paper"):
        self.name = name
        self.kind = kind
        self.is_paper = kind != "live"


def test_register_and_get():
    registry = BrokerRegistry()
    adapter = _StubAdapter("stub_a")
    registry.register(adapter)
    assert registry.get("stub_a") is adapter
    assert registry.get("does_not_exist") is None


def test_first_registered_becomes_default_when_not_specified():
    registry = BrokerRegistry()
    first = _StubAdapter("first")
    second = _StubAdapter("second")
    registry.register(first)
    registry.register(second)
    assert registry.get_default() is first


def test_is_default_flag_overrides_registration_order():
    registry = BrokerRegistry()
    first = _StubAdapter("first")
    second = _StubAdapter("second")
    registry.register(first)
    registry.register(second, is_default=True)
    assert registry.get_default() is second


def test_list_returns_every_registered_adapter():
    registry = BrokerRegistry()
    registry.register(_StubAdapter("a"))
    registry.register(_StubAdapter("b"))
    assert len(registry) == 2
    assert {a.name for a in registry.list()} == {"a", "b"}


def test_get_default_on_empty_registry_is_none():
    assert BrokerRegistry().get_default() is None


def test_build_default_registry_registers_a_real_paper_adapter(db_session):
    registry = build_default_registry(db_session)
    default = registry.get_default()
    assert default is not None
    assert isinstance(default, PaperBrokerAdapter)
    assert default.kind == "paper"


def test_get_or_create_broker_row_is_idempotent(db_session):
    first = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()
    second = get_or_create_broker_row(db_session, name="paper", kind="paper")
    assert first.id == second.id
    assert db_session.query(Broker).filter(Broker.name == "paper").count() == 1
