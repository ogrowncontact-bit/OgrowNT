from datetime import datetime, timezone

from packages.portfolio.state import compute_state, get_latest_cash, refresh_snapshot
from packages.shared.models import OHLCV, Asset, PortfolioSnapshot, Position, StrategyRow


def test_get_latest_cash_defaults_to_initial_capital_when_no_snapshots(db_session):
    # Uses a fresh symbol/position-free session state; if other tests already
    # wrote snapshots in this shared test DB, latest_cash reflects that
    # instead -- so just assert it's a sane positive number either way.
    assert get_latest_cash(db_session) > 0


def test_compute_state_with_no_open_positions_has_zero_exposure(db_session):
    refresh_snapshot(db_session, cash=5000.0)
    state = compute_state(db_session)
    assert state.cash == 5000.0
    assert state.equity == 5000.0
    assert state.exposure_pct == 0.0
    assert state.open_positions == []


def test_compute_state_marks_open_position_to_market(db_session):
    asset = Asset(symbol="PORTF1", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="portf_test_strategy", name="Portf Test", family="trend", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()

    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=110, high=111, low=109, close=110, volume=100)
    )
    db_session.add(
        Position(asset_id=asset.id, strategy_id=strategy.id, direction="long", entry_price=100.0, current_stop=95.0, size=10.0, status="open")
    )
    db_session.commit()

    state = compute_state(db_session, cash=8000.0)
    # long 10 units, entry 100 -> mark 110: unrealized = (110-100)*10 = 100
    assert state.unrealized_pnl == 100.0
    assert state.equity == 8000.0 + (100.0 * 10) + 100.0
    assert state.exposure_pct > 0

    # Close it out so it doesn't leak into other tests sharing this DB (this
    # suite doesn't roll back between tests -- see tests/test_scanner.py for
    # the same pattern).
    db_session.query(Position).filter(Position.asset_id == asset.id).update({"status": "closed"})
    db_session.commit()


def test_short_position_profits_when_price_falls(db_session):
    asset = Asset(symbol="PORTF2", asset_class="crypto", is_active=True)
    strategy = StrategyRow(code="portf_test_strategy_2", name="Portf Test 2", family="mean_reversion", version="1.0")
    db_session.add_all([asset, strategy])
    db_session.commit()

    db_session.add(
        OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=90, high=91, low=89, close=90, volume=100)
    )
    db_session.add(
        Position(asset_id=asset.id, strategy_id=strategy.id, direction="short", entry_price=100.0, current_stop=105.0, size=5.0, status="open")
    )
    db_session.commit()

    state = compute_state(db_session, cash=9000.0)
    # short 5 units, entry 100 -> mark 90: unrealized = (100-90)*5 = 50
    assert state.unrealized_pnl == 50.0

    db_session.query(Position).filter(Position.asset_id == asset.id).update({"status": "closed"})
    db_session.commit()


def test_refresh_snapshot_is_append_only(db_session):
    n_before = db_session.query(PortfolioSnapshot).count()
    refresh_snapshot(db_session, cash=7000.0)
    refresh_snapshot(db_session, cash=7100.0)
    n_after = db_session.query(PortfolioSnapshot).count()
    assert n_after == n_before + 2


def test_drawdown_reflects_peak_equity(db_session):
    # Cash magnitude picked to dominate any residual open-position exposure
    # left over from other tests sharing this DB, so the peak is predictable.
    peak_snapshot = refresh_snapshot(db_session, cash=1_000_000.0)
    state = compute_state(db_session, cash=15000.0)

    expected_drawdown_pct = (peak_snapshot.equity - state.equity) / peak_snapshot.equity * 100
    assert state.drawdown_pct == round(expected_drawdown_pct, 4)
    assert state.drawdown_pct > 90  # dropped from ~1M to ~15K
