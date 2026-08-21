"""LiveBrokerAdapter — "PROMPT 13" §25.

The interface exists so the shape is ready; it is NEVER a usable
implementation. Every method raises LiveTradingDisabledError immediately,
regardless of arguments — this is the third of three independent layers
that keep live trading unreachable this phase (see
packages/execution/firewall.py's module docstring for the other two):
even if a caller somehow obtained a LiveBrokerAdapter instance and called
it directly, bypassing BrokerRegistry (which never registers one) and
ExecutionGate (which blocks upstream), this adapter self-destructs on
first use. No network client, no credential handling, no order
construction logic exists in this file — there is nothing here a future
"enable live trading" change could accidentally activate by flipping one
flag.
"""
from __future__ import annotations

from packages.execution.firewall import LiveTradingDisabledError


class LiveBrokerAdapter:
    name = "live"
    is_paper = False
    kind = "live"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise LiveTradingDisabledError("LiveBrokerAdapter cannot be instantiated — live trading is permanently disabled this phase")

    def __getattr__(self, _name: str) -> object:
        raise LiveTradingDisabledError("LiveBrokerAdapter has no usable methods — live trading is permanently disabled this phase")
