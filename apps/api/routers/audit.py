"""Audit Center — "PROMPT 14" §94-95.

`AuditLog` (packages/shared/models.py, Phase 1) has been written to since
Phase 1 by every admin/system mutation (kill switch, risk-limit changes,
agent restore, research approvals, strategy promotion/quarantine...) but had
no GET endpoint anywhere until this phase — write-only from the API's own
perspective. This router adds exactly that read surface, nothing else: no
new write path, no new audit-producing logic (§95's "auditoria não deve ser
facilmente alterável pelos agentes" already holds by construction — nothing
in this router, or anywhere else, ever UPDATEs or DELETEs an AuditLog row).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import AuditLogOut
from packages.shared.models import AdminUser, AuditLog

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    limit: int = 100,
    actor: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[AuditLog]:
    limit = min(max(limit, 1), 500)
    query = db.query(AuditLog)
    if actor is not None:
        query = query.filter(AuditLog.actor == actor)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.id.desc()).limit(limit).all()
