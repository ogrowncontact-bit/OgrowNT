from datetime import datetime, timezone

from apps.api.security import hash_password
from packages.shared.models import AdminUser, Asset, PortfolioSnapshot, Position, StrategyRow

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
    assert "weekly_pnl" in body
    assert "monthly_pnl" in body
    assert "monthly_loss_pct" in body


def test_portfolio_exposure_breaks_down_by_asset_strategy_direction(client, db_session):
    asset_a = Asset(symbol="EXPOSUREBTC", asset_class="crypto", is_active=True)
    asset_b = Asset(symbol="EXPOSUREETH", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="exposure_strategy", name="Exposure Test", family="trend", version="1.0")
    db_session.add_all([asset_a, asset_b, strategy])
    db_session.commit()

    db_session.add(
        PortfolioSnapshot(
            ts=datetime.now(timezone.utc), equity=10000.0, cash=8000.0,
            exposure_pct=20.0, daily_pnl=0.0, drawdown_pct=0.0, safety_belt_level="normal",
        )
    )
    db_session.add(Position(
        asset_id=asset_a.id, strategy_id=strategy.id, direction="long",
        entry_price=100.0, current_stop=95.0, size=10.0, status="open",
    ))
    db_session.add(Position(
        asset_id=asset_b.id, strategy_id=strategy.id, direction="short",
        entry_price=50.0, current_stop=55.0, size=20.0, status="open",
    ))
    db_session.commit()

    token = _login(client, db_session)
    resp = client.get("/api/portfolio/exposure", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()

    by_asset = {item["key"]: item for item in body["by_asset"]}
    assert by_asset["EXPOSUREBTC"]["notional"] == 1000.0
    assert by_asset["EXPOSUREETH"]["notional"] == 1000.0

    by_strategy = {item["key"]: item for item in body["by_strategy"]}
    assert by_strategy["exposure_strategy"]["notional"] == 2000.0

    by_direction = {item["key"]: item for item in body["by_direction"]}
    assert by_direction["long"]["notional"] == 1000.0
    assert by_direction["short"]["notional"] == 1000.0
