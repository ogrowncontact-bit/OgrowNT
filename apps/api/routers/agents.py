"""Multi-Agent Quant Intelligence API — "PROMPT 9" §47-50.

Read-only for every specialist/decision/contradiction endpoint (the
worker's own `packages/agents/orchestrator.py` cycle is the only writer);
the one mutation is POST /{code}/restore, admin-only (RBAC, same as every
other mutating endpoint in this API) since restoring a quarantined agent
is exactly as deliberate an action as restoring a quarantined strategy
(`apps/api/routers/learning.py` has no equivalent yet — this is the first
one, `packages/agents/reliability.py::restore_from_quarantine` mirrors
`packages/quant/learning/quarantine.py`'s precedent).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session, require_admin_role
from apps.api.schemas import (
    AgentMessageOut,
    AgentOut,
    AgentReliabilityOut,
    ContradictionOut,
    DecisionDetailOut,
    DecisionOut,
    RestoreAgentRequest,
)
from packages.agents import reliability
from packages.agents.specialists import SPECIALIST_REGISTRY
from packages.shared.models import AdminUser, Agent, AgentHealth, AgentMessageRow, Asset, Contradiction, Decision

router = APIRouter(prefix="/api/agents", tags=["agents"])
decisions_router = APIRouter(prefix="/api/decisions", tags=["decisions"])
contradictions_router = APIRouter(prefix="/api/contradictions", tags=["contradictions"])


def _agent_out(db: Session, agent: Agent) -> AgentOut:
    last_health = (
        db.execute(select(AgentHealth).where(AgentHealth.agent_code == agent.code).order_by(AgentHealth.ts.desc()).limit(1))
        .scalar_one_or_none()
    )
    latest_reliability = reliability.latest_reliability(db, agent.code)
    return AgentOut(
        code=agent.code, name=agent.name, directional=agent.directional, version=agent.version, status=agent.status,
        quarantined_at=agent.quarantined_at, quarantine_reason=agent.quarantine_reason,
        last_health_status=last_health.status if last_health else None,
        last_seen_at=last_health.ts if last_health else None,
        reliability=AgentReliabilityOut.model_validate(latest_reliability) if latest_reliability else None,
    )


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[AgentOut]:
    reliability.sync_agents_from_registry(db)
    agents = db.execute(select(Agent).order_by(Agent.code)).scalars().all()
    return [_agent_out(db, agent) for agent in agents]


@router.get("/{code}", response_model=AgentOut)
def get_agent(code: str, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> AgentOut:
    if code not in SPECIALIST_REGISTRY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown agent code")
    agent = db.get(Agent, code)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not yet synced -- no cycle has run")
    return _agent_out(db, agent)


@router.get("/{code}/messages", response_model=list[AgentMessageOut])
def list_agent_messages(
    code: str, limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[AgentMessageOut]:
    if code not in SPECIALIST_REGISTRY:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown agent code")
    rows = db.execute(
        select(AgentMessageRow, Asset)
        .outerjoin(Asset, Asset.id == AgentMessageRow.asset_id)
        .where(AgentMessageRow.agent_code == code)
        .order_by(AgentMessageRow.generated_at.desc())
        .limit(limit)
    ).all()
    return [
        AgentMessageOut(
            id=message.id, agent_code=message.agent_code, asset_symbol=asset.symbol if asset else None,
            status=message.status, signal=message.signal, confidence=message.confidence, evidence=message.evidence,
            risk_flags=message.risk_flags, rationale=message.rationale, generated_at=message.generated_at,
            expires_at=message.expires_at,
        )
        for message, asset in rows
    ]


@router.post("/{code}/restore", response_model=AgentOut)
def restore_agent(
    code: str, body: RestoreAgentRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role)
) -> AgentOut:
    if not body.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm=true required")
    try:
        agent = reliability.restore_from_quarantine(db, code, actor=admin.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _agent_out(db, agent)


@decisions_router.get("", response_model=list[DecisionOut])
def list_decisions(
    asset_id: int | None = None, decision_state: str | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[DecisionOut]:
    query = select(Decision, Asset).join(Asset, Asset.id == Decision.asset_id).order_by(Decision.ts.desc())
    if asset_id is not None:
        query = query.where(Decision.asset_id == asset_id)
    if decision_state is not None:
        query = query.where(Decision.decision_state == decision_state)
    rows = db.execute(query.limit(limit)).all()
    return [
        DecisionOut(
            id=d.id, asset_symbol=asset.symbol, ts=d.ts, decision_state=d.decision_state,
            consensus_score=d.consensus_score, contradiction_score=d.contradiction_score,
            reasoning_summary=d.reasoning_summary, blocked_reason=d.blocked_reason,
            critical_agent_failure=d.critical_agent_failure,
        )
        for d, asset in rows
    ]


@decisions_router.get("/{decision_id}", response_model=DecisionDetailOut)
def get_decision(decision_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> DecisionDetailOut:
    row = db.execute(select(Decision, Asset).join(Asset, Asset.id == Decision.asset_id).where(Decision.id == decision_id)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="decision not found")
    decision, asset = row
    contradictions = db.execute(select(Contradiction).where(Contradiction.decision_id == decision_id)).scalars().all()
    return DecisionDetailOut(
        id=decision.id, asset_symbol=asset.symbol, ts=decision.ts, decision_state=decision.decision_state,
        consensus_score=decision.consensus_score, contradiction_score=decision.contradiction_score,
        reasoning_summary=decision.reasoning_summary, blocked_reason=decision.blocked_reason,
        critical_agent_failure=decision.critical_agent_failure, agent_inputs=decision.agent_inputs,
        contradictions=[ContradictionOut.model_validate(c) for c in contradictions],
    )


@contradictions_router.get("", response_model=list[ContradictionOut])
def list_contradictions(
    decision_id: int | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ContradictionOut]:
    query = select(Contradiction).order_by(Contradiction.id.desc())
    if decision_id is not None:
        query = query.where(Contradiction.decision_id == decision_id)
    rows = db.execute(query.limit(limit)).scalars().all()
    return [ContradictionOut.model_validate(c) for c in rows]
