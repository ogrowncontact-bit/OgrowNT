"""packages/risk/concentration.py -- "PROMPT 12" Portfolio Concentration &
Hidden Factor Exposure."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.risk.concentration import (
    CONCENTRATED,
    HIGH,
    LOW,
    MODERATE,
    assess_concentration,
)
from packages.risk.config import load_risk_limits
from packages.shared.models import Asset, CorrelationMatrixEntry, Position, StrategyRow

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
LIMITS = load_risk_limits()  # max_correlated_cluster_pct == 25 in config/risk_limits.yaml


def _asset(db_session, symbol: str, asset_class: str = "crypto") -> Asset:
    asset = Asset(symbol=symbol, asset_class=asset_class)
    db_session.add(asset)
    db_session.commit()
    return asset


def _strategy(db_session, code: str) -> StrategyRow:
    strategy = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _open_position(db_session, asset: Asset, strategy: StrategyRow, *, direction: str, entry_price: float, size: float) -> Position:
    position = Position(
        asset_id=asset.id, strategy_id=strategy.id, direction=direction, entry_price=entry_price,
        current_stop=entry_price * 0.9, size=size, status="open",
    )
    db_session.add(position)
    db_session.commit()
    return position


def _corr(db_session, a: Asset, b: Asset, value: float) -> None:
    db_session.add(CorrelationMatrixEntry(ts=_NOW, asset_id_a=a.id, asset_id_b=b.id, window_days=30, correlation=value))
    db_session.commit()


def test_no_open_positions_is_low_concentration(db_session):
    assessment = assess_concentration(db_session, LIMITS, equity=10000.0)
    assert assessment.open_position_count == 0
    assert assessment.concentration_state == LOW
    assert assessment.clusters == []
    assert assessment.hidden_factor_warnings == []


def test_single_uncorrelated_position_is_low_concentration(db_session):
    strategy = _strategy(db_session, "concentration_single_strategy")
    asset = _asset(db_session, "CONC_SINGLE")
    _open_position(db_session, asset, strategy, direction="long", entry_price=100.0, size=1.0)

    assessment = assess_concentration(db_session, LIMITS, equity=10000.0)
    assert assessment.open_position_count == 1
    assert assessment.max_cluster_exposure_pct == 0.0  # a lone position isn't a "cluster" (needs >=2 members)
    assert assessment.concentration_state == LOW


def test_correlated_cluster_of_open_positions_is_detected(db_session):
    strategy = _strategy(db_session, "concentration_cluster_strategy")
    btc = _asset(db_session, "CONC_BTC")
    eth = _asset(db_session, "CONC_ETH")
    _corr(db_session, btc, eth, 0.9)
    _open_position(db_session, btc, strategy, direction="long", entry_price=100.0, size=10.0)  # 1000 notional
    _open_position(db_session, eth, strategy, direction="long", entry_price=100.0, size=10.0)  # 1000 notional

    equity = 10000.0
    assessment = assess_concentration(db_session, LIMITS, equity=equity)
    assert len(assessment.clusters) == 1
    cluster = assessment.clusters[0]
    assert set(cluster.symbols) == {"CONC_BTC", "CONC_ETH"}
    # 2000 combined notional / 10000 equity = 20%
    assert assessment.max_cluster_exposure_pct == 20.0
    # 20% is below the 25% hard limit but above the 70% warning fraction (17.5%)
    assert assessment.concentration_state == HIGH


def test_opposite_direction_positions_are_not_clustered_together(db_session):
    """find_clusters groups by direction first -- a long and a short in the
    same correlated pair are two separate, opposing bets, not one
    concentrated position."""
    strategy = _strategy(db_session, "concentration_opposite_strategy")
    a = _asset(db_session, "CONC_OPP_A")
    b = _asset(db_session, "CONC_OPP_B")
    _corr(db_session, a, b, 0.9)
    _open_position(db_session, a, strategy, direction="long", entry_price=100.0, size=10.0)
    _open_position(db_session, b, strategy, direction="short", entry_price=100.0, size=10.0)

    assessment = assess_concentration(db_session, LIMITS, equity=10000.0)
    assert assessment.clusters == []
    assert assessment.max_cluster_exposure_pct == 0.0


def test_concentrated_state_when_cluster_exceeds_hard_limit(db_session):
    strategy = _strategy(db_session, "concentration_hard_limit_strategy")
    btc = _asset(db_session, "CONC_HARD_BTC")
    eth = _asset(db_session, "CONC_HARD_ETH")
    _corr(db_session, btc, eth, 0.95)
    equity = 10000.0
    # 1500 + 1500 = 3000 / 10000 = 30% > 25% hard limit
    _open_position(db_session, btc, strategy, direction="long", entry_price=100.0, size=15.0)
    _open_position(db_session, eth, strategy, direction="long", entry_price=100.0, size=15.0)

    assessment = assess_concentration(db_session, LIMITS, equity=equity)
    assert assessment.max_cluster_exposure_pct == 30.0
    assert assessment.concentration_state == CONCENTRATED
    assert any("cluster" in w for w in assessment.hidden_factor_warnings)


def test_moderate_state_below_high_threshold(db_session):
    strategy = _strategy(db_session, "concentration_moderate_strategy")
    btc = _asset(db_session, "CONC_MOD_BTC")
    eth = _asset(db_session, "CONC_MOD_ETH")
    _corr(db_session, btc, eth, 0.9)
    equity = 10000.0
    # 600 + 600 = 1200 / 10000 = 12% -- above 10% (0.4x25) but below 17.5% (0.7x25)
    _open_position(db_session, btc, strategy, direction="long", entry_price=100.0, size=6.0)
    _open_position(db_session, eth, strategy, direction="long", entry_price=100.0, size=6.0)

    assessment = assess_concentration(db_session, LIMITS, equity=equity)
    assert assessment.max_cluster_exposure_pct == 12.0
    assert assessment.concentration_state == MODERATE


def test_asset_class_exposure_and_hidden_factor_warning(db_session):
    strategy = _strategy(db_session, "concentration_asset_class_strategy")
    crypto_a = _asset(db_session, "CONC_AC_CRYPTO_A", asset_class="crypto")
    crypto_b = _asset(db_session, "CONC_AC_CRYPTO_B", asset_class="crypto")
    forex_a = _asset(db_session, "CONC_AC_FOREX_A", asset_class="forex")
    _open_position(db_session, crypto_a, strategy, direction="long", entry_price=100.0, size=10.0)  # 1000
    _open_position(db_session, crypto_b, strategy, direction="long", entry_price=100.0, size=10.0)  # 1000
    _open_position(db_session, forex_a, strategy, direction="long", entry_price=100.0, size=2.0)  # 200

    assessment = assess_concentration(db_session, LIMITS, equity=10000.0)
    assert assessment.asset_class_exposure_pct["crypto"] > assessment.asset_class_exposure_pct["forex"]
    assert assessment.asset_class_exposure_pct["crypto"] >= 50.0  # 2000/2200 ~= 90.9%
    assert any("crypto" in w for w in assessment.hidden_factor_warnings)


def test_total_exposure_notional_sums_all_open_positions(db_session):
    strategy = _strategy(db_session, "concentration_notional_strategy")
    a = _asset(db_session, "CONC_NOTIONAL_A")
    b = _asset(db_session, "CONC_NOTIONAL_B")
    _open_position(db_session, a, strategy, direction="long", entry_price=50.0, size=2.0)  # 100
    _open_position(db_session, b, strategy, direction="long", entry_price=200.0, size=1.0)  # 200

    assessment = assess_concentration(db_session, LIMITS, equity=10000.0)
    assert assessment.total_exposure_notional == 300.0
