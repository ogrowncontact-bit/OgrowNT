from apps.api.security import create_access_token, decode_access_token, hash_password, verify_password
from packages.shared.models import AdminUser


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    token, expires_at = create_access_token(subject="admin@example.com")
    assert decode_access_token(token) == "admin@example.com"
    assert expires_at is not None


def test_login_and_me(client, db_session):
    db_session.add(
        AdminUser(email="login-test@example.com", hashed_password=hash_password("correct-horse"))
    )
    db_session.commit()

    resp = client.post(
        "/api/auth/login", json={"email": "login-test@example.com", "password": "correct-horse"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "login-test@example.com"


def test_login_rejects_wrong_password(client, db_session):
    db_session.add(AdminUser(email="wrongpw@example.com", hashed_password=hash_password("right")))
    db_session.commit()

    resp = client.post("/api/auth/login", json={"email": "wrongpw@example.com", "password": "nope"})
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def _login(client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_admin_defaults_to_admin_role(client, db_session):
    db_session.add(AdminUser(email="rbac-default@example.com", hashed_password=hash_password("x")))
    db_session.commit()
    token = _login(client, "rbac-default@example.com", "x")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "admin"


def test_admin_can_create_a_viewer_account(client, db_session):
    db_session.add(AdminUser(email="rbac-admin@example.com", hashed_password=hash_password("x")))
    db_session.commit()
    admin_token = _login(client, "rbac-admin@example.com", "x")

    resp = client.post(
        "/api/auth/users",
        json={"email": "rbac-viewer@example.com", "password": "y", "role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "viewer"

    viewer_token = _login(client, "rbac-viewer@example.com", "y")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {viewer_token}"})
    assert me.json()["role"] == "viewer"


def test_viewer_cannot_create_users(client, db_session):
    db_session.add(AdminUser(email="rbac-viewer2@example.com", hashed_password=hash_password("x"), role="viewer"))
    db_session.commit()
    viewer_token = _login(client, "rbac-viewer2@example.com", "x")

    resp = client.post(
        "/api/auth/users",
        json={"email": "rbac-attempted@example.com", "password": "y"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_viewer_cannot_trigger_kill_switch(client, db_session):
    db_session.add(AdminUser(email="rbac-viewer3@example.com", hashed_password=hash_password("x"), role="viewer"))
    db_session.commit()
    viewer_token = _login(client, "rbac-viewer3@example.com", "x")

    resp = client.post("/api/system/kill-switch", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


def test_creating_a_duplicate_email_conflicts(client, db_session):
    db_session.add(AdminUser(email="rbac-dup-admin@example.com", hashed_password=hash_password("x")))
    db_session.add(AdminUser(email="rbac-dup-existing@example.com", hashed_password=hash_password("x")))
    db_session.commit()
    admin_token = _login(client, "rbac-dup-admin@example.com", "x")

    resp = client.post(
        "/api/auth/users",
        json={"email": "rbac-dup-existing@example.com", "password": "y"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
