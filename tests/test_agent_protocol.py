"""AgentMessage protocol invariants — "PROMPT 9" §1-10, §44.

"No hallucinated data": a non-OK message can never carry real conviction,
and confidence is always bounded. Both are enforced structurally
(__post_init__ raises), not just by convention.
"""
from __future__ import annotations

import pytest

from packages.agents.protocol import (
    CRITICAL_AGENT_CODES,
    AgentMessage,
    AgentSignal,
    AgentStatus,
    signal_from_direction_strength,
    unavailable,
)


def test_ok_message_with_zero_confidence_is_valid():
    # A directional-family agent with no edge this cycle is a legitimate OK
    # read, not an error -- confidence=0 under status=OK must not raise.
    AgentMessage(agent_code="technical_analysis", status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0)


def test_unavailable_message_with_nonzero_confidence_is_rejected():
    with pytest.raises(ValueError):
        AgentMessage(agent_code="data_quality", status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ, confidence=0.5)


def test_quarantined_message_with_nonzero_confidence_is_rejected():
    with pytest.raises(ValueError):
        AgentMessage(agent_code="momentum", status=AgentStatus.QUARANTINED, signal=AgentSignal.NO_READ, confidence=0.1)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_out_of_bounds_is_rejected(confidence):
    with pytest.raises(ValueError):
        AgentMessage(agent_code="momentum", status=AgentStatus.OK, signal=AgentSignal.LONG, confidence=confidence)


def test_unavailable_helper_produces_a_valid_zero_confidence_message():
    message = unavailable("macro", "provider unreachable")
    assert message.status == AgentStatus.UNAVAILABLE
    assert message.signal == AgentSignal.NO_READ
    assert message.confidence == 0.0
    assert message.evidence["reason"] == "provider unreachable"


@pytest.mark.parametrize(
    "direction,strength,expected",
    [
        (None, 0.9, AgentSignal.NEUTRAL),
        ("long", 0.5, AgentSignal.LONG),
        ("long", 0.7, AgentSignal.STRONG_LONG),
        ("short", 0.5, AgentSignal.SHORT),
        ("short", 0.7, AgentSignal.STRONG_SHORT),
    ],
)
def test_signal_from_direction_strength_mapping(direction, strength, expected):
    assert signal_from_direction_strength(direction, strength) == expected


def test_critical_agent_codes_are_exactly_the_documented_three():
    # Prompt 9 §65's "NO NEW TRADES" rule only fires for these -- a
    # deliberately small set (emergency + risk state + data trust), not
    # "any agent at all", or a single misbehaving specialist could halt
    # trading entirely.
    assert CRITICAL_AGENT_CODES == frozenset({"emergency_guardian", "risk_guardian", "data_quality"})
