"""Broker endpoints — "PROMPT 13" §105.

Read-only (get_current_admin, same as every other read endpoint in this
codebase — admin OR viewer). Constructs its own PaperBrokerAdapter per
request, same established pattern as apps/api/routers/trading_control.py's
manual close-position action and apps/api/routers/market.py's
get_market_data_provider() calls — the API process and the worker process
are separate, each builds its own short-lived adapter/registry per call.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import BrokerCapabilitiesOut, BrokerHealthOut, BrokerOut
from packages.execution.broker.paper import PaperBrokerAdapter
from packages.execution.broker.registry import BrokerRegistry, get_or_create_broker_row
from packages.execution.health import assess_broker_health
from packages.execution.secrets import EnvSecretProvider, is_broker_configured
from packages.shared.models import AdminUser, Broker

router = APIRouter(prefix="/api/brokers", tags=["brokers"])


def _build_registry(db: Session) -> BrokerRegistry:
    registry = BrokerRegistry()
    registry.register(PaperBrokerAdapter(db), is_default=True)
    return registry


def _broker_out(broker_row: Broker, adapter) -> BrokerOut:  # noqa: ANN001 - BrokerAdapter Protocol
    return BrokerOut(
        id=broker_row.id, name=broker_row.name, kind=broker_row.kind, status=broker_row.status,
        is_default=broker_row.is_default,
        configured=is_broker_configured(EnvSecretProvider(), broker_name=broker_row.name),
        capabilities=BrokerCapabilitiesOut(**asdict(adapter.get_capabilities())),
    )


@router.get("", response_model=list[BrokerOut])
def list_brokers(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> list[BrokerOut]:
    registry = _build_registry(db)
    out: list[BrokerOut] = []
    for adapter in registry.list():
        broker_row = get_or_create_broker_row(db, name=adapter.name, kind=adapter.kind)
        db.commit()
        out.append(_broker_out(broker_row, adapter))
    return out


@router.get("/{broker_id}", response_model=BrokerOut)
def get_broker(broker_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> BrokerOut:
    broker_row = db.get(Broker, broker_id)
    if broker_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found")
    registry = _build_registry(db)
    adapter = registry.get(broker_row.name)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker adapter not registered")
    return _broker_out(broker_row, adapter)


@router.get("/{broker_id}/health", response_model=BrokerHealthOut)
def get_broker_health(broker_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> BrokerHealthOut:
    broker_row = db.get(Broker, broker_id)
    if broker_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker not found")
    registry = _build_registry(db)
    adapter = registry.get(broker_row.name)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker adapter not registered")
    assessment = assess_broker_health(db, adapter, broker_id=broker_row.id)
    return BrokerHealthOut(
        broker_name=broker_row.name, state=assessment.state, latency_ms=assessment.latency_ms,
        recent_error_count=assessment.recent_error_count, reasons=assessment.reasons,
    )
