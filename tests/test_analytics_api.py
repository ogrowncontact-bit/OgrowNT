from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, PortfolioSnapshot


def _login(client, db_session, email="analytics-admin@example.com", password="correct-horse") -> str:
    db_session.add(AdminUser(email=email, hashed_password=hash_password(password)))
    db_session.commit()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_overview_requires_auth(client, db_session):
    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 401


def test_overview_empty_database_returns_honest_defaults(client, db_session):
    token = _login(client, db_session)
    resp = client.get("/api/analytics/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["equity_curve"] == []
    assert body["trade_stats"]["total_trades"] == 0
    assert body["trade_stats"]["win_rate"] is None
    assert body["drawdown"]["current_drawdown_pct"] is None
    assert body["tier_distribution"] == {}
    assert body["pattern_leaderboard"] == []
    assert body["regime_distribution"] == {}


def test_overview_returns_real_data(client, db_session):
    db_session.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc), equity=10_000.0, cash=10_000.0,
            exposure_pct=0.0, daily_pnl=0.0, drawdown_pct=0.0, safety_belt_level="normal",
        )
    )
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/analytics/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["equity_curve"]) == 1
    assert body["equity_curve"][0]["equity"] == 10_000.0
    assert body["drawdown"]["peak_equity"] == 10_000.0
