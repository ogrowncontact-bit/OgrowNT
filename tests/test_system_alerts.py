from apps.api.security import hash_password
from packages.portfolio.state import refresh_snapshot
from packages.risk.monitor import _ALERT_SEVERITY_BY_BELT, update_safety_belt
from packages.risk.safety_belt import CAUTION, DEFENSIVE, EMERGENCY, KILL_SWITCH, NORMAL
from packages.shared.models import AdminUser, Alert


def _login(client, db_session, email="alerts-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_severity_mapping_covers_every_belt_level():
    assert set(_ALERT_SEVERITY_BY_BELT) == {NORMAL, CAUTION, DEFENSIVE, EMERGENCY, KILL_SWITCH}
    assert _ALERT_SEVERITY_BY_BELT[EMERGENCY] == "critical"
    assert _ALERT_SEVERITY_BY_BELT[KILL_SWITCH] == "critical"
    assert _ALERT_SEVERITY_BY_BELT[NORMAL] == "info"


def test_no_alert_written_when_belt_level_unchanged(db_session):
    update_safety_belt(db_session)  # first call always "changes" from unset -> normal
    before = db_session.query(Alert).count()
    update_safety_belt(db_session)  # second call: still normal, no transition
    after = db_session.query(Alert).count()
    assert after == before


def test_critical_alert_written_on_auto_kill_switch(db_session):
    refresh_snapshot(db_session, cash=1_000_000.0)  # sets a high peak equity
    refresh_snapshot(db_session, cash=100.0)  # ~99.99% drawdown from peak -> well past kill-switch threshold

    new_level = update_safety_belt(db_session)
    assert new_level == KILL_SWITCH

    alert = db_session.query(Alert).filter(Alert.category == "emergency").order_by(Alert.id.desc()).first()
    assert alert is not None
    assert alert.severity == "critical"
    assert "kill_switch" in alert.message or "normal -> kill_switch" in alert.message


def test_manual_kill_switch_trigger_writes_critical_alert(client, db_session):
    token = _login(client, db_session)
    resp = client.post("/api/system/kill-switch", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    alert = db_session.query(Alert).filter(Alert.category == "emergency", Alert.message.like("%manually triggered%")).first()
    assert alert is not None
    assert alert.severity == "critical"


def test_manual_kill_switch_release_writes_info_alert(client, db_session):
    token = _login(client, db_session)
    client.post("/api/system/kill-switch", headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/api/system/kill-switch/release", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    alert = db_session.query(Alert).filter(Alert.category == "emergency", Alert.message.like("%released%")).first()
    assert alert is not None
    assert alert.severity == "info"
