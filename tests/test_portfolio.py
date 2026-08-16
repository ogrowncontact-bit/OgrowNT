from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, PortfolioSnapshot

# Two Phase 1 tests lived here that no longer hold once Phase 3 exists:
# - "/api/portfolio returns 404 before any snapshot exists" -- true in
#   isolation, but other test modules (execution, portfolio_state, ...)
#   write snapshots to this same shared test DB, so "before seeding" is not
#   a reachable state once the full suite runs together.
# - "/api/positions is always []" -- Phase 3's Execution Engine makes this
#   intentionally false now; real position listing (including status
#   filtering) is covered in tests/test_trading_api.py instead.


def _login(client, db_session, email="portfolio-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_portfolio_requires_auth(client, db_session):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 401


def test_portfolio_reflects_latest_snapshot(client, db_session):
    db_session.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc),
            equity=10000.0,
            cash=10000.0,
            exposure_pct=0.0,
            daily_pnl=0.0,
            drawdown_pct=0.0,
            safety_belt_level="normal",
        )
    )
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/portfolio", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["equity"] == 10000.0
    assert body["cash"] == 10000.0
    assert body["safety_belt_level"] == "normal"
