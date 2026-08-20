"""Fast Market Scanner -- "PROMPT 11" §25-32."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.fast_scanner import DEFAULT_TOP_N, FastMarketScanner
from packages.market.universe import STATUS_ACTIVE, STATUS_QUARANTINED
from packages.shared.models import OHLCV, Asset, NewsEvent, NewsImpact

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _asset(db_session, symbol: str, status: str = STATUS_ACTIVE, **overrides) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", status=status, **overrides)
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_candles(db_session, asset: Asset, *, count: int = 30, base_close: float = 100.0, volume: float = 500.0):
    for i in range(count):
        close = base_close * (1.0 + 0.001 * i)
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_NOW - timedelta(minutes=count - i), open=close, high=close * 1.002,
                low=close * 0.998, close=close, volume=volume, data_quality="high",
            )
        )
    db_session.commit()


def test_score_asset_with_no_candles_is_honest_zero(db_session):
    asset = _asset(db_session, "FS_NO_DATA")
    scanner = FastMarketScanner()
    result = scanner.score_asset(db_session, asset, now=_NOW)
    assert result.score == 0.0
    assert result.reason == "no recent candle data"


def test_score_asset_with_candles_produces_all_components(db_session):
    asset = _asset(db_session, "FS_SCORED")
    _seed_candles(db_session, asset)
    scanner = FastMarketScanner()
    result = scanner.score_asset(db_session, asset, now=_NOW)
    assert 0.0 <= result.score <= 100.0
    assert set(result.components) == {
        "momentum", "volatility", "volume", "breakout_proximity", "range_position", "liquidity", "news_activity",
    }
    assert result.reason is None


def test_score_asset_uses_persisted_liquidity_score(db_session):
    asset = _asset(db_session, "FS_LIQUIDITY", liquidity_score=17.5)
    _seed_candles(db_session, asset)
    scanner = FastMarketScanner()
    result = scanner.score_asset(db_session, asset, now=_NOW)
    assert result.components["liquidity"] == 17.5


def test_score_asset_reflects_recent_news_activity(db_session):
    asset = _asset(db_session, "FS_NEWSY")
    _seed_candles(db_session, asset)
    for i in range(2):
        event = NewsEvent(
            source="Reuters", published_at=_NOW - timedelta(hours=1), headline=f"Newsy headline {i}",
            category="crypto", sentiment="bullish", importance="medium",
        )
        db_session.add(event)
        db_session.commit()
        db_session.add(
            NewsImpact(
                news_event_id=event.id, asset_id=asset.id, impact="medium", direction="bullish", confidence=0.6,
                horizon_hours=12, rationale="test",
            )
        )
    db_session.commit()

    quiet_asset = _asset(db_session, "FS_QUIET")
    _seed_candles(db_session, quiet_asset)

    scanner = FastMarketScanner()
    newsy = scanner.score_asset(db_session, asset, now=_NOW)
    quiet = scanner.score_asset(db_session, quiet_asset, now=_NOW)
    assert newsy.components["news_activity"] > quiet.components["news_activity"]


def test_scan_excludes_non_paper_eligible_assets(db_session):
    eligible = _asset(db_session, "FS_SCAN_ELIGIBLE", status=STATUS_ACTIVE)
    _seed_candles(db_session, eligible)
    ineligible = _asset(db_session, "FS_SCAN_QUARANTINED", status=STATUS_QUARANTINED)
    _seed_candles(db_session, ineligible)

    scanner = FastMarketScanner()
    results = scanner.scan(db_session, now=_NOW)
    symbols = {r.symbol for r in results}
    assert "FS_SCAN_ELIGIBLE" in symbols
    assert "FS_SCAN_QUARANTINED" not in symbols


def test_scan_respects_top_n_and_sorts_descending(db_session):
    for i in range(5):
        asset = _asset(db_session, f"FS_TOPN_{i}", status=STATUS_ACTIVE)
        _seed_candles(db_session, asset, base_close=100.0 + i * 10)

    scanner = FastMarketScanner()
    results = scanner.scan(db_session, top_n=3, now=_NOW)
    assert len(results) == 3
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_default_top_n_is_a_reasonable_positive_number():
    assert 0 < DEFAULT_TOP_N <= 100
