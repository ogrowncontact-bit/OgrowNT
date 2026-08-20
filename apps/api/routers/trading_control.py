"""Autonomous trading control plane — "PROMPT 8" §58-59, §64-66, §78.

Deliberately does NOT duplicate GET /api/positions, /api/orders, /api/trades
(apps/api/routers/trading.py), /api/portfolio (routers/portfolio.py), or
POST /api/system/kill-switch (routers/system.py) under a /api/trading/*
alias — those already exist, are already tested, and the spec's request for
"/api/trading/*" paths is satisfied by treating this router as the home for
what's genuinely NEW (status/activity/performance reads, and the manual
controls), not a second copy of what already works. The dashboard's
Autonomous Trading Center composes both sets of endpoints.

Every manual control here is admin-only (require_admin_role — "PROMPT 8"
§77 RBAC) and writes a ManualAction row with a full before/after snapshot
(§65), on top of whatever TradingEvent the underlying operation already
emits on its own (packages/execution/order_manager.py, this module).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session, require_admin_role
from apps.api.schemas import (
    AutonomousStatusOut,
    CloseOrCancelReasonRequest,
    ManualActionOut,
    OrderOut,
    PauseRequest,
    PositionOut,
    ResetAccountRequest,
    SystemStatusResponse,
    TradingEventOut,
    TradingPerformanceOut,
)
from packages.execution.adapters.paper import PaperExecutionProvider
from packages.execution.order_manager import close_position
from packages.portfolio.state import compute_state, refresh_snapshot
from packages.shared.models import AdminUser, Asset, ManualAction, Order, Position, StrategyRow, Trade, TradingEvent
from packages.shared.settings import get_settings
from packages.shared.worker_health import compute_autonomous_status, is_heartbeat_stale

router = APIRouter(prefix="/api/trading", tags=["trading-control"])


def _get_or_create_system_state(db: Session):
    from packages.shared.models import SystemState

    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _position_out(db: Session, position: Position, asset: Asset, strategy: StrategyRow) -> PositionOut:
    return PositionOut(
        id=position.id, asset_symbol=asset.symbol, strategy_code=strategy.code, direction=position.direction,
        entry_price=position.entry_price, current_stop=position.current_stop, target_price=position.target_price,
        size=position.size, opened_at=position.opened_at, closed_at=position.closed_at, status=position.status,
        unrealized_pnl=position.unrealized_pnl, realized_pnl=position.realized_pnl,
        exit_price=position.exit_price, exit_reason=position.exit_reason,
    )


@router.get("/status", response_model=AutonomousStatusOut)
def get_autonomous_status(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> AutonomousStatusOut:
    state = _get_or_create_system_state(db)
    settings = get_settings()
    worker_alive = not is_heartbeat_stale(state.worker_last_heartbeat, scan_interval_seconds=settings.scan_interval_seconds)
    autonomous_status = compute_autonomous_status(state, safety_belt_level=state.safety_belt_level, worker_alive=worker_alive)
    open_positions_count = db.query(Position).filter(Position.status == "open").count()

    return AutonomousStatusOut(
        status=autonomous_status, trading_mode=state.trading_mode, trading_enabled=state.trading_enabled,
        trading_paused=state.trading_paused, paused_reason=state.paused_reason, safety_belt_level=state.safety_belt_level,
        worker_alive=worker_alive, worker_last_heartbeat=state.worker_last_heartbeat,
        open_positions_count=open_positions_count, worker_restart_count=state.worker_restart_count,
    )


@router.get("/activity", response_model=list[TradingEventOut])
def get_activity_feed(
    limit: int = 100, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[TradingEventOut]:
    """§59's "# AI ACTIVITY" feed — the raw packages/shared/models.py
    TradingEvent stream, newest first."""
    limit = min(max(limit, 1), 500)
    rows = db.execute(select(TradingEvent).order_by(TradingEvent.id.desc()).limit(limit)).scalars().all()
    return [TradingEventOut.model_validate(r) for r in rows]


@router.get("/performance", response_model=TradingPerformanceOut)
def get_realtime_performance(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> TradingPerformanceOut:
    """§45 real-time performance metrics — today's trades/win-rate plus the
    current portfolio snapshot, all cheap aggregate queries (never a full
    analytics recompute inline in the request — that's
    GET /api/analytics/overview's job, on its own cadence)."""
    state = _get_or_create_system_state(db)
    portfolio_state = compute_state(db)

    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    todays_trades = db.query(Trade).filter(Trade.closed_at >= day_start).all()
    wins = sum(1 for t in todays_trades if t.outcome == "win")
    losses = sum(1 for t in todays_trades if t.outcome == "loss")
    win_rate = (wins / len(todays_trades) * 100) if todays_trades else None

    autonomous_status = compute_autonomous_status(
        state, safety_belt_level=state.safety_belt_level,
        worker_alive=not is_heartbeat_stale(state.worker_last_heartbeat, scan_interval_seconds=get_settings().scan_interval_seconds),
    )

    return TradingPerformanceOut(
        trades_today=len(todays_trades), wins_today=wins, losses_today=losses, win_rate_today=win_rate,
        daily_pnl=portfolio_state.daily_pnl, open_positions_count=len(portfolio_state.open_positions),
        exposure_pct=portfolio_state.exposure_pct, drawdown_pct=portfolio_state.drawdown_pct,
        safety_belt_level=state.safety_belt_level, autonomous_status=autonomous_status,
    )


@router.post("/pause", response_model=SystemStatusResponse)
def pause_trading(
    payload: PauseRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role)
) -> SystemStatusResponse:
    """§64 PAUSE — voluntary and reversible, distinct from the Kill Switch
    (POST /api/system/kill-switch): trading_enabled stays True."""
    state = _get_or_create_system_state(db)
    before = {"trading_paused": state.trading_paused, "paused_reason": state.paused_reason}
    now = datetime.now(timezone.utc)
    state.trading_paused = True
    state.paused_reason = payload.reason
    state.paused_at = now
    db.add(state)
    after = {"trading_paused": True, "paused_reason": payload.reason}
    db.add(
        ManualAction(
            actor=admin.email, action="pause", entity_type="system_state", reason=payload.reason, before=before, after=after,
        )
    )
    db.add(TradingEvent(event_type="trading_paused", entity_type="system_state", payload={"reason": payload.reason, "actor": admin.email}))
    db.commit()
    db.refresh(state)
    return state


@router.post("/resume", response_model=SystemStatusResponse)
def resume_trading(db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role)) -> SystemStatusResponse:
    state = _get_or_create_system_state(db)
    before = {"trading_paused": state.trading_paused, "paused_reason": state.paused_reason}
    state.trading_paused = False
    state.paused_reason = None
    state.paused_at = None
    db.add(state)
    after = {"trading_paused": False, "paused_reason": None}
    db.add(ManualAction(actor=admin.email, action="resume", entity_type="system_state", before=before, after=after))
    db.add(TradingEvent(event_type="trading_resumed", entity_type="system_state", payload={"actor": admin.email}))
    db.commit()
    db.refresh(state)
    return state


@router.post("/positions/{position_id}/close", response_model=PositionOut)
def close_paper_position(
    position_id: int, payload: CloseOrCancelReasonRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role),
) -> PositionOut:
    """§64 CLOSE PAPER POSITION. Deliberately does not run the Learning
    Agent side effects apps/worker/trade_monitor.py's own close path does
    (Pattern Memory, Strategy Health, Quarantine, Trade Journal) — apps/api
    never imports from apps/worker (docs/blueprint/01-repo-structure.md),
    and a manual override isn't evidence about the strategy's own edge the
    same way an autonomous exit is. The trade itself is still fully
    recorded (positions/orders/trades), just not folded into strategy
    learning stats.
    """
    position = db.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    if position.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Position is already closed")
    asset = db.get(Asset, position.asset_id)
    strategy = db.get(StrategyRow, position.strategy_id)
    if asset is None or strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position's asset or strategy row missing")

    before = {"status": position.status, "size": position.size, "current_stop": position.current_stop}
    provider = PaperExecutionProvider(db)
    trade = close_position(db, provider, position, asset=asset, exit_reason="manual_close")
    if trade is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="DATA_UNAVAILABLE — could not fill the closing order right now")

    after = {"status": position.status, "exit_price": position.exit_price, "realized_pnl": position.realized_pnl}
    db.add(
        ManualAction(
            actor=admin.email, action="close_position", entity_type="position", entity_id=position.id,
            reason=payload.reason, before=before, after=after,
        )
    )
    db.commit()
    return _position_out(db, position, asset, strategy)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_paper_order(
    order_id: int, payload: CloseOrCancelReasonRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role),
) -> Order:
    """§64 CANCEL PAPER ORDER. Honest limitation, same one
    packages/execution/adapters/paper.py's cancel_order() already documents:
    the paper provider fills market orders synchronously, so no Order ever
    actually sits in 'new'/'submitted' long enough to cancel today. This
    endpoint is fully functional for whenever a future order type or
    provider produces a real pending state."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status not in ("new", "submitted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is already '{order.status}', not cancellable")

    before = {"status": order.status}
    order.status = "cancelled"
    db.add(order)
    after = {"status": "cancelled"}
    db.add(
        ManualAction(
            actor=admin.email, action="cancel_order", entity_type="order", entity_id=order.id,
            reason=payload.reason, before=before, after=after,
        )
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/reset-paper", response_model=SystemStatusResponse)
def reset_paper_account(
    payload: ResetAccountRequest, db: Session = Depends(get_session), admin: AdminUser = Depends(require_admin_role),
) -> SystemStatusResponse:
    """§64/§66 RESET PAPER ACCOUNT — requires explicit confirm=true, and
    refuses while any position is open (closing risk silently as a side
    effect of a reset is exactly the "comportamento implícito" §30
    forbids). Every PortfolioSnapshot/Order/Trade from before the reset
    stays in the DB untouched (append-only, fully auditable) — only
    SystemState.last_reset_at moves, which is what
    packages/portfolio/state.py and packages/portfolio/reconciliation.py
    both key off of to treat this as the account's fresh start.
    """
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm=true is required to reset the paper account")

    open_count = db.query(Position).filter(Position.status == "open").count()
    if open_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"{open_count} open position(s) must be closed before resetting the account",
        )

    before_state = compute_state(db)
    before = {"equity": before_state.equity, "cash": before_state.cash, "drawdown_pct": before_state.drawdown_pct}

    state = _get_or_create_system_state(db)
    state.last_reset_at = datetime.now(timezone.utc)
    db.add(state)
    db.commit()

    capital = get_settings().initial_paper_capital
    refresh_snapshot(db, cash=capital, safety_belt_level="normal")
    after = {"equity": capital, "cash": capital, "drawdown_pct": 0.0}

    db.add(
        ManualAction(
            actor=admin.email, action="reset_paper_account", entity_type="system_state", before=before, after=after,
        )
    )
    db.commit()
    db.refresh(state)
    return state


@router.get("/manual-actions", response_model=list[ManualActionOut])
def list_manual_actions(
    limit: int = 100, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[ManualActionOut]:
    limit = min(max(limit, 1), 500)
    rows = db.execute(select(ManualAction).order_by(ManualAction.id.desc()).limit(limit)).scalars().all()
    return [ManualActionOut.model_validate(r) for r in rows]
