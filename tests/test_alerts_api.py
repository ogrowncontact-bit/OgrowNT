from apps.api.security import hash_password
from packages.shared.models import AdminUser, Alert


def _login(client, db_session, email="alertsapi-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_list_alerts_requires_auth(client, db_session):
    resp = client.get("/api/alerts")
    assert resp.status_code == 401


def test_list_alerts_returns_recent_first(client, db_session):
    db_session.add(Alert(severity="info", category="learning", message="first"))
    db_session.add(Alert(severity="critical", category="emergency", message="second"))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/alerts?limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    messages = [a["message"] for a in resp.json()]
    assert messages.index("second") < messages.index("first")


def test_list_alerts_filters_by_severity(client, db_session):
    db_session.add(Alert(severity="critical", category="emergency", message="crit-one"))
    db_session.add(Alert(severity="info", category="learning", message="info-one"))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/alerts?severity=critical&limit=50", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    messages = {a["message"] for a in resp.json()}
    assert "crit-one" in messages
    assert "info-one" not in messages


def test_list_alerts_filters_by_acknowledged(client, db_session):
    db_session.add(Alert(severity="warning", category="risk", message="unseen", acknowledged=False))
    db_session.add(Alert(severity="warning", category="risk", message="seen", acknowledged=True))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/alerts?acknowledged=false&limit=50", headers={"Authorization": f"Bearer {token}"})
    messages = {a["message"] for a in resp.json()}
    assert "unseen" in messages
    assert "seen" not in messages


def test_ack_requires_auth(client, db_session):
    alert = Alert(severity="warning", category="risk", message="needs ack")
    db_session.add(alert)
    db_session.commit()

    resp = client.post(f"/api/alerts/{alert.id}/ack")
    assert resp.status_code == 401


def test_ack_marks_alert_acknowledged(client, db_session):
    alert = Alert(severity="warning", category="risk", message="ack me")
    db_session.add(alert)
    db_session.commit()

    token = _login(client, db_session)
    resp = client.post(f"/api/alerts/{alert.id}/ack", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["acknowledged"] is True

    db_session.refresh(alert)
    assert alert.acknowledged is True


def test_ack_unknown_alert_404s(client, db_session):
    token = _login(client, db_session)
    resp = client.post("/api/alerts/999999/ack", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
