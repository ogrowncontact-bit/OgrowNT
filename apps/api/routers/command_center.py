"""Command Bar — "PROMPT 14" §91-93, §76-81.

§92: "A interface de linguagem pode: QUERY/ANALYZE/EXPLAIN/SUMMARIZE. Mas:
NO DIRECT EXECUTION." Every request is classified by
packages/system/command_router.py::classify_command() BEFORE this router
touches the database at all — an execution-verb input never reaches any
query logic below, let alone order_manager/broker code (which this router
doesn't import and couldn't reach anyway; see tests/
test_command_center_red_team.py). The safe-QUERY path is a small, curated
keyword router over already-existing data, not a full LLM NLU pipeline —
see command_router.py's own docstring for why that's a deliberate,
documented scope decision this phase, not an oversight.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import CommandQueryIn, CommandQueryOut
from packages.shared.models import (
    AdminUser,
    OpportunityScore,
    RiskDecision,
    Signal,
    StrategyPerformance,
    StrategyRow,
)
from packages.system.briefing import generate_daily_briefing
from packages.system.command_router import (
    INTENT_LAST_BLOCKED_TRADE,
    INTENT_RISK_SUMMARY,
    INTENT_TOP_OPPORTUNITIES,
    INTENT_UNDERPERFORMING_STRATEGIES,
    UNAUTHORIZED,
    classify_command,
    route_query_intent,
)

router = APIRouter(prefix="/api/command-center", tags=["command-center"])


def _top_opportunities(db: Session) -> list[dict]:
    rows = (
        db.query(OpportunityScore, Signal)
        .join(Signal, Signal.id == OpportunityScore.signal_id)
        .filter(OpportunityScore.tier != "ignore")
        .order_by(OpportunityScore.final_score.desc())
        .limit(5)
        .all()
    )
    return [{"signal_id": s.id, "final_score": sc.final_score, "tier": sc.tier} for sc, s in rows]


def _risk_summary(db: Session) -> dict:
    recent = db.query(RiskDecision).order_by(RiskDecision.id.desc()).limit(20).all()
    blocked = sum(1 for r in recent if not r.approved)
    return {"recent_decisions": len(recent), "recent_blocked": blocked}


def _underperforming_strategies(db: Session) -> list[dict]:
    rows = (
        db.query(StrategyPerformance, StrategyRow)
        .join(StrategyRow, StrategyRow.id == StrategyPerformance.strategy_id)
        .filter(StrategyPerformance.health_score.isnot(None))
        .order_by(StrategyPerformance.health_score.asc())
        .limit(5)
        .all()
    )
    return [{"strategy_code": s.code, "health_score": p.health_score} for p, s in rows]


def _last_blocked_trade(db: Session) -> dict | None:
    row = db.query(RiskDecision).filter(RiskDecision.approved.is_(False)).order_by(RiskDecision.id.desc()).first()
    if row is None:
        return None
    return {"signal_id": row.signal_id, "reason": row.reason, "created_at": row.created_at.isoformat()}


_INTENT_HANDLERS = {
    INTENT_TOP_OPPORTUNITIES: _top_opportunities,
    INTENT_RISK_SUMMARY: _risk_summary,
    INTENT_UNDERPERFORMING_STRATEGIES: _underperforming_strategies,
    INTENT_LAST_BLOCKED_TRADE: _last_blocked_trade,
}


@router.post("/query", response_model=CommandQueryOut)
def query_command_bar(
    payload: CommandQueryIn, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> CommandQueryOut:
    result = classify_command(payload.text)
    if result.classification == UNAUTHORIZED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result.reason)

    intent = route_query_intent(payload.text)
    handler = _INTENT_HANDLERS.get(intent)
    data = handler(db) if handler is not None else None
    return CommandQueryOut(classification=result.classification, intent=intent, data=data)


@router.get("/briefing")
def get_daily_briefing(
    window_hours: int = 24, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> dict:
    return asdict(generate_daily_briefing(db, window_hours=window_hours))
