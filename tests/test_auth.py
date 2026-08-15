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
