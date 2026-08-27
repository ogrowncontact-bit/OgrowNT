"""apps/api/routers/command_center.py -- "PROMPT 14" §76-81, §91-93."""
from __future__ import annotations

from apps.api.security import hash_password
from packages.shared.models import AdminUser, RiskDecision, Signal, StrategyRow


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db_session, email: str = "cc-admin@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x")))
    db_session.commit()
    return _login(client, email, "x")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_command_query_requires_auth(client):
    resp = client.post("/api/command-center/query", json={"text": "show me the top opportunities"})
    assert resp.status_code == 401


def test_command_query_rejects_an_execution_verb_with_403(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": "buy 10 BTC now"}, headers=_auth(token))
    assert resp.status_code == 403


def test_command_query_never_reaches_the_database_for_an_unauthorized_verb(client, db_session, monkeypatch):
    """The classifier check happens before any query function is called --
    patch every intent handler to blow up if invoked, then prove an
    execution-verb request still comes back 403, never 500."""
    import apps.api.routers.command_center as cc

    def _boom(_db):
        raise AssertionError("an execution-verb command must never reach a query handler")

    for name in ("_top_opportunities", "_risk_summary", "_underperforming_strategies", "_last_blocked_trade"):
        monkeypatch.setattr(cc, name, _boom)

    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": "close all positions"}, headers=_auth(token))
    assert resp.status_code == 403


def test_command_query_answers_a_safe_query_with_classification_and_intent(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": "show me the top opportunities"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "query"
    assert body["intent"] == "top_opportunities"


def test_command_query_risk_summary_reflects_real_risk_decisions(client, db_session):
    strategy = StrategyRow(code="cc_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    from datetime import datetime, timezone

    from packages.shared.models import Asset

    asset = Asset(symbol="CCTEST", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, ts=datetime.now(timezone.utc), direction="long", entry_price=100.0, stop_price=95.0, status="scored")
    db_session.add(signal)
    db_session.commit()
    db_session.add(RiskDecision(signal_id=signal.id, approved=False, reason="daily loss limit reached", safety_belt_level="normal"))
    db_session.commit()

    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": "what is our risk exposure"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "risk_summary"
    assert body["data"]["recent_blocked"] == 1


def test_command_query_unrecognized_intent_returns_null_data(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": "what is the weather today"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "unrecognized"
    assert body["data"] is None


def test_daily_briefing_requires_auth(client):
    resp = client.get("/api/command-center/briefing")
    assert resp.status_code == 401


def test_daily_briefing_returns_a_real_briefing_on_an_empty_system(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/command-center/briefing", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["trades_closed"] == 0
    assert body["win_rate"] is None
