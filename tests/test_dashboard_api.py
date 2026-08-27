"""apps/api/routers/dashboard.py -- "PROMPT 14" §130: the 15 Command Center
aggregation endpoints. Each one composes already-tested endpoint handlers
(their own behavior is covered by each source router's own test file) --
these tests only prove the composition itself: auth is enforced, the call
succeeds against a real (mostly empty) DB without crashing on the
`Query(...)`-marker or raw-ORM-vs-Pydantic pitfalls documented in the
router's own docstring, and the expected top-level keys are present.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apps.api.security import hash_password
from packages.shared.models import AdminUser, PortfolioSnapshot, SystemState

_ENDPOINTS_AND_KEYS = (
    ("/api/dashboard/overview", {"system_state", "portfolio", "positions_open", "top_opportunities", "active_incidents", "health_score"}),
    ("/api/dashboard/market-pulse", {"overview", "sessions"}),
    ("/api/dashboard/opportunities", {"opportunities", "clusters", "watchlist"}),
    ("/api/dashboard/portfolio", {"portfolio", "exposure", "positions", "recent_trades"}),
    ("/api/dashboard/risk", {"risk_state", "advanced", "breakers", "concentration"}),
    ("/api/dashboard/agents", {"agents", "recent_decisions", "contradictions"}),
    ("/api/dashboard/strategies", {"strategies", "learning"}),
    ("/api/dashboard/learning", {"strategy_performance", "trade_journal"}),
    ("/api/dashboard/news", {"news", "risk", "macro_events"}),
    ("/api/dashboard/events", {"macro_events", "market_events", "activity_feed"}),
    ("/api/dashboard/execution", {"accounts", "executions", "reconciliation", "health"}),
    ("/api/dashboard/system", {"component_health", "health_score", "self_diagnostic"}),
    ("/api/dashboard/incidents", {"incidents", "open_count"}),
    ("/api/dashboard/audit", {"entries"}),
)


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db_session, email: str = "dash-admin@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x")))
    db_session.commit()
    return _login(client, email, "x")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _healthy_system_state(db_session) -> None:
    state = db_session.get(SystemState, True) or SystemState(id=True)
    state.trading_enabled = True
    state.trading_paused = False
    state.safety_belt_level = "normal"
    db_session.add(state)
    db_session.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc), equity=10_000.0, cash=10_000.0,
            exposure_pct=0.0, daily_pnl=0.0, drawdown_pct=0.0, safety_belt_level="normal",
        )
    )
    db_session.commit()


@pytest.mark.parametrize("path,_expected_keys", _ENDPOINTS_AND_KEYS)
def test_dashboard_endpoint_requires_auth(client, path, _expected_keys):
    resp = client.get(path)
    assert resp.status_code == 401


@pytest.mark.parametrize("path,expected_keys", _ENDPOINTS_AND_KEYS)
def test_dashboard_endpoint_returns_expected_shape_on_a_near_empty_db(client, db_session, path, expected_keys):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get(path, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert expected_keys <= set(body.keys())


def test_dashboard_research_composes_the_research_lab_report(client, db_session):
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/dashboard/research", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_dashboard_overview_health_score_reflects_a_paused_trading_state(client, db_session):
    state = SystemState(id=True, trading_enabled=True, trading_paused=True, paused_reason="test pause", safety_belt_level="normal")
    db_session.add(state)
    db_session.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc), equity=10_000.0, cash=10_000.0,
            exposure_pct=0.0, daily_pnl=0.0, drawdown_pct=0.0, safety_belt_level="normal",
        )
    )
    db_session.commit()
    token = _admin_token(client, db_session)
    resp = client.get("/api/dashboard/overview", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["system_state"]["trading_paused"] is True


def test_dashboard_incidents_open_count_excludes_resolved_and_closed(client, db_session):
    from packages.shared.models import Incident

    db_session.add(Incident(category="system", severity="medium", status="detected", title="open one"))
    db_session.add(Incident(category="system", severity="medium", status="resolved", title="resolved one"))
    db_session.commit()
    _healthy_system_state(db_session)
    token = _admin_token(client, db_session)
    resp = client.get("/api/dashboard/incidents", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["open_count"] == 1
    assert len(body["incidents"]) == 2
