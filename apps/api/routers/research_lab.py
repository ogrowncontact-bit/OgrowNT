"""Autonomous Research Lab API — "PROMPT 10" §90-91.

Prefix `/api/research-lab`, deliberately distinct from the existing
`/api/research` (Phase 5's `LearnedRule` endpoints, a narrower and older
concept — see `packages/shared/models.py::ResearchHypothesis`'s docstring
for why the two are not merged).

Every GET is read-only. The only mutations are POST /approvals (create a
pending review) and POST /approvals/{id}/decide (record a human decision)
and POST /queue (enqueue a research_queue job for apps/research_worker to
pick up) — all admin-only (RBAC), and `decide` is the ONLY endpoint in
this router that can ever change a `StrategyVersion`'s lifecycle_status or
a `ResearchHypothesis`'s status, via `packages.research.approval`'s
human-reviewer requirement. Nothing in this router can promote a strategy
version, approve an experiment, or touch live trading state on its own.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session, require_admin_role
from apps.api.schemas import (
    ApprovalDecisionRequest,
    DriftDetectionOut,
    EnqueueResearchJobRequest,
    ExperimentOut,
    RequestApprovalRequest,
    ResearchApprovalOut,
    ResearchBudgetStatusOut,
    ResearchHypothesisOut,
    ResearchKnowledgeEdgeOut,
    ResearchQueueItemOut,
    StrategyVersionOut,
)
from packages.research import approval as approval_pkg
from packages.research import budget
from packages.research.report import generate_research_report
from packages.research.versioning import get_lineage
from packages.shared.models import (
    AdminUser,
    DriftDetection,
    ResearchApproval,
    ResearchHypothesis,
    ResearchKnowledgeEdge,
    ResearchQueueItem,
    StrategyVersion,
)
from packages.shared.models import Experiment as ExperimentRow

router = APIRouter(prefix="/api/research-lab", tags=["research-lab"])


@router.get("/report")
def get_research_report(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> dict:
    return asdict(generate_research_report(db))


@router.get("/hypotheses", response_model=list[ResearchHypothesisOut])
def list_hypotheses(
    status_filter: str | None = None, limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ResearchHypothesis]:
    stmt = select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc()).limit(limit)
    if status_filter is not None:
        stmt = stmt.where(ResearchHypothesis.status == status_filter)
    return list(db.execute(stmt).scalars().all())


@router.get("/hypotheses/{hypothesis_id}", response_model=ResearchHypothesisOut)
def get_hypothesis(hypothesis_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> ResearchHypothesis:
    hypothesis = db.get(ResearchHypothesis, hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hypothesis not found")
    return hypothesis


@router.get("/experiments", response_model=list[ExperimentOut])
def list_experiments(
    status_filter: str | None = None, hypothesis_id: int | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ExperimentRow]:
    stmt = select(ExperimentRow).order_by(ExperimentRow.created_at.desc()).limit(limit)
    if status_filter is not None:
        stmt = stmt.where(ExperimentRow.status == status_filter)
    if hypothesis_id is not None:
        stmt = stmt.where(ExperimentRow.hypothesis_id == hypothesis_id)
    return list(db.execute(stmt).scalars().all())


@router.get("/experiments/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> ExperimentRow:
    experiment = db.get(ExperimentRow, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    return experiment


@router.get("/strategy-versions", response_model=list[StrategyVersionOut])
def list_strategy_versions(
    strategy_id: int | None = None, lifecycle_status: str | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[StrategyVersion]:
    stmt = select(StrategyVersion).order_by(StrategyVersion.created_at.desc()).limit(limit)
    if strategy_id is not None:
        stmt = stmt.where(StrategyVersion.strategy_id == strategy_id)
    if lifecycle_status is not None:
        stmt = stmt.where(StrategyVersion.lifecycle_status == lifecycle_status)
    return list(db.execute(stmt).scalars().all())


@router.get("/strategy-versions/{version_id}", response_model=StrategyVersionOut)
def get_strategy_version(version_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> StrategyVersion:
    version = db.get(StrategyVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy_version not found")
    return version


@router.get("/strategy-versions/{version_id}/lineage", response_model=list[StrategyVersionOut])
def get_strategy_version_lineage(
    version_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[StrategyVersion]:
    if db.get(StrategyVersion, version_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy_version not found")
    return get_lineage(db, version_id)


@router.get("/knowledge-edges", response_model=list[ResearchKnowledgeEdgeOut])
def list_knowledge_edges(
    subject: str | None = None, relation: str | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ResearchKnowledgeEdge]:
    stmt = select(ResearchKnowledgeEdge).order_by(ResearchKnowledgeEdge.confidence.desc()).limit(limit)
    if subject is not None:
        stmt = stmt.where(ResearchKnowledgeEdge.subject == subject)
    if relation is not None:
        stmt = stmt.where(ResearchKnowledgeEdge.relation == relation)
    return list(db.execute(stmt).scalars().all())


@router.get("/drift", response_model=list[DriftDetectionOut])
def list_drift_detections(
    drift_type: str | None = None, limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[DriftDetection]:
    stmt = select(DriftDetection).order_by(DriftDetection.ts.desc()).limit(limit)
    if drift_type is not None:
        stmt = stmt.where(DriftDetection.drift_type == drift_type)
    return list(db.execute(stmt).scalars().all())


@router.get("/budget", response_model=list[ResearchBudgetStatusOut])
def get_budget_status(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[budget.BudgetStatus]:
    return [budget.check_budget(db, resource_type=rt) for rt in budget.RESOURCE_TYPES]


@router.get("/approvals", response_model=list[ResearchApprovalOut])
def list_approvals(
    pending_only: bool = True, entity_type: str | None = None, limit: int = 50,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ResearchApproval]:
    if pending_only:
        return approval_pkg.list_pending_approvals(db, entity_type=entity_type)[:limit]
    stmt = select(ResearchApproval).order_by(ResearchApproval.created_at.desc()).limit(limit)
    if entity_type is not None:
        stmt = stmt.where(ResearchApproval.entity_type == entity_type)
    return list(db.execute(stmt).scalars().all())


@router.post("/approvals", response_model=ResearchApprovalOut)
def create_approval_request(
    body: RequestApprovalRequest, db: Session = Depends(get_session), _: AdminUser = Depends(require_admin_role),
) -> ResearchApproval:
    try:
        return approval_pkg.request_approval(
            db, entity_type=body.entity_type, entity_id=body.entity_id, action=body.action, evidence=body.evidence, detail=body.detail,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/decide", response_model=ResearchApprovalOut)
def decide_approval(
    approval_id: int, body: ApprovalDecisionRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role),
) -> ResearchApproval:
    try:
        return approval_pkg.record_decision(db, approval_id, decision=body.decision, reviewer=admin.email, detail=body.detail)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/queue", response_model=list[ResearchQueueItemOut])
def list_queue_items(
    status_filter: str | None = None, limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[ResearchQueueItem]:
    stmt = select(ResearchQueueItem).order_by(ResearchQueueItem.created_at.desc()).limit(limit)
    if status_filter is not None:
        stmt = stmt.where(ResearchQueueItem.status == status_filter)
    return list(db.execute(stmt).scalars().all())


@router.post("/queue", response_model=ResearchQueueItemOut)
def enqueue_research_job(
    body: EnqueueResearchJobRequest, db: Session = Depends(get_session), _: AdminUser = Depends(require_admin_role),
) -> ResearchQueueItem:
    if body.queue_type not in (
        "hypothesis", "experiment", "feature_test", "strategy_test", "regime_test", "event_test", "knowledge_update",
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown queue_type: {body.queue_type!r}")
    item = ResearchQueueItem(queue_type=body.queue_type, payload=body.payload, status="queued")
    db.add(item)
    db.commit()
    return item
