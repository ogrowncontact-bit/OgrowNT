from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import ComponentHealth, HealthResponse, SystemStatusResponse
from packages.data.connectors.market.factory import get_market_data_provider
from packages.shared.models import AdminUser, AuditLog, SystemState

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_session)) -> HealthResponse:
    components: list[ComponentHealth] = []

    try:
        db.execute(text("SELECT 1"))
        components.append(ComponentHealth(name="database", status="green"))
    except Exception as exc:  # noqa: BLE001 - report, don't hide
        components.append(ComponentHealth(name="database", status="red", detail=str(exc)))

    try:
        provider = get_market_data_provider()
        connected = provider.is_connected()
        components.append(
            ComponentHealth(
                name="market_data",
                status="green" if connected else "red",
                detail=f"provider={provider.name}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        components.append(ComponentHealth(name="market_data", status="red", detail=str(exc)))

    # Components that arrive in later phases (news, AI services, risk engine,
    # execution, learning engine — docs/blueprint/09-dashboard-spec.md#6) are
    # intentionally omitted here rather than faked as green: they don't exist
    # yet in Phase 1.

    overall = "green" if all(c.status == "green" for c in components) else "degraded"
    return HealthResponse(overall=overall, components=components)


@router.get("/status", response_model=SystemStatusResponse)
def status_(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> SystemState:
    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


@router.post("/kill-switch", response_model=SystemStatusResponse)
def trigger_kill_switch(
    db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)
) -> SystemState:
    state = db.get(SystemState, True) or SystemState(id=True)
    state.safety_belt_level = "kill_switch"
    state.trading_enabled = False
    state.updated_reason = f"manual kill switch by {admin.email}"
    state.updated_at = datetime.now(timezone.utc)
    db.add(state)
    db.add(
        AuditLog(
            actor=admin.email,
            action="kill_switch_triggered",
            entity_type="system_state",
            detail={"trigger": "manual"},
        )
    )
    db.commit()
    db.refresh(state)
    return state


@router.post("/kill-switch/release", response_model=SystemStatusResponse)
def release_kill_switch(
    db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)
) -> SystemState:
    state = db.get(SystemState, True) or SystemState(id=True)
    state.safety_belt_level = "normal"
    state.trading_enabled = True
    state.updated_reason = f"manual release by {admin.email}"
    state.updated_at = datetime.now(timezone.utc)
    db.add(state)
    db.add(
        AuditLog(
            actor=admin.email,
            action="kill_switch_released",
            entity_type="system_state",
            detail={},
        )
    )
    db.commit()
    db.refresh(state)
    return state
