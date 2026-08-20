"""Human Approval Workflow + Audit Trail — "PROMPT 10" §64, §90-91.

`ResearchApproval` is the ONLY door between something this phase's engines
propose and something that actually changes: `request_approval` records a
pending request; `record_decision` requires a non-empty human `reviewer`
and, only on an "approved" decision, applies the corresponding state
change via `packages.research.versioning` (never directly) or by flipping
a `ResearchHypothesis.status`. A rejected or request_more_tests decision
changes nothing beyond the `ResearchApproval` row itself — the whole point
of this module is that NOTHING in `packages/research/*` or
`apps/research_worker/*` can reach a production-affecting state on its
own. Every decision also writes an `AuditLog` row, so "who approved what
and when" is answerable the same way every other admin-gated action in
this codebase already is (`packages/agents/reliability.py::restore_from_quarantine`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.research import versioning
from packages.shared.models import AuditLog, ResearchApproval, ResearchHypothesis, StrategyRow, StrategyVersion
from packages.shared.models import Experiment as ExperimentRow

ENTITY_HYPOTHESIS = "hypothesis"
ENTITY_STRATEGY_VERSION = "strategy_version"
ENTITY_EXPERIMENT = "experiment"
ENTITY_TYPES = (ENTITY_HYPOTHESIS, ENTITY_STRATEGY_VERSION, ENTITY_EXPERIMENT)

ACTION_APPROVE = "approve"
ACTION_REJECT = "reject"
ACTION_REQUEST_MORE_TESTS = "request_more_tests"
ACTION_PROMOTE = "promote"
ACTION_ROLLBACK = "rollback"
ACTION_QUARANTINE = "quarantine"
ACTIONS = (ACTION_APPROVE, ACTION_REJECT, ACTION_REQUEST_MORE_TESTS, ACTION_PROMOTE, ACTION_ROLLBACK, ACTION_QUARANTINE)

STATUS_PENDING = "pending_review"
DECISION_STATUSES = (STATUS_PENDING, "approved", "rejected", ACTION_REQUEST_MORE_TESTS)


def request_approval(
    db: Session, *, entity_type: str, entity_id: int, action: str, evidence: dict, detail: str | None = None,
) -> ResearchApproval:
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"unknown entity_type: {entity_type!r} (expected one of {ENTITY_TYPES})")
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action!r} (expected one of {ACTIONS})")

    row = ResearchApproval(
        entity_type=entity_type, entity_id=entity_id, action=action, status=STATUS_PENDING, evidence=evidence, detail=detail,
    )
    db.add(row)
    db.commit()
    return row


def list_pending_approvals(db: Session, *, entity_type: str | None = None) -> list[ResearchApproval]:
    stmt = select(ResearchApproval).where(ResearchApproval.status == STATUS_PENDING)
    if entity_type is not None:
        stmt = stmt.where(ResearchApproval.entity_type == entity_type)
    return list(db.execute(stmt.order_by(ResearchApproval.created_at.asc())).scalars().all())


def record_decision(db: Session, approval_id: int, *, decision: str, reviewer: str, detail: str | None = None) -> ResearchApproval:
    if decision not in ("approved", "rejected", ACTION_REQUEST_MORE_TESTS):
        raise ValueError(f"unknown decision: {decision!r} (expected 'approved', 'rejected', or {ACTION_REQUEST_MORE_TESTS!r})")
    if not reviewer or not reviewer.strip():
        raise ValueError("a review decision requires a non-empty human reviewer identity")

    approval = db.get(ResearchApproval, approval_id)
    if approval is None:
        raise ValueError(f"unknown ResearchApproval id: {approval_id!r}")
    if approval.status != STATUS_PENDING:
        raise ValueError(f"approval {approval_id} was already resolved (status={approval.status!r})")

    if decision == "approved":
        # Applied BEFORE the approval row itself is marked resolved: if this
        # raises (e.g. a spoofed/stale entity_id), nothing about `approval`
        # has changed yet -- it honestly stays pending_review rather than
        # recording "approved" for a promotion that never actually happened.
        _apply_approved_action(db, approval, reviewer=reviewer)

    approval.status = decision
    approval.reviewer = reviewer
    approval.reviewed_at = datetime.now(timezone.utc)
    if detail is not None:
        approval.detail = detail
    db.add(
        AuditLog(
            actor=reviewer, action=f"research_approval_{decision}", entity_type=approval.entity_type,
            entity_id=approval.entity_id, detail={"approval_id": approval.id, "requested_action": approval.action},
        )
    )
    db.commit()
    return approval


def _apply_approved_action(db: Session, approval: ResearchApproval, *, reviewer: str) -> None:
    if approval.entity_type == ENTITY_HYPOTHESIS:
        hypothesis = db.get(ResearchHypothesis, approval.entity_id)
        if hypothesis is not None:
            hypothesis.status = "approved"
            db.commit()
        return

    if approval.entity_type == ENTITY_STRATEGY_VERSION:
        version = db.get(StrategyVersion, approval.entity_id)
        if version is None:
            return
        if approval.action == ACTION_PROMOTE:
            if version.lifecycle_status == versioning.LIFECYCLE_EXPERIMENTAL:
                versioning.promote_to_challenger(db, version.id, reviewer=reviewer)
            elif version.lifecycle_status == versioning.LIFECYCLE_CHALLENGER:
                versioning.promote_to_champion(db, version.id, reviewer=reviewer)
            else:
                raise ValueError(f"cannot promote a strategy_version with lifecycle_status={version.lifecycle_status!r}")
        elif approval.action == ACTION_ROLLBACK:
            versioning.rollback(db, version.strategy_id, reviewer=reviewer, to_version_id=version.id)
        elif approval.action == ACTION_QUARANTINE:
            versioning.quarantine_version(db, version.id, reviewer=reviewer, reason=approval.detail or "quarantined via approval workflow")
        elif approval.action == ACTION_REJECT:
            versioning.retire(db, version.id, reviewer=reviewer, reason=approval.detail or "rejected via approval workflow")
        return

    if approval.entity_type == ENTITY_EXPERIMENT and approval.action == ACTION_PROMOTE:
        _promote_experiment_to_version(db, approval, reviewer=reviewer)


def _promote_experiment_to_version(db: Session, approval: ResearchApproval, *, reviewer: str) -> StrategyVersion:
    """A human approving `action="promote"` on an EXPERIMENT (not yet a
    `StrategyVersion`) is how a validated control-vs-candidate result
    actually becomes a new, persisted, EXPERIMENTAL-lifecycle version —
    closing the propose -> approve -> persist loop §64 requires stay
    manual at the final step.
    """
    experiment = db.get(ExperimentRow, approval.entity_id)
    if experiment is None or experiment.result is None:
        raise ValueError(f"experiment {approval.entity_id} not found or has no result yet")

    candidate = experiment.candidate or {}
    strategy_code = candidate.get("strategy_code")
    strategy = db.execute(select(StrategyRow).where(StrategyRow.code == strategy_code)).scalars().first()
    if strategy is None:
        raise ValueError(f"no registered strategy for code {strategy_code!r}")

    candidate_report = experiment.result.get("candidate_report") or {}
    changed = experiment.result.get("changed_params") or []
    changes = [f"from experiment #{experiment.id}: {param} changed"[:200] for param in changed] or [f"from experiment #{experiment.id}"]

    return versioning.create_version(
        db, strategy_id=strategy.id, params=candidate.get("params", {}), changes=changes,
        validation_status=candidate_report.get("quality_status", "EXPERIMENTAL"),
        lifecycle_status=versioning.LIFECYCLE_EXPERIMENTAL, created_by=reviewer, performance=candidate_report,
    )
