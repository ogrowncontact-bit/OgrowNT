"""packages/execution/firewall.py + packages/execution/broker/live.py --
"PROMPT 13" §2, §26-27, §83, §97: LiveTradingFirewall and LiveBrokerAdapter,
the two of three independent layers keeping live trading unreachable that
don't depend on any particular caller (the third, ExecutionGate calling the
firewall, is covered in tests/test_execution_gate.py)."""
from __future__ import annotations

import pytest

from packages.execution.broker.live import LiveBrokerAdapter
from packages.execution.firewall import ENABLE_LIVE_TRADING, LiveTradingDisabledError, LiveTradingFirewall


def test_enable_live_trading_is_hardcoded_false():
    assert ENABLE_LIVE_TRADING is False


@pytest.mark.parametrize("mode", ["paper", "sandbox", "simulation"])
def test_firewall_allows_non_live_modes(mode):
    LiveTradingFirewall.check(mode)  # must not raise


def test_firewall_denies_live_unconditionally():
    with pytest.raises(LiveTradingDisabledError):
        LiveTradingFirewall.check("live")


def test_firewall_denies_unrecognized_mode():
    with pytest.raises(LiveTradingDisabledError):
        LiveTradingFirewall.check("something_made_up")


def test_live_broker_adapter_cannot_be_instantiated():
    with pytest.raises(LiveTradingDisabledError):
        LiveBrokerAdapter()


def test_live_broker_adapter_class_attributes_mark_it_as_live():
    assert LiveBrokerAdapter.kind == "live"
    assert LiveBrokerAdapter.is_paper is False
