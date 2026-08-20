"""AgentOrchestrator — "PROMPT 9" §37-39, §65.

Runs all 18 specialists for one (asset, cycle) `AgentContext`, persists
every `AgentMessage` and the resulting `Decision` (+ any `Contradiction`s),
and returns the Chief Decision Engine's verdict for the worker cycle to
consult before `apps/worker/risk_execution.py`'s existing, unchanged Risk
Engine gate.

Concurrency is deliberately split, not a blanket ThreadPoolExecutor over
all 18 agents: 11 of the 18 specialists are pure functions of the already-
computed `AgentContext` (chief_quant, technical_analysis, pattern_hunter,
market_regime, momentum, mean_reversion, news_intelligence, macro,
sentiment, anomaly_detection, data_quality) and never touch `ctx.db` --
those run genuinely in parallel via `ThreadPoolExecutor`. The remaining 7
(quant_research, strategy_health, portfolio_intelligence, risk_guardian,
emergency_guardian, learning, execution_intelligence) query `ctx.db`, and
SQLAlchemy's `Session` is not safe for concurrent use from multiple
threads -- running those in the same worker threads as the pure group
would corrupt the shared session's connection state (the same class of
problem already documented in `tests/conftest.py`'s SAVEPOINT-isolated
`db_session` fixture, which is exactly why
`tests/test_crash_recovery_and_continuous_simulation.py`'s "simulated
restart" test uses `expunge_all()` instead of a second real connection).
So the DB-touching group runs sequentially in the caller's own
thread/transaction -- still individually try/except-isolated so one
agent's exception can never crash the cycle, just without the preemptive
parallel timeout the pure group gets. A literal "18-way ThreadPoolExecutor"
would need a per-thread `Session`, which this process's transaction model
does not support safely; this is the honest, correctness-preserving
alternative, documented per this codebase's deliberate-divergence
convention (see docs/multi-agent-architecture.md).

An agent that raises, times out, or is quarantined is marked UNAVAILABLE/
QUARANTINED -- Prompt 9 §65's "Se agente crítico falhar: NO NEW TRADES" is
enforced downstream in `packages/agents/chief.py`, never by crashing the
worker cycle itself.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy.orm import Session

from packages.agents import chief, reliability
from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus, unavailable
from packages.agents.specialists import SPECIALIST_REGISTRY
from packages.shared.models import Agent, AgentHealth, AgentMessageRow, Contradiction
from packages.shared.models import Decision as DecisionRow

logger = logging.getLogger("agents.orchestrator")

AGENT_TIMEOUT_SECONDS = 5.0

_PURE_CODES = frozenset({
    "chief_quant", "technical_analysis", "pattern_hunter", "market_regime", "momentum", "mean_reversion",
    "news_intelligence", "macro", "sentiment", "anomaly_detection", "data_quality",
})
_DB_CODES = frozenset(SPECIALIST_REGISTRY.keys()) - _PURE_CODES


def _run_one(code: str, ctx: AgentContext) -> tuple[AgentMessage, float]:
    started = time.monotonic()
    try:
        message = SPECIALIST_REGISTRY[code].analyze(ctx)
    except Exception as exc:  # noqa: BLE001 -- a specialist crashing must never crash the cycle
        logger.warning("agent %s raised %s -- marking unavailable", code, exc)
        message = unavailable(code, f"exception: {exc}")
    return message, round((time.monotonic() - started) * 1000, 2)


def _quarantined_message(code: str) -> AgentMessage:
    return AgentMessage(
        agent_code=code, status=AgentStatus.QUARANTINED, signal=AgentSignal.NO_READ, confidence=0.0,
        evidence={}, rationale="agent is quarantined by the reliability engine",
    )


def _serialize_message(message: AgentMessage) -> dict:
    return {
        "status": message.status.value, "signal": message.signal.value, "confidence": message.confidence,
        "evidence": message.evidence, "risk_flags": list(message.risk_flags), "rationale": message.rationale,
        "generated_at": message.generated_at.isoformat(),
        "expires_at": message.expires_at.isoformat() if message.expires_at else None,
    }


def run_agent_cycle(db: Session, ctx: AgentContext) -> tuple[chief.Decision, DecisionRow]:
    reliability.sync_agents_from_registry(db)
    agent_status = {row.code: row.status for row in db.query(Agent).all()}

    messages: dict[str, AgentMessage] = {}
    latencies: dict[str, float] = {}

    active_pure = [code for code in _PURE_CODES if agent_status.get(code, "active") == "active"]
    for code in _PURE_CODES - set(active_pure):
        messages[code] = _quarantined_message(code)
        latencies[code] = 0.0

    if active_pure:
        with ThreadPoolExecutor(max_workers=len(active_pure)) as pool:
            futures = {pool.submit(_run_one, code, ctx): code for code in active_pure}
            for future, code in futures.items():
                try:
                    message, latency_ms = future.result(timeout=AGENT_TIMEOUT_SECONDS)
                except FutureTimeoutError:
                    message = unavailable(code, f"timed out after {AGENT_TIMEOUT_SECONDS}s")
                    latency_ms = AGENT_TIMEOUT_SECONDS * 1000
                messages[code] = message
                latencies[code] = latency_ms

    for code in _DB_CODES:
        if agent_status.get(code, "active") != "active":
            messages[code] = _quarantined_message(code)
            latencies[code] = 0.0
            continue
        message, latency_ms = _run_one(code, ctx)
        messages[code] = message
        latencies[code] = latency_ms

    for code, message in messages.items():
        db.add(AgentHealth(agent_code=code, status=message.status.value, latency_ms=latencies.get(code)))

    reliability_scores: dict[str, float | None] = {}
    for code in SPECIALIST_REGISTRY:
        latest = reliability.latest_reliability(db, code)
        reliability_scores[code] = latest.reliability_score if latest is not None else None

    decision = chief.decide(messages, reliability_scores)

    decision_row = DecisionRow(
        asset_id=ctx.asset.id, decision_state=decision.decision_state, consensus_score=decision.consensus.consensus_score,
        contradiction_score=decision.contradiction_score, reasoning_summary=decision.reasoning_summary,
        agent_inputs={code: _serialize_message(m) for code, m in messages.items()},
        blocked_reason=decision.blocked_reason, critical_agent_failure=decision.critical_agent_failure,
    )
    db.add(decision_row)
    db.flush()  # assign decision_row.id

    # Two round-trips (one flush for all 18 rows, not eighteen) -- assigning
    # ids one message at a time was measurably slower across a full worker
    # cycle for no benefit, since nothing needs a row's id before every
    # message has been added.
    reference_price = ctx.market.indicators.close
    message_rows: dict[str, AgentMessageRow] = {}
    for code, message in messages.items():
        row = AgentMessageRow(
            agent_code=code, asset_id=ctx.asset.id, decision_id=decision_row.id, status=message.status.value,
            signal=message.signal.value, confidence=message.confidence, evidence=message.evidence,
            risk_flags=list(message.risk_flags), rationale=message.rationale, generated_at=message.generated_at,
            expires_at=message.expires_at,
        )
        db.add(row)
        message_rows[code] = row
    db.flush()  # assign every row.id at once, for the prediction FKs below

    for code, message in messages.items():
        if SPECIALIST_REGISTRY[code].directional:
            reliability.record_prediction(db, message, message_rows[code], ctx.asset.id, reference_price)

    for record in decision.contradictions:
        db.add(
            Contradiction(
                decision_id=decision_row.id, agent_code_a=record.agent_code_a, agent_code_b=record.agent_code_b,
                signal_a=record.signal_a.value, signal_b=record.signal_b.value, severity=record.severity,
                description=record.description,
            )
        )

    db.commit()
    return decision, decision_row
