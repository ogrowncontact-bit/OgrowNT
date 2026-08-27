"""Incident Center — "PROMPT 14" §59-62.

Incidents are auto-created by packages/events/tailer.py (apps/api/realtime.py's
tail loop) from this system's own EXISTING critical-event detectors — this
router adds no new detection logic, only the durable, admin-workable
lifecycle §61 asks for. `status` is a manually-driven state machine since
none of those detectors know how to auto-mitigate/auto-recover on their own.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session, require_admin_role
from apps.api.schemas import IncidentOut, IncidentUpdateIn
from packages.shared.models import AdminUser, AuditLog, Incident

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# §61's literal order — a transition may skip stages forward (a trivial
# incident can jump straight from 'detected' to 'resolved') but never move
# backward through this endpoint; reopening a closed incident is deliberately
# out of scope for this phase (a genuinely new occurrence creates a NEW
# Incident row instead — packages/events/tailer.py's own idempotency check).
_LIFECYCLE_ORDER = ("detected", "investigating", "mitigated", "recovering", "resolved", "closed")


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status_filter: str | None = None,
    category: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[Incident]:
    limit = min(max(limit, 1), 500)
    query = db.query(Incident)
    if status_filter is not None:
        query = query.filter(Incident.status == status_filter)
    if category is not None:
        query = query.filter(Incident.category == category)
    return query.order_by(Incident.detected_at.desc()).limit(limit).all()


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="incident not found")
    return incident


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int,
    payload: IncidentUpdateIn,
    db: Session = Depends(get_session),
    admin: AdminUser = Depends(require_admin_role),
) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="incident not found")

    if payload.status is not None:
        if payload.status not in _LIFECYCLE_ORDER:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"invalid status: {payload.status}")
        if _LIFECYCLE_ORDER.index(payload.status) < _LIFECYCLE_ORDER.index(incident.status):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"cannot move an incident backward from '{incident.status}' to '{payload.status}'",
            )
        incident.status = payload.status
        if payload.status == "resolved" and incident.resolved_at is None:
            incident.resolved_at = datetime.now(timezone.utc)

    if payload.description is not None:
        incident.description = payload.description

    db.add(incident)
    db.add(
        AuditLog(
            actor=admin.email, action="incident_updated", entity_type="incident", entity_id=incident.id,
            detail={"status": payload.status, "description_changed": payload.description is not None},
        )
    )
    db.commit()
    db.refresh(incident)
    return incident
