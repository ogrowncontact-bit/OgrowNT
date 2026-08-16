from datetime import datetime, timezone

from packages.shared.models import PortfolioSnapshot


def test_overview_empty_database_returns_honest_defaults(client, db_session):
    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["equity_curve"] == []
    assert body["trade_stats"]["total_trades"] == 0
    assert body["trade_stats"]["win_rate"] is None
    assert body["drawdown"]["current_drawdown_pct"] is None
    assert body["tier_distribution"] == {}
    assert body["pattern_leaderboard"] == []
    assert body["regime_distribution"] == {}


def test_overview_is_public_no_auth_required(client, db_session):
    db_session.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc), equity=10_000.0, cash=10_000.0,
            exposure_pct=0.0, daily_pnl=0.0, drawdown_pct=0.0, safety_belt_level="normal",
        )
    )
    db_session.commit()

    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["equity_curve"]) == 1
    assert body["equity_curve"][0]["equity"] == 10_000.0
    assert body["drawdown"]["peak_equity"] == 10_000.0
