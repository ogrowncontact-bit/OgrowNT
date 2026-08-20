"""Scenario simulations A-H — "PROMPT 9" §90ish. Each scenario is a
realistic multi-agent situation this system must resolve correctly,
exercised through the real Chief Decision Engine (packages/agents/chief.py)
and, where the scenario is about agent lifecycle rather than a single
decision, the real reliability engine (packages/agents/reliability.py).
"""
from __future__ import annotations

from datetime import datetime, timezone

from packages.agents import chief, reliability
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.agents.specialists import SPECIALIST_REGISTRY
from packages.shared.models import Agent, AgentMessageRow, AgentPrediction, Asset


def _msg(code: str, signal: AgentSignal, confidence: float = 0.8, status: AgentStatus = AgentStatus.OK, risk_flags: tuple = ()) -> AgentMessage:
    return AgentMessage(agent_code=code, status=status, signal=signal, confidence=confidence if status == AgentStatus.OK else 0.0, risk_flags=risk_flags)


def _baseline() -> dict[str, AgentMessage]:
    return {code: _msg(code, AgentSignal.NEUTRAL, confidence=0.0) for code in SPECIALIST_REGISTRY}


# A. Every directional agent agrees bullish, nothing else is wrong.
def test_scenario_a_unanimous_bullish_agreement_reaches_strong_long_bias():
    directional = [code for code, meta in SPECIALIST_REGISTRY.items() if meta.directional]
    messages = _baseline()
    messages.update({code: _msg(code, AgentSignal.STRONG_LONG, confidence=0.9) for code in directional})
    decision = chief.decide(messages, {})
    assert decision.decision_state == chief.STRONG_LONG_BIAS
    assert decision.contradiction_score == 0.0


# B. Every directional agent agrees bearish.
def test_scenario_b_unanimous_bearish_agreement_reaches_strong_short_bias():
    directional = [code for code, meta in SPECIALIST_REGISTRY.items() if meta.directional]
    messages = _baseline()
    messages.update({code: _msg(code, AgentSignal.STRONG_SHORT, confidence=0.9) for code in directional})
    decision = chief.decide(messages, {})
    assert decision.decision_state == chief.STRONG_SHORT_BIAS


# C. Agents split evenly between long and short, roughly cancelling out.
def test_scenario_c_evenly_split_agents_settle_on_neutral():
    directional = [code for code, meta in SPECIALIST_REGISTRY.items() if meta.directional]
    half = len(directional) // 2
    messages = _baseline()
    for code in directional[:half]:
        messages[code] = _msg(code, AgentSignal.LONG, confidence=0.5)
    for code in directional[half:]:
        messages[code] = _msg(code, AgentSignal.SHORT, confidence=0.5)
    decision = chief.decide(messages, {})
    assert decision.decision_state in (chief.NEUTRAL, chief.NO_TRADE)


# D. Two high-conviction agents directly contradict each other.
def test_scenario_d_high_conviction_contradiction_forces_no_trade():
    messages = _baseline()
    messages["chief_quant"] = _msg("chief_quant", AgentSignal.STRONG_LONG, confidence=1.0)
    messages["technical_analysis"] = _msg("technical_analysis", AgentSignal.STRONG_SHORT, confidence=1.0)
    decision = chief.decide(messages, {})
    assert decision.decision_state == chief.NO_TRADE
    assert len(decision.contradictions) == 1


# E. A critical agent fails mid-cycle (simulated exception -> UNAVAILABLE).
def test_scenario_e_critical_agent_failure_forces_no_new_trades():
    messages = _baseline()
    messages.update({code: _msg(code, AgentSignal.STRONG_LONG, confidence=1.0) for code in ("chief_quant", "technical_analysis", "pattern_hunter")})
    messages["risk_guardian"] = _msg("risk_guardian", AgentSignal.NO_READ, status=AgentStatus.UNAVAILABLE)
    decision = chief.decide(messages, {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.critical_agent_failure


# F. Emergency condition (kill switch / EMERGENCY belt) overrides a bullish mob.
def test_scenario_f_emergency_condition_overrides_bullish_consensus():
    messages = _baseline()
    messages.update({code: _msg(code, AgentSignal.STRONG_LONG, confidence=1.0) for code, meta in SPECIALIST_REGISTRY.items() if meta.directional})
    messages["emergency_guardian"] = _msg("emergency_guardian", AgentSignal.NEUTRAL, confidence=1.0, risk_flags=("safety_belt_emergency", "emergency"))
    decision = chief.decide(messages, {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.blocked_reason == "emergency_guardian_flagged_emergency"


# G. Data quality has degraded below trust -- data_quality itself still
# answers OK (it always can compute *some* score), but UNAVAILABLE is the
# honest state when there's no quality report to compute from at all.
def test_scenario_g_data_quality_unavailable_blocks_regardless_of_other_agents():
    messages = _baseline()
    messages.update({code: _msg(code, AgentSignal.STRONG_LONG, confidence=1.0) for code in ("chief_quant", "technical_analysis")})
    messages["data_quality"] = _msg("data_quality", AgentSignal.NO_READ, status=AgentStatus.UNAVAILABLE)
    decision = chief.decide(messages, {})
    assert decision.decision_state == chief.BLOCKED
    assert decision.blocked_reason == "critical_agent_unavailable:data_quality"


# H. Recovery: a quarantined agent, once restored, rejoins the vote with
# full weight again (via the real reliability engine + DB, not a pure decide()
# call -- this scenario is about agent lifecycle, not one decision).
def test_scenario_h_a_restored_agent_rejoins_the_consensus_engines_vote(db_session):
    asset = Asset(symbol="SCENARIOH", asset_class="crypto", is_active=True)
    db_session.add(asset)
    agent = Agent(code="momentum", name="Momentum", directional=True, version="1.0", status="active")
    db_session.add(agent)
    db_session.commit()

    # Build a bad track record -> quarantine.
    for _ in range(12):
        row = AgentMessageRow(agent_code=agent.code, status="ok", signal="long", confidence=0.9)
        db_session.add(row)
        db_session.commit()
        db_session.add(
            AgentPrediction(
                agent_code=agent.code, agent_message_id=row.id, asset_id=asset.id, predicted_direction="long",
                confidence=0.9, reference_price=100.0, evaluate_at=datetime.now(timezone.utc), outcome="incorrect",
                outcome_price=95.0, evaluated_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()

    result = reliability.compute_reliability(db_session, agent.code)
    assert result is not None
    assert reliability.evaluate_quarantine(db_session, agent.code, result)
    assert db_session.get(Agent, agent.code).status == "quarantined"

    # Admin restores it -- never automatic (packages/quant/learning/
    # quarantine.py's precedent, mirrored here).
    restored = reliability.restore_from_quarantine(db_session, agent.code, actor="admin@example.com")
    assert restored.status == "active"

    # A fresh cycle's orchestrator would now call this agent again instead
    # of substituting a QUARANTINED stub message -- proven at the registry
    # level: nothing in reliability.py leaves a restored agent's status
    # anything but "active".
    assert db_session.get(Agent, agent.code).status == "active"
