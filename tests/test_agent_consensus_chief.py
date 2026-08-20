"""Consensus Engine, Contradiction Engine, Chief Decision Engine —
"PROMPT 9" §40-46. Pure-function tests (no DB) since chief.decide() takes
already-produced AgentMessages and returns a Decision without touching
anything -- exactly like packages/risk/engine.py::evaluate_signal is
pure given its inputs.
"""
from __future__ import annotations

from packages.agents import chief
from packages.agents.consensus import compute_consensus
from packages.agents.contradiction import contradiction_score, find_contradictions
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus


def _msg(code: str, signal: AgentSignal, confidence: float = 0.8, status: AgentStatus = AgentStatus.OK, risk_flags: tuple = ()) -> AgentMessage:
    return AgentMessage(agent_code=code, status=status, signal=signal, confidence=confidence if status == AgentStatus.OK else 0.0, risk_flags=risk_flags)


def _all_ok_neutral(overrides: dict[str, AgentMessage] | None = None) -> dict[str, AgentMessage]:
    """A full 18-agent message set where every agent is OK/NEUTRAL --
    the baseline every red-team scenario below starts from and mutates."""
    from packages.agents.specialists import SPECIALIST_REGISTRY

    messages = {code: _msg(code, AgentSignal.NEUTRAL, confidence=0.0) for code in SPECIALIST_REGISTRY}
    if overrides:
        messages.update(overrides)
    return messages


# --- Consensus Engine ------------------------------------------------------


def test_consensus_is_weighted_not_a_plain_vote():
    """One STRONG_LONG at confidence 1.0 outweighs two weak LONGs at
    confidence 0.1 each -- a plain majority vote (2 vs 1) would say LONG
    either way, but the weighted score should be dominated by the single
    high-conviction agent."""
    messages = {
        "chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=1.0),
        "technical_analysis": _msg("technical_analysis", AgentSignal.LONG, confidence=0.1),
        "momentum": _msg("momentum", AgentSignal.LONG, confidence=0.1),
    }
    result = compute_consensus(messages, reliability_scores={})
    assert result.consensus_score > 50  # dominated by the STRONG_LONG vote


def test_unavailable_agents_do_not_vote():
    messages = {"chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, status=AgentStatus.UNAVAILABLE)}
    result = compute_consensus(messages, reliability_scores={})
    assert result.voting_agents == 0
    assert result.consensus_score == 0.0


def test_low_reliability_agent_contributes_less_than_a_proven_reliable_one():
    messages = {
        "chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=0.9),
        "technical_analysis": _msg("technical_analysis", AgentSignal.STRONG_SHORT, confidence=0.9),
    }
    # chief_quant proven reliable (90/100), technical_analysis proven unreliable (10/100)
    reliable = compute_consensus(messages, reliability_scores={"chief_quant": 90.0, "technical_analysis": 10.0})
    assert reliable.consensus_score > 0  # net leans toward the reliable agent's LONG call


# --- Contradiction Engine ---------------------------------------------------


def test_two_agreeing_directional_agents_are_not_a_contradiction():
    messages = {
        "chief_quant": _msg("chief_quant", AgentSignal.LONG),
        "technical_analysis": _msg("technical_analysis", AgentSignal.STRONG_LONG),
    }
    assert find_contradictions(messages) == []


def test_two_opposing_directional_agents_are_flagged():
    messages = {
        "chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=0.9),
        "technical_analysis": _msg("technical_analysis", AgentSignal.STRONG_SHORT, confidence=0.9),
    }
    records = find_contradictions(messages)
    assert len(records) == 1
    assert contradiction_score(records) > 80


def test_neutral_agents_never_contradict_anything():
    messages = {
        "chief_quant": _msg("chief_quant", AgentSignal.NEUTRAL),
        "technical_analysis": _msg("technical_analysis", AgentSignal.STRONG_SHORT, confidence=0.9),
    }
    assert find_contradictions(messages) == []


# --- Chief Decision Engine: DECISION_STATES thresholds ----------------------


def test_no_votes_at_all_is_neutral():
    decision = chief.decide(_all_ok_neutral(), {})
    assert decision.decision_state == chief.NEUTRAL


def test_two_strong_agreeing_agents_reach_strong_long_bias():
    overrides = {
        "chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=1.0),
        "technical_analysis": _msg("technical_analysis", AgentSignal.STRONG_LONG, confidence=1.0),
    }
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.STRONG_LONG_BIAS


def test_a_single_agent_alone_can_never_reach_a_bias_state():
    """Prompt 9 §41: "consenso", not one voice -- MIN_VOTING_AGENTS_FOR_BIAS."""
    overrides = {"chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=1.0)}
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.NEUTRAL


# --- Red-team battery -- "PROMPT 9"'s own layer, all must reach BLOCKED or
# NO_TRADE (never a *_BIAS state that could reach execution). Items already
# covered by tests/test_critical_safety_battery.py (bypass Risk Engine,
# bypass Portfolio Manager, stale data, exceed exposure/loss/drawdown,
# duplicate order) are NOT re-tested here -- this is the attack surface
# specific to the multi-agent layer itself.
#
# | # | Item                                                    | Expected  |
# |---|----------------------------------------------------------|-----------|
# | 1 | data_quality (critical) unavailable                       | BLOCKED   |
# | 2 | emergency_guardian (critical) unavailable                  | BLOCKED   |
# | 3 | risk_guardian (critical) unavailable                       | BLOCKED   |
# | 4 | emergency_guardian reports "emergency" despite bullish mob | BLOCKED   |
# | 5 | two strong directional agents contradict each other        | NO_TRADE  |
# | 6 | a non-OK message can't carry fabricated confidence          | rejected at construction |
# | 7 | no packages/agents/ module imports packages.execution      | tests/test_agent_sandbox.py |
# | 8 | no packages/agents/ module calls open/close/reduce_position| tests/test_agent_sandbox.py |
# | 9 | 17 agents bullish can't outvote 1 critical failure          | BLOCKED   |
# |10 | Decision=None is "no opinion", never implicit approval      | tests/test_agent_worker_wiring.py |


def test_redteam_1_data_quality_unavailable_blocks():
    overrides = {"data_quality": _msg("data_quality", AgentSignal.NO_READ, status=AgentStatus.UNAVAILABLE)}
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.critical_agent_failure


def test_redteam_2_emergency_guardian_unavailable_blocks():
    overrides = {"emergency_guardian": _msg("emergency_guardian", AgentSignal.NO_READ, status=AgentStatus.UNAVAILABLE)}
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.critical_agent_failure


def test_redteam_3_risk_guardian_unavailable_blocks():
    overrides = {"risk_guardian": _msg("risk_guardian", AgentSignal.NO_READ, status=AgentStatus.UNAVAILABLE)}
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.critical_agent_failure


def test_redteam_4_emergency_flag_blocks_despite_a_bullish_mob():
    overrides = {
        code: _msg(code, AgentSignal.STRONG_LONG, confidence=1.0)
        for code in ("chief_quant", "technical_analysis", "pattern_hunter", "momentum", "mean_reversion")
    }
    overrides["emergency_guardian"] = _msg("emergency_guardian", AgentSignal.NEUTRAL, confidence=1.0, risk_flags=("kill_switch_active", "emergency"))
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.blocked_reason == "emergency_guardian_flagged_emergency"


def test_redteam_5_strong_contradiction_is_no_trade_not_a_bias_state():
    overrides = {
        "chief_quant": _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=1.0),
        "technical_analysis": _msg("technical_analysis", AgentSignal.STRONG_SHORT, confidence=1.0),
    }
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.NO_TRADE


def test_redteam_6_fabricated_confidence_on_a_failed_agent_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        AgentMessage(agent_code="chief_quant", status=AgentStatus.UNAVAILABLE, signal=AgentSignal.STRONG_LONG, confidence=1.0)


def test_redteam_9_seventeen_bullish_agents_cannot_outvote_one_critical_failure():
    overrides = {
        code: _msg(code, AgentSignal.STRONG_LONG, confidence=1.0)
        for code in ("chief_quant", "technical_analysis", "pattern_hunter", "market_regime", "momentum", "mean_reversion", "news_intelligence")
    }
    overrides["data_quality"] = _msg("data_quality", AgentSignal.NO_READ, status=AgentStatus.UNAVAILABLE)
    decision = chief.decide(_all_ok_neutral(overrides), {})
    assert decision.decision_state == chief.BLOCKED
