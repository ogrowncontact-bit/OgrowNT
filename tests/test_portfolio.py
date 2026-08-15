from datetime import datetime, timezone

from packages.shared.models import PortfolioSnapshot


def test_portfolio_returns_404_before_seeding(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 404


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

    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["equity"] == 10000.0
    assert body["cash"] == 10000.0
    assert body["safety_belt_level"] == "normal"


def test_positions_empty_in_phase1(client):
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    assert resp.json() == []
