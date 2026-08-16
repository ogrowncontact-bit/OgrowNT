"""Alerts API — docs/blueprint/03-api-spec.md §Alerts,
docs/blueprint/09-dashboard-spec.md §7 (screen 7). The read side of the
Alert rows written throughout the system (packages/quant/learning/*,
packages/risk/monitor.py, apps/api/routers/system.py) and delivered by
apps/worker/alerts.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import AlertOut
from packages.shared.models import AdminUser, Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    severity: str | None = None, acknowledged: bool | None = None, limit: int = 50, db: Session = Depends(get_session)
) -> list[Alert]:
    query = db.query(Alert)
    if severity is not None:
        query = query.filter(Alert.severity == severity)
    if acknowledged is not None:
        query = query.filter(Alert.acknowledged == acknowledged)
    return query.order_by(Alert.ts.desc()).limit(limit).all()


@router.post("/{alert_id}/ack", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.acknowledged = True
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
