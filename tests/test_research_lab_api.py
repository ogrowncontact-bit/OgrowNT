"""Autonomous Research Lab API — "PROMPT 10" §90-91."""
from __future__ import annotations

from packages.shared.models import AdminUser, ResearchHypothesis


def _make_admin(db_session, *, role="admin", email="api-admin@example.com"):
    from apps.api.security import hash_password

    user = AdminUser(email=email, hashed_password=hash_password("test-password-123"), role=role)
    db_session.add(user)
    db_session.commit()
    return user


def _login(client, email, password="test-password-123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_report_requires_auth(client):
    resp = client.get("/api/research-lab/report")
    assert resp.status_code == 401


def test_report_returns_all_sections(client, db_session):
    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    resp = client.get("/api/research-lab/report", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "executive_summary" in body
    assert "pending_approvals" in body
    assert "security_and_sandbox_posture" in body


def test_list_hypotheses_reflects_real_data(client, db_session):
    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    db_session.add(
        ResearchHypothesis(title="api test", description="d", problem="p", observation="o", hypothesis="h", expected_effect="e", source="manual", status="proposed")
    )
    db_session.commit()

    resp = client.get("/api/research-lab/hypotheses", headers=headers)
    assert resp.status_code == 200
    titles = [h["title"] for h in resp.json()]
    assert "api test" in titles


def test_get_hypothesis_404_for_unknown_id(client, db_session):
    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    resp = client.get("/api/research-lab/hypotheses/999999", headers=headers)
    assert resp.status_code == 404


def test_budget_endpoint_covers_every_resource_type(client, db_session):
    from packages.research import budget

    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    resp = client.get("/api/research-lab/budget", headers=headers)
    assert resp.status_code == 200
    resource_types = {row["resource_type"] for row in resp.json()}
    assert resource_types == set(budget.RESOURCE_TYPES)


def test_viewer_cannot_create_approval_request(client, db_session):
    _make_admin(db_session, role="viewer", email="api-viewer@example.com")
    headers = _login(client, "api-viewer@example.com")
    resp = client.post(
        "/api/research-lab/approvals", headers=headers,
        json={"entity_type": "hypothesis", "entity_id": 1, "action": "approve", "evidence": {}},
    )
    assert resp.status_code == 403


def test_admin_can_request_and_decide_an_approval(client, db_session):
    admin = _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    hyp = ResearchHypothesis(title="approve me", description="d", problem="p", observation="o", hypothesis="h", expected_effect="e", source="manual", status="proposed")
    db_session.add(hyp)
    db_session.commit()

    create_resp = client.post(
        "/api/research-lab/approvals", headers=headers,
        json={"entity_type": "hypothesis", "entity_id": hyp.id, "action": "approve", "evidence": {"x": 1}},
    )
    assert create_resp.status_code == 200
    approval_id = create_resp.json()["id"]

    decide_resp = client.post(
        f"/api/research-lab/approvals/{approval_id}/decide", headers=headers,
        json={"decision": "approved"},
    )
    assert decide_resp.status_code == 200
    assert decide_resp.json()["status"] == "approved"
    assert decide_resp.json()["reviewer"] == admin.email

    refreshed_hyp = db_session.get(ResearchHypothesis, hyp.id)
    assert refreshed_hyp.status == "approved"


def test_decide_twice_returns_400(client, db_session):
    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    hyp = ResearchHypothesis(title="t", description="d", problem="p", observation="o", hypothesis="h", expected_effect="e", source="manual", status="proposed")
    db_session.add(hyp)
    db_session.commit()

    create_resp = client.post(
        "/api/research-lab/approvals", headers=headers,
        json={"entity_type": "hypothesis", "entity_id": hyp.id, "action": "approve", "evidence": {}},
    )
    approval_id = create_resp.json()["id"]
    client.post(f"/api/research-lab/approvals/{approval_id}/decide", headers=headers, json={"decision": "approved"})
    second = client.post(f"/api/research-lab/approvals/{approval_id}/decide", headers=headers, json={"decision": "rejected"})
    assert second.status_code == 400


def test_enqueue_research_job_requires_admin_role(client, db_session):
    _make_admin(db_session, role="viewer", email="api-viewer2@example.com")
    headers = _login(client, "api-viewer2@example.com")
    resp = client.post("/api/research-lab/queue", headers=headers, json={"queue_type": "hypothesis", "payload": {}})
    assert resp.status_code == 403


def test_enqueue_research_job_rejects_unknown_queue_type(client, db_session):
    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    resp = client.post("/api/research-lab/queue", headers=headers, json={"queue_type": "not_a_real_type", "payload": {}})
    assert resp.status_code == 400


def test_enqueue_research_job_creates_a_queued_row(client, db_session):
    _make_admin(db_session)
    headers = _login(client, "api-admin@example.com")
    resp = client.post("/api/research-lab/queue", headers=headers, json={"queue_type": "hypothesis", "payload": {"trigger": "manual"}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    list_resp = client.get("/api/research-lab/queue", headers=headers)
    assert any(row["id"] == resp.json()["id"] for row in list_resp.json())
