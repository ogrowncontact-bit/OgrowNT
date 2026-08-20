"""Agent reliability, calibration, and quarantine — "PROMPT 9" §5-6, §55-59.

Mirrors `packages/quant/learning/strategy_stats.py` +
`packages/quant/learning/quarantine.py`'s precedent exactly: a rolling
DET-only score computed from real settled outcomes, "no penalty without
evidence" when the sample is too thin to trust, automatic demotion in the
risk-reducing direction only, and restoration always an explicit admin
action — never automatic.

Calibration source: `AgentPrediction` rows, written only for directional
agents' real long/short calls (`record_predictions_for_cycle`), settled
against real forward price movement once `evaluate_at` has passed
(`settle_predictions`) — never against a synthetic/backtested price, and
never guessed before a real candle at or after that time exists.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.agents.specialists import SPECIALIST_REGISTRY
from packages.shared.market_data import get_close_at_or_after
from packages.shared.models import Agent, AgentMessageRow, AgentPrediction, AgentReliability, AuditLog

# Below this many settled predictions, an agent's reliability_score is left
# None (not a fabricated confident number from a thin sample) -- same
# threshold magnitude as packages/quant/learning/strategy_stats.py's
# MIN_TRADES_FOR_HEALTH_SCORE, scaled up slightly since predictions settle
# far more often than closed trades.
MIN_SAMPLE_FOR_RELIABILITY = 10
# Below this reliability_score (0-100), with enough sample to trust it, the
# agent is quarantined -- same 35.0 magnitude as
# packages/quant/learning/quarantine.py::HEALTH_SCORE_QUARANTINE_THRESHOLD,
# reused deliberately rather than picking a new arbitrary number.
RELIABILITY_QUARANTINE_THRESHOLD = 35.0
PREDICTION_HORIZON_HOURS = 4.0
_DIRECTIONAL_SIGNALS = {AgentSignal.STRONG_LONG: "long", AgentSignal.LONG: "long", AgentSignal.STRONG_SHORT: "short", AgentSignal.SHORT: "short"}


def sync_agents_from_registry(db: Session) -> None:
    """Upserts one `Agent` row per `SPECIALIST_REGISTRY` entry -- inserts
    new agents, never overwrites an existing row's status/quarantine state
    (that's this module's own quarantine mechanism to own, not a redeploy).
    """
    existing = {row.code for row in db.execute(select(Agent.code)).all()}
    for code, meta in SPECIALIST_REGISTRY.items():
        if code in existing:
            continue
        db.add(Agent(code=code, name=meta.name, directional=meta.directional, version="1.0", status="active"))
    db.commit()


def record_prediction(db: Session, message: AgentMessage, message_row: AgentMessageRow, asset_id: int, reference_price: float | None) -> None:
    """Only ever called for a directional=True agent's real long/short
    call (Prompt 9 §5's calibration tracking has nothing to grade on a
    NEUTRAL/guardian read). `reference_price` is the close the market was
    at when the call was made -- None (data unavailable) skips recording
    rather than inventing a price."""
    direction = _DIRECTIONAL_SIGNALS.get(message.signal)
    if direction is None or message.status != AgentStatus.OK or reference_price is None:
        return
    db.add(
        AgentPrediction(
            agent_code=message.agent_code, agent_message_id=message_row.id, asset_id=asset_id,
            predicted_direction=direction, confidence=message.confidence, reference_price=reference_price,
            predicted_at=message.generated_at, evaluate_at=message.generated_at + timedelta(hours=PREDICTION_HORIZON_HOURS),
            outcome="pending",
        )
    )


def settle_predictions(db: Session, now: datetime | None = None) -> int:
    """Settles every pending prediction whose evaluate_at has passed AND a
    real candle at/after that instant already exists -- never settled
    against a guessed/interpolated price. Returns how many were settled."""
    now = now or datetime.now(timezone.utc)
    pending = db.execute(
        select(AgentPrediction).where(AgentPrediction.outcome == "pending", AgentPrediction.evaluate_at <= now)
    ).scalars().all()

    settled = 0
    for prediction in pending:
        price = get_close_at_or_after(db, prediction.asset_id, prediction.evaluate_at)
        if price is None:
            continue  # no candle yet -- stays pending, never guessed
        moved_up = price > prediction.reference_price
        correct = moved_up if prediction.predicted_direction == "long" else not moved_up
        prediction.outcome = "correct" if correct else "incorrect"
        prediction.outcome_price = price
        prediction.evaluated_at = now
        db.add(prediction)
        settled += 1
    if settled:
        db.commit()
    return settled


def compute_reliability(db: Session, agent_code: str) -> AgentReliability | None:
    """Computes and persists a fresh AgentReliability snapshot from every
    settled prediction this agent has. Returns None (writes nothing) when
    the sample is too thin to trust -- "no penalty without evidence", the
    same convention as classify_strategy_health(health_score=None)."""
    settled = db.execute(
        select(AgentPrediction).where(AgentPrediction.agent_code == agent_code, AgentPrediction.outcome != "pending")
    ).scalars().all()
    if len(settled) < MIN_SAMPLE_FOR_RELIABILITY:
        return None

    correct = [p for p in settled if p.outcome == "correct"]
    incorrect = [p for p in settled if p.outcome == "incorrect"]
    accuracy = round(len(correct) / len(settled), 4)
    avg_conf_correct = round(sum(p.confidence for p in correct) / len(correct), 4) if correct else None
    avg_conf_incorrect = round(sum(p.confidence for p in incorrect) / len(incorrect), 4) if incorrect else None

    # Overconfidence gap (§5): how much MORE confident the agent is on
    # calls it gets wrong than its overall hit rate would justify. Only
    # meaningful with enough wrong calls to average -- otherwise None,
    # never a fabricated gap from one unlucky miss.
    overconfidence_gap = (
        round(avg_conf_incorrect - accuracy, 4)
        if avg_conf_incorrect is not None and len(incorrect) >= 3
        else None
    )

    # reliability_score: accuracy scaled to 0-100, penalized for
    # overconfidence when detected -- never rewarded for it (the penalty
    # only ever pulls the score down, mirroring the loss-streak/anti-
    # martingale "only ever reduces" convention used across this codebase).
    reliability_score = accuracy * 100.0
    if overconfidence_gap is not None and overconfidence_gap > 0:
        reliability_score = max(0.0, reliability_score - overconfidence_gap * 100.0)

    row = AgentReliability(
        agent_code=agent_code, sample_size=len(settled), correct_count=len(correct), accuracy=accuracy,
        avg_confidence_when_correct=avg_conf_correct, avg_confidence_when_incorrect=avg_conf_incorrect,
        overconfidence_gap=overconfidence_gap, reliability_score=round(reliability_score, 4),
    )
    db.add(row)
    db.commit()
    return row


def latest_reliability(db: Session, agent_code: str) -> AgentReliability | None:
    return db.execute(
        select(AgentReliability).where(AgentReliability.agent_code == agent_code).order_by(AgentReliability.as_of.desc()).limit(1)
    ).scalar_one_or_none()


def evaluate_quarantine(db: Session, agent_code: str, reliability: AgentReliability) -> bool:
    """Same shape as packages/quant/learning/quarantine.py::evaluate_quarantine
    -- demotes an unreliable agent out of the Consensus Engine's vote.
    Returns True iff this call just quarantined it."""
    if reliability.reliability_score is None or reliability.reliability_score >= RELIABILITY_QUARANTINE_THRESHOLD:
        return False
    agent = db.get(Agent, agent_code)
    if agent is None or agent.status != "active":
        return False

    agent.status = "quarantined"
    agent.quarantined_at = datetime.now(timezone.utc)
    agent.quarantine_reason = (
        f"reliability_score {reliability.reliability_score:.2f} < threshold {RELIABILITY_QUARANTINE_THRESHOLD} "
        f"over {reliability.sample_size} settled predictions (accuracy={reliability.accuracy}, "
        f"overconfidence_gap={reliability.overconfidence_gap})"
    )
    db.add(agent)
    db.add(
        AuditLog(
            actor="reliability_engine", action="quarantine_agent", entity_type="agent",
            detail={"agent_code": agent_code, "reason": agent.quarantine_reason},
        )
    )
    db.commit()
    return True


def restore_from_quarantine(db: Session, agent_code: str, *, actor: str = "admin") -> Agent:
    """Admin-only restoration -- never called by the worker, exactly like
    packages/quant/learning/quarantine.py::restore_from_quarantine."""
    agent = db.get(Agent, agent_code)
    if agent is None:
        raise ValueError("agent not found")
    if agent.status != "quarantined":
        raise ValueError("agent is not in quarantine")
    agent.status = "active"
    agent.quarantined_at = None
    agent.quarantine_reason = None
    db.add(agent)
    db.add(AuditLog(actor=actor, action="restore_agent", entity_type="agent", detail={"agent_code": agent_code}))
    db.commit()
    return agent
