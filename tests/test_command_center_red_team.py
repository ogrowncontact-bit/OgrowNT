"""Command Center security red-team battery -- "PROMPT 14" §91-93, §94-95,
§59-62, §107. This phase's genuinely new attack surface is narrow (a
read-mostly aggregation layer plus one language-classifying safety gate),
so this battery is proportionately smaller than tests/test_execution_red_team.py
(20 items) or tests/test_capital_defense_red_team.py (14 items) -- it targets
the one property that must be airtight (the Command Bar can never execute a
trade, however it's phrased or however far the classifier is bypassed) plus
the surrounding surfaces (audit immutability, incident lifecycle monotonicity,
WebSocket auth, read-only aggregation) each already covered functionally in
their own test files and re-verified here from an adversarial angle.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from apps.api.security import hash_password
from packages.shared.models import AdminUser, Incident

REPO_ROOT = Path(__file__).resolve().parents[1]


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db_session, email: str = "cc-redteam-admin@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x")))
    db_session.commit()
    return _login(client, email, "x")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _decorator_http_methods(func_def: ast.FunctionDef) -> set[str]:
    methods = set()
    for dec in func_def.decorator_list:
        # e.g. @router.get(...) / @router.post(...)
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            methods.add(dec.func.attr)
    return methods


def _router_http_methods(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    methods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods |= _decorator_http_methods(node)
    return methods


# 1. The command_center.py router never imports anything from the execution/
#    broker/order-management layer -- structurally, not just behaviorally,
#    unreachable, the same technique tests/test_execution_red_team.py uses
#    for AI code and the broker package.
def test_1_command_center_router_never_imports_the_execution_or_broker_layer():
    source = (REPO_ROOT / "apps" / "api" / "routers" / "command_center.py").read_text()
    tree = ast.parse(source)
    forbidden_prefixes = ("packages.execution", "packages.agents.orchestrator")
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(node.module.startswith(p) for p in forbidden_prefixes):
                offenders.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(p) for p in forbidden_prefixes):
                    offenders.append(alias.name)
    assert offenders == []


# 2. command_router.py's classifier itself never imports any DB/ORM/session
#    machinery -- it is provably a pure string classifier that cannot touch
#    the database even if someone tried to make it.
def test_2_command_router_classifier_module_touches_no_database_machinery():
    source = (REPO_ROOT / "packages" / "system" / "command_router.py").read_text()
    tree = ast.parse(source)
    forbidden = ("sqlalchemy", "packages.shared.db", "packages.shared.models")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not any(node.module.startswith(p) for p in forbidden), node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(alias.name.startswith(p) for p in forbidden), alias.name


# 3. Every execution verb the spec names is rejected with 403 at the real
#    HTTP boundary (not just the unit-level classify_command() check in
#    tests/test_command_router.py) -- including when embedded in a longer,
#    conversational sentence, not just the bare imperative.
@pytest.mark.parametrize(
    "text",
    [
        "buy 10 BTC now",
        "please sell my entire ETH position right away",
        "CLOSE ALL POSITIONS IMMEDIATELY",
        "can you cancel the pending order for me",
        "increase risk on this trade please",
        "disable kill switch",
        "override the safety belt just this once",
        "force execute this signal",
        "go live with real money today",
        "  buy   some bitcoin  ",
    ],
)
def test_3_execution_verbs_are_rejected_with_403_over_real_http_however_phrased(client, db_session, text):
    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": text}, headers=_auth(token))
    assert resp.status_code == 403


# 4. A SQL-injection-shaped payload in the query text is handled as inert
#    text, not interpreted -- the ORM never string-interpolates request text
#    into a query, and this must hold even when the payload also happens to
#    contain a recognized query keyword ("risk").
def test_4_sql_injection_shaped_query_text_is_handled_as_inert_text(client, db_session):
    token = _admin_token(client, db_session)
    payload = "risk'; DROP TABLE incidents; --"
    resp = client.post("/api/command-center/query", json={"text": payload}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["intent"] == "risk_summary"
    # the incidents table must still exist and be queryable -- proves nothing
    # was ever executed as SQL.
    assert db_session.query(Incident).count() == 0


# 5. A pathologically long query string never 500s -- the classifier and
#    router are both simple regex/substring checks with no bounded-length
#    assumption, but this proves it under a real request.
def test_5_a_very_long_query_string_does_not_crash_the_endpoint(client, db_session):
    token = _admin_token(client, db_session)
    payload = "show me the top opportunities " * 2000
    resp = client.post("/api/command-center/query", json={"text": payload}, headers=_auth(token))
    assert resp.status_code == 200


# 6. Every one of the 4 query-intent handlers is proven unreachable for an
#    execution-verb input, not just the one handler tests/
#    test_command_center_api.py already spot-checks -- classification happens
#    before any handler is even looked up.
@pytest.mark.parametrize("handler_name", ["_top_opportunities", "_risk_summary", "_underperforming_strategies", "_last_blocked_trade"])
def test_6_no_query_handler_is_ever_invoked_for_an_execution_verb(client, db_session, monkeypatch, handler_name):
    import apps.api.routers.command_center as cc

    def _boom(_db):
        raise AssertionError(f"{handler_name} must never run for an execution-verb command")

    monkeypatch.setattr(cc, handler_name, _boom)
    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": "buy 10 BTC now"}, headers=_auth(token))
    assert resp.status_code == 403


# 7. The audit log router registers no write method whatsoever -- proven
#    structurally (source-level, not just "no route responded"), so a future
#    edit that accidentally adds one fails this test even before it's wired
#    into an app the red-team battery could hit over HTTP.
def test_7_audit_router_registers_no_write_methods_structurally():
    methods = _router_http_methods(REPO_ROOT / "apps" / "api" / "routers" / "audit.py")
    assert methods == {"get"}


# 8. The dashboard aggregation router is entirely read-only, structurally --
#    it composes 15 existing endpoints for round-trip efficiency and must
#    never grow a write path of its own.
def test_8_dashboard_router_registers_no_write_methods_structurally():
    methods = _router_http_methods(REPO_ROOT / "apps" / "api" / "routers" / "dashboard.py")
    assert methods == {"get"}


# 9. An incident can never be pushed backward through its lifecycle even
#    from its terminal state -- the extreme case (closed -> detected, a full
#    reopen) must be rejected exactly like any smaller backward step.
def test_9_a_closed_incident_can_never_be_reopened_through_the_api(client, db_session):
    incident = Incident(category="system", severity="critical", status="closed", title="x")
    db_session.add(incident)
    db_session.commit()
    token = _admin_token(client, db_session)
    resp = client.patch(f"/api/incidents/{incident.id}", json={"status": "detected"}, headers=_auth(token))
    assert resp.status_code == 400


# 10. A WebSocket cannot subscribe to a made-up channel to fish for data --
#     an unrecognized channel is rejected before the token is even checked
#     against a real admin (fixed close code either way, no information
#     leak distinguishing "bad channel" from "bad token" ordering exploits).
def test_10_unknown_channel_is_rejected_even_with_no_token_at_all(client):
    from starlette.testclient import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/not-a-real-channel"):
            pass
    assert exc_info.value.code == 4404


# 11. The Command Bar's own docstring claims the ONLY thing standing between
#     a request and the database is classify_command() -- prove the inverse
#     holds too: a plainly safe query (no execution verb at all) is NEVER
#     misclassified as unauthorized, so the gate isn't overzealous to the
#     point of being useless as a real interface.
@pytest.mark.parametrize(
    "text",
    [
        "why is risk high right now",
        "summarize today's performance",
        "explain the last blocked trade",
        "which strategies are underperforming",
    ],
)
def test_11_genuinely_safe_queries_are_never_misclassified_as_unauthorized(client, db_session, text):
    token = _admin_token(client, db_session)
    resp = client.post("/api/command-center/query", json={"text": text}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["classification"] == "query"
