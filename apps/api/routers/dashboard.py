"""Command Center aggregation endpoints — "PROMPT 14" §130.

Each endpoint bundles a handful of ALREADY-EXISTING endpoint functions
(apps/api/routers/*.py) into one response, so a routed Command Center page
(apps/dashboard/app/command-center/**) needs one round trip instead of
re-fetching the same 5-8 endpoints the old all-in-one /dashboard page always
fetched together. Every call below is a plain Python function call to
another router's own handler (FastAPI route handlers are ordinary functions
— the `Depends(...)` defaults on their `db`/admin parameters are simply
overridden with the real objects this router already has), never a second
copy of the underlying query. No aggregator here computes anything its
target page couldn't already get by calling the individual endpoints
one-by-one — this is composition for round-trip efficiency, not new
business logic.

`_dump()` exists because some of those handlers return already-constructed
Pydantic `...Out` objects (most do) while a few (list_watchlist, list_clusters,
list_universe, list_volatility_events, list_anomalies, list_strategies, and
this router's own list_incidents/list_audit_log) return raw SQLAlchemy rows,
relying on FastAPI's `response_model=` to serialize them ONLY when reached
through actual HTTP dispatch — a direct Python call bypasses that. `_dump()`
handles both uniformly.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.routers import agents as agents_router
from apps.api.routers import execution as execution_router
from apps.api.routers import global_market as global_market_router
from apps.api.routers import learning as learning_router
from apps.api.routers import market as market_router
from apps.api.routers import news as news_router
from apps.api.routers import opportunities as opportunities_router
from apps.api.routers import portfolio as portfolio_router
from apps.api.routers import research_lab as research_lab_router
from apps.api.routers import risk as risk_router
from apps.api.routers import trading as trading_router
from apps.api.routers import trading_control as trading_control_router
from apps.api.routers.audit import list_audit_log
from apps.api.routers.incidents import list_incidents
from packages.shared.models import AdminUser, SystemState
from packages.system.diagnostics import run_self_diagnostic
from packages.system.health_score import compute_system_health_score

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _dump(value: object) -> dict:
    if isinstance(value, BaseModel):
        return value.model_dump()
    mapper = sa_inspect(type(value), raiseerr=False)
    if mapper is not None:
        return {col.key: getattr(value, col.key) for col in mapper.columns}
    return dict(value)  # type: ignore[call-overload]


def _component_health(db: Session) -> dict[str, str]:
    """Same component checks GET /api/system/health computes — imported
    directly rather than re-derived, so the two never disagree."""
    from apps.api.routers.system import health as system_health_endpoint

    response = system_health_endpoint(db=db)
    return {c.name: c.status for c in response.components}


@router.get("/overview")
def dashboard_overview(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    state = db.get(SystemState, True)
    component_health = _component_health(db)
    health = compute_system_health_score(db, component_health=component_health)
    return {
        "system_state": {
            "trading_enabled": state.trading_enabled if state else None,
            "trading_paused": state.trading_paused if state else None,
            "safety_belt_level": state.safety_belt_level if state else None,
            "trading_mode": state.trading_mode if state else None,
        },
        "portfolio": _dump(portfolio_router.get_portfolio(db=db, _=admin)),
        "positions_open": len(trading_router.list_positions(status_filter="open", db=db, _=admin)),
        "top_opportunities": [_dump(o) for o in opportunities_router.list_opportunities(limit=5, db=db, _=admin)],
        "active_incidents": sum(
            1 for i in list_incidents(status_filter=None, category=None, limit=500, db=db, _=admin)
            if i.status not in ("resolved", "closed")
        ),
        "health_score": asdict(health),
    }


@router.get("/market-pulse")
def dashboard_market_pulse(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "overview": _dump(market_router.market_overview(db=db, _=admin)),
        "sessions": _dump(global_market_router.get_global_sessions(_=admin)),
    }


@router.get("/opportunities")
def dashboard_opportunities(
    limit: int = 20, db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)
) -> dict:
    return {
        "opportunities": [_dump(o) for o in opportunities_router.list_opportunities(limit=limit, db=db, _=admin)],
        "clusters": [_dump(c) for c in global_market_router.list_clusters(db=db, _=admin)],
        "watchlist": [_dump(w) for w in global_market_router.list_watchlist(db=db, _=admin)],
    }


@router.get("/portfolio")
def dashboard_portfolio(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "portfolio": _dump(portfolio_router.get_portfolio(db=db, _=admin)),
        "exposure": _dump(portfolio_router.get_portfolio_exposure(db=db, _=admin)),
        "positions": [_dump(p) for p in trading_router.list_positions(status_filter="open", db=db, _=admin)],
        "recent_trades": [_dump(t) for t in trading_router.list_trades(limit=10, db=db, _=admin)],
    }


@router.get("/risk")
def dashboard_risk(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "risk_state": _dump(risk_router.get_risk_state(limit=10, db=db, _=admin)),
        "advanced": _dump(risk_router.get_advanced_risk(db=db, _=admin)),
        "breakers": [_dump(b) for b in risk_router.get_circuit_breakers(db=db, _=admin)],
        "concentration": _dump(risk_router.get_concentration(db=db, _=admin)),
    }


@router.get("/agents")
def dashboard_agents(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "agents": [_dump(a) for a in agents_router.list_agents(db=db, _=admin)],
        "recent_decisions": [
            _dump(d) for d in agents_router.list_decisions(asset_id=None, decision_state=None, limit=20, db=db, _=admin)
        ],
        "contradictions": [_dump(c) for c in agents_router.list_contradictions(db=db, _=admin)],
    }


@router.get("/strategies")
def dashboard_strategies(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    from apps.api.routers.strategies import list_strategies

    return {
        "strategies": [_dump(s) for s in list_strategies(db=db, _=admin)],
        "learning": [_dump(s) for s in learning_router.list_strategy_performance(db=db, _=admin)],
    }


@router.get("/research")
def dashboard_research(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return research_lab_router.get_research_report(db=db, _=admin)


@router.get("/learning")
def dashboard_learning(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "strategy_performance": [_dump(s) for s in learning_router.list_strategy_performance(db=db, _=admin)],
        "trade_journal": [_dump(j) for j in learning_router.list_trade_journal(limit=10, db=db, _=admin)],
    }


@router.get("/news")
def dashboard_news(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "news": [_dump(n) for n in news_router.list_news(limit=15, db=db, _=admin)],
        "risk": _dump(news_router.get_news_risk(db=db, _=admin)),
        "macro_events": [_dump(m) for m in news_router.list_macro_events(db=db, _=admin)],
    }


@router.get("/events")
def dashboard_events(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "macro_events": [_dump(m) for m in news_router.list_macro_events(db=db, _=admin)],
        "market_events": [_dump(e) for e in market_router.market_events(limit=50, db=db, _=admin)],
        "activity_feed": [_dump(e) for e in trading_control_router.get_activity_feed(limit=50, db=db, _=admin)],
    }


@router.get("/execution")
def dashboard_execution(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "accounts": [_dump(a) for a in execution_router.list_accounts(db=db, _=admin)],
        "executions": [_dump(e) for e in execution_router.list_executions(limit=20, db=db, _=admin)],
        "reconciliation": [_dump(r) for r in execution_router.list_reconciliation_runs(limit=10, db=db, _=admin)],
        "health": _dump(execution_router.get_execution_health(db=db, _=admin)),
    }


@router.get("/system")
def dashboard_system(
    request: Request, db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)
) -> dict:
    component_health = _component_health(db)
    health = compute_system_health_score(db, component_health=component_health)
    diagnostic = run_self_diagnostic(db, bus=getattr(request.app.state, "bus", None))
    return {
        "component_health": component_health,
        "health_score": asdict(health),
        "self_diagnostic": asdict(diagnostic),
    }


@router.get("/incidents")
def dashboard_incidents(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    rows = list_incidents(status_filter=None, category=None, limit=100, db=db, _=admin)
    return {
        "incidents": [_dump(i) for i in rows],
        "open_count": sum(1 for i in rows if i.status not in ("resolved", "closed")),
    }


@router.get("/audit")
def dashboard_audit(db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin)) -> dict:
    entries = list_audit_log(limit=50, actor=None, action=None, db=db, _=admin)
    return {"entries": [_dump(e) for e in entries]}
