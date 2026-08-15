from apps.worker.scanner import run_scan_cycle
from packages.data.connectors.market.mock import MockMarketDataProvider
from packages.shared.models import OHLCV, Asset


def test_scan_cycle_stores_candles_for_active_assets_only(db_session):
    active = Asset(symbol="TESTBTC", asset_class="crypto", is_active=True)
    inactive = Asset(symbol="TESTOLD", asset_class="crypto", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    summary = run_scan_cycle(db_session, MockMarketDataProvider())

    assert summary["scanned"] == 1
    assert summary["stored"] == 1
    assert summary["unavailable"] == 0

    stored = db_session.query(OHLCV).filter(OHLCV.asset_id == active.id).all()
    assert len(stored) == 1
    assert stored[0].data_quality == "high"

    assert db_session.query(OHLCV).filter(OHLCV.asset_id == inactive.id).count() == 0
