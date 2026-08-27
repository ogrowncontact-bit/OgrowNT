"""apps/api/routers/audit.py + incidents.py -- "PROMPT 14" §59-62, §94-95."""
from __future__ import annotations

from apps.api.security import hash_password
from packages.shared.models import AdminUser, AuditLog, Incident


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db_session, email: str = "aud-admin@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x"), role="admin"))
    db_session.commit()
    return _login(client, email, "x")


def _viewer_token(client, db_session, email: str = "aud-viewer@example.com") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password("x"), role="viewer"))
    db_session.commit()
    return _login(client, email, "x")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# -- audit.py --------------------------------------------------------------
def test_audit_log_requires_auth(client):
    resp = client.get("/api/audit")
    assert resp.status_code == 401


def test_audit_log_lists_entries_newest_first(client, db_session):
    db_session.add(AuditLog(actor="x@example.com", action="first_action", detail={}))
    db_session.add(AuditLog(actor="x@example.com", action="second_action", detail={}))
    db_session.commit()
    token = _admin_token(client, db_session)
    resp = client.get("/api/audit", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["action"] == "second_action"


def test_audit_log_filters_by_actor_and_action(client, db_session):
    db_session.add(AuditLog(actor="alice@example.com", action="kill_switch_triggered", detail={}))
    db_session.add(AuditLog(actor="bob@example.com", action="kill_switch_triggered", detail={}))
    db_session.add(AuditLog(actor="alice@example.com", action="risk_limits_updated", detail={}))
    db_session.commit()
    token = _admin_token(client, db_session)
    resp = client.get("/api/audit", params={"actor": "alice@example.com"}, headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    resp = client.get("/api/audit", params={"action": "kill_switch_triggered"}, headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_audit_log_has_no_write_endpoint(client, db_session):
    """§95: the audit trail is never mutable through this API -- only GET
    is registered under /api/audit."""
    token = _admin_token(client, db_session)
    for method in ("post", "patch", "put", "delete"):
        resp = getattr(client, method)("/api/audit", headers=_auth(token))
        assert resp.status_code in (404, 405)


# -- incidents.py ------------------------------------------------------------
def test_incidents_list_requires_auth(client):
    resp = client.get("/api/incidents")
    assert resp.status_code == 401


def test_incidents_list_and_get_by_id(client, db_session):
    incident = Incident(category="system", severity="critical", status="detected", title="test incident")
    db_session.add(incident)
    db_session.commit()
    token = _admin_token(client, db_session)

    resp = client.get("/api/incidents", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/api/incidents/{incident.id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "test incident"


def test_incident_get_404_for_unknown_id(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.get("/api/incidents/999999", headers=_auth(token))
    assert resp.status_code == 404


def test_incident_update_requires_admin_role_not_just_viewer(client, db_session):
    incident = Incident(category="system", severity="medium", status="detected", title="x")
    db_session.add(incident)
    db_session.commit()
    viewer_token = _viewer_token(client, db_session)
    resp = client.patch(f"/api/incidents/{incident.id}", json={"status": "investigating"}, headers=_auth(viewer_token))
    assert resp.status_code == 403


def test_incident_lifecycle_can_move_forward(client, db_session):
    incident = Incident(category="system", severity="medium", status="detected", title="x")
    db_session.add(incident)
    db_session.commit()
    token = _admin_token(client, db_session)

    resp = client.patch(f"/api/incidents/{incident.id}", json={"status": "investigating"}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "investigating"

    resp = client.patch(f"/api/incidents/{incident.id}", json={"status": "resolved"}, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolved_at"] is not None


def test_incident_lifecycle_cannot_move_backward(client, db_session):
    incident = Incident(category="system", severity="medium", status="mitigated", title="x")
    db_session.add(incident)
    db_session.commit()
    token = _admin_token(client, db_session)

    resp = client.patch(f"/api/incidents/{incident.id}", json={"status": "investigating"}, headers=_auth(token))
    assert resp.status_code == 400
    assert "backward" in resp.json()["detail"]


def test_incident_update_rejects_an_invalid_status_value(client, db_session):
    incident = Incident(category="system", severity="medium", status="detected", title="x")
    db_session.add(incident)
    db_session.commit()
    token = _admin_token(client, db_session)
    resp = client.patch(f"/api/incidents/{incident.id}", json={"status": "not_a_real_status"}, headers=_auth(token))
    assert resp.status_code == 400


def test_incident_update_writes_an_audit_log_entry(client, db_session):
    incident = Incident(category="system", severity="medium", status="detected", title="x")
    db_session.add(incident)
    db_session.commit()
    token = _admin_token(client, db_session)
    client.patch(f"/api/incidents/{incident.id}", json={"status": "investigating"}, headers=_auth(token))
    entry = db_session.query(AuditLog).filter(AuditLog.action == "incident_updated").one()
    assert entry.entity_id == incident.id


def test_incident_update_404_for_unknown_id(client, db_session):
    token = _admin_token(client, db_session)
    resp = client.patch("/api/incidents/999999", json={"status": "investigating"}, headers=_auth(token))
    assert resp.status_code == 404
