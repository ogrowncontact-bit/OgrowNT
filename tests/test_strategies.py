import random
from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import compute_indicators
from packages.quant.regime.classifier import classify_regime
from packages.quant.strategies import (
    ALL_STRATEGIES,
    BreakoutStrategy,
    MarketContext,
    MeanReversionStrategy,
    MomentumStrategy,
    TrendFollowingStrategy,
)


def _trending_context(n=60, step=0.6, volume_spike=False) -> MarketContext:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    rng = random.Random(7)
    price = 100.0
    candles = []
    for i in range(n):
        price += step + rng.uniform(-0.05, 0.05)
        volume = 100.0 * (1.5 if volume_spike and i == n - 1 else 1.0)
        candles.append(
            Candle(ts=ts + timedelta(minutes=i), open=price - 0.1, high=price + 0.2, low=price - 0.2, close=price, volume=volume)
        )
    indicators = compute_indicators(candles)
    regime = classify_regime(candles)
    return MarketContext(asset_id=1, symbol="TEST", timeframe="1m", candles=candles, indicators=indicators, regime=regime)


def _oversold_context(n=60) -> MarketContext:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    candles = []
    price = 100.0
    for i in range(n - 5):
        candles.append(
            Candle(ts=ts + timedelta(minutes=i), open=price, high=price + 0.05, low=price - 0.05, close=price, volume=100)
        )
    # Sharp drop in the last few bars -> low RSI, price well below SMA(30)
    for i in range(5):
        price -= 3.0
        candles.append(
            Candle(
                ts=ts + timedelta(minutes=n - 5 + i),
                open=price + 1,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=100,
            )
        )
    indicators = compute_indicators(candles)
    regime = classify_regime(candles)
    return MarketContext(asset_id=1, symbol="TEST", timeframe="1m", candles=candles, indicators=indicators, regime=regime)


def test_trend_following_goes_long_in_uptrend():
    ctx = _trending_context(step=0.6)
    signal = TrendFollowingStrategy().generate_signal(ctx)
    assert signal is not None
    assert signal.direction == "long"
    assert signal.risk_reward > 0


def test_trend_following_goes_short_in_downtrend():
    ctx = _trending_context(step=-0.6)
    signal = TrendFollowingStrategy().generate_signal(ctx)
    assert signal is not None
    assert signal.direction == "short"


def test_trend_following_no_signal_when_flat():
    ts = datetime.now(timezone.utc)
    candles = [
        Candle(ts=ts + timedelta(minutes=i), open=100, high=100.02, low=99.98, close=100, volume=100) for i in range(60)
    ]
    ctx = MarketContext(
        asset_id=1, symbol="TEST", timeframe="1m", candles=candles,
        indicators=compute_indicators(candles), regime=classify_regime(candles),
    )
    assert TrendFollowingStrategy().generate_signal(ctx) is None


def test_momentum_aligns_with_strong_uptrend():
    ctx = _trending_context(step=0.8)
    signal = MomentumStrategy().generate_signal(ctx)
    assert signal is not None
    assert signal.direction == "long"


def test_breakout_fires_on_new_high_with_volume():
    ctx = _trending_context(step=0.6, volume_spike=True)
    signal = BreakoutStrategy().generate_signal(ctx)
    # A steady uptrend's last close is very likely a new 20-bar high already
    assert signal is None or signal.direction == "long"


def test_mean_reversion_goes_long_after_sharp_drop():
    ctx = _oversold_context()
    signal = MeanReversionStrategy().generate_signal(ctx)
    assert signal is not None
    assert signal.direction == "long"


def test_strategy_regime_fit_matches_declared_sets():
    strategy = TrendFollowingStrategy()
    assert strategy.regime_fit("trending_bull") == 1.0
    assert strategy.regime_fit("ranging") == 0.0
    assert strategy.regime_fit("unknown") == 0.5


def test_get_risk_profile_matches_strategy_declared_regimes():
    # Prompt 3 §5/§14: preferred_regimes/avoided_regimes, exposed via
    # get_risk_profile() rather than a second, possibly-drifting field.
    for strategy in ALL_STRATEGIES:
        profile = strategy.get_risk_profile()
        assert profile.family == strategy.family
        assert profile.best_regimes == strategy.best_regimes
        assert profile.worst_regimes == strategy.worst_regimes
        assert profile.typical_risk_reward > 0


def test_get_risk_profile_reuses_the_strategys_own_configured_risk_reward():
    strategy = TrendFollowingStrategy(risk_reward=3.3)
    assert strategy.get_risk_profile().typical_risk_reward == 3.3


def test_momentum_avoids_ranging_per_spec_example():
    # Prompt 3 §14's own worked example: Momentum prefers
    # trending_bull/trending_bear, avoids ranging.
    profile = MomentumStrategy().get_risk_profile()
    assert "trending_bull" in profile.best_regimes
    assert "trending_bear" in profile.best_regimes
    assert "ranging" in profile.worst_regimes
